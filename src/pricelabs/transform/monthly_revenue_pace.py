"""Monthly revenue-pace aggregation from enriched future pricing."""

from __future__ import annotations

import argparse
import calendar
import csv
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import sys


REQUIRED_INPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_date",
    "status",
    "booked_revenue_proxy",
    "open_revenue_ask",
    "booked_stay_start_proxy",
)
OUTPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_month",
    "month_time_bucket",
    "days_in_scope",
    "days_in_month",
    "month_scope_status",
    "booked_nights",
    "available_nights",
    "unavailable_nights",
    "booked_revenue_proxy",
    "open_revenue_ask",
    "total_future_revenue_proxy",
    "monthly_target",
    "booked_gap_to_target",
    "total_gap_to_target",
    "booked_cleanings_proxy",
    "avg_stay_length_proxy",
    "revenue_per_cleaning_proxy",
    "booked_revenue_pct_of_target",
    "total_future_revenue_pct_of_target",
    "revenue_pace_status",
    "cleaning_efficiency_status",
    "month_action_level",
)
MONTHLY_TARGET = Decimal("10000")
ZERO = Decimal("0")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate enriched future pricing to monthly revenue pace.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--enriched-file",
        help="Enriched daily CSV. Defaults to analysis/future_daily_pricing_enriched_<run-date>.csv.",
    )
    parser.add_argument(
        "--output-file",
        help="Monthly revenue pace CSV. Defaults to analysis/monthly_revenue_pace_<run-date>.csv.",
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


def parse_decimal(value: str) -> Decimal:
    stripped = value.strip()
    if not stripped:
        return ZERO
    try:
        return Decimal(stripped.replace("$", "").replace(",", ""))
    except InvalidOperation:
        return ZERO


def decimal_for_output(value: Decimal | None) -> str:
    if value is None:
        return ""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded)


