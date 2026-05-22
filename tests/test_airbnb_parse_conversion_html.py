import csv
import json
from pathlib import Path

from airbnb import parse_conversion_html


def test_parse_airbnb_html_extracts_structured_metrics(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_booking_conversion_daily.html"
    html = """
    <html>
      <head><title>Aloha Poconos</title></head>
      <body data-report_date="2026-05-20" data-window_start="2026-05-10" data-window_end="2026-05-17">
        <h1 data-field="listing_name">Aloha Poconos</h1>
        <span data-metric="page_views">123</span>
        <span data-metric="first_page_search_impressions">456</span>
        <span data-metric="similar_listing_page_views">211</span>
        <span data-metric="average_overall_conversion_rate">3.2%</span>
        <span data-metric="similar_listing_overall_conversion_rate">4.1%</span>
        <span data-metric="first_page_search_impression_rate">18%</span>
        <span data-metric="search_to_listing_conversion_rate">7.5%</span>
        <span data-metric="listing_to_booking_conversion_rate">1.1%</span>
        <span data-metric="wishlist_additions">9</span>
        <span data-metric="similar_listing_wishlist_additions">14</span>
      </body>
    </html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="booking_conversion",
        source_file=source,
    )

    assert row["run_date"] == "2026-05-21"
    assert row["report_date"] == "2026-05-20"
    assert row["metric_window_start"] == "2026-05-10"
    assert row["metric_window_end"] == "2026-05-17"
    assert row["listing_name"] == "Aloha Poconos"
    assert row["page_views"] == "123"
    assert row["first_page_search_impressions"] == "456"
    assert row["similar_listing_page_views"] == "211"
    assert row["first_page_search_impression_rate"] == "18%"
    assert row["listing_to_booking_conversion_rate"] == "1.1%"
    assert row["wishlist_additions"] == "9"
    assert row["data_quality_status"] == "parsed"
    assert row["extraction_method"] == "manual_html"


def test_parse_airbnb_html_extracts_label_metrics(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_page_views_daily.html"
    html = """
    <html><body>
      Listing name: Aloha Poconos
      2026-05-10 to 2026-05-17
      Report date: 2026-05-20
      Page views: 88
      Similar listing page views: 140
      Search-to-listing conversion rate: 6.4%
      Listing-to-booking conversion rate: 0.8%
    </body></html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="page_views",
        source_file=source,
    )

    assert row["listing_name"] == "Aloha Poconos"
    assert row["metric_window_start"] == "2026-05-10"
    assert row["metric_window_end"] == "2026-05-17"
    assert row["page_views"] == "88"
    assert row["similar_listing_page_views"] == "140"
    assert row["search_to_listing_conversion_rate"] == "6.4%"
    assert row["listing_to_booking_conversion_rate"] == "0.8%"
    assert row["data_quality_status"] == "parsed"


def test_metric_cards_map_value_before_label_text(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_booking_conversion_daily.html"
    html = """
    <html><body>
      <h1>Booking conversion</h1>
      Apr 12 → Apr 19
      Apr 12–19
      Apr 5–12
      <div>0.36% Average overall conversion rate</div>
      <div>52.4% First-page search impression rate</div>
      <div>27.21% Average search-to-listing conversion</div>
      <div>1.32% Average listing-to-booking conversion</div>
    </body></html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="booking_conversion",
        source_file=source,
    )

    assert row["metric_window_start"] == "2026-04-12"
    assert row["metric_window_end"] == "2026-04-19"
    assert row["average_overall_conversion_rate"] == "0.36%"
    assert row["first_page_search_impression_rate"] == "52.4%"
    assert row["search_to_listing_conversion_rate"] == "27.21%"
    assert row["listing_to_booking_conversion_rate"] == "1.32%"
    assert row["data_quality_status"] == "parsed"
    assert "Chart legend ranges detected" in row["notes"]


def test_page_views_table_uses_total_value(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_page_views_daily.html"
    html = """
    <html><body>
      <h1>Page views</h1>
      Apr 12 â†’ Apr 19
      <section>
        <h2>Average page views</h2>
        <table>
          <tr><th>Change</th><th>Total</th></tr>
          <tr><td>-157</td><td>176</td></tr>
        </table>
      </section>
      <section>
        <h2>Average first-page search impressions</h2>
        <table>
          <tr><th>Change</th><th>Total</th></tr>
          <tr><td>-18</td><td>64</td></tr>
        </table>
      </section>
    </body></html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="page_views",
        source_file=source,
    )

    assert row["page_views"] == "176"
    assert row["first_page_search_impressions"] == "64"
    assert row["page_views_change_vs_previous_week"] == "-157"
    assert row["first_page_search_impressions_change_vs_previous_week"] == "-18"
    assert row["data_quality_status"] == "parsed"


