import csv
import sys

from pricelabs.transform.email_revenue_report import build_markdown, run


def rolling_row(
    stay_month: str,
    position: str,
    data: str,
    bucket: str = "",
    scope: str = "",
    booked_revenue: str = "",
    open_ask: str = "",
    total_calendar_value: str = "",
    booked_nights: str = "",
    cleanings: str = "",
    days_in_scope: str = "",
    revenue_per_cleaning: str = "",
    revenue_status: str = "no_source_data",
    cleaning_status: str = "",
    action_level: str = "monitor",
    historical_booked_nights: str = "",
    historical_calendar_occupancy_pct: str = "",
    historical_total_revenue: str = "",
    historical_rental_adr: str = "",
    historical_booked_nights_source: str = "",
    historical_cleanings_proxy: str = "",
    historical_cleanings_source: str = "",
    monthly_trends_revenue: str = "",
    monthly_trends_occupancy_pct: str = "",
    monthly_trends_adr: str = "",
    airbnb_stays: str = "",
    vrbo_stays: str = "",
    direct_stays: str = "",
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "stay_month": stay_month,
        "month_relative_index": "",
        "month_window_position": position,
        "data_availability": data,
        "days_in_scope": days_in_scope,
        "days_in_month": "",
        "month_scope_status": scope,
        "booked_nights": booked_nights,
        "available_nights": "",
        "unavailable_nights": "",
        "booked_revenue_proxy": booked_revenue,
        "open_revenue_ask": open_ask,
        "total_future_revenue_proxy": total_calendar_value,
        "monthly_target": "10000" if data not in {"no_source_data", "data_not_available", "historical_actuals", "monthly_trends_actuals"} else "",
        "booked_gap_to_target": "",
        "total_gap_to_target": "",
        "booked_cleanings_proxy": cleanings,
        "avg_stay_length_proxy": "",
        "revenue_per_cleaning_proxy": revenue_per_cleaning,
        "booked_revenue_pct_of_target": "",
        "total_future_revenue_pct_of_target": "",
        "month_time_bucket": bucket,
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": cleaning_status,
        "month_action_level": action_level,
        "historical_bookable_nights": "",
        "historical_booked_nights": historical_booked_nights,
        "historical_booked_nights_source": historical_booked_nights_source,
        "historical_cleanings_proxy": historical_cleanings_proxy,
        "historical_cleanings_source": historical_cleanings_source,
        "historical_paid_occupancy_pct": "",
        "historical_occupancy_pct": "",
        "historical_calendar_occupancy_pct": historical_calendar_occupancy_pct,
        "historical_rental_adr": historical_rental_adr,
        "historical_rental_revpar": "",
        "historical_total_revenue": historical_total_revenue,
        "historical_source": "pricelabs_monthly_trends" if data == "monthly_trends_actuals" else "pricelabs_kpis_on_the_books" if data == "historical_actuals" else "",
        "historical_data_quality_flag": "",
        "monthly_trends_revenue": monthly_trends_revenue,
        "monthly_trends_occupancy_pct": monthly_trends_occupancy_pct,
        "monthly_trends_booked_occupancy_pct": monthly_trends_occupancy_pct,
        "monthly_trends_blocked_occupancy_pct": "",
        "monthly_trends_adr": monthly_trends_adr,
        "monthly_trends_source": "pricelabs_monthly_trends" if monthly_trends_revenue else "",
        "bookings_report_bookings": "",
        "bookings_report_cleanings_proxy": cleanings,
        "bookings_report_booked_nights": "",
        "bookings_report_avg_los": "",
        "bookings_report_rental_revenue": "",
        "bookings_report_total_revenue": "",
        "bookings_report_adr": "",
        "bookings_report_avg_booking_window": "",
        "airbnb_stays": airbnb_stays,
        "vrbo_stays": vrbo_stays,
        "direct_stays": direct_stays,
        "other_unknown_stays": "",
        "main_booking_source": "airbnb" if airbnb_stays else "vrbo" if vrbo_stays else "direct" if direct_stays else "",
        "booking_source_mix_summary": ", ".join(
            part
            for part in (
                f"Airbnb {airbnb_stays}" if airbnb_stays else "",
                f"Vrbo {vrbo_stays}" if vrbo_stays else "",
                f"Direct {direct_stays}" if direct_stays else "",
            )
            if part
        ),
    }


