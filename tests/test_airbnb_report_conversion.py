import csv
from pathlib import Path

from airbnb import compare_daily_to_weekly_avg, compare_similar_listings, compare_weekly_history, extract_daily_wow, report_conversion, summarize_conversion


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def create_inputs(run_dir: Path, run_date: str) -> None:
    write_csv(
        run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv",
        summarize_conversion.SUMMARY_COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "airbnb_data_quality_status": "complete",
                "comparison_type": "previous_week",
                "comparison_window_start": "2026-05-03",
                "comparison_window_end": "2026-05-10",
                "page_views": "176",
                "first_page_search_impressions": "64",
                "wishlist_additions": "28",
                "average_overall_conversion_rate": "0.36%",
                "first_page_search_impression_rate": "52.4%",
                "search_to_listing_conversion_rate": "27.21%",
                "listing_to_booking_conversion_rate": "1.32%",
                "page_views_change_vs_previous_week": "-157",
                "wishlist_additions_change_vs_previous_week": "-2",
                "first_page_search_impressions_change_vs_previous_week": "-18",
                "overall_conversion_change_vs_previous_week": "",
                "search_to_listing_change_vs_previous_week": "1.0%",
                "listing_to_booking_change_vs_previous_week": "-0.2%",
                "has_recent_history_baseline": "false",
                "has_similar_listing_benchmark": "false",
                "diagnostic_confidence": "medium",
                "parsed_metric_pages": "booking_conversion;page_views;wishlist_additions",
                "diagnostic_summary": "Airbnb page views declined versus the previous 7 days; compare with PriceLabs market context before assigning cause.",
            }
        ],
    )
    write_csv(
        run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv",
        extract_daily_wow.COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "comparison_window_start": "2026-05-03",
                "comparison_window_end": "2026-05-10",
                "report_date": "2026-05-16",
                "weekday": "Saturday",
                "comparison_report_date": "2026-05-09",
                "airbnb_metric_page": "page_views",
                "metric_name": "page_views",
                "current_value": "14",
                "previous_week_value": "110",
                "change_vs_previous_week": "-96",
                "percent_change_vs_previous_week": "-87.27",
                "data_quality_status": "parsed",
            },
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "comparison_window_start": "2026-05-03",
                "comparison_window_end": "2026-05-10",
                "report_date": "2026-05-10",
                "weekday": "Sunday",
                "comparison_report_date": "2026-05-03",
                "airbnb_metric_page": "page_views",
                "metric_name": "page_views",
                "current_value": "44",
                "previous_week_value": "3",
                "change_vs_previous_week": "41",
                "percent_change_vs_previous_week": "1366.67",
                "data_quality_status": "parsed",
            },
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "comparison_window_start": "2026-05-03",
                "comparison_window_end": "2026-05-10",
                "report_date": "2026-05-11",
                "weekday": "Monday",
                "comparison_report_date": "2026-05-04",
                "airbnb_metric_page": "wishlist_additions",
                "metric_name": "wishlist_additions",
                "current_value": "3",
                "previous_week_value": "13",
                "change_vs_previous_week": "-10",
                "percent_change_vs_previous_week": "-76.92",
                "data_quality_status": "parsed",
            },
        ],
    )
    write_csv(
        run_dir / "analysis" / f"airbnb_daily_week_average_deviation_{run_date}.csv",
        compare_daily_to_weekly_avg.COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "report_date": "2026-05-16",
                "weekday": "Saturday",
                "airbnb_metric_page": "page_views",
                "metric_name": "page_views",
                "daily_value": "14",
                "current_week_avg": "22",
                "difference_vs_week_avg": "-8",
                "percent_difference_vs_week_avg": "-36.36",
                "data_quality_status": "parsed",
            },
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "report_date": "2026-05-10",
                "weekday": "Sunday",
                "airbnb_metric_page": "page_views",
                "metric_name": "page_views",
                "daily_value": "44",
                "current_week_avg": "22",
                "difference_vs_week_avg": "22",
                "percent_difference_vs_week_avg": "100",
                "data_quality_status": "parsed",
            },
        ],
    )
    write_csv(
        run_dir / "analysis" / f"airbnb_similar_listing_summary_{run_date}.csv",
        compare_similar_listings.SUMMARY_COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "airbnb_metric_page": "booking_conversion",
                "metric_name": "average_overall_conversion_rate",
                "current_value": "0.91%",
                "similar_listing_value": "0.19%",
                "difference_vs_similar_listings": "0.72",
                "percent_difference_vs_similar_listings": "378.95",
                "benchmark_mode": "similar_listings",
                "data_quality_status": "parsed",
            }
        ],
    )
    write_csv(
        run_dir / "analysis" / f"airbnb_daily_similar_listing_comparison_{run_date}.csv",
        compare_similar_listings.DAILY_COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "report_date": "2026-05-10",
                "weekday": "Sunday",
                "airbnb_metric_page": "booking_conversion",
                "metric_name": "average_overall_conversion_rate",
                "your_value": "0.91%",
                "similar_listing_value": "0.19%",
                "difference_vs_similar_listings": "0.72",
                "percent_difference_vs_similar_listings": "378.95",
                "benchmark_mode": "similar_listings",
                "data_quality_status": "parsed",
            },
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "report_date": "2026-05-11",
                "weekday": "Monday",
                "airbnb_metric_page": "booking_conversion",
                "metric_name": "average_overall_conversion_rate",
                "your_value": "0.10%",
                "similar_listing_value": "0.25%",
                "difference_vs_similar_listings": "-0.15",
                "percent_difference_vs_similar_listings": "-60",
                "benchmark_mode": "similar_listings",
                "data_quality_status": "parsed",
            },
        ],
    )