def test_page_views_sentence_comparison_populates_previous_week_change(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_page_views_daily.html"
    html = """
    <html><body>
      <h1>Page views</h1>
      May 10â€“17
      May 3â€“10
      Average page views
      Total 176
      The total page views for May 10â€“17 was down 157 compared to the previous 7 days.
    </body></html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="page_views",
        source_file=source,
    )

    assert row["metric_window_start"] == "2026-05-10"
    assert row["metric_window_end"] == "2026-05-17"
    assert row["comparison_window_start"] == "2026-05-03"
    assert row["comparison_window_end"] == "2026-05-10"
    assert row["page_views"] == "176"
    assert row["page_views_change_vs_previous_week"] == "-157"


def test_wishlist_table_uses_total_value(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_wishlist_additions_daily.html"
    html = """
    <html><body>
      <h1>Wishlist additions</h1>
      May 10â€“17
      May 3â€“10
      <section>
        <h2>Average wishlist additions</h2>
        <dl>
          <dt>May 10</dt><dd>3</dd>
          <dt>May 11</dt><dd>4</dd>
        </dl>
        <table>
          <tr><th>Change</th><th>Total</th></tr>
          <tr><td>-2</td><td>28</td></tr>
        </table>
      </section>
    </body></html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="wishlist_additions",
        source_file=source,
    )

    assert row["metric_window_start"] == "2026-05-10"
    assert row["metric_window_end"] == "2026-05-17"
    assert row["comparison_window_start"] == "2026-05-03"
    assert row["comparison_window_end"] == "2026-05-10"
    assert row["wishlist_additions"] == "28"
    assert row["wishlist_additions_change_vs_previous_week"] == "-2"
    assert row["data_quality_status"] == "parsed"
    assert "Chart legend ranges detected" in row["notes"]
    chart_values = json.loads(row["daily_chart_values_json"])
    assert chart_values == [
        {"date": "2026-05-10", "value": "3"},
        {"date": "2026-05-11", "value": "4"},
    ]


