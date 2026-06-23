"""Compare current Airbnb weekly diagnostics against retained weekly history."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from datetime import timedelta
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
    "benchmark_type",
    "benchmark_value",
    "percent_vs_benchmark",
]

METRICS = (
    "page_views",
    "first_page_search_impressions",
    "estimated_relevant_searches",
    "estimated_relevant_searches_per_day",
    "wishlist_additions",
    "average_overall_conversion_rate",
    "first_page_search_impression_rate",
    "search_to_listing_conversion_rate",
    "listing_to_booking_conversion_rate",
)

SUMMARY_BENCHMARK_FIELDS = (
    "benchmark_type",
    "relevant_searches_wow_change",
    "relevant_searches_vs_trailing_benchmark_pct",
    "search_to_listing_conversion_vs_benchmark_pct",
    "listing_to_booking_conversion_vs_benchmark_pct",
    "market_demand_status",
    "visibility_status",
    "search_card_status",
    "listing_conversion_status",
    "airbnb_diagnostic_category",
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


def parse_percent_decimal(value: str) -> float | None:
    number = parse_number(value)
    if number is None:
        return None
    return number / 100


def format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def percent_change(current: float | None, benchmark: float | None) -> float | None:
    if current is None or benchmark is None or benchmark == 0:
        return None
    return ((current - benchmark) / benchmark) * 100


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


def benchmark_rows(prior_rows: list[dict[str, str]], current_window_start: str) -> tuple[str, list[dict[str, str]]]:
    current_start = parse_date(current_window_start)
    if current_start is None or not prior_rows:
        return "no_history", []
    oldest_end = min((parse_date(row.get("metric_window_end", "")) for row in prior_rows), default=None)
    trailing_cutoff = current_start - timedelta(days=365)
    trailing_rows = [
        row
        for row in prior_rows
        if (parse_date(row.get("metric_window_end", "")) or datetime.min) >= trailing_cutoff
    ]
    if oldest_end is not None and oldest_end <= trailing_cutoff and trailing_rows:
        return "trailing_365_days", trailing_rows
    return "all_available_history", prior_rows


def average_metric(rows: list[dict[str, str]], metric: str) -> float | None:
    values = [parse_number(row.get(metric, "")) for row in rows]
    numbers = [value for value in values if value is not None]
    return sum(numbers) / len(numbers) if numbers else None


def classify_threshold(percent_vs_benchmark: float | None, *, weak_threshold: float, strong_threshold: float | None = None) -> str:
    if percent_vs_benchmark is None:
        return "unknown"
    if strong_threshold is not None and percent_vs_benchmark >= strong_threshold:
        return "strong"
    if percent_vs_benchmark <= weak_threshold:
        return "soft" if strong_threshold is not None else "weaker"
    return "normal" if strong_threshold is not None else "stable_or_strong"


def conversion_status(percent_vs_benchmark: float | None) -> str:
    if percent_vs_benchmark is None:
        return "unknown"
    return "weak" if percent_vs_benchmark <= -15 else "stable_or_strong"


def diagnostic_category(
    market: str,
    search_card: str,
    listing: str,
    first_page_search_impressions_vs_benchmark: float | None = None,
    page_views_vs_benchmark: float | None = None,
) -> str:
    high_visibility = (
        first_page_search_impressions_vs_benchmark is not None
        and first_page_search_impressions_vs_benchmark > 0
        and page_views_vs_benchmark is not None
        and page_views_vs_benchmark > 0
    )
    if market == "unknown" and search_card == "weak" and high_visibility:
        return "high_visibility_weak_search_card"
    if market == "strong" and search_card == "weak":
        return "strong_market_weak_search_card"
    if market == "soft" and search_card != "weak" and listing != "weak":
        return "soft_market_normal_conversion"
    if market == "strong" and listing == "weak":
        return "strong_views_weak_booking_conversion"
    return "balanced_monitor_only"


def build_summary_benchmark_fields(current: dict[str, str], prior_rows: list[dict[str, str]]) -> dict[str, str]:
    benchmark_type, benchmark_source = benchmark_rows(prior_rows, current.get("metric_window_start", ""))
    relevant_total_current = parse_number(current.get("estimated_relevant_searches", ""))
    relevant_total_previous = parse_number(prior_rows[0].get("estimated_relevant_searches", "")) if prior_rows else None
    relevant_current = parse_number(current.get("estimated_relevant_searches_per_day", ""))
    relevant_benchmark = average_metric(benchmark_source, "estimated_relevant_searches_per_day")
    page_views_current = parse_number(current.get("page_views", ""))
    page_views_benchmark = average_metric(benchmark_source, "page_views")
    first_page_search_impressions_current = parse_number(current.get("first_page_search_impressions", ""))
    first_page_search_impressions_benchmark = average_metric(benchmark_source, "first_page_search_impressions")
    visibility_current = parse_number(current.get("first_page_search_impression_rate", ""))
    visibility_benchmark = average_metric(benchmark_source, "first_page_search_impression_rate")
    search_current = parse_number(current.get("search_to_listing_conversion_rate", ""))
    search_benchmark = average_metric(benchmark_source, "search_to_listing_conversion_rate")
    listing_current = parse_number(current.get("listing_to_booking_conversion_rate", ""))
    listing_benchmark = average_metric(benchmark_source, "listing_to_booking_conversion_rate")

    relevant_vs_benchmark = percent_change(relevant_current, relevant_benchmark)
    page_views_vs_benchmark = percent_change(page_views_current, page_views_benchmark)
    first_page_search_impressions_vs_benchmark = percent_change(
        first_page_search_impressions_current, first_page_search_impressions_benchmark
    )
    visibility_vs_benchmark = percent_change(visibility_current, visibility_benchmark)
    search_vs_benchmark = percent_change(search_current, search_benchmark)
    listing_vs_benchmark = percent_change(listing_current, listing_benchmark)

    market_status = classify_threshold(relevant_vs_benchmark, weak_threshold=-15, strong_threshold=15)
    visibility_status = classify_threshold(visibility_vs_benchmark, weak_threshold=-10)
    search_card_status = conversion_status(search_vs_benchmark)
    listing_status = conversion_status(listing_vs_benchmark)

    return {
        "benchmark_type": benchmark_type,
        "relevant_searches_wow_change": ""
        if relevant_total_current is None or relevant_total_previous is None
        else format_number(relevant_total_current - relevant_total_previous),
        "relevant_searches_vs_trailing_benchmark_pct": "" if relevant_vs_benchmark is None else format_number(relevant_vs_benchmark),
        "search_to_listing_conversion_vs_benchmark_pct": "" if search_vs_benchmark is None else format_number(search_vs_benchmark),
        "listing_to_booking_conversion_vs_benchmark_pct": "" if listing_vs_benchmark is None else format_number(listing_vs_benchmark),
        "market_demand_status": market_status,
        "visibility_status": visibility_status,
        "search_card_status": search_card_status,
        "listing_conversion_status": listing_status,
        "airbnb_diagnostic_category": diagnostic_category(
            market_status,
            search_card_status,
            listing_status,
            first_page_search_impressions_vs_benchmark,
            page_views_vs_benchmark,
        ),
    }


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
    benchmark_type, benchmark_source = benchmark_rows(prior_rows, current.get("metric_window_start", ""))
    output: list[dict[str, str]] = []
    for metric in METRICS:
        current_num = parse_number(current.get(metric, ""))
        previous_num = parse_number(prior_rows[0].get(metric, "")) if prior_rows else None
        benchmark_value = average_metric(benchmark_source, metric)
        percent_vs_benchmark = percent_change(current_num, benchmark_value)
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
                "benchmark_type": benchmark_type,
                "benchmark_value": "" if benchmark_value is None else format_number(benchmark_value),
                "percent_vs_benchmark": "" if percent_vs_benchmark is None else format_number(percent_vs_benchmark),
            }
        )
    return output


def update_current_summary(path: Path, current: dict[str, str], fields: dict[str, str]) -> None:
    if not path.exists():
        return
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        columns = list(reader.fieldnames or current.keys())
    if not rows:
        return
    rows[0].update(fields)
    fieldnames = list(dict.fromkeys([*columns, *SUMMARY_BENCHMARK_FIELDS]))
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({column: rows[0].get(column, "") for column in fieldnames})


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
    update_current_summary(resolved_current, current, build_summary_benchmark_fields(current, prior))
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