def test_report_file_created_from_weekly_and_daily_inputs(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    output = report_conversion.run(run_date, run_dir=run_dir)

    assert output == run_dir / "analysis" / f"airbnb_conversion_diagnostic_report_{run_date}.md"
    assert output.exists()


def test_missing_weekly_summary_raises_clear_error(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date

    try:
        report_conversion.run(run_date, run_dir=run_dir)
    except FileNotFoundError as exc:
        message = str(exc)
    else:
        raise AssertionError("missing weekly summary should fail clearly")

    assert "Missing Airbnb weekly summary" in message
    assert f"python -m airbnb.summarize_conversion --run-date {run_date}" in message


def test_empty_weekly_summary_raises_clear_error(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    write_csv(
        run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv",
        summarize_conversion.SUMMARY_COLUMNS,
        [],
    )

    try:
        report_conversion.run(run_date, run_dir=run_dir)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("empty weekly summary should fail clearly")

    assert "Airbnb weekly summary has no usable row" in message


def test_report_includes_weekly_snapshot_fields(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert text.startswith("# Airbnb Conversion Diagnostic Report")
    assert "run_date,metric_window_start" not in text
    assert "metric_name,current_value" not in text
    assert "## Airbnb Diagnostic Snapshot" in text
    assert "Metric window: 2026-05-10 to 2026-05-17" in text
    assert "Comparison window: 2026-05-03 to 2026-05-10" in text
    assert "Diagnostic confidence: medium" in text
    assert "Recent history baseline: false" in text
    assert "booking_conversion;page_views;wishlist_additions" in text


def test_report_uses_history_comparison_for_high_confidence(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)
    write_csv(
        run_dir / "analysis" / f"airbnb_weekly_history_comparison_{run_date}.csv",
        compare_weekly_history.COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "metric_name": "page_views",
                "history_quality_status": "recent_baseline_ready",
            }
        ],
    )

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert text.startswith("# Airbnb Conversion Diagnostic Report")
    assert "run_date,metric_window_start" not in text
    assert "metric_name,current_value" not in text
    assert "Diagnostic confidence: high" in text
    assert "Recent history baseline: true" in text


def test_report_overwrites_stale_csv_content(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)
    output = run_dir / "analysis" / f"airbnb_conversion_diagnostic_report_{run_date}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "run_date,metric_window_start,metric_window_end\n"
        "2026-05-21,2026-05-10,2026-05-17\n"
        "metric_name,current_value,history_quality_status\n",
        encoding="utf-8",
    )

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert text.startswith("# Airbnb Conversion Diagnostic Report")
    assert "run_date,metric_window_start" not in text
    assert "metric_name,current_value" not in text
    assert "## Weekly Funnel Signals" in text


def test_weekly_funnel_table_has_five_columns(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "| Signal | Value | WoW Change | 4-Week Avg | vs 4-Week Avg |" in text
    assert "| Page views | 176 | -157 | - | - |" in text
    assert "| Wishlist additions | 28 | -2 | - | - |" in text
    assert "| First-page search impression rate | 52.4% | - | - | - |" in text
    signal_lines = [line for line in text.splitlines() if line.startswith("| ") and line.endswith(" |")]
    for line in signal_lines:
        assert len([cell for cell in line.split("|") if cell.strip()]) == 5


def test_weekly_funnel_table_uses_history_baseline_columns(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)
    write_csv(
        run_dir / "analysis" / f"airbnb_weekly_history_comparison_{run_date}.csv",
        compare_weekly_history.COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "metric_name": "page_views",
                "change_vs_previous_week": "-157",
                "last_4_week_avg": "150",
                "change_vs_last_4_week_avg": "26",
                "history_quality_status": "recent_baseline_ready",
            },
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "metric_name": "wishlist_additions",
                "change_vs_previous_week": "-2",
                "last_4_week_avg": "32",
                "change_vs_last_4_week_avg": "-4",
                "history_quality_status": "recent_baseline_ready",
            },
        ],
    )

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "| Page views | 176 | -157 | 150 | 26 |" in text
    assert "| Wishlist additions | 28 | -2 | 32 | -4 |" in text
    assert "run_date,metric_window_start" not in text
    assert "metric_name,current_value" not in text