def sample_rows() -> list[dict[str, str]]:
    return [
        rolling_row("2025-11", "historical", "no_source_data"),
        rolling_row(
            "2026-03",
            "historical",
            "monthly_trends_actuals",
            revenue_status="historical_actuals",
            historical_booked_nights="23",
            historical_booked_nights_source="estimated_from_monthly_trends",
            historical_cleanings_proxy="11",
            historical_cleanings_source="estimated_from_monthly_trends",
            historical_calendar_occupancy_pct="74.2",
            historical_total_revenue="8887.86",
            historical_rental_adr="351.26",
            revenue_per_cleaning="807.99",
        ),
        rolling_row(
            "2026-05",
            "current",
            "monthly_trends_current",
            "current_month",
            "partial_month",
            "2834",
            "7425",
            "10259",
            "7",
            "6",
            "24",
            "472.33",
            "conversion_risk",
            "inefficient",
            "advisory",
            monthly_trends_revenue="2834",
            monthly_trends_occupancy_pct="55",
            monthly_trends_adr="425",
            airbnb_stays="5",
            vrbo_stays="1",
        ),
        rolling_row(
            "2026-06",
            "future",
            "future_calendar",
            "next_month",
            "full_month",
            "314",
            "14090",
            "14404",
            "1",
            "1",
            "30",
            "314",
            "conversion_risk",
            "inefficient",
            "advisory",
        ),
        rolling_row(
            "2026-07",
            "future",
            "future_calendar",
            "future_month",
            "full_month",
            "0",
            "22614",
            "22614",
            "0",
            "",
            "31",
            "",
            "protect_open_value",
            "no_booked_cleanings",
            "protect",
        ),
        rolling_row(
            "2026-11",
            "future",
            "partial_horizon",
            "far_future_month",
            "partial_month",
            "0",
            "988",
            "988",
            "0",
            "",
            "3",
            "",
            "partial_horizon",
            "no_booked_cleanings",
            "monitor",
        ),
    ]


def test_email_revenue_report_content() -> None:
    markdown = build_markdown("2026-05-08", sample_rows())

    assert "Subject: Aloha Poconos Weekly Revenue Snapshot — 2026-05-08" in markdown
    assert "## Executive Snapshot" in markdown
    assert "## What Needs Attention" in markdown
    assert "## What To Protect" in markdown
    assert "## Recommendation Review" in markdown
    assert "## Booking Source Notes" in markdown
    assert "## Data Notes" in markdown
    assert "Current month 2026-05 is conversion_risk." in markdown
    assert "Next month 2026-06 is conversion_risk." in markdown
    assert "Protected future months: 2026-07." in markdown
    assert "Historical actuals available: 2026-03." in markdown
    assert "| 2025-11 |" not in markdown
    assert "Cleanings / Stays" in markdown
    assert "| 2026-03 | monthly_trends_actuals | $8,888 | - | $8,888 | 23 | 11 | 74.2% | $351 | $808 | historical_actuals | monitor |" in markdown
    assert "| 2026-05 | monthly_trends_current | $2,834 | $7,425 | $10,259 | 7 | 6 | 55.0% | $425 | $472 | conversion_risk | advisory |" in markdown
    assert "- 2026-05: Airbnb 5, Vrbo 1. Main source: airbnb." in markdown
    assert "| 2026-06 | future_calendar | $314 | $14,090 | $14,404 | 1 | 1 | 3.3% | $314 | $314 | conversion_risk | advisory |" in markdown
    assert "| 2026-07 | future_calendar | $0 | $22,614 | $22,614 | 0 | - | 0.0% | - | - | protect_open_value | protect |" in markdown
    assert "| 2026-11 | partial_horizon | $0 | $988 | $988 | 0 | - | - | - | - | partial_horizon | monitor |" in markdown
    assert "Partial horizon monitor note: 2026-11 is inside the export horizon only partially." in markdown
    assert "Historical occupancy is calculated from booked nights divided by calendar days." in markdown
    assert "Future full-month occupancy is calculated from booked nights divided by days in scope." in markdown
    assert "Current and partial horizon month occupancy is hidden unless Monthly Trends provides monthly occupancy." in markdown
    assert "Revenue Captured uses Monthly Trends when available" in markdown
    assert "Cleaning and length-of-stay metrics use Bookings Report when available." in markdown
    assert "Historical booked nights are estimated from Monthly Trends revenue divided by ADR." in markdown
    assert "Historical cleanings are estimated from Monthly Trends booked-night estimates and observed current/future Bookings Report LOS." in markdown
    assert "Bookings Report is not treated as exact historical truth unless a future enhancement validates coverage." in markdown
    assert "Revenue / Cleaning is calculated using Cleanings / Stays, not Booked Nights." in markdown
    assert "data_not_available" in markdown
    assert "Airbnb revenue is not mixed into this report." in markdown
    assert "Historical actuals come from PriceLabs KPI On The Books." not in markdown

    prohibited = (
        "lower prices",
        "match the 75th percentile",
        "discount all open dates",
        "manually override",
        "change base price to",
    )
    for phrase in prohibited:
        assert phrase not in markdown.lower()


def test_email_revenue_report_cli_writes_file(tmp_path, monkeypatch) -> None:
    rolling_file = tmp_path / "rolling_13_month_revenue_view_2026-05-08.csv"
    summary_file = tmp_path / "monthly_revenue_summary_2026-05-08.md"
    output_file = tmp_path / "email_revenue_report_2026-05-08.md"

    with rolling_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=sample_rows()[0].keys())
        writer.writeheader()
        writer.writerows(sample_rows())
    summary_file.write_text("# Monthly Revenue Summary - 2026-05-08\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_revenue_report",
            "--run-date",
            "2026-05-08",
            "--rolling-file",
            str(rolling_file),
            "--summary-file",
            str(summary_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0
    assert output_file.exists()
    assert "Aloha Poconos Weekly Revenue Snapshot" in output_file.read_text(encoding="utf-8")
