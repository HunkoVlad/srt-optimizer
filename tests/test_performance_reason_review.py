import csv
from pathlib import Path

from pricelabs.transform import performance_reason_review
from pricelabs.transform.email_revenue_report import reason_review_section
from pricelabs.transform.monthly_revenue_summary import build_reason_review


def window_summary(market_occupancy: str = "35", window_name: str = "days_0_15") -> dict[str, str]:
    return {
        "run_date": "2026-05-14",
        "listing_id": "650255___717243",
        "window_name": window_name,
        "market_occupancy_avg": market_occupancy,
    }


def window_signal(
    pace_status: str = "behind_market",
    price_position_status: str = "near_75th",
    window_name: str = "days_0_15",
) -> dict[str, str]:
    return {
        "run_date": "2026-05-14",
        "listing_id": "650255___717243",
        "window_name": window_name,
        "pace_status": pace_status,
        "price_position_status": price_position_status,
    }


def settings_change(field_name: str) -> dict[str, str]:
    return {
        "run_date": "2026-05-14",
        "prior_run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "field_name": field_name,
        "previous_value": "old",
        "current_value": "new",
        "changed_flag": "true",
    }


def monthly_row(status: str = "conversion_risk") -> dict[str, str]:
    return {
        "run_date": "2026-05-14",
        "listing_id": "650255___717243",
        "stay_month": "2026-05",
        "month_window_position": "current",
        "data_availability": "monthly_trends_current",
        "revenue_pace_status": status,
        "cleaning_efficiency_status": "ok",
        "month_action_level": "advisory",
    }


def first_window(rows: list[dict[str, str]]) -> dict[str, str]:
    return next(row for row in rows if row["scope_type"] == "window")


def test_market_weak_plus_weak_revenue_blocks_pricelabs_recommendation() -> None:
    rows = performance_reason_review.build_reason_rows(
        run_date="2026-05-14",
        monthly_rows=[],
        window_summaries=[window_summary("30")],
        window_signals=[window_signal("behind_market")],
        settings_changes=[],
    )

    row = first_window(rows)
    assert row["likely_reason"] == "market_weakness"
    assert row["recommendation_allowed"] == "false"
    assert row["recommendation_type"] == "monitor"


def test_market_normal_and_our_pace_weak_classifies_conversion_or_price_issue() -> None:
    rows = performance_reason_review.build_reason_rows(
        run_date="2026-05-14",
        monthly_rows=[],
        window_summaries=[window_summary("55")],
        window_signals=[window_signal("behind_market", "above_75th")],
        settings_changes=[],
    )

    row = first_window(rows)
    assert row["likely_reason"] == "price_or_rule_issue"
    assert row["recommendation_allowed"] == "true"
    assert row["recommendation_type"] == "consider_pricelabs_rule_change"


def test_recent_setting_change_and_weakened_performance_classifies_settings_impact() -> None:
    rows = performance_reason_review.build_reason_rows(
        run_date="2026-05-14",
        monthly_rows=[],
        window_summaries=[window_summary("55")],
        window_signals=[window_signal("behind_market", "near_75th")],
        settings_changes=[settings_change("far_out_premium")],
    )

    row = first_window(rows)
    assert row["likely_reason"] == "settings_change_impact"
    assert row["relevant_setting_change"] == "far_out_premium"
    assert row["performance_after_change"] == "weakened"


def test_insufficient_prior_market_data_blocks_recommendation() -> None:
    rows = performance_reason_review.build_reason_rows(
        run_date="2026-05-14",
        monthly_rows=[monthly_row()],
        window_summaries=[],
        window_signals=[window_signal("behind_market")],
        settings_changes=[],
    )

    row = first_window(rows)
    assert row["likely_reason"] == "insufficient_data"
    assert row["recommendation_allowed"] == "false"


def test_oba_only_change_does_not_automatically_trigger_rule_recommendation() -> None:
    rows = performance_reason_review.build_reason_rows(
        run_date="2026-05-14",
        monthly_rows=[],
        window_summaries=[window_summary("55")],
        window_signals=[window_signal("behind_market", "near_75th")],
        settings_changes=[settings_change("occupancy_based_adjustments_snapshot")],
    )

    row = first_window(rows)
    assert row["relevant_setting_change"] == "occupancy_based_adjustments_snapshot"
    assert row["likely_reason"] == "listing_or_conversion_issue"
    assert row["recommendation_type"] == "investigate_listing"


def test_cli_writes_performance_reason_review_csv(tmp_path: Path, monkeypatch) -> None:
    monthly_file = tmp_path / "monthly.csv"
    summary_file = tmp_path / "summary.csv"
    signals_file = tmp_path / "signals.csv"
    settings_file = tmp_path / "settings_changes.csv"
    output_file = tmp_path / "performance_reason_review_2026-05-14.csv"

    write_csv(monthly_file, [monthly_row()])
    write_csv(summary_file, [window_summary("55")])
    write_csv(signals_file, [window_signal("behind_market", "above_75th")])
    write_csv(settings_file, [])

    monkeypatch.setattr(
        "sys.argv",
        [
            "performance_reason_review",
            "--run-date",
            "2026-05-14",
            "--monthly-file",
            str(monthly_file),
            "--window-summary-file",
            str(summary_file),
            "--window-signals-file",
            str(signals_file),
            "--settings-changes-file",
            str(settings_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert performance_reason_review.run() == 0
    rows = list(csv.DictReader(output_file.open("r", encoding="utf-8")))
    assert rows
    assert rows[0]["likely_reason"] in {"price_or_rule_issue", "listing_or_conversion_issue"}


def test_reports_include_reason_review_section() -> None:
    reason_rows = [
        {
            "scope_type": "window",
            "scope_name": "days_0_15",
            "observed_issue": "weak_pickup",
            "market_context": "market_normal",
            "likely_reason": "price_or_rule_issue",
            "recommendation_allowed": "true",
            "recommendation_type": "consider_pricelabs_rule_change",
            "explanation_note": "Reason classified before recommendation.",
        }
    ]

    monthly_lines = build_reason_review(reason_rows)
    email_lines = reason_review_section(reason_rows)

    assert "## Reason Review" in monthly_lines
    assert "## Reason Review" in email_lines
    assert any("PriceLabs rule change justified now" in line for line in monthly_lines)
    assert any("PriceLabs rule change justified now" in line for line in email_lines)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if rows:
        fieldnames = list(rows[0])
    else:
        fieldnames = ["run_date", "prior_run_date", "listing_id", "field_name", "changed_flag"]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
