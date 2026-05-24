"""Compare Airbnb daily diagnostic values against current-week averages."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


COLUMNS = [
    "run_date",
    "metric_window_start",
    "metric_window_end",
    "report_date",
    "weekday",
    "airbnb_metric_page",
    "metric_name",
    "daily_value",
    "current_week_avg",
    "difference_vs_week_avg",
    "percent_difference_vs_week_avg",
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Airbnb daily diagnostics to current-week averages.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--input-file", help="Daily Airbnb week-over-week CSV.")
    parser.add_argument("--output-file", help="Daily Airbnb weekly-average deviation CSV.")
    return parser.parse_args(argv)


def default_input_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv"


def default_output_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_daily_week_average_deviation_{run_date}.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


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


def percent_difference(value: float, avg: float) -> str:
    if avg == 0:
        return ""
    return format_number(((value - avg) / avg) * 100)


def build_rows(daily_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in daily_rows:
        metric_name = row.get("metric_name", "")
        value = numeric(row.get("current_value", ""))
        if not metric_name or value is None:
            continue
        grouped.setdefault(metric_name, []).append(row)

    output: list[dict[str, str]] = []
    for metric_name, rows in grouped.items():
        values = [numeric(row.get("current_value", "")) for row in rows]
        numbers = [value for value in values if value is not None]
        if not numbers:
            continue
        avg = sum(numbers) / len(numbers)
        for row in rows:
            value = numeric(row.get("current_value", ""))
            if value is None:
                continue
            output.append(
                {
                    "run_date": row.get("run_date", ""),
                    "metric_window_start": row.get("metric_window_start", ""),
                    "metric_window_end": row.get("metric_window_end", ""),
                    "report_date": row.get("report_date", ""),
                    "weekday": row.get("weekday", ""),
                    "airbnb_metric_page": row.get("airbnb_metric_page", ""),
                    "metric_name": metric_name,
                    "daily_value": row.get("current_value", ""),
                    "current_week_avg": format_number(avg),
                    "difference_vs_week_avg": format_number(value - avg),
                    "percent_difference_vs_week_avg": percent_difference(value, avg),
                    "data_quality_status": row.get("data_quality_status", ""),
                    "notes": "Daily deviation from current-week Airbnb average only; do not infer cause from Airbnb alone.",
                }
            )
    return output


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    forbidden = [column for column in COLUMNS if column in DISALLOWED_COLUMNS]
    if forbidden:
        raise ValueError(f"Airbnb daily average deviation output includes disallowed truth fields: {', '.join(forbidden)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run(run_date: str, *, run_dir: Path | None = None, input_file: Path | None = None, output_file: Path | None = None) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    resolved_input = input_file or default_input_path(resolved_run_dir, run_date)
    resolved_output = output_file or default_output_path(resolved_run_dir, run_date)
    write_rows(resolved_output, build_rows(read_rows(resolved_input)))
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
