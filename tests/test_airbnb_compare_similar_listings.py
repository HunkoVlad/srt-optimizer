import csv
from pathlib import Path

import pytest

from airbnb import compare_similar_listings


SIMILAR_BOOKING_HTML = """
<html><body>
  ctype=MARKET
  <h1>Aloha Poconos</h1>
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


def test_similar_parser_detects_real_competitor_file_and_daily_values(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "airbnb_booking_conversion_similar.html").write_text(SIMILAR_BOOKING_HTML, encoding="utf-8")

    summary_path, daily_path = compare_similar_listings.run(run_date, run_dir=run_dir)
    summary_rows = list(csv.DictReader(summary_path.open("r", encoding="utf-8")))
    daily_rows = list(csv.DictReader(daily_path.open("r", encoding="utf-8")))
    booking = next(row for row in summary_rows if row["airbnb_metric_page"] == "booking_conversion")

    assert booking["data_quality_status"] == "parsed"
    assert booking["metric_window_start"] == "2026-05-10"
    assert booking["metric_window_end"] == "2026-05-17"
    assert booking["current_value"] == "1.65"
    assert booking["similar_listing_value"] == "0.26"
    assert booking["difference_vs_similar_listings"] == "1.39"
    assert booking["benchmark_mode"] == "similar_listings"
    assert booking["notes"] == "Summary calculated from daily similar-listing chart values."
    assert len(daily_rows) == 8
    assert daily_rows[0]["report_date"] == "2026-05-10"
    assert daily_rows[0]["metric_window_start"] == "2026-05-10"
    assert daily_rows[0]["metric_window_end"] == "2026-05-17"
    assert daily_rows[0]["your_value"] == "0.91%"
    assert daily_rows[0]["similar_listing_value"] == "0.19%"
    assert daily_rows[-1]["report_date"] == "2026-05-17"
    assert daily_rows[-1]["your_value"] == "2.38%"
    assert daily_rows[-1]["similar_listing_value"] == "0.28%"
    assert not (raw_dir / "airbnb_booking_conversion_similar.html").exists()


def test_similar_parser_rejects_dropdown_only_file(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "airbnb_page_views_similar.html").write_text(
        """
        <html><body>
          <select><option>Similar listings</option></select>
          May 10–17
          May 3–10
          Previous week chart values only
        </body></html>
        """,
        encoding="utf-8",
    )

    summary_path, daily_path = compare_similar_listings.run(run_date, run_dir=run_dir)
    summary_rows = list(csv.DictReader(summary_path.open("r", encoding="utf-8")))
    page_views = next(row for row in summary_rows if row["airbnb_metric_page"] == "page_views")

    assert page_views["data_quality_status"] == "unsupported_structure"
    assert list(csv.DictReader(daily_path.open("r", encoding="utf-8"))) == []
    assert (raw_dir / "airbnb_page_views_similar.html").exists()


def test_similar_outputs_are_created_with_missing_sources(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date

    summary_path, daily_path = compare_similar_listings.run(run_date, run_dir=run_dir)
    summary_rows = list(csv.DictReader(summary_path.open("r", encoding="utf-8")))

    assert summary_path == run_dir / "analysis" / f"airbnb_similar_listing_summary_{run_date}.csv"
    assert daily_path == run_dir / "analysis" / f"airbnb_daily_similar_listing_comparison_{run_date}.csv"
    assert len(summary_rows) == 3
    assert {row["data_quality_status"] for row in summary_rows} == {"missing_source"}


def test_similar_listing_columns_exclude_performance_truth_fields() -> None:
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

    assert not prohibited.intersection(compare_similar_listings.SUMMARY_COLUMNS)
    assert not prohibited.intersection(compare_similar_listings.DAILY_COLUMNS)


def test_missing_similar_source_does_not_cause_cleanup_error(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date

    summary_path, daily_path = compare_similar_listings.run(run_date, run_dir=run_dir)

    assert summary_path.exists()
    assert daily_path.exists()


def test_output_write_failure_keeps_parsed_similar_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    source_path = raw_dir / "airbnb_booking_conversion_similar.html"
    source_path.write_text(SIMILAR_BOOKING_HTML, encoding="utf-8")

    def failing_write_csv(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated write failure")

    monkeypatch.setattr(compare_similar_listings, "write_csv", failing_write_csv)

    with pytest.raises(OSError, match="simulated write failure"):
        compare_similar_listings.run(run_date, run_dir=run_dir)

    assert source_path.exists()


def test_cleanup_does_not_delete_daily_html_or_non_airbnb_raw_files(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True)
    (raw_dir / "airbnb_booking_conversion_similar.html").write_text(SIMILAR_BOOKING_HTML, encoding="utf-8")
    daily_html = raw_dir / "airbnb_booking_conversion_daily.html"
    pricelabs_raw = raw_dir / "priceLabs_future_export.csv"
    daily_html.write_text("<html><body>daily over-time file</body></html>", encoding="utf-8")
    pricelabs_raw.write_text("Date,Price\n2026-05-21,100\n", encoding="utf-8")

    compare_similar_listings.run(run_date, run_dir=run_dir)

    assert daily_html.exists()
    assert pricelabs_raw.exists()
