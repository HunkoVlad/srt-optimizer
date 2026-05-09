import csv
import sys

from pricelabs.transform.rolling_13_month_revenue_view import build_rolling_rows, run


def monthly_row(stay_month: str, revenue_status: str = "conversion_risk") -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "stay_month": stay_month,
        "days_in_scope": "30",
        "days_in_month": "30",
        "month_scope_status": "full_month",
        "booked_nights": "1",
        "available_nights": "29",
        "unavailable_nights": "0",
        "booked_revenue_proxy": "314",
        "open_revenue_ask": "14090",
        "total_future_revenue_proxy": "14404",
        "monthly_target": "10000",
        "booked_gap_to_target": "9686",
        "total_gap_to_target": "-4404",
        "booked_cleanings_proxy": "1",
        "avg_stay_length_proxy": "1",
        "revenue_per_cleaning_proxy": "314",
        "booked_revenue_pct_of_target": "0.0314",
        "total_future_revenue_pct_of_target": "1.4404",
        "month_time_bucket": "next_month",
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": "inefficient",
        "month_action_level": "advisory",
    }


def by_month(rows: list[dict[str, str]], month: str) -> dict[str, str]:
    return next(row for row in rows if row["stay_month"] == month)


def test_build_rolling_rows_covers_13_months_and_positions() -> None:
    rows = build_rolling_rows(
        [
            monthly_row("2026-05"),
            monthly_row("2026-06"),
            monthly_row("2026-07", "protect_open_value"),
        ],
        "2026-05-08",
    )

    assert len(rows) == 13
    assert [row["month_relative_index"] for row in rows] == [str(index) for index in range(-6, 7)]
    assert rows[0]["stay_month"] == "2025-11"
    assert rows[6]["stay_month"] == "2026-05"
    assert rows[-1]["stay_month"] == "2026-11"
    assert rows[0]["month_window_position"] == "historical"
    assert rows[6]["month_window_position"] == "current"
    assert rows[-1]["month_window_position"] == "future"


def test_build_rolling_rows_preserves_available_months_and_marks_missing() -> None:
    rows = build_rolling_rows([monthly_row("2026-06")], "2026-05-08")
    june = by_month(rows, "2026-06")
    november = by_month(rows, "2025-11")

    assert june["data_availability"] == "available"
    assert june["booked_revenue_proxy"] == "314"
    assert june["revenue_pace_status"] == "conversion_risk"
    assert june["month_action_level"] == "advisory"

    assert november["data_availability"] == "no_source_data"
    assert november["booked_revenue_proxy"] == ""
    assert november["revenue_pace_status"] == "no_source_data"
    assert november["month_action_level"] == "monitor"


def test_rolling_view_cli_writes_output(tmp_path, monkeypatch) -> None:
    monthly_file = tmp_path / "monthly_revenue_pace_2026-05-08.csv"
    output_file = tmp_path / "rolling_13_month_revenue_view_2026-05-08.csv"

    with monthly_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=monthly_row("2026-06").keys())
        writer.writeheader()
        writer.writerow(monthly_row("2026-06"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rolling_13_month_revenue_view",
            "--run-date",
            "2026-05-08",
            "--monthly-file",
            str(monthly_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0

    with output_file.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 13
    assert rows[0]["month_relative_index"] == "-6"
    assert rows[-1]["month_relative_index"] == "6"
