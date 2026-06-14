"""Summarize parsed Airbnb diagnostic extraction into weekly analysis output."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


SUMMARY_COLUMNS = [
    "run_date",
    "metric_window_start",
    "metric_window_end",
    "airbnb_data_quality_status",
    "comparison_type",
    "comparison_window_start",
    "comparison_window_end",
    "page_views",
    "first_page_search_impressions",
    "estimated_relevant_searches",
    "estimated_relevant_searches_per_day",
    "wishlist_additions",
    "average_overall_conversion_rate",
    "first_page_search_impression_rate",
    "search_to_listing_conversion_rate",
    "listing_to_booking_conversion_rate",
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
    "page_views_change_vs_previous_week",
    "wishlist_additions_change_vs_previous_week",
    "first_page_search_impressions_change_vs_previous_week",
    "overall_conversion_change_vs_previous_week",
    "search_to_listing_change_vs_previous_week",
    "listing_to_booking_change_vs_previous_week",
    "has_recent_history_baseline",
    "has_similar_listing_benchmark",
    "diagnostic_confidence",
    "parsed_metric_pages",
    "missing_metric_pages",
    "diagnostic_summary",
    "notes",
]

EXPECTED_METRIC_PAGES = ("booking_conversion", "page_views", "wishlist_additions")

DISALLOWED_SUMMARY_COLUMNS = {
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
    parser = argparse.ArgumentParser(description="Summarize parsed Airbnb diagnostic extraction.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--input-file", help="Parsed Airbnb extraction CSV.")
    parser.add_argument("--output-file", help="Weekly Airbnb summary CSV.")
    return parser.parse_args(argv)


def default_input_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "raw" / f"airbnb_daily_conversion_parsed_{run_date}.csv"


def default_output_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def quality_status(rows_by_page: dict[str, dict[str, str]]) -> str:
    statuses = [rows_by_page.get(page, {}).get("data_quality_status", "missing_source") for page in EXPECTED_METRIC_PAGES]
    if "date_range_warning" in statuses:
        return "date_range_warning"
    if "unsupported_structure" in statuses:
        return "needs_parser_review"
    if "missing_source" in statuses:
        return "incomplete"
    if all(status == "parsed" for status in statuses):
        return "complete"
    return "incomplete"


def first_non_empty(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = row.get(field, "")
        if value:
            return value
    return ""


def parse_number(value: str) -> float | None:
    text = (value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        return None


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def metric_window_days(start: str, end: str) -> int:
    from datetime import date

    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 7
    return days if days > 0 else 7


def estimated_relevant_searches(impressions: str, impression_rate: str) -> float | None:
    impression_count = parse_number(impressions)
    rate_percent = parse_number(impression_rate)
    if impression_count is None or rate_percent is None or rate_percent <= 0:
        return None
    return impression_count / (rate_percent / 100)


def has_previous_week_comparison(row: dict[str, str]) -> bool:
    change_fields = (
        "page_views_change_vs_previous_week",
        "wishlist_additions_change_vs_previous_week",
        "first_page_search_impressions_change_vs_previous_week",
        "overall_conversion_change_vs_previous_week",
        "search_to_listing_change_vs_previous_week",
        "listing_to_booking_change_vs_previous_week",
    )
    return bool(row.get("comparison_window_start") and row.get("comparison_window_end")) or any(row.get(field, "") for field in change_fields)


def has_similar_listing_benchmark(rows: list[dict[str, str]]) -> bool:
    benchmark_fields = (
        "similar_listing_page_views",
        "similar_listing_overall_conversion_rate",
        "similar_listing_wishlist_additions",
    )
    return any(row.get(field, "") for row in rows for field in benchmark_fields)


def diagnostic_confidence(parsed_rows: list[dict[str, str]], summary_row: dict[str, str]) -> str:
    if not has_previous_week_comparison(summary_row):
        return "low"
    historical_windows = {
        (row.get("metric_window_start", ""), row.get("metric_window_end", ""))
        for row in parsed_rows
        if row.get("metric_window_start") and row.get("metric_window_end")
    }
    comparison_windows = {
        (row.get("comparison_window_start", ""), row.get("comparison_window_end", ""))
        for row in parsed_rows
        if row.get("comparison_window_start") and row.get("comparison_window_end")
    }
    return "high" if len(historical_windows | comparison_windows) >= 5 else "medium"


def comparison_summary(row: dict[str, str]) -> str:
    if not has_previous_week_comparison(row):
        return "Airbnb diagnostics parsed successfully, but interpretation is limited because no historical baseline is available."
    if row.get("page_views_change_vs_previous_week", "").startswith("-"):
        return "Airbnb page views declined versus the previous 7 days; compare with PriceLabs market context before assigning cause."
    return "Airbnb conversion signals are available for the selected week; no portfolio revenue conclusion should be made from Airbnb alone."


def build_summary_row(run_date: str, parsed_rows: list[dict[str, str]]) -> dict[str, str]:
    rows_by_page = {row.get("airbnb_metric_page", ""): row for row in parsed_rows}
    rows = [rows_by_page[page] for page in EXPECTED_METRIC_PAGES if page in rows_by_page]
    parsed_pages = [page for page in EXPECTED_METRIC_PAGES if rows_by_page.get(page, {}).get("data_quality_status") in {"parsed", "date_range_warning"}]
    missing_pages = [
        page
        for page in EXPECTED_METRIC_PAGES
        if page not in rows_by_page or rows_by_page.get(page, {}).get("data_quality_status") == "missing_source"
    ]
    status = quality_status(rows_by_page)
    if status == "incomplete":
        missing = ", ".join(missing_pages) or "one or more metric pages"
        diagnostic_summary = f"Airbnb diagnostics are incomplete because {missing} are missing."
    elif status == "needs_parser_review":
        diagnostic_summary = "Airbnb diagnostics need parser review because one or more saved pages had unsupported structure."
    elif status == "date_range_warning":
        diagnostic_summary = "Airbnb diagnostics were parsed, but the selected date range needs review."
    else:
        diagnostic_summary = ""

    notes = " ".join(row.get("notes", "") for row in rows if row.get("notes", "")).strip()
    estimated_searches = estimated_relevant_searches(
        rows_by_page.get("page_views", {}).get("first_page_search_impressions", ""),
        rows_by_page.get("booking_conversion", {}).get("first_page_search_impression_rate", ""),
    )
    window_days = metric_window_days(first_non_empty(rows, "metric_window_start"), first_non_empty(rows, "metric_window_end"))
    summary_row = {
        "run_date": run_date,
        "metric_window_start": first_non_empty(rows, "metric_window_start"),
        "metric_window_end": first_non_empty(rows, "metric_window_end"),
        "airbnb_data_quality_status": status,
        "comparison_type": "",
        "comparison_window_start": first_non_empty(rows, "comparison_window_start"),
        "comparison_window_end": first_non_empty(rows, "comparison_window_end"),
        "page_views": rows_by_page.get("page_views", {}).get("page_views", ""),
        "first_page_search_impressions": rows_by_page.get("page_views", {}).get("first_page_search_impressions", ""),
        "estimated_relevant_searches": format_number(estimated_searches),
        "estimated_relevant_searches_per_day": format_number(estimated_searches / window_days if estimated_searches is not None else None),
        "wishlist_additions": rows_by_page.get("wishlist_additions", {}).get("wishlist_additions", ""),
        "average_overall_conversion_rate": rows_by_page.get("booking_conversion", {}).get("average_overall_conversion_rate", ""),
        "first_page_search_impression_rate": rows_by_page.get("booking_conversion", {}).get("first_page_search_impression_rate", ""),
        "search_to_listing_conversion_rate": rows_by_page.get("booking_conversion", {}).get("search_to_listing_conversion_rate", ""),
        "listing_to_booking_conversion_rate": rows_by_page.get("booking_conversion", {}).get("listing_to_booking_conversion_rate", ""),
        "benchmark_type": "",
        "relevant_searches_wow_change": "",
        "relevant_searches_vs_trailing_benchmark_pct": "",
        "search_to_listing_conversion_vs_benchmark_pct": "",
        "listing_to_booking_conversion_vs_benchmark_pct": "",
        "market_demand_status": "",
        "visibility_status": "",
        "search_card_status": "",
        "listing_conversion_status": "",
        "airbnb_diagnostic_category": "",
        "page_views_change_vs_previous_week": rows_by_page.get("page_views", {}).get("page_views_change_vs_previous_week", ""),
        "wishlist_additions_change_vs_previous_week": rows_by_page.get("wishlist_additions", {}).get("wishlist_additions_change_vs_previous_week", ""),
        "first_page_search_impressions_change_vs_previous_week": rows_by_page.get("page_views", {}).get(
            "first_page_search_impressions_change_vs_previous_week", ""
        ),
        "overall_conversion_change_vs_previous_week": rows_by_page.get("booking_conversion", {}).get("overall_conversion_change_vs_previous_week", ""),
        "search_to_listing_change_vs_previous_week": rows_by_page.get("booking_conversion", {}).get("search_to_listing_change_vs_previous_week", ""),
        "listing_to_booking_change_vs_previous_week": rows_by_page.get("booking_conversion", {}).get("listing_to_booking_change_vs_previous_week", ""),
        "has_recent_history_baseline": "false",
        "has_similar_listing_benchmark": "true" if has_similar_listing_benchmark(rows) else "false",
        "diagnostic_confidence": "",
        "parsed_metric_pages": ";".join(parsed_pages),
        "missing_metric_pages": ";".join(missing_pages),
        "diagnostic_summary": diagnostic_summary,
        "notes": notes,
    }
    summary_row["comparison_type"] = "previous_week" if has_previous_week_comparison(summary_row) else "none"
    summary_row["has_recent_history_baseline"] = "false"
    summary_row["diagnostic_confidence"] = diagnostic_confidence(parsed_rows, summary_row)
    if status == "complete":
        summary_row["diagnostic_summary"] = comparison_summary(summary_row)
    return summary_row


def write_summary(path: Path, row: dict[str, str]) -> None:
    forbidden = [column for column in SUMMARY_COLUMNS if column in DISALLOWED_SUMMARY_COLUMNS]
    if forbidden:
        raise ValueError(f"Airbnb summary output includes disallowed truth fields: {', '.join(forbidden)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def run(run_date: str, *, run_dir: Path | None = None, input_file: Path | None = None, output_file: Path | None = None) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    resolved_input = input_file or default_input_path(resolved_run_dir, run_date)
    resolved_output = output_file or default_output_path(resolved_run_dir, run_date)
    row = build_summary_row(run_date, read_rows(resolved_input))
    write_summary(resolved_output, row)
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
