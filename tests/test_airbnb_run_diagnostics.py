import csv
from pathlib import Path

from airbnb import parse_conversion_html, run_diagnostics


RUN_DATE = "2026-05-21"


DAILY_HTML_BY_FILE = {
    "airbnb_booking_conversion_daily.html": """
    <html><body data-report_date="2026-05-21" data-window_start="2026-05-10" data-window_end="2026-05-17">
      <h1 data-field="listing_name">Aloha Poconos</h1>
      <span data-metric="average_overall_conversion_rate">1.43%</span>
      <span data-metric="first_page_search_impression_rate">55.6%</span>
      <span data-metric="search_to_listing_conversion_rate">35.99%</span>
      <span data-metric="listing_to_booking_conversion_rate">3.98%</span>
    </body></html>
    """,
    "airbnb_page_views_daily.html": """
    <html><body data-report_date="2026-05-21" data-window_start="2026-05-10" data-window_end="2026-05-17">
      <h1 data-field="listing_name">Aloha Poconos</h1>
      <span data-metric="page_views">176</span>
      <span data-metric="first_page_search_impressions">489</span>
    </body></html>
    """,
    "airbnb_wishlist_additions_daily.html": """
    <html><body data-report_date="2026-05-21" data-window_start="2026-05-10" data-window_end="2026-05-17">
      <h1 data-field="listing_name">Aloha Poconos</h1>
      <span data-metric="wishlist_additions">28</span>
    </body></html>
    """,
}


SIMILAR_HTML = """
<html><body>
  ctype=MARKET Airbnb performance Similar listings Your listings
  May 10 - Your listings = 0.91%
  May 10 - Similar listings = 0.19%
  May 11 - Your listings = 1.20%
  May 11 - Similar listings = 0.12%
  May 12 - Your listings = 1.67%
  May 12 - Similar listings = 0.11%
  May 13 - Your listings = 0.00%
  May 13 - Similar listings = 0.12%
  May 14 - Your listings = 3.57%
  May 14 - Similar listings = 0.11%
  May 15 - Your listings = 2.17%
  May 15 - Similar listings = 0.43%
  May 16 - Your listings = 1.30%
  May 16 - Similar listings = 0.69%
  May 17 - Your listings = 2.38%
  May 17 - Similar listings = 0.28%
</body></html>
"""


def write_daily_raw_html(run_dir: Path) -> None:
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for filename, html in DAILY_HTML_BY_FILE.items():
        (raw_dir / filename).write_text(html, encoding="utf-8")


def write_similar_raw_html(run_dir: Path) -> None:
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "airbnb_booking_conversion_similar.html").write_text(SIMILAR_HTML, encoding="utf-8")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_promoted_raw_html_filenames_are_accepted_by_airbnb_diagnostics_flow(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_daily_raw_html(run_dir)
    write_similar_raw_html(run_dir)

    outputs = run_diagnostics.run(RUN_DATE, run_dir=run_dir)

    expected_outputs = {
        run_dir / "raw" / f"airbnb_daily_conversion_parsed_{RUN_DATE}.csv",
        run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{RUN_DATE}.csv",
        run_dir / "analysis" / f"airbnb_weekly_history_comparison_{RUN_DATE}.csv",
        run_dir / "analysis" / f"airbnb_similar_listing_summary_{RUN_DATE}.csv",
        run_dir / "analysis" / f"airbnb_daily_similar_listing_comparison_{RUN_DATE}.csv",
        run_dir / "analysis" / f"airbnb_conversion_diagnostic_report_{RUN_DATE}.md",
    }
    assert expected_outputs.issubset(set(outputs))
    for path in expected_outputs:
        assert path.exists()
    parsed_rows = read_rows(run_dir / "raw" / f"airbnb_daily_conversion_parsed_{RUN_DATE}.csv")
    assert {row["airbnb_metric_page"] for row in parsed_rows} == {"booking_conversion", "page_views", "wishlist_additions"}
    assert not (run_dir / "raw" / "airbnb_booking_conversion_daily.html").exists()
    assert not (run_dir / "raw" / "airbnb_booking_conversion_similar.html").exists()


def test_existing_manual_raw_html_flow_still_uses_parser_expected_filenames(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_daily_raw_html(run_dir)

    output = parse_conversion_html.run(RUN_DATE, run_dir=run_dir)

    assert output == run_dir / "raw" / f"airbnb_daily_conversion_parsed_{RUN_DATE}.csv"
    rows = read_rows(output)
    assert all(row["data_quality_status"] == "parsed" for row in rows)


def test_missing_airbnb_raw_inputs_do_not_crash_optional_diagnostics(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    outputs = run_diagnostics.run(RUN_DATE, run_dir=run_dir)

    assert outputs == []
    assert not (run_dir / "analysis").exists()
    assert not (run_dir / "raw").exists()


def test_existing_parsed_csv_runs_downstream_without_raw_html(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    parsed = run_dir / "raw" / f"airbnb_daily_conversion_parsed_{RUN_DATE}.csv"
    parsed.parent.mkdir(parents=True)
    with parsed.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=parse_conversion_html.COLUMNS)
        writer.writeheader()
        row = {column: "" for column in parse_conversion_html.COLUMNS}
        row.update(
            {
                "run_date": RUN_DATE,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "airbnb_metric_page": "page_views",
                "page_views": "176",
                "data_quality_status": "parsed",
            }
        )
        writer.writerow(row)

    outputs = run_diagnostics.run(RUN_DATE, run_dir=run_dir)

    assert run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{RUN_DATE}.csv" in outputs
    assert run_dir / "analysis" / f"airbnb_weekly_history_comparison_{RUN_DATE}.csv" in outputs


def test_airbnb_diagnostic_outputs_do_not_add_forbidden_truth_fields(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_daily_raw_html(run_dir)

    run_diagnostics.run(RUN_DATE, run_dir=run_dir)

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
    output_files = [
        run_dir / "raw" / f"airbnb_daily_conversion_parsed_{RUN_DATE}.csv",
        run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{RUN_DATE}.csv",
        run_dir / "analysis" / f"airbnb_weekly_history_comparison_{RUN_DATE}.csv",
    ]
    for path in output_files:
        with path.open("r", newline="", encoding="utf-8") as csv_file:
            headers = set(next(csv.reader(csv_file)))
        assert not prohibited.intersection(headers)
