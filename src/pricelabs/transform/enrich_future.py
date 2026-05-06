"""Manual enrichment of standardized future pricing with Price Occ benchmarks."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import sys


OPERATIONAL_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_date",
    "nightly_price",
    "min_stay",
    "status",
    "upcoming_adr",
    "analysis_status",
    "status_confidence",
    "status_reason",
)
REQUIRED_OPERATIONAL_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_date",
    "nightly_price",
    "min_stay",
    "status",
    "analysis_status",
    "status_confidence",
    "status_reason",
)
PRICE_OCC_REQUIRED_COLUMNS = ("Date", "Market Occupancy", "Market 50th Percentile Price")
ENRICHED_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_date",
    "nightly_price",
    "min_stay",
    "status",
    "upcoming_adr",
    "booked_revenue_proxy",
    "open_revenue_ask",
    "previous_status",
    "previous_upcoming_adr",
    "booked_stay_start_proxy",
    "booked_stay_id_proxy",
    "analysis_status",
    "status_confidence",
    "status_reason",
    "market_occupancy",
    "market_50th_price",
    "market_25th_price",
    "market_75th_price",
    "market_90th_price",
    "median_booked_price",
    "last_seen_price",
    "final_price",
    "holiday_event",
)

PRICE_OCC_FIELD_MAP = {
    "Market Occupancy": "market_occupancy",
    "Market 50th Percentile Price": "market_50th_price",
    "Market 25th Percentile Price": "market_25th_price",
    "Market 75th Percentile Price": "market_75th_price",
    "Market 90th Percentile Price": "market_90th_price",
    "Median Booked Price": "median_booked_price",
    "Last Seen Price": "last_seen_price",
    "Final Price": "final_price",
    "Holiday/Event": "holiday_event",
}
ZERO = Decimal("0")


def parse_decimal(value: str) -> Decimal | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped.replace("$", "").replace(",", ""))
    except InvalidOperation:
        return None


def decimal_for_output(value: Decimal | None) -> str:
    if value is None:
        return ""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded)


def rounded_money(value: str) -> Decimal | None:
    parsed = parse_decimal(value)
    if parsed is None:
        return None
    return parsed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich V1 future pricing with Price Occ benchmarks.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--standardized-file",
        help="Standardized future pricing CSV. Defaults to standardized/future_daily_pricing_<run-date>.csv.",
    )
    parser.add_argument(
        "--price-occ-file",
        default="sample_data/Price Occ for 650255___717243.csv",
        help="Price Occ benchmark CSV.",
    )
    parser.add_argument(
        "--output-file",
        help="Enriched output CSV. Defaults to analysis/future_daily_pricing_enriched_<run-date>.csv.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None, required_columns: tuple[str, ...], label: str) -> None:
    if fieldnames is None:
        raise ValueError(f"{label} CSV is missing a header row")
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        raise ValueError(f"{label} CSV is missing required columns: {', '.join(missing)}")


def read_csv_rows(path: Path, required_columns: tuple[str, ...], label: str) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"{label} CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames, required_columns, label)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def build_price_occ_by_date(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_date: dict[str, dict[str, str]] = {}
    for row in rows:
        stay_date = row["Date"].strip()
        if stay_date in by_date:
            raise ValueError(f"Duplicate Price Occ Date found: {stay_date}")
        by_date[stay_date] = {
            target: row.get(source, "").strip()
            for source, target in PRICE_OCC_FIELD_MAP.items()
        }
    return by_date


def add_revenue_and_stay_proxies(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    enriched_rows = sorted(rows, key=lambda row: row["stay_date"])
    previous_status = ""
    previous_upcoming_adr = ""
    previous_booked_adr: Decimal | None = None
    booked_stay_id = 0

    for row in enriched_rows:
        status = row["status"].strip()
        upcoming_adr = rounded_money(row["upcoming_adr"])
        nightly_price = parse_decimal(row["nightly_price"])
        row["upcoming_adr"] = decimal_for_output(upcoming_adr)

        row["previous_status"] = previous_status
        row["previous_upcoming_adr"] = previous_upcoming_adr

        if status == "booked":
            row["booked_revenue_proxy"] = decimal_for_output(upcoming_adr or ZERO)
            row["open_revenue_ask"] = "0"
            is_new_stay = previous_status != "booked" or upcoming_adr != previous_booked_adr
            if is_new_stay:
                booked_stay_id += 1
            row["booked_stay_start_proxy"] = "1" if is_new_stay else "0"
            row["booked_stay_id_proxy"] = str(booked_stay_id)
            previous_booked_adr = upcoming_adr
        elif status == "available":
            row["booked_revenue_proxy"] = "0"
            row["open_revenue_ask"] = decimal_for_output(nightly_price or ZERO)
            row["booked_stay_start_proxy"] = "0"
            row["booked_stay_id_proxy"] = ""
            previous_booked_adr = None
        else:
            row["booked_revenue_proxy"] = "0"
            row["open_revenue_ask"] = "0"
            row["booked_stay_start_proxy"] = "0"
            row["booked_stay_id_proxy"] = ""
            previous_booked_adr = None

        previous_status = status
        previous_upcoming_adr = decimal_for_output(upcoming_adr)

    return enriched_rows


def enrich_rows(
    operational_rows: list[dict[str, str]],
    price_occ_by_date: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    enriched_rows = []
    for row in operational_rows:
        enriched_row = {column: row.get(column, "").strip() for column in OPERATIONAL_COLUMNS}
        enrichment = price_occ_by_date.get(row["stay_date"].strip(), {})
        for column in ENRICHED_COLUMNS:
            if not enriched_row.get(column):
                enriched_row[column] = enrichment.get(column, "")
        enriched_rows.append(enriched_row)
    return add_revenue_and_stay_proxies(enriched_rows)


def write_enriched_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=ENRICHED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    standardized_path = Path(args.standardized_file or f"standardized/future_daily_pricing_{args.run_date}.csv")
    price_occ_path = Path(args.price_occ_file)
    output_path = Path(args.output_file or f"analysis/future_daily_pricing_enriched_{args.run_date}.csv")

    operational_rows = read_csv_rows(standardized_path, REQUIRED_OPERATIONAL_COLUMNS, "Standardized")
    price_occ_rows = read_csv_rows(price_occ_path, PRICE_OCC_REQUIRED_COLUMNS, "Price Occ")
    price_occ_by_date = build_price_occ_by_date(price_occ_rows)
    enriched_rows = enrich_rows(operational_rows, price_occ_by_date)

    if len(enriched_rows) != len(operational_rows):
        raise ValueError("Enriched output row count does not match standardized input row count")

    write_enriched_rows(output_path, enriched_rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
