import csv
import sys

from pricelabs.transform.rolling_13_month_revenue_view import build_rolling_rows, run


def monthly_row(
    stay_month: str,
    revenue_status: str = "conversion_risk",
    monthly_trends_revenue: str = "",
    monthly_trends_occupancy: str = "45",
    monthly_trends_adr: str = "383",
    booking_cleanings: str = "",
    booking_nights: str = "",
) -> dict[str, str]:
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
        "monthly_trends_revenue": monthly_trends_revenue,
        "monthly_trends_occupancy_pct": monthly_trends_occupancy if monthly_trends_revenue else "",
        "monthly_trends_booked_occupancy_pct": "",
        "monthly_trends_blocked_occupancy_pct": "",
        "monthly_trends_adr": monthly_trends_adr if monthly_trends_revenue else "",
        "monthly_trends_source": "pricelabs_monthly_trends" if monthly_trends_revenue else "",
        "bookings_report_bookings": booking_cleanings,
        "bookings_report_cleanings_proxy": booking_cleanings,
        "bookings_report_booked_nights": booking_nights,
        "bookings_report_avg_los": "",
        "bookings_report_rental_revenue": "",
        "bookings_report_total_revenue": "",
        "bookings_report_adr": "",
        "bookings_report_avg_booking_window": "",
        "airbnb_stays": booking_cleanings if booking_cleanings else "",
        "vrbo_stays": "",
        "direct_stays": "",
        "other_unknown_stays": "",
        "main_booking_source": "airbnb" if booking_cleanings else "",
        "booking_source_mix_summary": f"Airbnb {booking_cleanings}" if booking_cleanings else "",
        "month_time_bucket": "next_month",
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": "inefficient",
        "month_action_level": "advisory",
    }


