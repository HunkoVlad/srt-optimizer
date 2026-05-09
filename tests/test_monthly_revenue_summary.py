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
    booked_pct: str = "",
    total_pct: str = "",
    revenue_status: str = "no_source_data",
    cleaning_status: str = "",
    action_level: str = "monitor",
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "stay_month": stay_month,
        "month_window_position": position,
        "data_availability": data,
        "month_time_bucket": bucket,
        "month_scope_status": scope,
        "booked_revenue_proxy": booked_revenue,
        "open_revenue_ask": open_ask,
        "total_future_revenue_proxy": total_future_value,
        "monthly_target": "10000" if data == "available" else "",
        "booked_revenue_pct_of_target": booked_pct,
        "total_future_revenue_pct_of_target": total_pct,
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": cleaning_status,
        "month_action_level": action_level,
    }


def sample_rows() -> list[dict[str, str]]:
    rows = [
        monthly_row(month, "historical", "no_source_data")
        for month in ("2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04")
    ]
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

    assert "| 2025-11 | historical |  |  | no_source_data | - |" in markdown
    assert "| 2026-05 | current | current_month | partial_month | available |" in markdown
    assert "Current month 2026-05 revenue pace is conversion_risk." in markdown
    assert "Next month 2026-06 revenue pace is conversion_risk." in markdown
    assert "Far-out open value is protected in 2026-07, 2026-08, 2026-09, 2026-10." in markdown
    assert "Historical months without source data are shown for context." in markdown
    assert "- Market benchmark is context only." in markdown
    assert "2026-11 revenue pace" not in markdown
    assert "## Executive Decision View" in markdown
    assert "### Advisory" in markdown
    assert "- 2026-05: conversion_risk - booked $2,834, total future value $10,259, cleaning inefficient." in markdown
    assert "- 2026-06: conversion_risk - booked $314, total future value $14,404, cleaning inefficient." in markdown
    assert "### Protect" in markdown
    assert "- 2026-07: protect_open_value - total future value $22,614." in markdown
    assert "- 2026-10: protect_open_value - total future value $12,647." in markdown
    assert "- 2025-11:" not in markdown
    assert "- 2026-11: partial_horizon" not in markdown
    assert "## Interpretation" in markdown
    assert (
        "- 2026-05: Booked revenue is low, but total future value is above target. "
        "This points to conversion risk rather than weak calendar value."
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
    assert "2025-11: Booked revenue" not in markdown
    assert "$2,834" in markdown
    assert "$22,614" in markdown
    assert "28.3%" in markdown
    assert "226.1%" in markdown
    assert "recommend" not in markdown.lower()
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
