"""Manual window-level summaries from enriched future pricing."""

from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import sys


REQUIRED_INPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_date",
    "nightly_price",
    "analysis_status",
    "status_confidence",
    "market_occupancy",
    "market_75th_price",
)
OUTPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "window_name",
    "listing_booked_pct",
    "market_occupancy_avg",
    "occupancy_vs_market_pct",
    "booked_days",
    "low_confidence_booked_days",
    "blocked_days",
    "avg_available_price",
    "avg_market_75th_price",
    "price_vs_market_75th_pct",
    "avg_booked_price_proxy",
)
WINDOWS = (
    ("days_0_15", 0, 14),
    ("days_16_45", 15, 44),
    ("days_46_90", 45, 89),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize enriched V1 future pricing by analysis windows.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--enriched-file",
        help="Enriched daily CSV. Defaults to analysis/future_daily_pricing_enriched_<run-date>.csv.",
    )
    parser.add_argument(
        "--output-file",
        help="Window summary CSV. Defaults to analysis/future_window_summary_<run-date>.csv.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Enriched CSV is missing a header row")
    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"Enriched CSV is missing required columns: {', '.join(missing)}")


def read_enriched_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Enriched CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def parse_decimal(value: str) -> Decimal | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped.replace("$", "").replace(",", ""))
    except InvalidOperation:
        return None


def average(values: list[Decimal]) -> str:
    if not values:
        return ""
    result = sum(values) / Decimal(len(values))
    return str(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    result = Decimal(numerator) / Decimal(denominator) * Decimal("100")
    return str(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def subtract_pct(left: str, right: str) -> str:
    if not left or not right:
        return ""
    result = Decimal(left) - Decimal(right)
    return str(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def relative_pct(numerator: str, denominator: str) -> str:
    if not numerator or not denominator:
        return ""
    denominator_decimal = Decimal(denominator)
    if denominator_decimal == 0:
        return ""
    result = (Decimal(numerator) - denominator_decimal) / denominator_decimal * Decimal("100")
    return str(result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def summarize_window(
    rows: list[dict[str, str]],
    *,
    run_date: date,
    listing_id: str,
    window_name: str,
    start_offset_days: int,
    end_offset_days: int,
) -> dict[str, str]:
    start_date = run_date + timedelta(days=start_offset_days)
    end_date = run_date + timedelta(days=end_offset_days)
    window_rows = [
        row
        for row in rows
        if start_date <= date.fromisoformat(row["stay_date"]) <= end_date
    ]

    booked_days = 0
    low_confidence_booked_days = 0
    blocked_days = 0
    available_prices: list[Decimal] = []
    booked_price_proxies: list[Decimal] = []
    market_75th_prices: list[Decimal] = []
    market_occupancies: list[Decimal] = []

    for row in window_rows:
        analysis_status = row["analysis_status"].strip()
        nightly_price = parse_decimal(row["nightly_price"])

        if analysis_status == "available":
            if nightly_price is not None:
                available_prices.append(nightly_price)
        elif analysis_status == "booked":
            booked_days += 1
            if row["status_confidence"].strip() == "low":
                low_confidence_booked_days += 1
            if nightly_price is not None:
                booked_price_proxies.append(nightly_price)
        elif analysis_status == "blocked":
            blocked_days += 1

        market_75th_price = parse_decimal(row["market_75th_price"])
        if market_75th_price is not None:
            market_75th_prices.append(market_75th_price)

        market_occupancy = parse_decimal(row["market_occupancy"])
        if market_occupancy is not None:
            market_occupancies.append(market_occupancy)

    total_days = len(window_rows)
    listing_booked_pct = pct(booked_days, total_days)
    market_occupancy_avg = average(market_occupancies)
    avg_available_price = average(available_prices)
    avg_market_75th_price = average(market_75th_prices)
    return {
        "run_date": run_date.isoformat(),
        "listing_id": listing_id,
        "window_name": window_name,
        "listing_booked_pct": listing_booked_pct,
        "market_occupancy_avg": market_occupancy_avg,
        "occupancy_vs_market_pct": subtract_pct(listing_booked_pct, market_occupancy_avg),
        "booked_days": str(booked_days),
        "low_confidence_booked_days": str(low_confidence_booked_days),
        "blocked_days": str(blocked_days),
        "avg_available_price": avg_available_price,
        "avg_market_75th_price": avg_market_75th_price,
        "price_vs_market_75th_pct": relative_pct(avg_available_price, avg_market_75th_price),
        "avg_booked_price_proxy": average(booked_price_proxies),
    }


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date)
    enriched_path = Path(args.enriched_file or f"analysis/future_daily_pricing_enriched_{args.run_date}.csv")
    output_path = Path(args.output_file or f"analysis/future_window_summary_{args.run_date}.csv")

    rows = read_enriched_rows(enriched_path)
    listing_ids = {row["listing_id"].strip() for row in rows if row["listing_id"].strip()}
    if len(listing_ids) != 1:
        raise ValueError(f"Expected exactly one listing_id in enriched input, found {len(listing_ids)}")
    listing_id = next(iter(listing_ids))

    summary_rows = [
        summarize_window(
            rows,
            run_date=run_date,
            listing_id=listing_id,
            window_name=name,
            start_offset_days=start_offset_days,
            end_offset_days=end_offset_days,
        )
        for name, start_offset_days, end_offset_days in WINDOWS
    ]
    if len(summary_rows) != 3:
        raise ValueError("Window summary must contain exactly 3 rows")

    write_summary(output_path, summary_rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