def test_wishlist_sentence_comparison_populates_previous_week_change(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_wishlist_additions_daily.html"
    html = """
    <html><body>
      <h1>Wishlist additions</h1>
      May 10â€“17
      May 3â€“10
      Average wishlist additions
      Total 28
      The total wishlist additions for May 10â€“17 was down 2 compared to the previous 7 days.
    </body></html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="wishlist_additions",
        source_file=source,
    )

    assert row["comparison_window_start"] == "2026-05-03"
    assert row["comparison_window_end"] == "2026-05-10"
    assert row["wishlist_additions"] == "28"
    assert row["wishlist_additions_change_vs_previous_week"] == "-2"


def test_sunday_to_sunday_validation() -> None:
    assert parse_conversion_html.validate_sunday_to_sunday("2026-04-12", "2026-04-19") == ""
    assert "start date is not Sunday" in parse_conversion_html.validate_sunday_to_sunday("2026-04-13", "2026-04-19")
    assert "end date is not Sunday" in parse_conversion_html.validate_sunday_to_sunday("2026-04-12", "2026-04-18")
    assert "range is not one full week" in parse_conversion_html.validate_sunday_to_sunday("2026-04-12", "2026-04-26")


def test_non_sunday_date_range_warns(tmp_path: Path) -> None:
    source = tmp_path / "airbnb_page_views_daily.html"
    html = """
    <html><body>
      <h1>Page views</h1>
      Apr 13 → Apr 20
      Page views: 88
    </body></html>
    """

    row = parse_conversion_html.parse_airbnb_html(
        html,
        run_date="2026-05-21",
        metric_page="page_views",
        source_file=source,
    )

    assert row["metric_window_start"] == "2026-04-13"
    assert row["metric_window_end"] == "2026-04-20"
    assert row["data_quality_status"] == "date_range_warning"
    assert "start date is not Sunday" in row["notes"]
    assert "end date is not Sunday" in row["notes"]


def test_run_writes_missing_rows_without_required_airbnb_sources(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / "2026-05-21"
    (run_dir / "raw").mkdir(parents=True)
    output = parse_conversion_html.run("2026-05-21", run_dir=run_dir)

    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))

    assert output == run_dir / "raw" / "airbnb_daily_conversion_parsed_2026-05-21.csv"
    assert len(rows) == 3
    assert {row["data_quality_status"] for row in rows} == {"missing_source"}
    assert {row["airbnb_metric_page"] for row in rows} == {
        "booking_conversion",
        "page_views",
        "wishlist_additions",
    }


def test_run_writes_parsed_and_missing_rows(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "airbnb_wishlist_additions_daily.html").write_text(
        """
        <html><body>
          <h1>Aloha Poconos</h1>
          Apr 12 → Apr 19
          Report date: 2026-05-20
          Wishlist additions: 12
          Similar listing wishlist additions: 18
        </body></html>
        """,
        encoding="utf-8",
    )

    output = parse_conversion_html.run(run_date, run_dir=run_dir)
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    wishlist = next(row for row in rows if row["airbnb_metric_page"] == "wishlist_additions")

    assert wishlist["wishlist_additions"] == "12"
    assert wishlist["similar_listing_wishlist_additions"] == "18"
    assert wishlist["data_quality_status"] == "parsed"
    assert sum(1 for row in rows if row["data_quality_status"] == "missing_source") == 2


def test_run_preserves_existing_parsed_rows_when_source_missing(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    existing_output = raw_dir / f"airbnb_daily_conversion_parsed_{run_date}.csv"
    existing_rows = [
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
            "source_file": "old.html",
            "extraction_method": "manual_html",
            "data_quality_status": "parsed",
            "notes": "existing booking row",
        },
        {
            "run_date": run_date,
            "metric_window_start": "2026-05-10",
            "metric_window_end": "2026-05-17",
            "listing_name": "Aloha Poconos",
            "airbnb_metric_page": "page_views",
            "page_views": "176",
            "first_page_search_impressions": "64",
            "source_file": "old.html",
            "extraction_method": "manual_html",
            "data_quality_status": "parsed",
            "notes": "existing page row",
        },
        {
            "run_date": run_date,
            "airbnb_metric_page": "wishlist_additions",
            "source_file": "old.html",
            "extraction_method": "manual_html",
            "data_quality_status": "missing_source",
            "notes": "missing old wishlist row",
        },
    ]
    with existing_output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=parse_conversion_html.COLUMNS)
        writer.writeheader()
        writer.writerows(existing_rows)
    (raw_dir / "airbnb_wishlist_additions_daily.html").write_text(
        """
        <html><body>
          <h1>Wishlist additions</h1>
          May 10â€“17
          Average wishlist additions
          Change Total
          -2 28
        </body></html>
        """,
        encoding="utf-8",
    )

    output = parse_conversion_html.run(run_date, run_dir=run_dir)
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))

    booking = next(row for row in rows if row["airbnb_metric_page"] == "booking_conversion")
    page_views = next(row for row in rows if row["airbnb_metric_page"] == "page_views")
    wishlist = next(row for row in rows if row["airbnb_metric_page"] == "wishlist_additions")

    assert booking["data_quality_status"] == "parsed"
    assert booking["notes"] == "existing booking row"
    assert page_views["data_quality_status"] == "parsed"
    assert page_views["page_views"] == "176"
    assert wishlist["wishlist_additions"] == "28"
    assert wishlist["data_quality_status"] == "parsed"


def test_run_migrates_preservation_from_deprecated_analysis_output(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    analysis_dir = run_dir / "analysis"
    raw_dir.mkdir(parents=True)
    analysis_dir.mkdir(parents=True)
    legacy_output = analysis_dir / f"airbnb_daily_conversion_{run_date}.csv"
    with legacy_output.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=parse_conversion_html.COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "run_date": run_date,
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "listing_name": "Aloha Poconos",
                "airbnb_metric_page": "page_views",
                "page_views": "176",
                "source_file": "old.html",
                "extraction_method": "manual_html",
                "data_quality_status": "parsed",
                "notes": "legacy page row",
            }
        )

    output = parse_conversion_html.run(run_date, run_dir=run_dir)
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))
    page_views = next(row for row in rows if row["airbnb_metric_page"] == "page_views")

    assert output == raw_dir / f"airbnb_daily_conversion_parsed_{run_date}.csv"
    assert page_views["data_quality_status"] == "parsed"
    assert page_views["notes"] == "legacy page row"
    assert legacy_output.exists()


def test_run_deletes_only_temporary_airbnb_html_after_success(tmp_path: Path, capsys) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    for filename in parse_conversion_html.TEMPORARY_AIRBNB_HTML_FILES:
        (raw_dir / filename).write_text(
            "<html><body><h1>Aloha Poconos</h1>Report date: 2026-05-20 Page views: 3</body></html>",
            encoding="utf-8",
        )
    protected_files = {
        "bookings_report.xlsx": b"fake workbook",
        "monthly_trends.csv": b"month_year,Revenue\nMay 2026,1\n",
        "price_occ.csv": b"Date,Market Occupancy\n2026-05-20,1\n",
        "priceLabs_future_export.csv": b"Listing ID,Date\n1,2026-05-20\n",
        "pricelabs_settings_snapshot_from_ui.json": b"{}",
    }
    for filename, content in protected_files.items():
        (raw_dir / filename).write_bytes(content)

    parse_conversion_html.run(run_date, run_dir=run_dir)

    output = capsys.readouterr().out
    for filename in parse_conversion_html.TEMPORARY_AIRBNB_HTML_FILES:
        assert not (raw_dir / filename).exists()
        assert filename in output
    for filename in protected_files:
        assert (raw_dir / filename).exists()


def test_run_keeps_airbnb_html_if_output_write_fails(tmp_path: Path, monkeypatch) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    html_path = raw_dir / "airbnb_booking_conversion_daily.html"
    html_path.write_text(
        "<html><body><h1>Aloha Poconos</h1>Report date: 2026-05-20 Page views: 3</body></html>",
        encoding="utf-8",
    )

    def fail_write(_path, _rows):
        raise RuntimeError("write failed")

    monkeypatch.setattr(parse_conversion_html, "write_rows", fail_write)

    try:
        parse_conversion_html.run(run_date, run_dir=run_dir)
    except RuntimeError:
        pass
    else:
        raise AssertionError("parser run should fail when output write fails")

    assert html_path.exists()


def test_output_columns_exclude_performance_truth_fields() -> None:
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

    assert not prohibited.intersection(parse_conversion_html.COLUMNS)
