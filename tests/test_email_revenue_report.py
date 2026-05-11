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
    days_in_scope: str = "",
    revenue_per_cleaning: str = "",
    revenue_status: str = "no_source_data",
    cleaning_status: str = "",
    action_level: str = "monitor",
    historical_booked_nights: str = "",
    historical_calendar_occupancy_pct: str = "",
    historical_total_revenue: str = "",
    historical_rental_adr: str = "",
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
        "monthly_target": "10000" if data == "available" else "",
        "booked_gap_to_target": "",
        "total_gap_to_target": "",
        "booked_cleanings_proxy": "",
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
        "historical_paid_occupancy_pct": "",
        "historical_occupancy_pct": "",
        "historical_calendar_occupancy_pct": historical_calendar_occupancy_pct,
        "historical_rental_adr": historical_rental_adr,
        "historical_rental_revpar": "",
        "historical_total_revenue": historical_total_revenue,
        "historical_source": "pricelabs_kpis_on_the_books" if data == "historical_actuals" else "",
        "historical_data_quality_flag": "",
    }


def sample_rows() -> list[dict[str, str]]:
    return [
        rolling_row("2025-11", "historical", "no_source_data"),
        rolling_row(
            "2026-03",
            "historical",
            "historical_actuals",
            revenue_status="historical_actuals",
            historical_booked_nights="23",
            historical_calendar_occupancy_pct="74.2",
            historical_total_revenue="8887.86",
            historical_rental_adr="351.26",
        ),
        rolling_row(
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
            "conversion_risk",
            "inefficient",
            "advisory",
        ),
        rolling_row(
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
            "conversion_risk",
            "inefficient",
            "advisory",
        ),
        rolling_row(
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
            "protect_open_value",
            "no_booked_cleanings",
            "protect",
        ),
        rolling_row(
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
    assert "## Data Notes" in markdown
    assert "Current month 2026-05 is conversion_risk." in markdown
    assert "Next month 2026-06 is conversion_risk." in markdown
    assert "Protected future months: 2026-07." in markdown
    assert "Historical actuals available: 2026-03." in markdown
    assert "| 2025-11 |" not in markdown
    assert "| 2026-03 | historical_actuals | $8,888 | - | $8,888 | 74.2% | $351 | - | historical_actuals | monitor |" in markdown
    assert "| 2026-05 | available | $2,834 | $7,425 | $10,259 | - | $405 | $472 | conversion_risk | advisory |" in markdown
    assert "| 2026-06 | available | $314 | $14,090 | $14,404 | 3.3% | $314 | $314 | conversion_risk | advisory |" in markdown
    assert "| 2026-07 | available | $0 | $22,614 | $22,614 | 0.0% | - | - | protect_open_value | protect |" in markdown
    assert "| 2026-11 | available | $0 | $988 | $988 | - | - | - | partial_horizon | monitor |" in markdown
    assert "Partial horizon monitor note: 2026-11 is inside the export horizon only partially." in markdown
    assert "Historical occupancy is calculated from booked nights divided by calendar days." in markdown
    assert "Future full-month occupancy is calculated from booked nights divided by days in scope." in markdown
    assert "Current and partial horizon month occupancy is hidden to avoid misleading partial-month interpretation." in markdown
    assert "Airbnb revenue is not mixed into this report." in markdown

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
