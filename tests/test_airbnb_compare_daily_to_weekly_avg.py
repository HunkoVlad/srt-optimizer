import csv
from pathlib import Path

from airbnb import compare_daily_to_weekly_avg, extract_daily_wow


def write_daily_wow(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=extract_daily_wow.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def daily_row(run_date: str, report_date: str, value: str, metric_name: str = "page_views") -> dict[str, str]:
    return {
        "run_date": run_date,
        "metric_window_start": "2026-05-10",
        "metric_window_end": "2026-05-17",
        "report_date": report_date,
        "weekday": "Sunday",
        "airbnb_metric_page": "page_views",
        "metric_name": metric_name,
        "current_value": value,
        "data_quality_status": "parsed",
    }


def test_daily_average_deviation_output_created(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    write_daily_wow(
        run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv",
        [daily_row(run_date, "2026-05-10", "10"), daily_row(run_date, "2026-05-11", "30")],
    )

    output = compare_daily_to_weekly_avg.run(run_date, run_dir=run_dir)
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))

    assert output == run_dir / "analysis" / f"airbnb_daily_week_average_deviation_{run_date}.csv"
    assert len(rows) == 2
    assert rows[0]["daily_value"] == "10"
    assert rows[0]["current_week_avg"] == "20"
    assert rows[0]["difference_vs_week_avg"] == "-10"
    assert rows[0]["percent_difference_vs_week_avg"] == "-50"
    assert rows[1]["difference_vs_week_avg"] == "10"


def test_percent_difference_blank_when_weekly_average_zero(tmp_path: Path) -> None:
    run_date = "2026-05-21"
    run_dir = tmp_path / "data" / "runs" / run_date
    write_daily_wow(
        run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv",
        [daily_row(run_date, "2026-05-10", "0"), daily_row(run_date, "2026-05-11", "0")],
    )

    output = compare_daily_to_weekly_avg.run(run_date, run_dir=run_dir)
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))

    assert {row["current_week_avg"] for row in rows} == {"0"}
    assert {row["percent_difference_vs_week_avg"] for row in rows} == {""}


def test_daily_average_deviation_columns_exclude_performance_truth_fields() -> None:
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

    assert not prohibited.intersection(compare_daily_to_weekly_avg.COLUMNS)
