"""Compare current Airbnb weekly diagnostics against retained weekly history."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path


COLUMNS = [
    "run_date",
    "metric_window_start",
    "metric_window_end",
    "metric_name",
    "current_value",
    "previous_week_value",
    "change_vs_previous_week",
    "last_4_week_avg",
    "change_vs_last_4_week_avg",
    "recent_history_weeks_used",
    "history_quality_status",
    "notes",
]

METRICS = (
    "page_views",
    "first_page_search_impressions",
    "wishlist_additions",
    "average_overall_conversion_rate",
    "first_page_search_impression_rate",
    "search_to_listing_conversion_rate",
    "listing_to_booking_conversion_rate",
)

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
    parser = argparse.ArgumentParser(description="Compare Airbnb weekly summary against retained historical summaries.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--runs-dir", help="Runs directory. Defaults to data/runs.")
    parser.add_argument("--current-file", help="Current Airbnb weekly summary CSV.")
    parser.add_argument("--output-file", help="Airbnb weekly history comparison CSV.")
    return parser.parse_args(argv)


def read_first_row(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))
    return rows[0] if rows else None


def parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def parse_number(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value.rstrip("%"))
    except (AttributeError, ValueError):
        return None


def format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def default_current_path(runs_dir: Path, run_date: str) -> Path:
    return runs_dir / run_date / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv"


def default_output_path(runs_dir: Path, run_date: str) -> Path:
    return runs_dir / run_date / "analysis" / f"airbnb_weekly_history_comparison_{run_date}.csv"


def find_prior_summary_paths(runs_dir: Path, run_date: str) -> list[Path]:
    current_path = default_current_path(runs_dir, run_date).resolve()
    return sorted(
        path
        for path in runs_dir.glob("*/analysis/airbnb_weekly_conversion_summary_*.csv")
        if path.resolve() != current_path
    )


def valid_prior_rows(paths: list[Path], current_window_start: str) -> list[dict[str, str]]:
    current_start = parse_date(current_window_start)
    if current_start is None:
        return []
    rows: list[dict[str, str]] = []
    for path in paths:
        row = read_first_row(path)
        if not row or row.get("airbnb_data_quality_status") != "complete":
            continue
        start = parse_date(row.get("metric_window_start", ""))
        end = parse_date(row.get("metric_window_end", ""))
        if start is None or end is None or end > current_start:
            continue
        if not any(parse_number(row.get(metric, "")) is not None for metric in METRICS):
            continue
        rows.append(row)
    return sorted(rows, key=lambda row: parse_date(row.get("metric_window_end", "")) or datetime.min, reverse=True)


def history_quality(count: int) -> str:
    if count == 0:
        return "no_history"
    if count == 1:
        return "previous_week_only"
    if count in {2, 3}:
        return "limited_history"
    return "recent_baseline_ready"


def build_rows(run_date: str, current: dict[str, str], prior_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    quality = history_quality(len(prior_rows))
    output: list[dict[str, str]] = []
    for metric in METRICS:
        current_num = parse_number(current.get(metric, ""))
        previous_num = parse_number(prior_rows[0].get(metric, "")) if prior_rows else None
        last_four_values = [parse_number(row.get(metric, "")) for row in prior_rows[:4]]
        last_four_numbers = [value for value in last_four_values if value is not None]
        last_four_avg = sum(last_four_numbers) / len(last_four_numbers) if len(last_four_numbers) >= 4 else None
        output.append(
            {
                "run_date": run_date,
                "metric_window_start": current.get("metric_window_start", ""),
                "metric_window_end": current.get("metric_window_end", ""),
                "metric_name": metric,
                "current_value": current.get(metric, ""),
                "previous_week_value": "" if previous_num is None else format_number(previous_num),
                "change_vs_previous_week": ""
                if current_num is None or previous_num is None
                else format_number(current_num - previous_num),
                "last_4_week_avg": "" if last_four_avg is None else format_number(last_four_avg),
                "change_vs_last_4_week_avg": ""
                if current_num is None or last_four_avg is None
                else format_number(current_num - last_four_avg),
                "recent_history_weeks_used": str(len(prior_rows)),
                "history_quality_status": quality,
                "notes": "Airbnb retained-history comparison only; do not infer portfolio revenue cause from Airbnb alone.",
            }
        )
    return output


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    forbidden = [column for column in COLUMNS if column in DISALLOWED_COLUMNS]
    if forbidden:
        raise ValueError(f"Airbnb history comparison includes disallowed truth fields: {', '.join(forbidden)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run(
    run_date: str,
    *,
    runs_dir: Path | None = None,
    current_file: Path | None = None,
    output_file: Path | None = None,
) -> Path:
    resolved_runs_dir = runs_dir or Path("data") / "runs"
    resolved_current = current_file or default_current_path(resolved_runs_dir, run_date)
    resolved_output = output_file or default_output_path(resolved_runs_dir, run_date)
    current = read_first_row(resolved_current)
    if not current:
        raise ValueError(f"Missing or empty Airbnb weekly summary: {resolved_current}")
    prior = valid_prior_rows(find_prior_summary_paths(resolved_runs_dir, run_date), current.get("metric_window_start", ""))
    write_rows(resolved_output, build_rows(run_date, current, prior))
    return resolved_output


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = run(
        args.run_date,
        runs_dir=Path(args.runs_dir) if args.runs_dir else None,
        current_file=Path(args.current_file) if args.current_file else None,
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