def test_report_uses_history_comparison_wow_values_for_all_metrics(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)
    history_rows = [
        ("page_views", "-157", "292.25", "-116.25"),
        ("first_page_search_impressions", "-205", "879", "-390"),
        ("wishlist_additions", "-2", "29.75", "-1.75"),
        ("average_overall_conversion_rate", "0.71", "0.69", "0.74"),
        ("first_page_search_impression_rate", "-1", "55.92", "-0.32"),
        ("search_to_listing_conversion_rate", "-11.99", "38.72", "-2.73"),
        ("listing_to_booking_conversion_rate", "2.48", "1.7", "2.29"),
    ]
    write_csv(
        run_dir / "analysis" / f"airbnb_weekly_history_comparison_{run_date}.csv",
        compare_weekly_history.COLUMNS,
        [
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "metric_name": metric,
                "change_vs_previous_week": wow,
                "last_4_week_avg": avg,
                "change_vs_last_4_week_avg": vs_avg,
                "history_quality_status": "recent_baseline_ready",
            }
            for metric, wow, avg, vs_avg in history_rows
        ],
    )

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "| Page views | 176 | -157 | 292.25 | -116.25 |" in text
    assert "| First-page search impressions | 64 | -205 | 879 | -390 |" in text
    assert "| Wishlist additions | 28 | -2 | 29.75 | -1.75 |" in text
    assert "| Average overall conversion rate | 0.36% | 0.71 | 0.69 | 0.74 |" in text
    assert "| First-page search impression rate | 52.4% | -1 | 55.92 | -0.32 |" in text
    assert "| Search-to-listing conversion rate | 27.21% | -11.99 | 38.72 | -2.73 |" in text
    assert "| Listing-to-booking conversion rate | 1.32% | 2.48 | 1.7 | 2.29 |" in text


def test_missing_daily_wow_keeps_weekly_snapshot(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)
    (run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv").unlink()

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "Metric window: 2026-05-10 to 2026-05-17" in text
    assert "| Page views | 176 | -157 | - | - |" in text
    assert "Daily movement is unavailable" in text


def test_report_includes_largest_page_view_drops(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "### page_views" in text
    assert "2026-05-16 Saturday: 14 vs 110 (-96 (-87.27%))" in text
    assert "2026-05-10 Sunday: 44 vs 3 (41 (1366.67%))" in text


def test_report_includes_daily_movement_vs_weekly_average(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "## Daily Movement vs Weekly Average" in text
    assert "2026-05-16 Saturday: 14 vs avg 22 (-8 (-36.36%))" in text
    assert "2026-05-10 Sunday: 44 vs avg 22 (22 (100%))" in text
    assert "These daily deviations show intra-week movement only. PriceLabs market context is required before assigning cause." in text


def test_report_includes_similar_listings_sections(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "## Similar Listings Benchmark" in text
    assert "| average_overall_conversion_rate | 0.91% | 0.19% | 0.72 | 378.95 |" in text
    assert "## Daily Similar Listings Movement" in text
    assert "2026-05-11 Monday: 0.10% vs similar 0.25% (-0.15 (-60%))" in text
    assert "2026-05-10 Sunday: 0.91% vs similar 0.19% (0.72 (378.95%))" in text


def test_report_includes_neutral_boundary_wording(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8")

    assert "PriceLabs market context is required before assigning cause." in text
    assert "Similar listings data is an Airbnb diagnostic benchmark only." in text
    assert "Airbnb data is used only for visibility and conversion diagnostics." in text
    assert "PriceLabs remains the source of truth" in text


def test_report_avoids_pricelabs_rule_recommendations(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    create_inputs(run_dir, run_date)

    text = report_conversion.run(run_date, run_dir=run_dir).read_text(encoding="utf-8").lower()

    assert "rule areas to review" not in text
    assert "raise price" not in text
    assert "lower price" not in text
    assert "change pricelabs" not in text
    assert "pricing problem" not in text
    assert "market weakness" not in text


def test_report_does_not_add_forbidden_airbnb_metric_fields() -> None:
    prohibited = {
        "booked_nights",
        "booking_value",
        "total_bookings",
        "cleaning_count",
        "monthly_revenue_pace",
    }

    combined_columns = (
        set(summarize_conversion.SUMMARY_COLUMNS)
        | set(extract_daily_wow.COLUMNS)
        | set(compare_daily_to_weekly_avg.COLUMNS)
        | set(compare_similar_listings.SUMMARY_COLUMNS)
        | set(compare_similar_listings.DAILY_COLUMNS)
    )

    assert not prohibited.intersection(combined_columns)
