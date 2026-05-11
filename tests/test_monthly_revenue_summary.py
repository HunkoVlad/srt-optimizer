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
        "monthly_target": "10000" if data == "available" else "",
        "booked_revenue_pct_of_target": booked_pct,
        "total_future_revenue_pct_of_target": total_pct,
        "revenue_per_cleaning_proxy": revenue_per_cleaning,
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": cleaning_status,
        "month_action_level": action_level,
        "historical_bookable_nights": "",
        "historical_booked_nights": historical_booked_nights,
        "historical_paid_occupancy_pct": "",
        "historical_occupancy_pct": historical_occupancy_pct,
        "historical_calendar_occupancy_pct": historical_calendar_occupancy_pct,
        "historical_rental_adr": historical_rental_adr,
        "historical_rental_revpar": "",
        "historical_total_revenue": historical_total_revenue,
        "historical_source": "pricelabs_kpis_on_the_books" if data == "historical_actuals" else "",
        "historical_data_quality_flag": historical_data_quality_flag,
    }


def sample_rows() -> list[dict[str, str]]:
    rows = [
        monthly_row(month, "historical", "no_source_data")
        for month in ("2025-11", "2025-12")
    ]
    rows.extend(
        [
            monthly_row(
                "2026-01",
                "historical",
                "historical_actuals",
                revenue_status="historical_actuals",
                historical_booked_nights="0",
                historical_occupancy_pct="0",
                historical_calendar_occupancy_pct="0",
                historical_total_revenue="0",
                historical_rental_adr="0",
                historical_data_quality_flag="suspicious",
            ),
            monthly_row(
                "2026-02",
                "historical",
                "historical_actuals",
                revenue_status="historical_actuals",
                historical_booked_nights="19",
                historical_occupancy_pct="38",
                historical_calendar_occupancy_pct="67.9",
                historical_total_revenue="9511.34",
                historical_rental_adr="455.32",
                historical_data_quality_flag="suspicious",
            ),
            monthly_row(
                "2026-03",
                "historical",
                "historical_actuals",
                revenue_status="historical_actuals",
                historical_booked_nights="23",
                historical_occupancy_pct="74.19",
                historical_calendar_occupancy_pct="74.2",
                historical_total_revenue="8887.86",
                historical_rental_adr="351.26",
                historical_data_quality_flag="ok",
            ),
            monthly_row(
                "2026-04",
                "historical",
                "historical_actuals",
                revenue_status="historical_actuals",
                historical_booked_nights="16",
                historical_occupancy_pct="55.17",
                historical_calendar_occupancy_pct="53.3",
                historical_total_revenue="6609.76",
                historical_rental_adr="369.63",
                historical_data_quality_flag="ok",
            ),
        ]
    )
    rows.extend(
        [
            monthly_row(
                "2026-05",
                "current",
                "available",
                "current_month",
                "partial_month",
                "2834",
                "7425",
                "10259",
                "7",
                "24",
                "472.33",
                "0.2834",
                "1.0259",
                "conversion_risk",
                "inefficient",
                "advisory",
            ),
            monthly_row(
                "2026-06",
                "future",
                "available",
                "next_month",
                "full_month",
                "314",
                "14090",
                "14404",
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
                "available",
                "future_month",
                "full_month",
                "0",
                "22614",
                "22614",
                "0",
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
                "available",
                "future_month",
                "full_month",
                "0",
                "23669",
                "23669",
                "0",
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
                "available",
                "far_future_month",
                "full_month",
                "0",
                "14672",
                "14672",
                "0",
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
                "available",
                "far_future_month",
                "full_month",
                "0",
                "12647",
                "12647",
                "0",
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
                "available",
                "far_future_month",
                "partial_month",
                "0",
                "988",
                "988",
                "0",
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
    assert "| 2025-11 | historical |  |  | no_source_data | - |" in markdown
    assert "| 2026-02 | historical |  |  | historical_actuals | $9,511 | - | $9,511 | - | - | - | 19 | 67.9% | $455 | - | historical_actuals |" in markdown
    assert "| 2026-02 | historical |  |  | historical_actuals | $9,511 | - | $9,511 | - | - | - | 19 | 38.0% |" not in markdown
    assert "| 2026-03 | historical |  |  | historical_actuals | $8,888 | - | $8,888 | - | - | - | 23 | 74.2% | $351 | - | historical_actuals |" in markdown
    assert "| 2026-05 | current | current_month | partial_month | available | $2,834 | $7,425 | $10,259 | $10,000 | 28.3% | 102.6% | 7 | - | $405 | $472 | conversion_risk |" in markdown
    assert "| 2026-06 | future | next_month | full_month | available | $314 | $14,090 | $14,404 | $10,000 | 3.1% | 144.0% | 1 | 3.3% | $314 | $314 | conversion_risk |" in markdown
    assert "| 2026-07 | future | future_month | full_month | available | $0 | $22,614 | $22,614 | $10,000 | 0.0% | 226.1% | 0 | 0.0% | - | - | protect_open_value |" in markdown
    assert "| 2026-11 | future | far_future_month | partial_month | available | $0 | $988 | $988 | $10,000 | 0.0% | 9.9% | 0 | - | - | - | partial_horizon |" in markdown
    assert "| 2026-05 | current | current_month | partial_month | available |" in markdown
    assert "Current month 2026-05 revenue pace is conversion_risk." in markdown
    assert "Next month 2026-06 revenue pace is conversion_risk." in markdown
    assert "Far-out open value is protected in 2026-07, 2026-08, 2026-09, 2026-10." in markdown
    assert (
        "Historical actuals are available for 2026-01, 2026-02, 2026-03, 2026-04; "
        "missing historical months remain no_source_data."
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
        "- 2026-03: Historical actuals are available from PriceLabs KPI data: "
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
    assert "2026-03: Monitor" not in markdown
    assert "2026-03: Review" not in markdown
    assert "2025-11: Booked revenue" not in markdown
    assert "2025-11: Monitor" not in markdown
    assert "$2,834" in markdown
    assert "$22,614" in markdown
    assert "28.3%" in markdown
    assert "226.1%" in markdown
    assert "ADR per cleaning" not in markdown
    assert "`historical_actuals` means the month was filled from PriceLabs KPI On The Books historical data." in markdown
    assert "`suspicious` means the historical KPI row passed through but has a data-quality warning" in markdown
    assert "Historical occupancy is calculated from booked nights divided by calendar days in month" in markdown
    assert "Future full-month occupancy is calculated from booked nights divided by days in scope." in markdown
    assert "Current and partial horizon month occupancy is hidden to avoid misleading partial-month interpretation." in markdown
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
