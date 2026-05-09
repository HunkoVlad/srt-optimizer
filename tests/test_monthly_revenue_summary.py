import csv
import sys

from pricelabs.transform.monthly_revenue_summary import build_markdown, run


def monthly_row(
    stay_month: str,
    bucket: str,
    scope: str,
    booked_revenue: str,
    open_ask: str,
    total_future_value: str,
    booked_pct: str,
    total_pct: str,
    revenue_status: str,
    cleaning_status: str,
    action_level: str,
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "stay_month": stay_month,
        "month_time_bucket": bucket,
        "month_scope_status": scope,
        "booked_revenue_proxy": booked_revenue,
        "open_revenue_ask": open_ask,
        "total_future_revenue_proxy": total_future_value,
        "monthly_target": "10000",
        "booked_revenue_pct_of_target": booked_pct,
        "total_future_revenue_pct_of_target": total_pct,
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": cleaning_status,
        "month_action_level": action_level,
    }


def sample_rows() -> list[dict[str, str]]:
    return [
        monthly_row(
            "2026-05",
            "current_month",
            "full_month",
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
            "2026-11",
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


def test_monthly_revenue_summary_markdown_content() -> None:
    markdown = build_markdown("2026-05-08", sample_rows())

    assert "# Monthly Revenue Summary - 2026-05-08" in markdown
    assert "| 2026-05 | current_month | full_month |" in markdown
    assert "| 2026-06 | next_month | full_month |" in markdown
    assert "| 2026-07 | future_month | full_month |" in markdown
    assert "| 2026-11 | far_future_month | partial_month |" in markdown
    assert "conversion_risk" in markdown
    assert "protect_open_value" in markdown
    assert "partial_horizon" in markdown
    assert "`partial_horizon` means only part of the month" in markdown
    assert "$2,834" in markdown
    assert "$22,614" in markdown
    assert "28.3%" in markdown
    assert "226.1%" in markdown
    assert "recommend" not in markdown.lower()
    assert "2026-11 revenue pace" not in markdown


def test_monthly_revenue_summary_cli_writes_file(tmp_path, monkeypatch) -> None:
    monthly_file = tmp_path / "monthly_revenue_pace_2026-05-08.csv"
    output_file = tmp_path / "monthly_revenue_summary_2026-05-08.md"

    with monthly_file.open("w", newline="", encoding="utf-8") as csv_file:
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
            "--monthly-file",
            str(monthly_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0
    assert output_file.exists()

    markdown = output_file.read_text(encoding="utf-8")
    assert "# Monthly Revenue Summary - 2026-05-08" in markdown
    assert "conversion_risk" in markdown
