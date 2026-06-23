import csv
from pathlib import Path

from airbnb import compare_weekly_history, summarize_conversion


def write_summary(runs_dir: Path, run_date: str, window_start: str, window_end: str, values: dict[str, str]) -> None:
    path = runs_dir / run_date / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "run_date": run_date,
        "metric_window_start": window_start,
        "metric_window_end": window_end,
        "airbnb_data_quality_status": "complete",
        "page_views": "100",
        "first_page_search_impressions": "50",
        "wishlist_additions": "10",
        "average_overall_conversion_rate": "1.0%",
        "first_page_search_impression_rate": "40%",
        "search_to_listing_conversion_rate": "20%",
        "listing_to_booking_conversion_rate": "2%",
        "estimated_relevant_searches": "",
        "estimated_relevant_searches_per_day": "",
    }
    row.update(values)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=summarize_conversion.SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def run_compare(tmp_path: Path, prior: list[tuple[str, str, str, dict[str, str]]]) -> list[dict[str, str]]:
    runs_dir = tmp_path / "data" / "runs"
    write_summary(
        runs_dir,
        "2026-05-21",
        "2026-05-10",
        "2026-05-17",
        {"page_views": "176", "average_overall_conversion_rate": "0.36%"},
    )
    for run_date, start, end, values in prior:
        write_summary(runs_dir, run_date, start, end, values)
    output = compare_weekly_history.run("2026-05-21", runs_dir=runs_dir)
    return list(csv.DictReader(output.open("r", encoding="utf-8")))


def metric(rows: list[dict[str, str]], name: str) -> dict[str, str]:
    return next(row for row in rows if row["metric_name"] == name)


def test_no_history_produces_no_history(tmp_path: Path) -> None:
    rows = run_compare(tmp_path, [])
    page_views = metric(rows, "page_views")

    assert page_views["history_quality_status"] == "no_history"
    assert page_views["recent_history_weeks_used"] == "0"
    assert page_views["previous_week_value"] == ""
    assert page_views["last_4_week_avg"] == ""


def test_one_prior_summary_produces_previous_week_only(tmp_path: Path) -> None:
    rows = run_compare(tmp_path, [("2026-05-14", "2026-05-03", "2026-05-10", {"page_views": "120"})])
    page_views = metric(rows, "page_views")

    assert page_views["history_quality_status"] == "previous_week_only"
    assert page_views["previous_week_value"] == "120"
    assert page_views["change_vs_previous_week"] == "56"
    assert page_views["last_4_week_avg"] == ""


def test_two_or_three_prior_summaries_produce_limited_history(tmp_path: Path) -> None:
    rows = run_compare(
        tmp_path,
        [
            ("2026-05-14", "2026-05-03", "2026-05-10", {"page_views": "120"}),
            ("2026-05-07", "2026-04-26", "2026-05-03", {"page_views": "140"}),
            ("2026-04-30", "2026-04-19", "2026-04-26", {"page_views": "160"}),
        ],
    )
    page_views = metric(rows, "page_views")

    assert page_views["history_quality_status"] == "limited_history"
    assert page_views["recent_history_weeks_used"] == "3"
    assert page_views["last_4_week_avg"] == ""


def test_four_prior_summaries_produce_recent_baseline_ready(tmp_path: Path) -> None:
    rows = run_compare(
        tmp_path,
        [
            ("2026-05-14", "2026-05-03", "2026-05-10", {"page_views": "120"}),
            ("2026-05-07", "2026-04-26", "2026-05-03", {"page_views": "140"}),
            ("2026-04-30", "2026-04-19", "2026-04-26", {"page_views": "160"}),
            ("2026-04-23", "2026-04-12", "2026-04-19", {"page_views": "180"}),
        ],
    )
    page_views = metric(rows, "page_views")

    assert page_views["history_quality_status"] == "recent_baseline_ready"
    assert page_views["recent_history_weeks_used"] == "4"
    assert page_views["last_4_week_avg"] == "150"
    assert page_views["change_vs_last_4_week_avg"] == "26"


