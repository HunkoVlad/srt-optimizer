"""Normalize PriceLabs Bookings Report and aggregate monthly booking metrics."""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import sys

from pricelabs.transform.historical_monthly_actuals import read_xlsx_rows


SOURCE_COLUMNS = (
    "Listing Name",
    "Check-in Date",
    "Check-out Date",
    "Booked Date",
    "Average Daily Rate",
    "Rental Revenue",
    "Total Revenue",
    "Booking Source",
    "Booking Status",
    "Length of Stay (Days)",
    "Booking Window (Days)",
    "Reservation ID",
    "Listing ID",
)
NORMALIZED_COLUMNS = (
    "run_date",
    "listing_id",
    "reservation_id",
    "check_in_date",
    "check_out_date",
    "booked_date",
    "stay_month",
    "booking_status",
    "booking_source",
    "length_of_stay_days",
    "booking_window_days",
    "average_daily_rate",
    "rental_revenue",
    "total_revenue",
)
METRIC_COLUMNS = (
    "run_date",
    "month",
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
)
EXCEL_EPOCH = date(1899, 12, 30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize PriceLabs Bookings Report XLSX.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument("--input-file", required=True, help="PriceLabs Bookings Report XLSX.")
    parser.add_argument("--normalized-output-file", required=True, help="Normalized bookings CSV output.")
    parser.add_argument("--metrics-output-file", required=True, help="Monthly booking metrics CSV output.")
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Bookings Report workbook is missing a header row")
    missing = [column for column in SOURCE_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"Bookings Report workbook is missing required columns: {', '.join(missing)}")


def rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        raise ValueError("Bookings Report workbook is empty")
    header = [value.strip() for value in rows[0]]
    require_columns(header)
    output = []
    for row in rows[1:]:
        output.append({column: row[index].strip() if index < len(row) else "" for index, column in enumerate(header)})
    return output


def clean_number(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    cleaned = stripped.replace("$", "").replace(",", "").replace("%", "").strip()
    if not cleaned:
        return ""
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return ""
    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded)


def parse_decimal(value: str) -> Decimal:
    cleaned = clean_number(value)
    return Decimal(cleaned) if cleaned else Decimal("0")


def parse_date_value(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    try:
        serial = Decimal(stripped)
        if serial > 1000:
            parsed = EXCEL_EPOCH + timedelta(days=int(serial))
            return parsed.isoformat()
    except InvalidOperation:
        pass
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(stripped, fmt).date().isoformat()
        except ValueError:
            continue
    return stripped


def normalize_booking_source(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return "other_unknown"
    if "airbnb" in normalized:
        return "airbnb"
    if "vrbo" in normalized or "v r b o" in normalized:
        return "vrbo"
    if "direct" in normalized or "website" in normalized or "lodgify" in normalized:
        return "direct"
    return "other_unknown"


def normalize_rows(rows: list[dict[str, str]], run_date: str) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        status = row.get("Booking Status", "").strip()
        if status.lower() != "booked":
            continue
        check_in = parse_date_value(row.get("Check-in Date", ""))
        stay_month = check_in[:7] if len(check_in) >= 7 else ""
        normalized.append(
            {
                "run_date": run_date,
                "listing_id": row.get("Listing ID", "").strip(),
                "reservation_id": row.get("Reservation ID", "").strip(),
                "check_in_date": check_in,
                "check_out_date": parse_date_value(row.get("Check-out Date", "")),
                "booked_date": parse_date_value(row.get("Booked Date", "")),
                "stay_month": stay_month,
                "booking_status": status,
                "booking_source": row.get("Booking Source", "").strip(),
                "length_of_stay_days": clean_number(row.get("Length of Stay (Days)", "")),
                "booking_window_days": clean_number(row.get("Booking Window (Days)", "")),
                "average_daily_rate": clean_number(row.get("Average Daily Rate", "")),
                "rental_revenue": clean_number(row.get("Rental Revenue", "")),
                "total_revenue": clean_number(row.get("Total Revenue", "")),
            }
        )
    return normalized


def decimal_for_output(value: Decimal | None) -> str:
    if value is None:
        return ""
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded)


def aggregate_monthly(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    groups: dict[str, dict[str, Decimal | int | str]] = {}
    for row in rows:
        month = row["stay_month"]
        if not month:
            continue
        group = groups.setdefault(
            month,
            {
                "run_date": row["run_date"],
                "bookings": 0,
                "booked_nights": Decimal("0"),
                "rental_revenue": Decimal("0"),
                "total_revenue": Decimal("0"),
                "booking_window_total": Decimal("0"),
                "booking_window_count": 0,
                "source_counts": {"airbnb": 0, "vrbo": 0, "direct": 0, "other_unknown": 0},
            },
        )
        group["bookings"] = int(group["bookings"]) + 1
        group["booked_nights"] = Decimal(group["booked_nights"]) + parse_decimal(row["length_of_stay_days"])
        group["rental_revenue"] = Decimal(group["rental_revenue"]) + parse_decimal(row["rental_revenue"])
        group["total_revenue"] = Decimal(group["total_revenue"]) + parse_decimal(row["total_revenue"])
        booking_window = row["booking_window_days"].strip()
        if booking_window:
            group["booking_window_total"] = Decimal(group["booking_window_total"]) + parse_decimal(booking_window)
            group["booking_window_count"] = int(group["booking_window_count"]) + 1
        source_counts = group["source_counts"]
        if isinstance(source_counts, dict):
            source = normalize_booking_source(row.get("booking_source", ""))
            source_counts[source] = int(source_counts.get(source, 0)) + 1

    output = []
    for month in sorted(groups):
        group = groups[month]
        bookings = int(group["bookings"])
        booked_nights = Decimal(group["booked_nights"])
        rental_revenue = Decimal(group["rental_revenue"])
        booking_window_count = int(group["booking_window_count"])
        avg_los = booked_nights / Decimal(bookings) if bookings else None
        adr = rental_revenue / booked_nights if booked_nights else None
        avg_booking_window = (
            Decimal(group["booking_window_total"]) / Decimal(booking_window_count)
            if booking_window_count
            else None
        )
        source_counts = group["source_counts"] if isinstance(group["source_counts"], dict) else {}
        ordered_sources = ("airbnb", "vrbo", "direct", "other_unknown")
        main_source = max(ordered_sources, key=lambda source: (int(source_counts.get(source, 0)), -ordered_sources.index(source)))
        if int(source_counts.get(main_source, 0)) == 0:
            main_source = ""
        labels = {
            "airbnb": "Airbnb",
            "vrbo": "Vrbo",
            "direct": "Direct",
            "other_unknown": "Other/Unknown",
        }
        mix_parts = [
            f"{labels[source]} {int(source_counts.get(source, 0))}"
            for source in ordered_sources
            if int(source_counts.get(source, 0)) > 0
        ]
        output.append(
            {
                "run_date": str(group["run_date"]),
                "month": month,
                "bookings_report_bookings": str(bookings),
                "bookings_report_cleanings_proxy": str(bookings),
                "bookings_report_booked_nights": decimal_for_output(booked_nights),
                "bookings_report_avg_los": decimal_for_output(avg_los),
                "bookings_report_rental_revenue": decimal_for_output(rental_revenue),
                "bookings_report_total_revenue": decimal_for_output(Decimal(group["total_revenue"])),
                "bookings_report_adr": decimal_for_output(adr),
                "bookings_report_avg_booking_window": decimal_for_output(avg_booking_window),
                "airbnb_stays": str(int(source_counts.get("airbnb", 0))),
                "vrbo_stays": str(int(source_counts.get("vrbo", 0))),
                "direct_stays": str(int(source_counts.get("direct", 0))),
                "other_unknown_stays": str(int(source_counts.get("other_unknown", 0))),
                "main_booking_source": main_source,
                "booking_source_mix_summary": ", ".join(mix_parts),
            }
        )
    return output


def write_rows(path: Path, rows: list[dict[str, str]], fieldnames: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    source_rows = rows_to_dicts(read_xlsx_rows(Path(args.input_file)))
    normalized_rows = normalize_rows(source_rows, args.run_date)
    metric_rows = aggregate_monthly(normalized_rows)
    write_rows(Path(args.normalized_output_file), normalized_rows, NORMALIZED_COLUMNS)
    write_rows(Path(args.metrics_output_file), metric_rows, METRIC_COLUMNS)
    print(f"Wrote {args.normalized_output_file} ({len(normalized_rows)} rows)")
    print(f"Wrote {args.metrics_output_file} ({len(metric_rows)} rows)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
