import csv
import sys

from pricelabs.transform.monthly_revenue_summary import build_markdown, run


def monthly_row(
    stay_month: str,
    position: str,
    data: str,
    bucket: str = "",
    scope: str = "",
    booked_revenue: str = "",
    open_ask: str = "",
    total_future_value: str = "",
    booked_nights: str = "",
    cleanings: str = "",
    days_in_scope: str = "",
    revenue_per_cleaning: str = "",
    booked_pct: str = "",
    total_pct: str = "",
    revenue_status: str = "no_source_data",
    cleaning_status: str = "",
    action_level: str = "monitor",
    historical_booked_nights: str = "",
    historical_occupancy_pct: str = "",
    historical_calendar_occupancy_pct: str = "",
    historical_total_revenue: str = "",
    historical_rental_adr: str = "",
    historical_data_quality_flag: str = "",
    historical_cleanings_proxy: str = "",
    historical_booked_nights_source: str = "",
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
        "month_window_position": position,
        "data_availability": data,
        "days_in_scope": days_in_scope,
        "month_time_bucket": bucket,
        "month_scope_status": scope,
        "booked_nights": booked_nights,
        "booked_revenue_proxy": booked_revenue,
        "open_revenue_ask": open_ask,
        "total_future_revenue_proxy": total_future_value,
        "monthly_target": "10000" if data not in {"no_source_data", "data_not_available", "historical_actuals", "monthly_trends_actuals"} else "",
        "booked_revenue_pct_of_target": booked_pct,
        "total_future_revenue_pct_of_target": total_pct,
        "revenue_per_cleaning_proxy": revenue_per_cleaning,
        "booked_cleanings_proxy": cleanings,
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": cleaning_status,
        "month_action_level": action_level,
        "historical_bookable_nights": "",
        "historical_booked_nights": historical_booked_nights,
        "historical_booked_nights_source": historical_booked_nights_source,
        "historical_cleanings_proxy": historical_cleanings_proxy,
        "historical_cleanings_source": historical_cleanings_source,
        "historical_paid_occupancy_pct": "",
        "historical_occupancy_pct": historical_occupancy_pct,
        "historical_calendar_occupancy_pct": historical_calendar_occupancy_pct,
        "historical_rental_adr": historical_rental_adr,
        "historical_rental_revpar": "",
        "historical_total_revenue": historical_total_revenue,
        "historical_source": "pricelabs_monthly_trends" if data == "monthly_trends_actuals" else "pricelabs_kpis_on_the_books" if data == "historical_actuals" else "",
        "historical_data_quality_flag": historical_data_quality_flag,
        "monthly_trends_revenue": monthly_trends_revenue,
        "monthly_trends_occupancy_pct": monthly_trends_occupancy_pct,
        "monthly_trends_booked_occupancy_pct": monthly_trends_occupancy_pct,
        "monthly_trends_blocked_occupancy_pct": "",
        "monthly_trends_adr": monthly_trends_adr,
        "monthly_trends_source": "pricelabs_monthly_trends" if monthly_trends_revenue else "",
        "bookings_report_bookings": cleanings,
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
    rows = [
        monthly_row(month, "historical", "data_not_available", bucket="historical_month", revenue_status="data_not_available", cleaning_status="data_not_available")
        for month in ("2025-11", "2025-12")
    ]
    rows.extend(
        [
            monthly_row(
                "2026-01",
                "historical",
                "data_not_available",
                "historical_month",
                revenue_status="data_not_available",
                cleaning_status="data_not_available",
                historical_data_quality_flag="data_not_available",
            ),
            monthly_row(
                "2026-02",
                "historical",
                "monthly_trends_actuals",
                revenue_status="historical_actuals",
                historical_booked_nights="19",
                historical_booked_nights_source="estimated_from_monthly_trends",
                historical_cleanings_proxy="10",
                historical_cleanings_source="estimated_from_monthly_trends",
                historical_occupancy_pct="38",
                historical_calendar_occupancy_pct="67.9",
                historical_total_revenue="9511.34",
                historical_rental_adr="455.32",
                revenue_per_cleaning="951.13",
                historical_data_quality_flag="suspicious",
            ),
            monthly_row(
                "2026-03",
                "historical",
                "monthly_trends_actuals",
                revenue_status="historical_actuals",
                historical_booked_nights="23",
                historical_booked_nights_source="estimated_from_monthly_trends",
                historical_cleanings_proxy="11",
                historical_cleanings_source="estimated_from_monthly_trends",
                historical_occupancy_pct="74.19",
                historical_calendar_occupancy_pct="74.2",
                historical_total_revenue="8887.86",
                historical_rental_adr="351.26",
                revenue_per_cleaning="807.99",
                historical_data_quality_flag="ok",
            ),
            monthly_row(
                "2026-04",
                "historical",
                "monthly_trends_actuals",
                revenue_status="historical_actuals",
                historical_booked_nights="16",
                historical_booked_nights_source="estimated_from_monthly_trends",
                historical_cleanings_proxy="9",
                historical_cleanings_source="estimated_from_monthly_trends",
                historical_occupancy_pct="55.17",
                historical_calendar_occupancy_pct="53.3",
                historical_total_revenue="6609.76",
                historical_rental_adr="369.63",
                revenue_per_cleaning="944.25",
                historical_data_quality_flag="ok",
            ),
        ]
    )
    rows.extend(
        [
            monthly_row(
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
                "0.2834",
                "1.0259",
                "conversion_risk",
                "inefficient",
                "advisory",
                monthly_trends_revenue="2834",
                monthly_trends_occupancy_pct="55",
                monthly_trends_adr="425",
                airbnb_stays="5",
                vrbo_stays="1",
            ),
            monthly_row(
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
                "0.0314",
                "1.4404",
                "conversion_risk",
                "inefficient",
                "advisory",
            ),
            monthly_row(
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
                "0",
                "2.2614",
                "protect_open_value",
                "no_booked_cleanings",
                "protect",
            ),
            monthly_row(
                "2026-08",
                "future",
                "future_calendar",
                "future_month",
                "full_month",
                "0",
                "23669",
                "23669",
                "0",
                "",
                "31",
                "",
                "0",
                "2.3669",
                "protect_open_value",
                "no_booked_cleanings",
                "protect",
            ),
            monthly_row(
                "2026-09",
                "future",
                "future_calendar",
                "far_future_month",
                "full_month",
                "0",
                "14672",
                "14672",
                "0",
                "",
                "30",
                "",
                "0",
                "1.4672",
                "protect_open_value",
                "no_booked_cleanings",
                "protect",
            ),
            monthly_row(
                "2026-10",
                "future",
                "future_calendar",
                "far_future_month",
                "full_month",
                "0",
                "12647",
                "12647",
                "0",
                "",
                "31",
                "",
                "0",
                "1.2647",
                "protect_open_value",
                "no_booked_cleanings",
                "protect",
            ),
            monthly_row(
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
                "0",
                "0.0988",
                "partial_horizon",
                "no_booked_cleanings",
                "monitor",
            ),
        ]
    )
    return rows


def test_monthly_revenue_summary_markdown_content() -> None:
    markdown = build_markdown("2026-05-08", sample_rows())

    assert "# Monthly Revenue Summary - 2026-05-08" in markdown
    for month in (
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
        "2026-10",
        "2026-11",
    ):
        assert f"| {month} |" in markdown

    assert "Revenue Captured" in markdown
    assert "Total Calendar Value" in markdown
    assert "Booked Revenue" not in markdown
    assert "Total Future Value" not in markdown
    assert "Revenue / Cleaning" in markdown
    assert "Cleanings / Stays" in markdown
    assert "Captured % of Target" in markdown
    assert "Calendar Value % of Target" in markdown
    assert "Booked %" not in markdown
    assert "Total %" not in markdown
    assert "| Month | Position | Bucket | Data |" in markdown
    assert "| Month | Position | Bucket | Scope |" not in markdown
    assert "| 2025-11 | historical | historical_month | data_not_available | - | - | - | - | - | - | - | - | - | - | - | data_not_available | data_not_available | monitor |" in markdown
    assert "| 2026-02 | historical |  | monthly_trends_actuals | $9,511 | - | $9,511 | - | - | - | 19 | 10 | 67.9% | $455 | $951 | historical_actuals |" in markdown
    assert "| 2026-02 | historical |  | monthly_trends_actuals | $9,511 | - | $9,511 | - | - | - | 19 | 38.0% |" not in markdown
    assert "| 2026-03 | historical |  | monthly_trends_actuals | $8,888 | - | $8,888 | - | - | - | 23 | 11 | 74.2% | $351 | $808 | historical_actuals |" in markdown
    assert "| 2026-05 | current | current_month | monthly_trends_current | $2,834 | $7,425 | $10,259 | $10,000 | 28.3% | 102.6% | 7 | 6 | 55.0% | $425 | $472 | conversion_risk |" in markdown
    assert "| 2026-06 | future | next_month | future_calendar | $314 | $14,090 | $14,404 | $10,000 | 3.1% | 144.0% | 1 | 1 | 3.3% | $314 | $314 | conversion_risk |" in markdown
    assert "| 2026-07 | future | future_month | future_calendar | $0 | $22,614 | $22,614 | $10,000 | 0.0% | 226.1% | 0 | - | 0.0% | - | - | protect_open_value |" in markdown
    assert "| 2026-11 | future | far_future_month | partial_horizon | $0 | $988 | $988 | $10,000 | 0.0% | 9.9% | 0 | - | - | - | - | partial_horizon |" in markdown
    assert "| 2026-05 | current | current_month | monthly_trends_current |" in markdown
    assert "Current month 2026-05 revenue pace is conversion_risk." in markdown
    assert "Next month 2026-06 revenue pace is conversion_risk." in markdown
    assert "Far-out open value is protected in 2026-07, 2026-08, 2026-09, 2026-10." in markdown
    assert (
        "Historical actuals are available for 2026-02, 2026-03, 2026-04; "
        "missing historical months remain data_not_available."
    ) in markdown
    assert "- Market benchmark is context only." in markdown
    assert "2026-11 revenue pace" not in markdown
    assert "## Executive Decision View" in markdown
    assert "### Advisory" in markdown
    assert "- 2026-05: conversion_risk - booked $2,834, total calendar value $10,259, cleaning inefficient." in markdown
    assert "- 2026-06: conversion_risk - booked $314, total calendar value $14,404, cleaning inefficient." in markdown
    assert "### Protect" in markdown
    assert "- 2026-07: protect_open_value - total calendar value $22,614." in markdown
    assert "- 2026-10: protect_open_value - total calendar value $12,647." in markdown
    assert "- 2025-11:" not in markdown
    assert "- 2026-11: partial_horizon" not in markdown
    assert "## Interpretation" in markdown
    assert (
        "- 2026-05: Booked revenue is low, but total calendar value is above target. "
        "This points to conversion risk rather than weak calendar value."
    ) in markdown
    assert (
        "- 2026-03: Historical actuals are available from PriceLabs monthly data: "
        "total revenue $8,888, booked nights 23, ADR $351."
    ) in markdown
    assert (
        "Data quality flag: suspicious; review PriceLabs historical denominator "
        "before using occupancy as final truth."
    ) in markdown
    assert (
        "- 2026-07: Open calendar value is healthy for a future month. "
        "This supports protecting premium positioning."
    ) in markdown
    assert (
        "- 2026-05: Revenue per cleaning is below the current efficiency threshold, "
        "so booking quality should be monitored."
    ) in markdown
    assert (
        "- 2026-11: Only part of the month is inside the current export horizon, "
        "so it is not judged against the full monthly target."
    ) in markdown
    assert "## Recommendation Review" in markdown
    assert "### Critical Now" in markdown
    assert "### Advisory" in markdown
    assert "### Protect / No Change" in markdown
    assert "### Monitor" in markdown
    assert "- None." in markdown
    assert (
        "- 2026-05: Review near-term conversion behavior and booking quality before changing premium positioning. "
        "Rule areas to review: Booking Recency Factor; last-minute behavior; 1-night LOS premium. "
        "Avoid broad pricing pressure."
    ) in markdown
    assert (
        "- 2026-06: Monitor next-month conversion risk while protecting premium positioning. "
        "Rule areas to review: Booking Recency Factor; minimum stay rules; 1-night LOS premium. "
        "Avoid early pricing pressure."
    ) in markdown
    assert "- 2026-07: Protect far-out open value; no PriceLabs rule change recommended now." in markdown
    assert "- 2026-11: Monitor only; do not judge this partial horizon month against the full monthly target." in markdown
    assert "## Booking Source Mix" in markdown
    assert "| 2026-05 | 5 | 1 | 0 | 0 | airbnb |" in markdown
    assert "2026-03: Monitor" not in markdown
    assert "2026-03: Review" not in markdown
    assert "2025-11: Booked revenue" not in markdown
    assert "2025-11: Monitor" not in markdown
    assert "$2,834" in markdown
    assert "$22,614" in markdown
    assert "28.3%" in markdown
    assert "226.1%" in markdown
    assert "ADR per cleaning" not in markdown
    assert "`monthly_trends_actuals` means the month was filled from PriceLabs Monthly Trends data." in markdown
    assert "`historical_actuals` means the month was filled from optional legacy KPI data." in markdown
    assert "Historical actuals come from PriceLabs KPI On The Books." not in markdown
    assert "`suspicious` means the historical KPI row passed through but has a data-quality warning" in markdown
    assert "Historical occupancy is calculated from booked nights divided by calendar days in month" in markdown
    assert "Future full-month occupancy is calculated from booked nights divided by days in scope." in markdown
    assert "Current and partial horizon month occupancy is hidden unless Monthly Trends provides monthly occupancy." in markdown
    assert "Revenue Captured uses Monthly Trends when available" in markdown
    assert "Cleaning and length-of-stay metrics use Bookings Report when available." in markdown
    assert "Historical booked nights are estimated from Monthly Trends revenue divided by ADR." in markdown
    assert "Historical cleanings are estimated from Monthly Trends booked-night estimates and observed current/future Bookings Report LOS." in markdown
    assert "Bookings Report is not treated as exact historical truth unless a future enhancement validates coverage." in markdown
    assert "Months with missing or suspicious monthly data are marked `data_not_available`" in markdown
    assert "lower prices" not in markdown.lower()
    assert "match the 75th percentile" not in markdown.lower()
    assert "discount all open dates" not in markdown.lower()
    assert "blanket discounting" not in markdown.lower()
    assert "aggressive early discounting" not in markdown.lower()
    assert "manually override" not in markdown.lower()
    assert "change base price" not in markdown.lower()
    assert "change min price" not in markdown.lower()
    assert "change los" not in markdown.lower()
    assert "change discounts" not in markdown.lower()


def test_monthly_revenue_summary_cli_writes_file(tmp_path, monkeypatch) -> None:
    rolling_file = tmp_path / "rolling_13_month_revenue_view_2026-05-08.csv"
    output_file = tmp_path / "monthly_revenue_summary_2026-05-08.md"

    with rolling_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=sample_rows()[0].keys())
        writer.writeheader()
        writer.writerows(sample_rows())

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "monthly_revenue_summary",
            "--run-date",
            "2026-05-08",
            "--rolling-file",
            str(rolling_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0
    assert output_file.exists()

    markdown = output_file.read_text(encoding="utf-8")
    assert "# Monthly Revenue Summary - 2026-05-08" in markdown
    assert "conversion_risk" in markdown
