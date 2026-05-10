"""Rolling 13-month revenue view from monthly revenue pace."""

from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys


METRIC_COLUMNS = (
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
    "month_time_bucket",
    "revenue_pace_status",
    "cleaning_efficiency_status",
    "month_action_level",
)
HISTORICAL_COLUMNS = (
    "historical_bookable_nights",
    "historical_booked_nights",
    "historical_paid_occupancy_pct",
    "historical_occupancy_pct",
    "historical_rental_adr",
    "historical_rental_revpar",
    "historical_total_revenue",
    "historical_source",
    "historical_data_quality_flag",
)
REQUIRED_INPUT_COLUMNS = ("run_date", "listing_id", "stay_month", *METRIC_COLUMNS)
REQUIRED_HISTORICAL_COLUMNS = (
    "stay_month",
    "historical_bookable_nights",
    "historical_booked_nights",
    "historical_occupancy_pct",
    "historical_rental_adr",
    "historical_total_revenue",
    "historical_source",
)
OUTPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_month",
    "month_relative_index",
    "month_window_position",
    "data_availability",
    *METRIC_COLUMNS,
    *HISTORICAL_COLUMNS,
)
MONTH_OFFSETS = tuple(range(-6, 7))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a rolling 13-month revenue view.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--monthly-file",
        help="Monthly revenue pace CSV. Defaults to analysis/monthly_revenue_pace_<run-date>.csv.",
    )
    parser.add_argument(
        "--historical-file",
        help="Optional historical monthly actuals CSV.",
    )
    parser.add_argument(
        "--output-file",
        help="Rolling 13-month CSV. Defaults to analysis/rolling_13_month_revenue_view_<run-date>.csv.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None, required_columns: tuple[str, ...], label: str) -> None:
    if fieldnames is None:
        raise ValueError(f"{label} CSV is missing a header row")
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        raise ValueError(f"{label} CSV is missing required columns: {', '.join(missing)}")


def read_monthly_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Monthly revenue pace CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames, REQUIRED_INPUT_COLUMNS, "Monthly revenue pace")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def read_historical_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames, REQUIRED_HISTORICAL_COLUMNS, "Historical monthly actuals")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def add_months(month: date, offset: int) -> str:
    month_index = month.year * 12 + month.month - 1 + offset
    year = month_index // 12
    month_number = month_index % 12 + 1
    return f"{year:04d}-{month_number:02d}"


def month_window_position(offset: int) -> str:
    if offset < 0:
        return "historical"
    if offset == 0:
        return "current"
    return "future"


def parse_decimal(value: str) -> Decimal | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped)
    except InvalidOperation:
        return None


def historical_quality_flag(row: dict[str, str], days_in_month: str) -> str:
    bookable_nights = parse_decimal(row.get("historical_bookable_nights", ""))
    booked_nights = parse_decimal(row.get("historical_booked_nights", ""))
    total_revenue = parse_decimal(row.get("historical_total_revenue", ""))
    occupancy_pct = parse_decimal(row.get("historical_occupancy_pct", ""))
    rental_adr = parse_decimal(row.get("historical_rental_adr", ""))
    days = parse_decimal(days_in_month)

    suspicious = False
    if bookable_nights is not None and days is not None and bookable_nights > days * Decimal("1.5"):
        suspicious = True
    if booked_nights is not None and bookable_nights is not None and booked_nights > bookable_nights:
        suspicious = True
    if total_revenue is not None and total_revenue < 0:
        suspicious = True
    if occupancy_pct is not None and occupancy_pct > 100:
        suspicious = True
    if rental_adr is not None and rental_adr < 0:
        suspicious = True
    return "suspicious" if suspicious else "ok"


def calendar_days_for_stay_month(stay_month: str) -> str:
    year, month = (int(part) for part in stay_month.split("-"))
    return str(calendar.monthrange(year, month)[1])


def merge_historical_actuals(
    rolling_rows: list[dict[str, str]],
    historical_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    historical_by_month = {row["stay_month"].strip(): row for row in historical_rows}
    for row in rolling_rows:
        for column in HISTORICAL_COLUMNS:
            row[column] = ""

        if row["month_window_position"] != "historical" and int(row["month_relative_index"]) >= 0:
            row["historical_data_quality_flag"] = ""
            continue

        historical_row = historical_by_month.get(row["stay_month"])
        if historical_row is None:
            row["historical_data_quality_flag"] = "no_historical_source"
            continue

        for column in HISTORICAL_COLUMNS:
            if column != "historical_data_quality_flag":
                row[column] = historical_row.get(column, "")
        days_in_month = row.get("days_in_month", "") or calendar_days_for_stay_month(row["stay_month"])
        row["historical_data_quality_flag"] = historical_quality_flag(historical_row, days_in_month)
        row["data_availability"] = "historical_actuals"
        row["revenue_pace_status"] = "historical_actuals"
        row["month_action_level"] = "monitor"
    return rolling_rows


def build_rolling_rows(
    rows: list[dict[str, str]],
    run_date: str,
    historical_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    monthly_by_stay_month = {row["stay_month"].strip(): row for row in rows}
    listing_ids = {row["listing_id"].strip() for row in rows if row["listing_id"].strip()}
    listing_id = next(iter(listing_ids)) if len(listing_ids) == 1 else ""
    run_month = date.fromisoformat(run_date).replace(day=1)

    rolling_rows: list[dict[str, str]] = []
    for offset in MONTH_OFFSETS:
        stay_month = add_months(run_month, offset)
        source_row = monthly_by_stay_month.get(stay_month)
        output_row = {
            "run_date": run_date,
            "listing_id": source_row.get("listing_id", listing_id) if source_row else listing_id,
            "stay_month": stay_month,
            "month_relative_index": str(offset),
            "month_window_position": month_window_position(offset),
            "data_availability": "available" if source_row else "no_source_data",
        }
        for column in METRIC_COLUMNS:
            output_row[column] = source_row.get(column, "") if source_row else ""
        if source_row is None:
            output_row["revenue_pace_status"] = "no_source_data"
            output_row["month_action_level"] = "monitor"
        rolling_rows.append(output_row)

    if len(rolling_rows) != 13:
        raise ValueError("Rolling revenue view must contain exactly 13 rows")
    merge_historical_actuals(rolling_rows, historical_rows or [])
    return rolling_rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    monthly_path = Path(args.monthly_file or f"analysis/monthly_revenue_pace_{args.run_date}.csv")
    output_path = Path(args.output_file or f"analysis/rolling_13_month_revenue_view_{args.run_date}.csv")
    historical_path = Path(args.historical_file) if args.historical_file else None

    monthly_rows = read_monthly_rows(monthly_path)
    historical_rows = read_historical_rows(historical_path) if historical_path else []
    rolling_rows = build_rolling_rows(monthly_rows, args.run_date, historical_rows)
    write_rows(output_path, rolling_rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
