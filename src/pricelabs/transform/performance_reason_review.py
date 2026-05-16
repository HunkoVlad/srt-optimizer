"""Causal review layer for settings changes and revenue performance."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys


OUTPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "scope_type",
    "scope_name",
    "observed_issue",
    "relevant_setting_change",
    "last_setting_change_date",
    "setting_change_summary",
    "performance_after_change",
    "market_context",
    "likely_reason",
    "confidence",
    "recommendation_allowed",
    "recommendation_type",
    "explanation_note",
)
OBA_FIELDS = {"occupancy_based_adjustments_snapshot"}
RULE_CHANGE_FIELDS = {
    "far_out_premium",
    "length_of_stay_based_pricing",
    "minimum_stay_settings",
    "booking_recency_factor",
    "last_minute",
    "last_minute_rule",
    "orphan_day_prices",
    "safety_minimum_price",
    "safety_minimum_price_rule",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create performance reason review CSV.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument("--monthly-file", help="Monthly revenue pace CSV.")
    parser.add_argument("--window-summary-file", help="Future window summary CSV.")
    parser.add_argument("--window-signals-file", help="Future window signals CSV.")
    parser.add_argument("--settings-changes-file", help="Settings changes CSV.")
    parser.add_argument("--signal-review-file", help="Optional future signal change review CSV.")
    parser.add_argument("--output-file", help="Reason review output CSV.")
    return parser.parse_args()


def read_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def parse_decimal(value: str) -> Decimal | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped.replace("$", "").replace(",", ""))
    except InvalidOperation:
        return None


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def changed_settings(settings_changes: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in settings_changes if row.get("changed_flag", "").lower() == "true"]


def relevant_setting_change(settings_changes: list[dict[str, str]], scope_name: str) -> dict[str, str] | None:
    changes = changed_settings(settings_changes)
    if not changes:
        return None
    non_oba = [row for row in changes if row.get("field_name", "") not in OBA_FIELDS]
    candidates = non_oba or changes
    for field in RULE_CHANGE_FIELDS:
        for row in candidates:
            if row.get("field_name") == field:
                return row
    return candidates[0]


def setting_summary(row: dict[str, str] | None) -> str:
    if not row:
        return ""
    field = row.get("field_name", "")
    if field in OBA_FIELDS:
        return f"{field} changed; treated as context because OBA may update frequently."
    return f"{field} changed in normalized PriceLabs settings."


def market_context_from_summary(row: dict[str, str] | None) -> str:
    if not row:
        return "insufficient_data"
    market_occupancy = parse_decimal(row.get("market_occupancy_avg", ""))
    if market_occupancy is None:
        return "insufficient_data"
    if market_occupancy < Decimal("40"):
        return "market_weak"
    if market_occupancy >= Decimal("70"):
        return "market_strong"
    return "market_normal"


def observed_issue_from_month(row: dict[str, str]) -> str:
    if row.get("data_availability") in {"no_source_data", "data_not_available"}:
        return "none"
    revenue_status = row.get("revenue_pace_status", "")
    cleaning_status = row.get("cleaning_efficiency_status", "")
    if revenue_status in {"urgent", "conversion_risk", "behind_target"}:
        return "revenue_gap" if revenue_status != "conversion_risk" else "conversion_risk"
    if cleaning_status == "inefficient":
        return "cleanings_efficiency_risk"
    return "none"


def observed_issue_from_signal(row: dict[str, str]) -> str:
    if row.get("pace_status") == "behind_market":
        return "weak_pickup"
    return "none"


def classify_reason(
    *,
    observed_issue: str,
    market_context: str,
    setting_change: dict[str, str] | None,
    price_position_status: str = "",
) -> tuple[str, str, bool, str, str, str]:
    if observed_issue == "none":
        return "no_issue", "high", False, "no_change", "neutral", "No material performance issue was detected."
    if market_context == "insufficient_data":
        return (
            "insufficient_data",
            "low",
            False,
            "insufficient_data",
            "insufficient_data",
            "Market or performance context is incomplete, so no rule change is justified.",
        )
    if market_context == "market_weak":
        return (
            "market_weakness",
            "medium",
            False,
            "monitor",
            "weakened",
            "Market context is weak, so avoid blaming PriceLabs rules without stronger listing evidence.",
        )
    if setting_change and setting_change.get("field_name", "") not in OBA_FIELDS:
        return (
            "settings_change_impact",
            "medium",
            True,
            "consider_pricelabs_rule_change",
            "weakened",
            "Performance weakened after a normalized settings change; review the related PriceLabs rule area.",
        )
    if price_position_status == "above_75th":
        return (
            "price_or_rule_issue",
            "medium",
            True,
            "consider_pricelabs_rule_change",
            "weakened",
            "Listing pace is weak while market context is normal or strong and pricing is above market context.",
        )
    return (
        "listing_or_conversion_issue",
        "medium",
        True,
        "investigate_listing",
        "weakened",
        "Listing pace is weak while market context is not weak; investigate conversion before changing rules.",
    )


def build_window_rows(
    *,
    run_date: str,
    window_summaries: list[dict[str, str]],
    window_signals: list[dict[str, str]],
    settings_changes: list[dict[str, str]],
) -> list[dict[str, str]]:
    summary_by_window = {row.get("window_name", ""): row for row in window_summaries}
    rows: list[dict[str, str]] = []
    for signal in window_signals:
        scope_name = signal.get("window_name", "")
        setting = relevant_setting_change(settings_changes, scope_name)
        observed_issue = observed_issue_from_signal(signal)
        market_context = market_context_from_summary(summary_by_window.get(scope_name))
        likely_reason, confidence, allowed, rec_type, perf_after, note = classify_reason(
            observed_issue=observed_issue,
            market_context=market_context,
            setting_change=setting,
            price_position_status=signal.get("price_position_status", ""),
        )
        rows.append(
            output_row(
                run_date=run_date,
                listing_id=signal.get("listing_id", ""),
                scope_type="window",
                scope_name=scope_name,
                observed_issue=observed_issue,
                setting=setting,
                performance_after_change=perf_after,
                market_context=market_context,
                likely_reason=likely_reason,
                confidence=confidence,
                recommendation_allowed=allowed,
                recommendation_type=rec_type,
                explanation_note=note,
            )
        )
    return rows


def month_market_context(window_rows: list[dict[str, str]]) -> str:
    contexts = [row["market_context"] for row in window_rows if row["market_context"] != "insufficient_data"]
    if not contexts:
        return "insufficient_data"
    if contexts.count("market_weak") >= 2:
        return "market_weak"
    if "market_strong" in contexts:
        return "market_strong"
    return "market_normal"


def build_month_rows(
    *,
    run_date: str,
    monthly_rows: list[dict[str, str]],
    settings_changes: list[dict[str, str]],
    window_reason_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    current_future_rows = [
        row
        for row in monthly_rows
        if row.get("month_window_position") in {"current", "future"}
        and row.get("month_action_level") in {"critical_now", "advisory", "protect", "monitor"}
    ]
    market_context = month_market_context(window_reason_rows)
    rows: list[dict[str, str]] = []
    for month in current_future_rows[:6]:
        setting = relevant_setting_change(settings_changes, month.get("stay_month", ""))
        observed_issue = observed_issue_from_month(month)
        likely_reason, confidence, allowed, rec_type, perf_after, note = classify_reason(
            observed_issue=observed_issue,
            market_context=market_context,
            setting_change=setting,
        )
        rows.append(
            output_row(
                run_date=run_date,
                listing_id=month.get("listing_id", ""),
                scope_type="month",
                scope_name=month.get("stay_month", ""),
                observed_issue=observed_issue,
                setting=setting,
                performance_after_change=perf_after,
                market_context=market_context,
                likely_reason=likely_reason,
                confidence=confidence,
                recommendation_allowed=allowed,
                recommendation_type=rec_type,
                explanation_note=note,
            )
        )
    return rows


def output_row(
    *,
    run_date: str,
    listing_id: str,
    scope_type: str,
    scope_name: str,
    observed_issue: str,
    setting: dict[str, str] | None,
    performance_after_change: str,
    market_context: str,
    likely_reason: str,
    confidence: str,
    recommendation_allowed: bool,
    recommendation_type: str,
    explanation_note: str,
) -> dict[str, str]:
    return {
        "run_date": run_date,
        "listing_id": listing_id,
        "scope_type": scope_type,
        "scope_name": scope_name,
        "observed_issue": observed_issue,
        "relevant_setting_change": setting.get("field_name", "") if setting else "none",
        "last_setting_change_date": setting.get("run_date", "") if setting else "",
        "setting_change_summary": setting_summary(setting),
        "performance_after_change": performance_after_change,
        "market_context": market_context,
        "likely_reason": likely_reason,
        "confidence": confidence,
        "recommendation_allowed": bool_text(recommendation_allowed),
        "recommendation_type": recommendation_type,
        "explanation_note": explanation_note,
    }


def build_reason_rows(
    *,
    run_date: str,
    monthly_rows: list[dict[str, str]],
    window_summaries: list[dict[str, str]],
    window_signals: list[dict[str, str]],
    settings_changes: list[dict[str, str]],
) -> list[dict[str, str]]:
    window_rows = build_window_rows(
        run_date=run_date,
        window_summaries=window_summaries,
        window_signals=window_signals,
        settings_changes=settings_changes,
    )
    month_rows = build_month_rows(
        run_date=run_date,
        monthly_rows=monthly_rows,
        settings_changes=settings_changes,
        window_reason_rows=window_rows,
    )
    if not window_rows and not month_rows:
        return [
            output_row(
                run_date=run_date,
                listing_id="",
                scope_type="window",
                scope_name="all",
                observed_issue="none",
                setting=None,
                performance_after_change="insufficient_data",
                market_context="insufficient_data",
                likely_reason="insufficient_data",
                confidence="low",
                recommendation_allowed=False,
                recommendation_type="insufficient_data",
                explanation_note="Required performance inputs were not available.",
            )
        ]
    return month_rows + window_rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    monthly_path = Path(args.monthly_file or f"analysis/monthly_revenue_pace_{args.run_date}.csv")
    window_summary_path = Path(args.window_summary_file or f"analysis/future_window_summary_{args.run_date}.csv")
    window_signals_path = Path(args.window_signals_file or f"analysis/future_window_signals_{args.run_date}.csv")
    settings_changes_path = Path(args.settings_changes_file or f"settings/pricelabs_settings_changes_{args.run_date}.csv")
    output_path = Path(args.output_file or f"analysis/performance_reason_review_{args.run_date}.csv")

    rows = build_reason_rows(
        run_date=args.run_date,
        monthly_rows=read_csv_rows(monthly_path),
        window_summaries=read_csv_rows(window_summary_path),
        window_signals=read_csv_rows(window_signals_path),
        settings_changes=read_csv_rows(settings_changes_path),
    )
    write_rows(output_path, rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
