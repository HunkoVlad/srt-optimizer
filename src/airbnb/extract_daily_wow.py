"""Create daily week-over-week Airbnb diagnostic comparisons."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


COLUMNS = [
    "run_date",
    "metric_window_start",
    "metric_window_end",
    "comparison_window_start",
    "comparison_window_end",
    "report_date",
    "weekday",
    "comparison_report_date",
    "airbnb_metric_page",
    "metric_name",
    "current_value",
    "previous_week_value",
    "change_vs_previous_week",
    "percent_change_vs_previous_week",
    "data_quality_status",
    "notes",
]

DISALLOWED_COLUMNS = {
    "adr",
    "occupancy",
    "revenue",
    "booked_nights",
    "booking_value",
    "total_bookings",
    "cleaning_count",
    "monthly_revenue_pace",
}

METRIC_NAME_BY_PAGE = {
    "page_views": "page_views",
    "wishlist_additions": "wishlist_additions",
    "booking_conversion": "average_overall_conversion_rate",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract daily Airbnb week-over-week diagnostic comparisons.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--input-file", help="Parsed Airbnb extraction CSV.")
    parser.add_argument("--output-file", help="Daily week-over-week Airbnb diagnostic CSV.")
    return parser.parse_args(argv)


def default_input_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "raw" / f"airbnb_daily_conversion_parsed_{run_date}.csv"


def default_output_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def date_range(start_date: str, end_date: str) -> list[str]:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days
    return [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(days + 1)]


def numeric(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value.rstrip("%"))
    except ValueError:
        return None


def format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def percent_change(current: str, previous: str) -> str:
    current_num = numeric(current)
    previous_num = numeric(previous)
    if current_num is None or previous_num in {None, 0}:
        return ""
    return format_number(((current_num - previous_num) / previous_num) * 100)


def load_chart_values(row: dict[str, str]) -> list[dict[str, str]]:
    payload = row.get("daily_chart_values_json", "")
    if not payload:
        return []
    try:
        values = json.loads(payload)
    except json.JSONDecodeError:
        return []
    return values if isinstance(values, list) else []


def build_daily_rows(parsed_rows: list[dict[str, str]], run_date: str) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []
    for row in parsed_rows:
        metric_page = row.get("airbnb_metric_page", "")
        metric_name = METRIC_NAME_BY_PAGE.get(metric_page)
        if not metric_name:
            continue
        values = load_chart_values(row)
        if not values:
            continue
        window_start = row.get("metric_window_start", "")
        window_end = row.get("metric_window_end", "")
        comparison_start = row.get("comparison_window_start", "")
        comparison_end = row.get("comparison_window_end", "")
        if not all([window_start, window_end, comparison_start, comparison_end]):
            continue
        current_dates = date_range(window_start, window_end)
        comparison_dates = date_range(comparison_start, comparison_end)
        pair_count = min(len(current_dates), len(comparison_dates), len(values) // 2)
        status = "parsed" if pair_count == len(current_dates) else "partial"
        notes = ""
        if len(current_dates) == 8:
            notes = "Airbnb chart includes 8 Sunday-to-Sunday points; preserved as provided."
        for index in range(pair_count):
            current_point = values[index * 2]
            previous_point = values[index * 2 + 1]
            current_value = str(current_point.get("value", ""))
            previous_value = str(previous_point.get("value", ""))
            current_date = current_dates[index]
            previous_date = comparison_dates[index]
            current_dt = datetime.strptime(current_date, "%Y-%m-%d")
            change_num = None
            current_num = numeric(current_value)
            previous_num = numeric(previous_value)
            if current_num is not None and previous_num is not None:
                change_num = current_num - previous_num
            output_rows.append(
                {
                    "run_date": run_date,
                    "metric_window_start": window_start,
                    "metric_window_end": window_end,
                    "comparison_window_start": comparison_start,
                    "comparison_window_end": comparison_end,
                    "report_date": current_date,
                    "weekday": current_dt.strftime("%A"),
                    "comparison_report_date": previous_date,
                    "airbnb_metric_page": metric_page,
                    "metric_name": metric_name,
                    "current_value": current_value,
                    "previous_week_value": previous_value,
                    "change_vs_previous_week": "" if change_num is None else format_number(change_num),
                    "percent_change_vs_previous_week": percent_change(current_value, previous_value),
                    "data_quality_status": status,
                    "notes": notes,
                }
            )
    return output_rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    forbidden = [column for column in COLUMNS if column in DISALLOWED_COLUMNS]
    if forbidden:
        raise ValueError(f"Airbnb daily WOW output includes disallowed truth fields: {', '.join(forbidden)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run(run_date: str, *, run_dir: Path | None = None, input_file: Path | None = None, output_file: Path | None = None) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    resolved_input = input_file or default_input_path(resolved_run_dir, run_date)
    resolved_output = output_file or default_output_path(resolved_run_dir, run_date)
    write_rows(resolved_output, build_daily_rows(read_rows(resolved_input), run_date))
    return resolved_output


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        input_file=Path(args.input_file) if args.input_file else None,
        output_file=Path(args.output_file) if args.output_file else None,
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
