import csv
from pathlib import Path

from airbnb import parse_conversion_html, summarize_conversion


def write_parsed_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=parse_conversion_html.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def base_rows(run_date: str) -> list[dict[str, str]]:
    return [
        {
            "run_date": run_date,
            "metric_window_start": "2026-05-10",
            "metric_window_end": "2026-05-17",
            "listing_name": "Aloha Poconos",
            "airbnb_metric_page": "booking_conversion",
            "average_overall_conversion_rate": "0.36%",
            "first_page_search_impression_rate": "52.4%",
            "search_to_listing_conversion_rate": "27.21%",
            "listing_to_booking_conversion_rate": "1.32%",
            "extraction_method": "manual_html",
            "data_quality_status": "parsed",
            "notes": "booking parsed",
        },
        {
            "run_date": run_date,
            "metric_window_start": "2026-05-10",
            "metric_window_end": "2026-05-17",
            "listing_name": "Aloha Poconos",
            "airbnb_metric_page": "page_views",
            "page_views": "176",
            "first_page_search_impressions": "64",
            "extraction_method": "manual_html",
            "data_quality_status": "parsed",
            "notes": "page parsed",
        },
        {
            "run_date": run_date,
            "metric_window_start": "2026-05-10",
            "metric_window_end": "2026-05-17",
            "listing_name": "Aloha Poconos",
            "airbnb_metric_page": "wishlist_additions",
            "wishlist_additions": "28",
            "extraction_method": "manual_html",
            "data_quality_status": "parsed",
            "notes": "wishlist parsed",
        },
    ]


def run_summary(tmp_path: Path, rows: list[dict[str, str]]) -> dict[str, str]:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    input_file = run_dir / "raw" / f"airbnb_daily_conversion_parsed_{run_date}.csv"
    write_parsed_rows(input_file, rows)
    output = summarize_conversion.run(run_date, run_dir=run_dir)
    summary_rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    assert output == run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv"
    assert len(summary_rows) == 1
    return summary_rows[0]


def test_complete_parsed_input_creates_complete_summary(tmp_path: Path) -> None:
    row = run_summary(tmp_path, base_rows("2026-05-21"))

    assert row["airbnb_data_quality_status"] == "complete"
    assert row["page_views"] == "176"
    assert row["first_page_search_impressions"] == "64"
    assert row["wishlist_additions"] == "28"
    assert row["average_overall_conversion_rate"] == "0.36%"
    assert row["parsed_metric_pages"] == "booking_conversion;page_views;wishlist_additions"
    assert row["missing_metric_pages"] == ""
    assert row["comparison_type"] == "none"
    assert row["has_recent_history_baseline"] == "false"
    assert row["diagnostic_confidence"] == "low"
    assert "no historical baseline" in row["diagnostic_summary"]
    assert row["estimated_relevant_searches"] == "122.14"
    assert row["estimated_relevant_searches_per_day"] == "17.45"


def test_estimated_relevant_searches_converts_percent_rate() -> None:
    estimate = summarize_conversion.estimated_relevant_searches("337", "58.1%")

    assert estimate is not None
    assert round(estimate, 2) == 580.03


def test_estimated_relevant_searches_handles_missing_or_zero_rate_safely(tmp_path: Path) -> None:
    rows = base_rows("2026-05-21")
    rows[0]["first_page_search_impression_rate"] = "0%"

    row = run_summary(tmp_path, rows)

    assert row["estimated_relevant_searches"] == ""
    assert row["estimated_relevant_searches_per_day"] == ""


def test_previous_week_comparison_creates_medium_confidence_summary(tmp_path: Path) -> None:
    rows = base_rows("2026-05-21")
    rows[1]["comparison_window_start"] = "2026-05-03"
    rows[1]["comparison_window_end"] = "2026-05-10"
    rows[1]["page_views_change_vs_previous_week"] = "-157"

    row = run_summary(tmp_path, rows)

    assert row["comparison_type"] == "previous_week"
    assert row["comparison_window_start"] == "2026-05-03"
    assert row["comparison_window_end"] == "2026-05-10"
    assert row["page_views_change_vs_previous_week"] == "-157"
    assert row["has_recent_history_baseline"] == "false"
    assert row["diagnostic_confidence"] == "medium"
    assert "declined versus the previous 7 days" in row["diagnostic_summary"]


def test_previous_week_wishlist_comparison_creates_medium_confidence_summary(tmp_path: Path) -> None:
    rows = base_rows("2026-05-21")
    rows[2]["comparison_window_start"] = "2026-05-03"
    rows[2]["comparison_window_end"] = "2026-05-10"
    rows[2]["wishlist_additions_change_vs_previous_week"] = "-2"

    row = run_summary(tmp_path, rows)

    assert row["comparison_type"] == "previous_week"
    assert row["comparison_window_start"] == "2026-05-03"
    assert row["comparison_window_end"] == "2026-05-10"
    assert row["wishlist_additions_change_vs_previous_week"] == "-2"
    assert row["diagnostic_confidence"] == "medium"


def test_missing_wishlist_row_creates_incomplete_summary(tmp_path: Path) -> None:
    rows = [row for row in base_rows("2026-05-21") if row["airbnb_metric_page"] != "wishlist_additions"]

    row = run_summary(tmp_path, rows)

    assert row["airbnb_data_quality_status"] == "incomplete"
    assert row["missing_metric_pages"] == "wishlist_additions"
    assert "wishlist_additions" in row["diagnostic_summary"]


def test_unsupported_structure_creates_needs_parser_review_summary(tmp_path: Path) -> None:
    rows = base_rows("2026-05-21")
    rows[1]["data_quality_status"] = "unsupported_structure"

    row = run_summary(tmp_path, rows)

    assert row["airbnb_data_quality_status"] == "needs_parser_review"
    assert "parser review" in row["diagnostic_summary"]


def test_date_range_warning_creates_date_range_warning_summary(tmp_path: Path) -> None:
    rows = base_rows("2026-05-21")
    rows[0]["data_quality_status"] = "date_range_warning"

    row = run_summary(tmp_path, rows)

    assert row["airbnb_data_quality_status"] == "date_range_warning"
    assert "date range needs review" in row["diagnostic_summary"]


def test_summary_columns_exclude_performance_truth_fields() -> None:
    prohibited = {
        "adr",
        "occupancy",
        "revenue",
        "booked_nights",
        "booking_value",
        "total_bookings",
        "cleaning_count",
        "monthly_revenue_pace",
    }

    assert not prohibited.intersection(summarize_conversion.SUMMARY_COLUMNS)
