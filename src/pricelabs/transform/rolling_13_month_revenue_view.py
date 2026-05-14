"""Rolling 13-month revenue view from monthly revenue pace."""

from __future__ import annotations

import argparse
import calendar
import csv
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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
    "monthly_trends_revenue",
    "monthly_trends_occupancy_pct",
    "monthly_trends_booked_occupancy_pct",
    "monthly_trends_blocked_occupancy_pct",
    "monthly_trends_adr",
    "monthly_trends_source",
    "bookings_report_bookings",
    "bookings_report_cleanings_proxy",
    "bookings_report_booked_nights",
    "bookings_report_avg_los",
    "bookings_report_rental_revenue",
    "bookings_report_total_revenue",
    "bookings_report_adr",
    "bookings_report_avg_booking_window",
    "airbnb_stays",
    "vrbo_stays",
    "direct_stays",
    "other_unknown_stays",
    "main_booking_source",
    "booking_source_mix_summary",
    "month_time_bucket",
    "revenue_pace_status",
    "cleaning_efficiency_status",
    "month_action_level",
)
HISTORICAL_COLUMNS = (
    "historical_bookable_nights",
    "historical_booked_nights",
    "historical_booked_nights_source",
    "historical_cleanings_proxy",
    "historical_cleanings_source",
    "historical_paid_occupancy_pct",
    "historical_occupancy_pct",
    "historical_calendar_occupancy_pct",
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


def monthly_trends_values_are_valid(source_row: dict[str, str] | None) -> bool:
    if source_row is None:
        return False
    revenue = parse_decimal(source_row.get("monthly_trends_revenue", ""))
    occupancy = parse_decimal(source_row.get("monthly_trends_occupancy_pct", ""))
    adr = parse_decimal(source_row.get("monthly_trends_adr", ""))
    exact_cleanings = parse_decimal(source_row.get("bookings_report_cleanings_proxy", ""))
    if revenue is None or occupancy is None or adr is None:
        return False
    if revenue <= 0 or occupancy <= 0 or adr <= 0:
        return False
    if revenue < Decimal("1000") and (exact_cleanings is None or exact_cleanings <= 0):
        return False
    return True


def source_label(source_row: dict[str, str] | None, offset: int) -> str:
    if source_row is None:
        return "data_not_available" if offset < 0 else "no_source_data"
    if source_row.get("monthly_trends_revenue", "").strip():
        if offset < 0 and not monthly_trends_values_are_valid(source_row):
            return "data_not_available"
        if offset < 0:
            return "monthly_trends_actuals"
        if offset == 0:
            return "monthly_trends_current"
        return "monthly_trends_future_on_books"
    if offset < 0:
        return "data_not_available"
    if source_row.get("revenue_pace_status", "").strip() == "partial_horizon":
        return "partial_horizon"
    return "future_calendar"


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


def historical_calendar_occupancy_pct(row: dict[str, str], days_in_month: str) -> str:
    booked_nights = parse_decimal(row.get("historical_booked_nights", ""))
    days = parse_decimal(days_in_month)
    if booked_nights is None or days is None or days == 0:
        return ""
    occupancy = (booked_nights / days * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{occupancy.normalize():f}"


def calendar_days_for_stay_month(stay_month: str) -> str:
    year, month = (int(part) for part in stay_month.split("-"))
    return str(calendar.monthrange(year, month)[1])


def decimal_for_output(value: Decimal | None) -> str:
    if value is None:
        return ""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded)


def observed_avg_los(rows: list[dict[str, str]], run_date: str) -> Decimal | None:
    total_nights = Decimal("0")
    total_bookings = Decimal("0")
    for row in rows:
        if month_window_position_for_stay_month(row.get("stay_month", ""), run_date) == "historical":
            continue
        nights = parse_decimal(row.get("bookings_report_booked_nights", ""))
        bookings = parse_decimal(row.get("bookings_report_cleanings_proxy", ""))
        if nights is not None and bookings is not None and bookings > 0:
            total_nights += nights
            total_bookings += bookings
    if total_bookings == 0:
        return None
    return total_nights / total_bookings


def month_window_position_for_stay_month(stay_month: str, run_date: str) -> str:
    if not stay_month:
        return ""
    run_month = date.fromisoformat(run_date).replace(day=1)
    stay_year, stay_month_number = (int(part) for part in stay_month.split("-"))
    month_delta = (stay_year - run_month.year) * 12 + (stay_month_number - run_month.month)
    return month_window_position(month_delta)


def apply_data_not_available(row: dict[str, str]) -> None:
    row["data_availability"] = "data_not_available"
    row["revenue_pace_status"] = "data_not_available"
    row["cleaning_efficiency_status"] = "data_not_available"
    row["month_action_level"] = "monitor"
    row["historical_data_quality_flag"] = "data_not_available"
    row["historical_booked_nights"] = ""
    row["historical_booked_nights_source"] = "data_not_available"
    row["historical_cleanings_proxy"] = ""
    row["historical_cleanings_source"] = "data_not_available"
    row["historical_calendar_occupancy_pct"] = ""
    row["historical_rental_adr"] = ""
    row["historical_total_revenue"] = ""
    row["historical_source"] = ""


def apply_monthly_trends_actuals(row: dict[str, str], avg_los: Decimal | None) -> None:
    revenue = parse_decimal(row.get("monthly_trends_revenue", ""))
    adr = parse_decimal(row.get("monthly_trends_adr", ""))

    row["historical_total_revenue"] = row.get("monthly_trends_revenue", "")
    row["historical_calendar_occupancy_pct"] = row.get("monthly_trends_occupancy_pct", "")
    row["historical_rental_adr"] = row.get("monthly_trends_adr", "")
    row["historical_source"] = row.get("monthly_trends_source", "")
    row["historical_data_quality_flag"] = "ok"
    row["cleaning_efficiency_status"] = "historical_actuals"

    if revenue is not None and adr is not None and adr > 0:
        booked_nights = (revenue / adr).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        row["historical_booked_nights_source"] = "estimated_from_monthly_trends"
    else:
        booked_nights = None
        row["historical_booked_nights_source"] = "data_not_available"

    row["historical_booked_nights"] = decimal_for_output(booked_nights)

    if booked_nights is not None and avg_los is not None and avg_los > 0:
        cleanings = (booked_nights / avg_los).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        row["historical_cleanings_source"] = "estimated_from_monthly_trends"
    else:
        cleanings = None
        row["historical_cleanings_source"] = "data_not_available"

    row["historical_cleanings_proxy"] = decimal_for_output(cleanings)
    if cleanings is not None and cleanings > 0 and revenue is not None:
        row["revenue_per_cleaning_proxy"] = decimal_for_output(revenue / cleanings)


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
        if row["data_availability"] in {"monthly_trends_actuals", "data_not_available"}:
            continue

        historical_row = historical_by_month.get(row["stay_month"])
        if historical_row is None:
            row["historical_data_quality_flag"] = "no_historical_source"
            continue

        for column in HISTORICAL_COLUMNS:
            if column != "historical_data_quality_flag":
                row[column] = historical_row.get(column, "")
        days_in_month = row.get("days_in_month", "") or calendar_days_for_stay_month(row["stay_month"])
        row["historical_calendar_occupancy_pct"] = historical_calendar_occupancy_pct(historical_row, days_in_month)
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
            "data_availability": source_label(source_row, offset),
        }
        for column in METRIC_COLUMNS:
            output_row[column] = source_row.get(column, "") if source_row else ""
        if source_row is None:
            if offset < 0:
                output_row["month_time_bucket"] = "historical_month"
                output_row["days_in_month"] = calendar_days_for_stay_month(stay_month)
                output_row["revenue_pace_status"] = "data_not_available"
                output_row["cleaning_efficiency_status"] = "data_not_available"
            else:
                output_row["revenue_pace_status"] = "no_source_data"
            output_row["month_action_level"] = "monitor"
        elif offset < 0:
            output_row["month_time_bucket"] = "historical_month"
            if output_row["data_availability"] == "monthly_trends_actuals":
                output_row["revenue_pace_status"] = "historical_actuals"
                output_row["month_action_level"] = "monitor"
            elif output_row["data_availability"] == "data_not_available":
                output_row["revenue_pace_status"] = "data_not_available"
                output_row["cleaning_efficiency_status"] = "data_not_available"
                output_row["month_action_level"] = "monitor"
        rolling_rows.append(output_row)

    if len(rolling_rows) != 13:
        raise ValueError("Rolling revenue view must contain exactly 13 rows")
    merge_historical_actuals(rolling_rows, historical_rows or [])
    avg_los = observed_avg_los(rows, run_date)
    for row in rolling_rows:
        if row["data_availability"] == "monthly_trends_actuals" and row.get("monthly_trends_revenue", "").strip():
            apply_monthly_trends_actuals(row, avg_los)
        elif row["data_availability"] == "data_not_available":
            apply_data_not_available(row)
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