def ratio_for_output(numerator: Decimal, denominator: Decimal) -> str:
    if denominator == 0:
        return ""
    return str((numerator / denominator).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def month_time_bucket(run_date_value: str, stay_month: str) -> str:
    run_date = date.fromisoformat(run_date_value)
    stay_year, stay_month_number = (int(part) for part in stay_month.split("-"))
    month_delta = (stay_year - run_date.year) * 12 + (stay_month_number - run_date.month)
    if month_delta == 0:
        return "current_month"
    if month_delta == 1:
        return "next_month"
    if 2 <= month_delta <= 3:
        return "future_month"
    return "far_future_month"


def revenue_pace_status(booked_pct: Decimal, total_pct: Decimal, time_bucket: str) -> str:
    if time_bucket == "current_month":
        if booked_pct >= Decimal("0.90"):
            return "on_track"
        if booked_pct >= Decimal("0.70"):
            return "watch"
        if total_pct >= Decimal("1.00"):
            return "conversion_risk"
        if total_pct >= Decimal("0.80"):
            return "behind"
        return "urgent"

    if time_bucket == "next_month":
        if booked_pct >= Decimal("0.70"):
            return "on_track"
        if booked_pct >= Decimal("0.40"):
            return "watch"
        if total_pct >= Decimal("1.00"):
            return "conversion_risk"
        if total_pct >= Decimal("0.80"):
            return "behind"
        return "urgent"

    if booked_pct >= Decimal("0.50"):
        return "on_track"
    if total_pct >= Decimal("1.00"):
        return "protect_open_value"
    if total_pct >= Decimal("0.80"):
        return "watch"
    return "behind"


def cleaning_efficiency_status(booked_cleanings: int, revenue_per_cleaning: Decimal | None) -> str:
    if booked_cleanings == 0 or revenue_per_cleaning is None:
        return "no_booked_cleanings"
    if revenue_per_cleaning >= Decimal("850"):
        return "strong"
    if revenue_per_cleaning >= Decimal("650"):
        return "acceptable"
    if revenue_per_cleaning >= Decimal("500"):
        return "watch"
    return "inefficient"


def month_action_level(revenue_status: str, cleaning_status: str) -> str:
    if revenue_status == "urgent":
        return "critical_now"
    if revenue_status in {"behind", "conversion_risk"}:
        return "advisory"
    if revenue_status == "watch":
        return "monitor"
    if revenue_status == "on_track" and cleaning_status in {"strong", "acceptable"}:
        return "protect"
    if revenue_status == "protect_open_value":
        return "protect"
    return "monitor"


def summarize_monthly(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str], dict[str, Decimal | int | str]] = defaultdict(
        lambda: {
            "days_in_scope": 0,
            "booked_nights": 0,
            "available_nights": 0,
            "unavailable_nights": 0,
            "booked_revenue_proxy": ZERO,
            "open_revenue_ask": ZERO,
            "booked_cleanings_proxy": 0,
        }
    )

    for row in rows:
        run_date = row["run_date"].strip()
        listing_id = row["listing_id"].strip()
        stay_month = row["stay_date"].strip()[:7]
        key = (run_date, listing_id, stay_month)
        group = groups[key]
        group["days_in_scope"] = int(group["days_in_scope"]) + 1

        status = row["status"].strip()
        if status == "booked":
            group["booked_nights"] = int(group["booked_nights"]) + 1
        elif status == "available":
            group["available_nights"] = int(group["available_nights"]) + 1
        else:
            group["unavailable_nights"] = int(group["unavailable_nights"]) + 1

        group["booked_revenue_proxy"] = Decimal(group["booked_revenue_proxy"]) + parse_decimal(
            row["booked_revenue_proxy"]
        )
        group["open_revenue_ask"] = Decimal(group["open_revenue_ask"]) + parse_decimal(row["open_revenue_ask"])
        group["booked_cleanings_proxy"] = int(group["booked_cleanings_proxy"]) + int(
            parse_decimal(row["booked_stay_start_proxy"])
        )

    output_rows: list[dict[str, str]] = []
    for run_date, listing_id, stay_month in sorted(groups):
        group = groups[(run_date, listing_id, stay_month)]
        stay_year, stay_month_number = (int(part) for part in stay_month.split("-"))
        days_in_scope = int(group["days_in_scope"])
        days_in_month = calendar.monthrange(stay_year, stay_month_number)[1]
        month_scope_status = "full_month" if days_in_scope == days_in_month else "partial_month"
        booked_nights = int(group["booked_nights"])
        booked_revenue = Decimal(group["booked_revenue_proxy"])
        open_revenue = Decimal(group["open_revenue_ask"])
        total_future_revenue = booked_revenue + open_revenue
        booked_cleanings = int(group["booked_cleanings_proxy"])

        avg_stay_length = None
        revenue_per_cleaning = None
        if booked_cleanings > 0:
            avg_stay_length = Decimal(booked_nights) / Decimal(booked_cleanings)
            revenue_per_cleaning = booked_revenue / Decimal(booked_cleanings)

        booked_pct = booked_revenue / MONTHLY_TARGET
        total_pct = total_future_revenue / MONTHLY_TARGET
        time_bucket = month_time_bucket(run_date, stay_month)
        cleaning_status = cleaning_efficiency_status(booked_cleanings, revenue_per_cleaning)
        if month_scope_status == "partial_month" and time_bucket == "far_future_month":
            pace_status = "partial_horizon"
            action_level = "monitor"
        else:
            pace_status = revenue_pace_status(booked_pct, total_pct, time_bucket)
            action_level = month_action_level(pace_status, cleaning_status)

        output_rows.append(
            {
                "run_date": run_date,
                "listing_id": listing_id,
                "stay_month": stay_month,
                "month_time_bucket": time_bucket,
                "days_in_scope": str(days_in_scope),
                "days_in_month": str(days_in_month),
                "month_scope_status": month_scope_status,
                "booked_nights": str(booked_nights),
                "available_nights": str(group["available_nights"]),
                "unavailable_nights": str(group["unavailable_nights"]),
                "booked_revenue_proxy": decimal_for_output(booked_revenue),
                "open_revenue_ask": decimal_for_output(open_revenue),
                "total_future_revenue_proxy": decimal_for_output(total_future_revenue),
                "monthly_target": decimal_for_output(MONTHLY_TARGET),
                "booked_gap_to_target": decimal_for_output(MONTHLY_TARGET - booked_revenue),
                "total_gap_to_target": decimal_for_output(MONTHLY_TARGET - total_future_revenue),
                "booked_cleanings_proxy": str(booked_cleanings),
                "avg_stay_length_proxy": decimal_for_output(avg_stay_length),
                "revenue_per_cleaning_proxy": decimal_for_output(revenue_per_cleaning),
                "booked_revenue_pct_of_target": ratio_for_output(booked_revenue, MONTHLY_TARGET),
                "total_future_revenue_pct_of_target": ratio_for_output(total_future_revenue, MONTHLY_TARGET),
                "revenue_pace_status": pace_status,
                "cleaning_efficiency_status": cleaning_status,
                "month_action_level": action_level,
            }
        )

    return output_rows


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    enriched_path = Path(args.enriched_file or f"analysis/future_daily_pricing_enriched_{args.run_date}.csv")
    output_path = Path(args.output_file or f"analysis/monthly_revenue_pace_{args.run_date}.csv")

    rows = read_enriched_rows(enriched_path)
    summary_rows = summarize_monthly(rows)
    write_summary(output_path, summary_rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