def historical_row(
    stay_month: str,
    bookable: str = "31",
    booked: str = "12",
    occupancy: str = "38.71",
    adr: str = "391",
    revenue: str = "5114.28",
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "stay_month": stay_month,
        "historical_bookable_nights": bookable,
        "historical_booked_nights": booked,
        "historical_paid_occupancy_pct": "19.35",
        "historical_occupancy_pct": occupancy,
        "historical_rental_adr": adr,
        "historical_rental_revpar": "151.35",
        "historical_total_revenue": revenue,
        "historical_source": "pricelabs_kpis_on_the_books",
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

    assert june["data_availability"] == "future_calendar"
    assert june["booked_revenue_proxy"] == "314"
    assert june["revenue_pace_status"] == "conversion_risk"
    assert june["month_action_level"] == "advisory"

    assert november["data_availability"] == "data_not_available"
    assert november["booked_revenue_proxy"] == ""
    assert november["revenue_pace_status"] == "data_not_available"
    assert november["month_action_level"] == "monitor"
    assert november["historical_data_quality_flag"] == "data_not_available"


def test_historical_actuals_merge_only_into_historical_rows() -> None:
    rows = build_rolling_rows(
        [
            monthly_row("2026-05"),
            monthly_row("2026-06"),
        ],
        "2026-05-08",
        [
            historical_row("2026-02"),
            historical_row("2026-05", revenue="9999"),
        ],
    )

    february = by_month(rows, "2026-02")
    may = by_month(rows, "2026-05")
    january = by_month(rows, "2026-01")

    assert february["data_availability"] == "data_not_available"
    assert february["historical_total_revenue"] == ""
    assert february["historical_source"] == ""
    assert february["historical_data_quality_flag"] == "data_not_available"
    assert february["revenue_pace_status"] == "data_not_available"
    assert february["month_action_level"] == "monitor"

    assert may["data_availability"] == "future_calendar"
    assert may["booked_revenue_proxy"] == "314"
    assert may["historical_total_revenue"] == ""
    assert may["revenue_pace_status"] == "conversion_risk"

    assert january["data_availability"] == "data_not_available"
    assert january["historical_data_quality_flag"] == "data_not_available"


def test_historical_calendar_occupancy_uses_calendar_days_not_kpi_denominator() -> None:
    rows = build_rolling_rows(
        [],
        "2026-05-08",
        [
            historical_row("2026-02", bookable="50", booked="19", occupancy="38.0"),
        ],
    )

    february = by_month(rows, "2026-02")

    assert february["data_availability"] == "data_not_available"
    assert february["historical_calendar_occupancy_pct"] == ""


def test_suspicious_historical_actuals_are_flagged_without_failure() -> None:
    rows = build_rolling_rows(
        [],
        "2026-05-08",
        [
            historical_row("2026-02", bookable="100", booked="120", occupancy="120", adr="-1", revenue="-10"),
        ],
    )

    february = by_month(rows, "2026-02")

    assert february["data_availability"] == "data_not_available"
    assert february["historical_data_quality_flag"] == "data_not_available"
    assert february["historical_total_revenue"] == ""


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


def test_monthly_trends_source_labels_by_window_position() -> None:
    rows = build_rolling_rows(
        [
            monthly_row("2026-04", "partial_horizon", monthly_trends_revenue="6609.76"),
            monthly_row("2026-05", monthly_trends_revenue="5357"),
            monthly_row("2026-06", monthly_trends_revenue="314"),
            monthly_row("2026-11", "partial_horizon"),
        ],
        "2026-05-08",
    )

    assert by_month(rows, "2026-04")["data_availability"] == "monthly_trends_actuals"
    assert by_month(rows, "2026-05")["data_availability"] == "monthly_trends_current"
    assert by_month(rows, "2026-06")["data_availability"] == "monthly_trends_future_on_books"
    assert by_month(rows, "2026-11")["data_availability"] == "partial_horizon"


def test_invalid_low_revenue_historical_month_is_data_not_available() -> None:
    rows = build_rolling_rows(
        [
            monthly_row("2025-11", monthly_trends_revenue="588", monthly_trends_occupancy="45", monthly_trends_adr="383"),
        ],
        "2026-05-08",
    )

    november = by_month(rows, "2025-11")

    assert november["data_availability"] == "data_not_available"
    assert november["revenue_pace_status"] == "data_not_available"
    assert november["cleaning_efficiency_status"] == "data_not_available"
    assert november["historical_total_revenue"] == ""


def test_historical_monthly_trends_estimates_booked_nights_and_cleanings_from_observed_los() -> None:
    rows = build_rolling_rows(
        [
            monthly_row("2026-03", monthly_trends_revenue="8887.86", monthly_trends_occupancy="74.2", monthly_trends_adr="351.26"),
            monthly_row("2026-05", booking_cleanings="12", booking_nights="24"),
        ],
        "2026-05-08",
    )

    march = by_month(rows, "2026-03")

    assert march["data_availability"] == "monthly_trends_actuals"
    assert march["historical_booked_nights"] == "25"
    assert march["historical_booked_nights_source"] == "estimated_from_monthly_trends"
    assert march["historical_cleanings_proxy"] == "13"
    assert march["historical_cleanings_source"] == "estimated_from_monthly_trends"
    assert march["revenue_per_cleaning_proxy"] == "683.68"
    assert march["cleaning_efficiency_status"] == "historical_actuals"


def test_historical_month_ignores_partial_booking_metrics_and_estimates_from_monthly_trends() -> None:
    rows = build_rolling_rows(
        [
            monthly_row(
                "2026-04",
                monthly_trends_revenue="6609.76",
                monthly_trends_occupancy="53.3",
                monthly_trends_adr="369.63",
                booking_cleanings="7",
                booking_nights="16",
            ),
            monthly_row("2026-05", booking_cleanings="12", booking_nights="24"),
        ],
        "2026-05-08",
    )

    april = by_month(rows, "2026-04")

    assert april["historical_booked_nights"] == "18"
    assert april["historical_booked_nights_source"] == "estimated_from_monthly_trends"
    assert april["historical_cleanings_proxy"] == "9"
    assert april["historical_cleanings_source"] == "estimated_from_monthly_trends"
    assert april["revenue_per_cleaning_proxy"] == "734.42"
    assert april["cleaning_efficiency_status"] == "historical_actuals"


def test_observed_avg_los_excludes_historical_booking_rows() -> None:
    rows = build_rolling_rows(
        [
            monthly_row(
                "2026-04",
                monthly_trends_revenue="6609.76",
                monthly_trends_occupancy="53.3",
                monthly_trends_adr="369.63",
                booking_cleanings="1",
                booking_nights="1",
            ),
            monthly_row("2026-05", booking_cleanings="10", booking_nights="30"),
        ],
        "2026-05-08",
    )

    april = by_month(rows, "2026-04")

    assert april["historical_booked_nights"] == "18"
    assert april["historical_cleanings_proxy"] == "6"
    assert april["revenue_per_cleaning_proxy"] == "1101.63"