def test_percent_values_parse_correctly(tmp_path: Path) -> None:
    rows = run_compare(
        tmp_path,
        [
            ("2026-05-14", "2026-05-03", "2026-05-10", {"average_overall_conversion_rate": "0.50%"}),
            ("2026-05-07", "2026-04-26", "2026-05-03", {"average_overall_conversion_rate": "0.40%"}),
            ("2026-04-30", "2026-04-19", "2026-04-26", {"average_overall_conversion_rate": "0.30%"}),
            ("2026-04-23", "2026-04-12", "2026-04-19", {"average_overall_conversion_rate": "0.20%"}),
        ],
    )
    conversion = metric(rows, "average_overall_conversion_rate")

    assert conversion["current_value"] == "0.36%"
    assert conversion["previous_week_value"] == "0.5"
    assert conversion["change_vs_previous_week"] == "-0.14"
    assert conversion["last_4_week_avg"] == "0.35"
    assert conversion["change_vs_last_4_week_avg"] == "0.01"


def test_percent_decimal_conversion() -> None:
    assert compare_weekly_history.parse_percent_decimal("58.1%") == 0.581


def test_benchmark_comparison_and_classification_updates_summary(tmp_path: Path) -> None:
    runs_dir = tmp_path / "data" / "runs"
    write_summary(
        runs_dir,
        "2026-05-21",
        "2026-05-10",
        "2026-05-17",
        {
            "first_page_search_impressions": "3280",
            "first_page_search_impression_rate": "56.5%",
            "search_to_listing_conversion_rate": "10.15%",
            "listing_to_booking_conversion_rate": "1.50%",
            "estimated_relevant_searches": "5805.31",
            "estimated_relevant_searches_per_day": "829.33",
        },
    )
    write_summary(
        runs_dir,
        "2026-05-14",
        "2026-05-03",
        "2026-05-10",
        {
            "first_page_search_impressions": "2500",
            "first_page_search_impression_rate": "70%",
            "search_to_listing_conversion_rate": "15%",
            "listing_to_booking_conversion_rate": "2%",
            "estimated_relevant_searches": "3571.43",
            "estimated_relevant_searches_per_day": "510.2",
        },
    )

    output = compare_weekly_history.run("2026-05-21", runs_dir=runs_dir)
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    summary = list(
        csv.DictReader(
            (runs_dir / "2026-05-21" / "analysis" / "airbnb_weekly_conversion_summary_2026-05-21.csv").open(
                "r", encoding="utf-8"
            )
        )
    )[0]

    relevant = metric(rows, "estimated_relevant_searches_per_day")
    assert relevant["benchmark_type"] == "all_available_history"
    assert relevant["benchmark_value"] == "510.2"
    assert relevant["percent_vs_benchmark"] == "62.55"
    assert summary["benchmark_type"] == "all_available_history"
    assert summary["relevant_searches_wow_change"] == "2233.88"
    assert summary["market_demand_status"] == "strong"
    assert summary["visibility_status"] == "weaker"
    assert summary["search_card_status"] == "weak"
    assert summary["listing_conversion_status"] == "weak"
    assert summary["airbnb_diagnostic_category"] == "strong_market_weak_search_card"


def test_unknown_demand_high_visibility_weak_search_card_gets_specific_category(tmp_path: Path) -> None:
    runs_dir = tmp_path / "data" / "runs"
    write_summary(
        runs_dir,
        "2026-05-21",
        "2026-05-10",
        "2026-05-17",
        {
            "page_views": "220",
            "first_page_search_impressions": "1200",
            "search_to_listing_conversion_rate": "8%",
            "listing_to_booking_conversion_rate": "2%",
            "estimated_relevant_searches": "",
            "estimated_relevant_searches_per_day": "",
        },
    )
    write_summary(
        runs_dir,
        "2026-05-14",
        "2026-05-03",
        "2026-05-10",
        {
            "page_views": "100",
            "first_page_search_impressions": "600",
            "search_to_listing_conversion_rate": "20%",
            "listing_to_booking_conversion_rate": "2%",
            "estimated_relevant_searches": "",
            "estimated_relevant_searches_per_day": "",
        },
    )

    compare_weekly_history.run("2026-05-21", runs_dir=runs_dir)
    summary = list(
        csv.DictReader(
            (runs_dir / "2026-05-21" / "analysis" / "airbnb_weekly_conversion_summary_2026-05-21.csv").open(
                "r", encoding="utf-8"
            )
        )
    )[0]

    assert summary["market_demand_status"] == "unknown"
    assert summary["search_card_status"] == "weak"
    assert summary["airbnb_diagnostic_category"] == "high_visibility_weak_search_card"


def test_history_comparison_columns_exclude_performance_truth_fields() -> None:
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

    assert not prohibited.intersection(compare_weekly_history.COLUMNS)
