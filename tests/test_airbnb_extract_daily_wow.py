import csv
import json
from pathlib import Path

from airbnb import extract_daily_wow, parse_conversion_html


def write_parsed_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=parse_conversion_html.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def chart_values(current_values: list[int], previous_values: list[int]) -> str:
    current_dates = ["2026-05-10", "2026-05-11", "2026-05-12", "2026-05-13", "2026-05-14", "2026-05-15", "2026-05-16", "2026-05-17"]
    previous_dates = ["2026-05-03", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08", "2026-05-09", "2026-05-10"]
    values = []
    for current_date, previous_date, current_value, previous_value in zip(current_dates, previous_dates, current_values, previous_values):
        values.append({"date": current_date, "value": str(current_value)})
        values.append({"date": previous_date, "value": str(previous_value)})
    return json.dumps(values, separators=(",", ":"))


def base_row(metric_page: str, metric_name: str, payload: str) -> dict[str, str]:
    return {
        "run_date": "2026-05-21",
        "metric_window_start": "2026-05-10",
        "metric_window_end": "2026-05-17",
        "comparison_window_start": "2026-05-03",
        "comparison_window_end": "2026-05-10",
        "listing_name": "Aloha Poconos",
        "airbnb_metric_page": metric_page,
        metric_name: "1",
        "daily_chart_values_json": payload,
        "source_file": "test.html",
        "extraction_method": "manual_html",
        "data_quality_status": "parsed",
    }


def run_daily(tmp_path: Path, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    input_file = run_dir / "raw" / f"airbnb_daily_conversion_parsed_{run_date}.csv"
    write_parsed_rows(input_file, rows)
    output = extract_daily_wow.run(run_date, run_dir=run_dir)
    assert output == run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv"
    return list(csv.DictReader(output.open("r", encoding="utf-8")))


def test_page_views_daily_week_over_week_rows(tmp_path: Path) -> None:
    rows = run_daily(
        tmp_path,
        [
            base_row(
                "page_views",
                "page_views",
                chart_values([44, 34, 12, 15, 24, 18, 14, 8], [3, 35, 19, 19, 18, 85, 110, 44]),
            )
        ],
    )

    assert len(rows) == 8
    assert rows[0]["report_date"] == "2026-05-10"
    assert rows[0]["weekday"] == "Sunday"
    assert rows[0]["comparison_report_date"] == "2026-05-03"
    assert rows[0]["metric_name"] == "page_views"
    assert rows[0]["current_value"] == "44"
    assert rows[0]["previous_week_value"] == "3"
    assert rows[0]["change_vs_previous_week"] == "41"
    assert rows[0]["percent_change_vs_previous_week"] == "1366.67"
    assert rows[-1]["report_date"] == "2026-05-17"
    assert rows[-1]["comparison_report_date"] == "2026-05-10"
    assert rows[-1]["change_vs_previous_week"] == "-36"
    assert rows[-1]["data_quality_status"] == "parsed"
    assert "8 Sunday-to-Sunday points" in rows[-1]["notes"]


def test_wishlist_daily_week_over_week_rows(tmp_path: Path) -> None:
    rows = run_daily(
        tmp_path,
        [
            base_row(
                "wishlist_additions",
                "wishlist_additions",
                chart_values([5, 3, 0, 0, 5, 2, 3, 9], [3, 13, 0, 3, 4, 2, 0, 5]),
            )
        ],
    )

    assert len(rows) == 8
    assert rows[0]["metric_name"] == "wishlist_additions"
    assert rows[0]["current_value"] == "5"
    assert rows[0]["previous_week_value"] == "3"
    assert rows[0]["change_vs_previous_week"] == "2"
    assert rows[2]["current_value"] == "0"
    assert rows[2]["previous_week_value"] == "0"
    assert rows[2]["percent_change_vs_previous_week"] == ""
    assert rows[-1]["current_value"] == "9"
    assert rows[-1]["previous_week_value"] == "5"


def test_missing_daily_chart_values_writes_no_rows(tmp_path: Path) -> None:
    rows = run_daily(tmp_path, [base_row("page_views", "page_views", "")])

    assert rows == []


def test_daily_wow_columns_exclude_performance_truth_fields() -> None:
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

    assert not prohibited.intersection(extract_daily_wow.COLUMNS)
