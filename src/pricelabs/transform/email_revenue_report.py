"""Email-ready monthly revenue report from the rolling revenue view."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys

from analysis.listing_competitor_review import build_competitor_calendar_context
from pricelabs.transform.monthly_revenue_summary import (
    build_recommendation_lines,
    format_currency,
    is_actionable_row,
    is_historical_actual_row,
    read_monthly_rows,
    read_reason_rows,
    reason_review_sentence,
    table_adr,
    table_booked_revenue,
    table_cleanings,
    table_occupancy,
    table_open_ask,
    table_revenue_per_cleaning,
    table_total_future_value,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an email-ready revenue report.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--rolling-file",
        help="Rolling 13-month revenue view CSV. Defaults to analysis/rolling_13_month_revenue_view_<run-date>.csv.",
    )
    parser.add_argument(
        "--summary-file",
        help="Monthly revenue summary markdown. Defaults to analysis/monthly_revenue_summary_<run-date>.md.",
    )
    parser.add_argument(
        "--output-file",
        help="Email report markdown. Defaults to analysis/email_revenue_report_<run-date>.md.",
    )
    parser.add_argument(
        "--reason-review-file",
        help="Optional performance reason review CSV. Defaults to analysis/performance_reason_review_<run-date>.csv.",
    )
    parser.add_argument(
        "--combined-signal-file",
        help="Optional combined market/listing signal CSV. Defaults to analysis/combined_market_listing_signal_<run-date>.csv.",
    )
    parser.add_argument(
        "--airbnb-summary-file",
        help="Optional Airbnb weekly conversion summary CSV. Defaults to analysis/airbnb_weekly_conversion_summary_<run-date>.csv.",
    )
    parser.add_argument(
        "--airbnb-weekly-history-file",
        help="Optional Airbnb weekly history comparison CSV. Defaults to analysis/airbnb_weekly_history_comparison_<run-date>.csv.",
    )
    parser.add_argument(
        "--diagnostic-issue-file",
        help="Optional diagnostic issue tracker CSV. Defaults to analysis/diagnostic_issue_tracker_<run-date>.csv.",
    )
    parser.add_argument(
        "--listing-review-file",
        help="Optional listing competitor review CSV. Defaults to analysis/listing_competitor_review_<run-date>.csv.",
    )
    parser.add_argument(
        "--competitor-list-file",
        help="Optional PriceLabs competitor list CSV. Defaults to raw/pricelabs_competitor_list_<run-date>.csv.",
    )
    parser.add_argument(
        "--competitor-calendar-file",
        help="Optional normalized PriceLabs competitor calendar CSV. Defaults to analysis/pricelabs_competitor_calendar_<run-date>.csv.",
    )
    parser.add_argument(
        "--listing-change-log-file",
        help="Optional listing change log CSV. Defaults to data/history/listing_change_log.csv.",
    )
    parser.add_argument(
        "--active-tests-file",
        help="Optional active tests CSV. Defaults to analysis/active_tests_<run-date>.csv.",
    )
    parser.add_argument(
        "--airbnb-search-visibility-file",
        help="Optional Airbnb search visibility diagnostic CSV. Defaults to analysis/airbnb_search_visibility_<run-date>.csv.",
    )
    parser.add_argument(
        "--stayfi-anniversary-summary-file",
        help="Optional StayFi anniversary email summary CSV. Defaults to analysis/stayfi_anniversary_email_summary_<run-date>.csv.",
    )
    parser.add_argument(
        "--stayfi-anniversary-send-results-file",
        help="Optional StayFi anniversary send results CSV. Defaults to analysis/stayfi_anniversary_email_send_results_<run-date>.csv.",
    )
    return parser.parse_args()


def available_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if is_actionable_row(row)]


def historical_actual_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if is_historical_actual_row(row)]


def find_available_bucket(rows: list[dict[str, str]], bucket: str) -> dict[str, str] | None:
    return next((row for row in available_rows(rows) if row["month_time_bucket"] == bucket), None)


def action_rows(rows: list[dict[str, str]], action_level: str) -> list[dict[str, str]]:
    return [
        row
        for row in available_rows(rows)
        if row["month_action_level"] == action_level
    ]


def protected_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return action_rows(rows, "protect")


def partial_horizon_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in available_rows(rows)
        if row["revenue_pace_status"] == "partial_horizon"
    ]


def executive_snapshot(rows: list[dict[str, str]]) -> list[str]:
    bullets: list[str] = []
    current = find_available_bucket(rows, "current_month")
    next_month = find_available_bucket(rows, "next_month")
    advisory = action_rows(rows, "advisory")
    protected = protected_rows(rows)
    historical = historical_actual_rows(rows)

    if current:
        bullets.append(f"Current month {current['stay_month']} is {current['revenue_pace_status']}.")
    if next_month:
        bullets.append(f"Next month {next_month['stay_month']} is {next_month['revenue_pace_status']}.")
    if advisory:
        bullets.append("Advisory months: " + ", ".join(row["stay_month"] for row in advisory) + ".")
    if protected:
        bullets.append("Protected future months: " + ", ".join(row["stay_month"] for row in protected) + ".")
    if historical:
        bullets.append("Historical actuals available: " + ", ".join(row["stay_month"] for row in historical) + ".")
    else:
        bullets.append("Historical actuals are not available in this run.")
    bullets.append("Market benchmark is context only.")
    return bullets[:6]


def attention_lines(rows: list[dict[str, str]], action_level: str) -> list[str]:
    matching_rows = action_rows(rows, action_level)
    if not matching_rows:
        return ["- None."]
    return [
        "- "
        f"{row['stay_month']}: {row['revenue_pace_status']} - "
        f"revenue captured {table_booked_revenue(row)}, "
        f"total calendar value {table_total_future_value(row)}, "
        f"cleaning {row['cleaning_efficiency_status']}."
        for row in matching_rows
    ]


def protect_lines(rows: list[dict[str, str]]) -> list[str]:
    matching_rows = protected_rows(rows)
    if not matching_rows:
        return ["- None."]
    return [
        "- "
        f"{row['stay_month']}: {row['revenue_pace_status']} - "
        f"total calendar value {table_total_future_value(row)}."
        for row in matching_rows
    ]


def key_snapshot_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    selected.extend(historical_actual_rows(rows))

    for row in available_rows(rows):
        if row["month_time_bucket"] in {"current_month", "next_month"}:
            selected.append(row)
        elif row["month_action_level"] == "protect":
            selected.append(row)
        elif row["revenue_pace_status"] == "partial_horizon":
            selected.append(row)

    by_month = {row["stay_month"]: row for row in selected if row["data_availability"] != "no_source_data"}
    return [by_month[month] for month in sorted(by_month)]


def has_pricing_efficiency_risk(signal_rows: list[dict[str, str]] | None) -> bool:
    if not signal_rows:
        return False
    row = signal_rows[0]
    return (
        row.get("revenue_pace_signal", "") == "weak"
        and row.get("occupancy_gap_signal", "") == "behind"
        and row.get("cleaning_efficiency_signal", "") == "inefficient"
        and row.get("data_quality_status", "") == "complete"
    )


def recommendation_section(
    rows: list[dict[str, str]],
    reason_rows: list[dict[str, str]] | None = None,
    combined_signal_rows: list[dict[str, str]] | None = None,
) -> list[str]:
    lines = ["## Recommendation Review", ""]
    if has_pricing_efficiency_risk(combined_signal_rows):
        lines.extend(
            [
                "- Pricing efficiency risk: PriceLabs core metrics show weak revenue pace, behind-market occupancy, and inefficient cleaning performance. Treat this as investigation context only; no rule change is recommended unless existing PriceLabs recommendation logic supports it.",
                "",
            ]
        )
    recommendation_rows = action_rows(rows, "critical_now") + action_rows(rows, "advisory") + protected_rows(rows)
    if not recommendation_rows:
        lines.append("- None.")
        lines.append("")
        return lines

    for action_level in ("critical_now", "advisory", "protect"):
        for line in build_recommendation_lines(rows, action_level, reason_rows or []):
            if line != "- None.":
                lines.append(line)
    lines.append("")
    return lines


def reason_review_section(reason_rows: list[dict[str, str]]) -> list[str]:
    lines = ["## Reason Review", ""]
    if not reason_rows:
        lines.append("- Reason review unavailable; no PriceLabs rule change is justified from this layer.")
        lines.append("")
        return lines
    issue_rows = [
        row
        for row in reason_rows
        if row.get("observed_issue", "") != "none"
        or row.get("likely_reason", "") in {"no_issue", "insufficient_data", "settings_change_impact"}
    ]
    selected = issue_rows[:2] or reason_rows[:1]
    for row in selected:
        lines.append(f"- {reason_review_sentence(row)}")
    lines.append("")
    return lines


def read_combined_signal_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_airbnb_summary_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_csv_rows_and_columns(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def airbnb_summary_status(path: Path) -> tuple[list[dict[str, str]], dict[str, object]]:
    if not path.exists():
        rows: list[dict[str, str]] = []
        missing_columns: list[str] = []
        status = "missing_file"
    else:
        rows, columns = read_csv_rows_and_columns(path)
        missing_columns = [column for column in AIRBNB_REQUIRED_SUMMARY_COLUMNS if column not in columns]
        if missing_columns:
            status = "missing_columns"
        elif not rows:
            status = "empty_file"
        else:
            status = "available"
    diagnostics: dict[str, object] = {
        "status": status,
        "path": str(path),
        "missing_columns": missing_columns,
        "row_count": len(rows),
    }
    if status == "missing_file":
        diagnostics.update(airbnb_capture_failure_context(path))
    return rows if status == "available" else [], diagnostics


def airbnb_capture_failure_context(summary_path: Path) -> dict[str, object]:
    match = re.search(r"airbnb_weekly_conversion_summary_(\d{4}-\d{2}-\d{2})\.csv$", summary_path.name)
    if not match:
        return {}
    run_date = match.group(1)
    run_dir = summary_path.parent.parent
    capture_path = run_dir / "downloads_staging" / "airbnb" / f"airbnb_capture_manifest_{run_date}.json"
    if not capture_path.exists():
        return {}
    try:
        manifest = json.loads(capture_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    failure_reason = manifest.get("failure_reason", "")
    if not failure_reason and manifest.get("capture_status") != "failed":
        return {}
    return {
        "status": "capture_failed",
        "root_cause": failure_reason or "airbnb_capture_failed",
        "capture_manifest_path": str(capture_path),
        "expected_date_range_start": manifest.get("expected_date_range_start", ""),
        "expected_date_range_end": manifest.get("expected_date_range_end", ""),
        "applied_date_range_start": manifest.get("applied_date_range_start", ""),
        "applied_date_range_end": manifest.get("applied_date_range_end", ""),
        "date_range_attempts": manifest.get("date_range_attempts", ""),
    }


def read_airbnb_weekly_history_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_diagnostic_issue_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_listing_review_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_competitor_calendar_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_listing_change_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_active_test_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_airbnb_search_visibility_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_stayfi_anniversary_summary_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_stayfi_anniversary_send_result_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def default_combined_signal_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"combined_market_listing_signal_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"combined_market_listing_signal_{run_date}.csv"


def default_airbnb_summary_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"airbnb_weekly_conversion_summary_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv"


def default_airbnb_weekly_history_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"airbnb_weekly_history_comparison_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"airbnb_weekly_history_comparison_{run_date}.csv"


def default_diagnostic_issue_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"diagnostic_issue_tracker_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"diagnostic_issue_tracker_{run_date}.csv"


def default_listing_review_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"listing_competitor_review_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"listing_competitor_review_{run_date}.csv"


def default_listing_review_markdown_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"listing_competitor_review_{run_date}.md"
    return Path("data") / "runs" / run_date / "analysis" / f"listing_competitor_review_{run_date}.md"


def default_listing_state_snapshot_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"listing_state_snapshot_{run_date}.md"
    return Path("data") / "runs" / run_date / "analysis" / f"listing_state_snapshot_{run_date}.md"


def default_listing_visual_snapshot_paths(run_date: str, output_path: Path) -> list[Path]:
    analysis_dir = output_path.parent if output_path.parent.name == "analysis" else Path("data") / "runs" / run_date / "analysis"
    return [
        analysis_dir / f"listing_search_card_{run_date}.png",
        analysis_dir / f"listing_page_top_{run_date}.png",
        analysis_dir / f"listing_first_5_photos_{run_date}.png",
    ]


def default_competitor_list_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        run_dir = output_path.parent.parent
        return run_dir / "raw" / f"pricelabs_competitor_list_{run_date}.csv"
    return Path("data") / "runs" / run_date / "raw" / f"pricelabs_competitor_list_{run_date}.csv"


def default_competitor_calendar_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"pricelabs_competitor_calendar_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"pricelabs_competitor_calendar_{run_date}.csv"


def default_listing_change_log_path(output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        try:
            return output_path.parents[3] / "history" / "listing_change_log.csv"
        except IndexError:
            pass
    return Path("data") / "history" / "listing_change_log.csv"


def default_active_tests_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"active_tests_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"active_tests_{run_date}.csv"


def default_airbnb_search_visibility_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"airbnb_search_visibility_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"airbnb_search_visibility_{run_date}.csv"


def default_stayfi_anniversary_summary_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"stayfi_anniversary_email_summary_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"stayfi_anniversary_email_summary_{run_date}.csv"


def default_stayfi_anniversary_send_results_path(run_date: str, output_path: Path) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / f"stayfi_anniversary_email_send_results_{run_date}.csv"
    return Path("data") / "runs" / run_date / "analysis" / f"stayfi_anniversary_email_send_results_{run_date}.csv"


def default_output_path(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "analysis" / f"email_revenue_report_{run_date}.md"


def default_analysis_input_path(run_date: str, output_path: Path, filename: str) -> Path:
    if output_path.parent.name == "analysis":
        return output_path.parent / filename
    return Path("data") / "runs" / run_date / "analysis" / filename


def display_category(value: str) -> str:
    labels = {
        "healthy_alignment": "Healthy alignment",
        "market_softness": "Market softness",
        "listing_specific_investigation": "Listing-specific investigation",
        "outperformance_pricing_efficiency_investigation": "Outperformance / pricing-efficiency review",
        "urgent_revenue_occupancy_gap": "Urgent revenue / occupancy gap",
        "insufficient_data": "Insufficient data",
    }
    return labels.get(value, (value or "unknown").replace("_", " ").capitalize())


def display_signal(value: str) -> str:
    labels = {
        "above_similar": "above similar listings",
        "above_similar_listings": "above similar listings",
        "below_similar": "below similar listings",
        "below_similar_listings": "below similar listings",
        "above_market": "above market",
        "market_soft": "soft",
        "down": "soft",
        "up": "up",
        "stable": "stable",
    }
    return labels.get(value, (value or "unknown").replace("_", " "))


def display_signal_value(key: str, value: str) -> str:
    if not value:
        return "unknown"
    percent_keys = {
        "average_overall_conversion_rate",
        "first_page_search_impression_rate",
        "search_to_listing_conversion_rate",
        "listing_to_booking_conversion_rate",
    }
    if key in percent_keys and not value.endswith("%"):
        return f"{value}%"
    return value


AIRBNB_FUNNEL_SIGNALS = (
    ("page_views", "Page views", "count"),
    ("first_page_search_impressions", "First-page search impressions", "count"),
    ("estimated_relevant_searches", "Estimated relevant searches", "count"),
    ("estimated_relevant_searches_per_day", "Estimated relevant searches/day", "count"),
    ("wishlist_additions", "Wishlist additions", "count"),
    ("average_overall_conversion_rate", "Average overall conversion rate", "rate"),
    ("first_page_search_impression_rate", "First-page search impression rate", "rate"),
    ("search_to_listing_conversion_rate", "Search-to-listing conversion rate", "rate"),
    ("listing_to_booking_conversion_rate", "Listing-to-booking conversion rate", "rate"),
)

AIRBNB_REQUIRED_SUMMARY_COLUMNS = (
    "metric_window_start",
    "metric_window_end",
    *(key for key, _label, _metric_type in AIRBNB_FUNNEL_SIGNALS),
)


def signed_number(value: str, *, decimals: int | None = None) -> str:
    if value == "":
        return "unknown"
    try:
        number = float(str(value).replace("%", ""))
    except ValueError:
        return value
    sign = "+" if number > 0 else ""
    if decimals is None:
        if number.is_integer():
            return f"{sign}{int(number)}"
        return f"{sign}{number:g}"
    formatted = f"{number:.{decimals}f}".rstrip("0").rstrip(".")
    return f"{sign}{formatted}"


def airbnb_wow_value(metric_name: str, value: str, metric_type: str) -> str:
    if not value:
        return "unknown"
    if metric_type == "rate":
        return display_signal_value(metric_name, value)
    try:
        number = float(value)
    except ValueError:
        return value
    return str(int(number)) if number.is_integer() else f"{number:g}"


def parse_airbnb_wow_number(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(str(value).replace("%", ""))
    except ValueError:
        return None


def airbnb_wow_direction(previous: str, current: str, change: str, metric_type: str) -> str:
    change_number = parse_airbnb_wow_number(change)
    if change_number is None:
        previous_number = parse_airbnb_wow_number(previous)
        current_number = parse_airbnb_wow_number(current)
        if previous_number is None or current_number is None:
            return "unavailable"
        change_number = current_number - previous_number

    if metric_type == "rate":
        if abs(change_number) < 0.10:
            return "essentially flat"
        return "improved" if change_number > 0 else "declined"

    if change_number == 0:
        return "essentially flat"
    previous_number = parse_airbnb_wow_number(previous)
    if previous_number not in (None, 0) and abs(change_number / previous_number) < 0.05:
        return "essentially flat"
    return "increased" if change_number > 0 else "declined"


def airbnb_wow_interpretation(label: str, direction: str) -> str:
    if direction == "unavailable":
        return f"- Interpretation: {label} direction is unavailable."
    return f"- Interpretation: {label} {direction}."

def airbnb_funnel_wow_section(history_rows: list[dict[str, str]] | None, *, history_path: Path | None = None) -> list[str]:
    lines = ["## Airbnb Funnel Week-over-Week", ""]
    if not history_rows:
        lines.append("- Airbnb funnel week-over-week comparison unavailable for this run.")
        if history_path is not None:
            lines.append(f"- Expected Airbnb weekly history file: {history_path}.")
        lines.append("")
        return lines

    rows_by_metric = {row.get("metric_name", ""): row for row in history_rows}
    rendered_any = False
    interpretation_lines: list[str] = []
    for metric_name, label, metric_type in AIRBNB_FUNNEL_SIGNALS:
        row = rows_by_metric.get(metric_name)
        if not row:
            continue
        previous_raw = row.get("previous_week_value", "")
        current_raw = row.get("current_value", "")
        change = row.get("change_vs_previous_week", "")
        previous = airbnb_wow_value(metric_name, previous_raw, metric_type)
        current = airbnb_wow_value(metric_name, current_raw, metric_type)
        if metric_type == "rate":
            change_text = f"{signed_number(change, decimals=2)} pp"
        else:
            change_text = signed_number(change)
        lines.append(f"- {label}: {previous} \u2192 {current} ({change_text})")
        direction = airbnb_wow_direction(previous_raw, current_raw, change, metric_type)
        interpretation_lines.append(airbnb_wow_interpretation(label, direction))
        rendered_any = True

    if not rendered_any:
        lines.extend(["- Airbnb funnel week-over-week comparison unavailable for this run.", ""])
        return lines

    lines.extend(interpretation_lines)
    lines.extend(["- Diagnostic only; this does not create a PriceLabs rule recommendation.", ""])
    return lines


def market_vs_listing_signal_section(signal_rows: list[dict[str, str]] | None) -> list[str]:
    lines = ["## Market vs Listing Signal", ""]
    if not signal_rows:
        lines.append("- Combined market/listing signal unavailable for this run.")
        lines.append("")
        return lines

    row = signal_rows[0]
    category = row.get("combined_signal_category", "")
    market = row.get("market_health_signal", "") or "unknown"
    listing = row.get("listing_airbnb_signal", "") or "unknown"
    explanation = row.get("explanation", "") or "Combined signal explanation unavailable."

    if category == "outperformance_pricing_efficiency_investigation":
        if (
            market == "down"
            and listing in {"above_similar", "above_similar_listings"}
            and row.get("revenue_pace_signal", "") == "weak"
            and row.get("occupancy_gap_signal", "") == "behind"
            and row.get("cleaning_efficiency_signal", "") == "inefficient"
        ):
            lines.append(
                "- Market/listing signal: Outperformance / pricing-efficiency review. "
                "Airbnb diagnostics are above similar listings, but PriceLabs core metrics show weak revenue pace, "
                "behind-market occupancy, and inefficient cleaning performance. This should be treated as a high-priority "
                "pricing-efficiency review, not an automatic discount signal. Protect premium positioning and avoid filling "
                "gaps with low-value turnovers unless PriceLabs revenue pace and booking-window data justify it."
            )
        else:
            lines.append(
                "- Market/listing signal: Outperformance / pricing-efficiency review. "
                f"Airbnb listing signals are {display_signal(listing)} while broader market context is {display_signal(market)}. "
                "This is positive, but may indicate pricing power. Review PriceLabs revenue pace, ADR, open ask, "
                "booking pace, and cleaning efficiency before any rule change."
            )
    else:
        lines.append(
            f"- Market/listing signal: {display_category(category)}. "
            f"Market health: {display_signal(market)}; listing Airbnb signal: {display_signal(listing)}. {explanation}"
        )
    metric_lines = [
        (key, label)
        for key, label in (
            ("average_overall_conversion_rate", "Average overall conversion rate"),
            ("first_page_search_impression_rate", "First-page search impression rate"),
            ("search_to_listing_conversion_rate", "Search-to-listing conversion rate"),
            ("listing_to_booking_conversion_rate", "Listing-to-booking conversion rate"),
        )
        if row.get(key, "")
    ]
    lines.extend(
        [
            f"- Investigation priority: {row.get('investigation_priority', '') or 'unknown'}.",
            f"- Revenue pace signal: {row.get('revenue_pace_signal', '') or 'unknown'}.",
            f"- Occupancy gap signal: {row.get('occupancy_gap_signal', '') or 'unknown'}.",
            f"- Cleaning efficiency signal: {row.get('cleaning_efficiency_signal', '') or 'unknown'}.",
            *[f"- {label}: {display_signal_value(key, row.get(key, ''))}." for key, label in metric_lines],
            f"- Data quality status: {row.get('data_quality_status', '') or 'unknown'}.",
            "- Airbnb diagnostics can raise investigation priority, but PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.",
            "",
        ]
    )
    return lines


def airbnb_funnel_signals_section(
    summary_rows: list[dict[str, str]] | None,
    *,
    summary_diagnostics: dict[str, object] | None = None,
    weekly_history_path: Path | None = None,
) -> list[str]:
    lines = ["## Airbnb Funnel Signals", ""]
    if not summary_rows:
        diagnostics = summary_diagnostics or {}
        missing_columns = diagnostics.get("missing_columns", [])
        lines.extend(
            [
                "- Airbnb funnel diagnostics unavailable for this run.",
                f"- Reason: {diagnostics.get('status', 'unavailable')}.",
                f"- Expected Airbnb summary file: {diagnostics.get('path', 'unknown')}.",
            ]
        )
        if weekly_history_path is not None:
            lines.append(f"- Expected Airbnb weekly history file: {weekly_history_path}.")
        if missing_columns:
            lines.append("- Missing Airbnb summary columns: " + ", ".join(str(column) for column in missing_columns) + ".")
        if diagnostics.get("root_cause"):
            root_cause = str(diagnostics.get("root_cause"))
            evidence = (
                "Airbnb capture attempted date setup but applied date range did not match expected range after retries."
                if root_cause == "date_range_not_able_to_set_up"
                else "Airbnb capture did not complete successfully before diagnostics could be parsed."
            )
            lines.extend(
                [
                    "",
                    "## Airbnb Diagnostics Root Cause",
                    "",
                    "- Status: unavailable",
                    f"- Root cause: {root_cause}",
                    f"- Evidence: {evidence}",
                    f"- Expected date range: {diagnostics.get('expected_date_range_start', '') or 'unavailable'} to {diagnostics.get('expected_date_range_end', '') or 'unavailable'}",
                    f"- Applied date range: {diagnostics.get('applied_date_range_start', '') or 'unavailable'} to {diagnostics.get('applied_date_range_end', '') or 'unavailable'}",
                    f"- Attempts: {diagnostics.get('date_range_attempts', '') or 'unavailable'}",
                    "- Recovery: rerun Airbnb capture manually and confirm date range is set before continuing.",
                ]
            )
        lines.extend(
            [
                "- Manual action required before final report: run Airbnb capture with browser login/MFA, then promote staged files and rerun diagnostics.",
                "- Commands:",
                '  `$env:PYTHONPATH = "src"`',
                "  `.\\.venv\\Scripts\\python.exe -m airbnb.download_diagnostics --run-date <run_date> --mode capture-headed-and-validate`",
                "  `.\\.venv\\Scripts\\python.exe -m airbnb.download_diagnostics --run-date <run_date> --mode promote-staged`",
                "  `.\\.venv\\Scripts\\python.exe -m airbnb.run_diagnostics --run-date <run_date>`",
                "  `.\\run_weekly_pipeline.ps1 -RunDate <run_date>`",
                "- Airbnb funnel signals are diagnostic only. PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.",
                "",
            ]
        )
        return lines

    row = summary_rows[0]
    window_start = row.get("metric_window_start", "") or "unknown"
    window_end = row.get("metric_window_end", "") or "unknown"
    lines.append(f"- Metric window: {window_start} to {window_end}.")
    for key, label, _metric_type in AIRBNB_FUNNEL_SIGNALS:
        lines.append(f"- {label}: {display_signal_value(key, row.get(key, ''))}.")
    if row.get("benchmark_type", ""):
        lines.extend(
            [
                f"- Relevant search benchmark: {row.get('benchmark_type', '')}.",
                f"- Relevant searches vs benchmark: {row.get('relevant_searches_vs_trailing_benchmark_pct', '') or 'unknown'}%.",
                f"- Search-to-listing conversion vs benchmark: {row.get('search_to_listing_conversion_vs_benchmark_pct', '') or 'unknown'}%.",
                f"- Listing-to-booking conversion vs benchmark: {row.get('listing_to_booking_conversion_vs_benchmark_pct', '') or 'unknown'}%.",
                f"- Market demand status: {row.get('market_demand_status', '') or 'unknown'}.",
                f"- Visibility status: {row.get('visibility_status', '') or 'unknown'}.",
                f"- Search card status: {row.get('search_card_status', '') or 'unknown'}.",
                f"- Listing conversion status: {row.get('listing_conversion_status', '') or 'unknown'}.",
                f"- Airbnb diagnostic category: {row.get('airbnb_diagnostic_category', '') or 'unknown'}.",
            ]
        )
    lines.extend(
        [
            "- Airbnb funnel signals are diagnostic only. PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.",
            "",
        ]
    )
    return lines


def display_severity(value: str) -> str:
    return (value or "unknown").replace("_", " ").capitalize()


def diagnostic_issue_label(row: dict[str, str]) -> str:
    status = row.get("status", "").strip().lower()
    title = row.get("issue_title", "") or row.get("issue_id", "Diagnostic issue").replace("_", " ")
    if status == "open":
        return f"{display_severity(row.get('severity', ''))}/Open: {sentence(title)}"
    if status == "improving":
        return f"Improving: {sentence(title)}"
    if status == "monitoring":
        return f"Monitoring: {sentence(title)}"
    return f"{display_severity(row.get('severity', ''))}: {sentence(title)}"


def sentence(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return text if text.endswith((".", "!", "?")) else f"{text}."


def open_diagnostic_issues_section(issue_rows: list[dict[str, str]] | None, *, run_date: str = "") -> list[str]:
    lines = ["## Open Diagnostic Issues", ""]
    if issue_rows is None:
        lines.append("- No diagnostic issue tracker available for this run.")
        lines.append("")
        return lines

    active_statuses = {"open", "improving", "monitoring"}
    active_rows = [row for row in issue_rows if row.get("status", "").strip().lower() in active_statuses]
    if not active_rows:
        lines.append("- No active diagnostic issues.")
        lines.append("")
    else:
        for row in active_rows:
            lines.append(f"- {diagnostic_issue_label(row)}")
            lines.append(f"  First seen: {row.get('first_seen_run_date', '') or 'unknown'}. Weeks open: {row.get('weeks_open', '') or 'unknown'}.")
            evidence = row.get("evidence_summary", "") or "Evidence summary unavailable."
            lines.append(f"  Evidence: {sentence(evidence)}")
            if row.get("status", "").strip().lower() == "improving":
                resolution_rule = row.get("resolution_rule", "") or "Keep monitoring until conversion improves for 2 consecutive runs."
                lines.append(f"  Next check: {sentence(resolution_rule)}")
            else:
                investigation = row.get("recommended_investigation", "") or "Investigation guidance unavailable."
                lines.append(f"  Investigation: {sentence(investigation)}")
            guardrail = row.get("blocked_recommendation_reason", "") or "Diagnostic issue context cannot create PriceLabs rule recommendations."
            lines.append(f"  Guardrail: {sentence(guardrail)}")
        lines.append("- Diagnostic issues are informational only. PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.")
        lines.append("")

    resolved_rows = [
        row
        for row in issue_rows
        if row.get("status", "").strip().lower() == "resolved"
        and (not run_date or row.get("last_seen_run_date", "") == run_date)
    ]
    if resolved_rows:
        lines.extend(["## Recently Resolved Diagnostic Issues", ""])
        for row in resolved_rows:
            title = row.get("issue_title", "") or row.get("issue_id", "Diagnostic issue").replace("_", " ")
            lines.append(f"- Resolved: {sentence(title)}")
            lines.append(
                f"  First seen: {row.get('first_seen_run_date', '') or 'unknown'}. "
                f"Resolved on: {row.get('last_seen_run_date', '') or 'unknown'}."
            )
            resolution_rule = row.get("resolution_rule", "") or "Resolution rule unavailable."
            lines.append(f"  Resolution rule: {sentence(resolution_rule)}")
        lines.append("")
    return lines


def listing_review_needed_section(
    run_date: str,
    review_rows: list[dict[str, str]] | None,
    *,
    full_review_available: bool = False,
    listing_snapshot_available: bool = False,
    visual_baseline_available: bool = False,
    competitor_list_available: bool = False,
    competitor_calendar_context: dict[str, str] | None = None,
) -> list[str]:
    lines = ["## Listing Review Needed", ""]
    if not review_rows:
        lines.append("- No active listing-side review is needed for this run.")
        lines.append("")
        return lines

    focus_order = [
        "search_card_appeal",
        "cover_photo_first_five_photos",
        "title_description_opening",
        "amenities_presentation",
        "guest_fit_sleeping_capacity",
        "trust_review_signals",
        "booking_friction_risks",
        "competitor_comparison",
    ]
    label_map = {
        "search_card_appeal": "search card appeal",
        "cover_photo_first_five_photos": "cover/first photos",
        "title_description_opening": "title/opening copy",
        "amenities_presentation": "amenities presentation",
        "guest_fit_sleeping_capacity": "guest fit",
        "trust_review_signals": "trust signals",
        "booking_friction_risks": "booking friction",
        "competitor_comparison": "competitor comparison",
    }
    available = {row.get("review_area", "") for row in review_rows}
    focus_labels = [label_map[area] for area in focus_order if area in available]
    if not focus_labels:
        focus_labels = ["listing presentation", "booking friction", "competitor comparison"]

    lines.extend(
        [
            "- Listing-side review is recommended because an open diagnostic issue shows Airbnb visibility increased sharply while conversion weakened or remained weak.",
            f"- Focus review areas: {', '.join(focus_labels)}.",
            "- Guardrail: This is diagnostic only and does not create a PriceLabs rule recommendation.",
        ]
    )
    if full_review_available:
        lines.append(f"- Full review: see listing_competitor_review_{run_date}.md in the evidence bundle.")
    if listing_snapshot_available:
        lines.append(f"- Listing snapshot: see listing_state_snapshot_{run_date}.md in the evidence bundle.")
    if visual_baseline_available:
        lines.append("- Visual baseline files are included in the evidence bundle when available.")
    if competitor_list_available:
        lines.append(f"- Competitor set: see pricelabs_competitor_list_{run_date}.csv in the evidence bundle.")
    if competitor_calendar_context:
        lines.append(
            "- Competitor context: selected PriceLabs comps show median average price of "
            f"${competitor_calendar_context['competitor_median_average_price']}, "
            f"median minimum stay of {competitor_calendar_context['competitor_median_min_stay']} nights, "
            f"and median available date count of {competitor_calendar_context['competitor_median_available_date_count']} "
            "across the 90-day window."
        )
        lines.append(
            "- Subject listing metrics are intentionally excluded from this competitor context because PriceLabs core outputs "
            "remain the source of truth for Aloha Poconos pricing, availability, revenue pace, and cleaning context."
        )
    lines.append("")
    return lines


def active_listing_changes_section(
    run_date: str,
    change_rows: list[dict[str, str]] | None,
    *,
    change_log_available: bool = False,
    visual_baseline_available: bool = False,
) -> list[str]:
    if not change_log_available:
        return []

    active_rows = [
        row
        for row in change_rows or []
        if row.get("status", "").strip().lower() == "active"
    ]
    if not active_rows:
        return []

    lines = ["## Active Listing Tests", ""]
    for row in active_rows:
        lines.append(f"- Active test: {row.get('change_type', '') or 'listing change'}.")
        lines.append(f"  Related issue: {row.get('related_issue_id', '') or 'unknown'}.")
        lines.append(f"  Change date: {row.get('change_date', '') or 'unknown'}.")
        lines.append(f"  Expected effect: {row.get('expected_effect', '') or 'not specified'}.")
        review_after = row.get("review_after_run_date", "") or "not specified"
        lines.append(f"  Review after: {review_after}.")
        due_this_run = review_after != "not specified" and review_after <= run_date
        lines.append(f"  Review due this run: {'Yes' if due_this_run else 'No'}.")
        lines.append(
            "  Guardrail: Do not make additional listing or pricing changes until this test has at least one full Airbnb diagnostic cycle, unless urgent risk appears."
        )
    if visual_baseline_available:
        lines.append("- Current visual baseline files are included in the evidence bundle.")
    lines.append("")
    return lines


def active_test_rows_by_type(rows: list[dict[str, str]] | None, test_type: str) -> list[dict[str, str]]:
    return [
        row
        for row in rows or []
        if row.get("test_type", "").strip().lower() == test_type
        and row.get("status", "").strip().lower() == "active"
    ]


def active_tests_section(
    run_date: str,
    rows: list[dict[str, str]] | None,
    *,
    active_tests_available: bool = False,
    test_type: str,
    heading: str,
    visual_baseline_available: bool = False,
) -> list[str]:
    if not active_tests_available:
        return []
    active_rows = active_test_rows_by_type(rows, test_type)
    if not active_rows:
        return []

    lines = [heading, ""]
    for row in active_rows:
        lines.append(f"- Active test: {row.get('test_id', '') or row.get('change_area', '') or 'active test'}.")
        if row.get("related_issue_id", ""):
            lines.append(f"  Related issue: {row.get('related_issue_id')}.")
        lines.append(f"  Change date: {row.get('change_date', '') or 'unknown'}.")
        if row.get("new_value", ""):
            lines.append(f"  New value: {row.get('new_value')}.")
        if row.get("expected_effect", ""):
            lines.append(f"  Expected effect: {row.get('expected_effect')}.")
        if row.get("primary_success_metrics", ""):
            lines.append(f"  Primary success metrics: {row.get('primary_success_metrics')}.")
        review_after = row.get("review_after_run_date", "") or "not specified"
        lines.append(f"  Review after: {review_after}.")
        review_due = row.get("review_due", "").strip().lower() == "true" or (
            review_after != "not specified" and review_after <= run_date
        )
        lines.append(f"  Review due this run: {'Yes' if review_due else 'No'}.")
        if row.get("guardrails", ""):
            lines.append(f"  Guardrail: {row.get('guardrails')}.")
        if row.get("supporting_changes", ""):
            lines.append(f"  Merged supporting changes: {row.get('supporting_changes')}.")
        if row.get("notes", ""):
            lines.append(f"  Notes: {row.get('notes').rstrip('.')}.")
    if test_type == "listing" and visual_baseline_available:
        lines.append("- Current visual baseline files are included in the evidence bundle.")
    lines.append("")
    return lines


def test_review_due_section(run_date: str, rows: list[dict[str, str]] | None, *, active_tests_available: bool = False) -> list[str]:
    if not active_tests_available:
        return []
    due_rows = [
        row
        for row in rows or []
        if row.get("status", "").strip().lower() == "active"
        and (
            row.get("review_due", "").strip().lower() == "true"
            or bool(row.get("review_after_run_date", "") and row.get("review_after_run_date", "") <= run_date)
        )
    ]
    if not due_rows:
        return []
    lines = ["## Test Review Due", ""]
    for row in due_rows:
        label = "PriceLabs" if row.get("test_type", "") == "pricelabs" else "Listing"
        lines.append(f"- {label}: {row.get('test_id', '') or row.get('change_area', '')}. Review after: {row.get('review_after_run_date', '')}.")
    lines.append("")
    return lines


def stayfi_anniversary_email_section(
    summary_rows: list[dict[str, str]] | None,
    *,
    summary_available: bool = False,
    send_result_rows: list[dict[str, str]] | None = None,
    send_results_available: bool = False,
) -> list[str]:
    if not summary_available:
        return []
    lines = ["## StayFi Anniversary Email Drafts", ""]
    if not summary_rows:
        lines.extend(
            [
                "- StayFi anniversary email summary unavailable for this run.",
                "- No emails were sent automatically.",
                "",
            ]
        )
        return lines
    row = summary_rows[0]
    if row.get("source_file_status", "") == "missing":
        lines.append(
            f"- Warning: StayFi source file missing: {row.get('stayfi_input_file', '') or 'data/source/stayfi/stayfi_guests_2026.csv'}."
        )
    if row.get("source_file_status", "") == "available_but_missing_columns":
        lines.append(f"- Warning: StayFi source file is missing required columns: {row.get('missing_required_columns', '')}.")
    lines.extend(
        [
            f"- Anniversary audience window: {row.get('anniversary_audience_window_start', '')} to {row.get('anniversary_audience_window_end', '')}.",
            f"- Date column used: {row.get('date_column_used', '') or 'unavailable'}. Email column used: {row.get('email_column_used', '') or 'unavailable'}.",
            f"- Total StayFi rows checked: {row.get('total_stayfi_rows_checked', '0')}.",
            f"- Rows in audience window: {row.get('rows_in_audience_window', '0')}.",
            f"- Eligible guests: {row.get('eligible_guests', '0')}.",
            f"- Draft-ready CSV records prepared: {row.get('drafts_prepared_csv', row.get('drafts_created', '0'))}.",
            f"- Gmail drafts created: {row.get('gmail_drafts_created', row.get('drafts_created', '0'))}.",
            f"- Gmail draft failures: {row.get('gmail_draft_failures', '0')}.",
            f"- Excluded invalid emails: {row.get('excluded_invalid_emails', '0')}.",
            f"- Excluded missing email: {row.get('excluded_missing_email', '0')}.",
            f"- Excluded wrong property: {row.get('excluded_wrong_property', '0')}.",
            f"- Excluded no opt-in: {row.get('excluded_no_opt_in', '0')}.",
            f"- Excluded bad rating 1-3 stars: {row.get('excluded_bad_rating', '0')}.",
            f"- Skipped duplicates from permanent log: {row.get('skipped_duplicates_from_log', row.get('skipped_duplicates', '0'))}.",
            f"- Date parse failures: {row.get('date_parse_failed', '0')}.",
            "- Manual send workflow; no emails were sent automatically by the weekly pipeline."
            if send_results_available
            else "- Draft-only workflow; no emails were sent automatically.",
        ]
    )
    if send_results_available:
        rows = send_result_rows or []
        dry_run_would_send = sum(1 for result in rows if result.get("send_status") == "dry_run_would_send")
        sent = sum(1 for result in rows if result.get("send_status") == "sent")
        failures = sum(1 for result in rows if result.get("send_status") == "failed")
        skipped = sum(1 for result in rows if result.get("send_status") == "skipped_duplicate_logged")
        lines.extend(
            [
                f"- Dry-run would send: {dry_run_would_send}.",
                f"- Emails sent: {sent}.",
                f"- Send failures: {failures}.",
                f"- Send skipped duplicates from permanent log: {skipped}.",
            ]
        )
    lines.append("")
    return lines


def find_visibility_scenario(rows: list[dict[str, str]], scenario_name: str) -> dict[str, str] | None:
    return next((row for row in rows if row.get("scenario_name") == scenario_name), None)


def visibility_status(row: dict[str, str] | None) -> str:
    if not row:
        return "unavailable"
    found = row.get("found_status", "") or "unknown"
    if found == "found":
        page = row.get("page_number", "") or "unknown"
        position = row.get("position_on_page", "")
        return f"found on page {page}" + (f", position {position}" if position else "")
    return f"{found} after {row.get('max_pages_checked', '') or 'unknown'} pages checked"


def best_filtered_visibility(rows: list[dict[str, str]]) -> dict[str, str] | None:
    found_rows = [row for row in rows if row.get("scenario_name") != "broad_no_filters" and row.get("found_status") == "found"]
    return min(
        found_rows,
        key=lambda row: (
            float(row.get("page_number") or 9999),
            float(row.get("position_on_page") or 9999),
        ),
        default=None,
    )


def airbnb_search_visibility_section(rows: list[dict[str, str]] | None, *, diagnostic_available: bool = False) -> list[str]:
    if not diagnostic_available or not rows:
        return []
    broad = find_visibility_scenario(rows, "broad_no_filters")
    high_intent = find_visibility_scenario(rows, "broad_high_intent_filters")
    best_filtered = best_filtered_visibility(rows)
    cover_status = next((row.get("cover_photo_status", "") for row in rows if row.get("cover_photo_status", "")), "unavailable")
    lines = [
        "## Airbnb Search Visibility Diagnostic",
        "",
        f"- Broad no-filter status: {visibility_status(broad)}.",
        f"- High-intent filter status: {visibility_status(high_intent)}.",
        f"- Best filtered scenario found: {best_filtered.get('scenario_name', 'unavailable') if best_filtered else 'unavailable'}.",
        f"- Cover photo status: {cover_status}.",
        "- Guardrail: Airbnb search visibility is diagnostic only and does not create a PriceLabs rule recommendation.",
        "",
    ]
    return lines


def booking_source_notes(rows: list[dict[str, str]]) -> list[str]:
    lines = ["## Booking Source Notes", ""]
    source_rows = [
        row
        for row in sorted(rows, key=lambda row: row["stay_month"])
        if row.get("booking_source_mix_summary", "").strip()
    ]
    if not source_rows:
        lines.append("- None.")
    for row in source_rows:
        main_source = row.get("main_booking_source", "") or "unknown"
        lines.append(f"- {row['stay_month']}: {row['booking_source_mix_summary']}. Main source: {main_source}.")
    lines.append("")
    return lines


def build_markdown(
    run_date: str,
    rows: list[dict[str, str]],
    reason_rows: list[dict[str, str]] | None = None,
    combined_signal_rows: list[dict[str, str]] | None = None,
    airbnb_summary_rows: list[dict[str, str]] | None = None,
    airbnb_summary_diagnostics: dict[str, object] | None = None,
    airbnb_weekly_history_rows: list[dict[str, str]] | None = None,
    airbnb_weekly_history_path: Path | None = None,
    diagnostic_issue_rows: list[dict[str, str]] | None = None,
    diagnostic_issue_tracker_available: bool = False,
    listing_review_rows: list[dict[str, str]] | None = None,
    listing_review_available: bool = False,
    listing_review_markdown_available: bool = False,
    listing_snapshot_available: bool = False,
    listing_visual_baseline_available: bool = False,
    competitor_list_available: bool = False,
    competitor_calendar_rows: list[dict[str, str]] | None = None,
    competitor_calendar_available: bool = False,
    listing_change_rows: list[dict[str, str]] | None = None,
    listing_change_log_available: bool = False,
    active_test_rows: list[dict[str, str]] | None = None,
    active_tests_available: bool = False,
    airbnb_search_visibility_rows: list[dict[str, str]] | None = None,
    airbnb_search_visibility_available: bool = False,
    stayfi_anniversary_summary_rows: list[dict[str, str]] | None = None,
    stayfi_anniversary_summary_available: bool = False,
    stayfi_anniversary_send_result_rows: list[dict[str, str]] | None = None,
    stayfi_anniversary_send_results_available: bool = False,
) -> str:
    sorted_rows = sorted(rows, key=lambda row: row["stay_month"])
    lines = [
        f"Subject: Aloha Poconos Weekly Revenue Snapshot â€” {run_date}",
        "",
        f"# Aloha Poconos Weekly Revenue Snapshot â€” {run_date}",
        "",
        "## Executive Snapshot",
        "",
    ]
    lines.extend(f"- {bullet}" for bullet in executive_snapshot(sorted_rows))
    lines.extend(
        [
            "",
            "## What Needs Attention",
            "",
            "### Critical Now",
            "",
            *attention_lines(sorted_rows, "critical_now"),
            "",
            "### Advisory",
            "",
            *attention_lines(sorted_rows, "advisory"),
            "",
            "## What To Protect",
            "",
            *protect_lines(sorted_rows),
            "",
        ]
    )
    lines.extend(reason_review_section(reason_rows or []))
    lines.extend(market_vs_listing_signal_section(combined_signal_rows))
    lines.extend(
        airbnb_funnel_signals_section(
            airbnb_summary_rows,
            summary_diagnostics=airbnb_summary_diagnostics,
            weekly_history_path=airbnb_weekly_history_path,
        )
    )
    lines.extend(
        airbnb_funnel_wow_section(
            airbnb_weekly_history_rows if airbnb_summary_rows else None,
            history_path=airbnb_weekly_history_path,
        )
    )
    lines.extend(open_diagnostic_issues_section(diagnostic_issue_rows if diagnostic_issue_tracker_available else None, run_date=run_date))
    lines.extend(
        listing_review_needed_section(
            run_date,
            listing_review_rows if listing_review_available else None,
            full_review_available=listing_review_markdown_available,
            listing_snapshot_available=listing_snapshot_available,
            visual_baseline_available=listing_visual_baseline_available,
            competitor_list_available=competitor_list_available,
            competitor_calendar_context=build_competitor_calendar_context(competitor_calendar_rows or [])
            if listing_review_available and competitor_calendar_available
            else None,
        )
    )
    lines.extend(
        airbnb_search_visibility_section(
            airbnb_search_visibility_rows,
            diagnostic_available=airbnb_search_visibility_available,
        )
    )
    lines.extend(
        active_tests_section(
            run_date,
            active_test_rows,
            active_tests_available=active_tests_available,
            test_type="listing",
            heading="## Active Listing Tests",
            visual_baseline_available=listing_visual_baseline_available,
        )
        if active_tests_available
        else active_listing_changes_section(
            run_date,
            listing_change_rows,
            change_log_available=listing_change_log_available,
            visual_baseline_available=listing_visual_baseline_available,
        )
    )
    lines.extend(
        active_tests_section(
            run_date,
            active_test_rows,
            active_tests_available=active_tests_available,
            test_type="pricelabs",
            heading="## Active PriceLabs Tests",
        )
    )
    lines.extend(
        test_review_due_section(
            run_date,
            active_test_rows,
            active_tests_available=active_tests_available,
        )
    )
    lines.extend(
        stayfi_anniversary_email_section(
            stayfi_anniversary_summary_rows,
            summary_available=stayfi_anniversary_summary_available,
            send_result_rows=stayfi_anniversary_send_result_rows,
            send_results_available=stayfi_anniversary_send_results_available,
        )
    )
    lines.extend(recommendation_section(sorted_rows, reason_rows or [], combined_signal_rows))
    lines.extend(booking_source_notes(sorted_rows))
    lines.extend(
        [
            "## Key Monthly Snapshot",
            "",
            "| Month | Data | Revenue Captured | Open Ask | Total Calendar Value | Booked Nights | Cleanings / Stays | Occupancy | ADR | Revenue / Cleaning | Status | Action |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in key_snapshot_rows(sorted_rows):
        lines.append(
            "| "
            + " | ".join(
                (
                    row["stay_month"],
                    row["data_availability"],
                    table_booked_revenue(row),
                    table_open_ask(row),
                    table_total_future_value(row),
                    row.get("historical_booked_nights", "") if row["data_availability"] in {"monthly_trends_actuals", "historical_actuals"} else row.get("booked_nights", "") or "-",
                    table_cleanings(row),
                    table_occupancy(row),
                    table_adr(row),
                    table_revenue_per_cleaning(row),
                    row["revenue_pace_status"],
                    row["month_action_level"],
                )
            )
            + " |"
        )

    partials = partial_horizon_rows(sorted_rows)
    if partials:
        lines.extend(
            [
                "",
                "Partial horizon monitor note: "
                + ", ".join(row["stay_month"] for row in partials)
                + " is inside the export horizon only partially.",
            ]
        )

    lines.extend(
        [
            "",
            "## Data Notes",
            "",
            "- Historical occupancy is calculated from booked nights divided by calendar days.",
            "- Historical occupancy uses Monthly Trends when the month passes data-quality checks.",
            "- Historical booked nights are estimated from Monthly Trends revenue divided by ADR.",
            "- Historical cleanings are estimated from Monthly Trends booked-night estimates and observed current/future Bookings Report LOS.",
            "- Bookings Report is not treated as exact historical truth unless a future enhancement validates coverage.",
            "- Booked Nights and Cleanings / Stays are separate metrics.",
            "- Revenue / Cleaning is calculated using Cleanings / Stays, not Booked Nights.",
            "- Months with missing or suspicious monthly data are marked data_not_available and excluded from decision signals.",
            "- Future full-month occupancy is calculated from booked nights divided by days in scope.",
            "- Current and partial horizon month occupancy is hidden unless Monthly Trends provides monthly occupancy.",
            "- Revenue Captured uses Monthly Trends when available; future export booked revenue proxy is used only when Monthly Trends does not provide monthly revenue.",
            "- Open Ask uses the future calendar export.",
            "- Cleaning and length-of-stay metrics use Bookings Report when available.",
            "- Monthly revenue, ADR, and occupancy use PriceLabs Monthly Trends when available. Legacy KPI On The Books is optional/deprecated.",
            "- Airbnb revenue is not mixed into this report.",
            "- Market benchmark is context only.",
            "- This report reviews PriceLabs rule areas; it does not recommend manual date overrides.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run() -> int:
    args = parse_args()
    output_path = Path(args.output_file) if args.output_file else default_output_path(args.run_date)
    rolling_path = Path(args.rolling_file) if args.rolling_file else default_analysis_input_path(
        args.run_date, output_path, f"rolling_13_month_revenue_view_{args.run_date}.csv"
    )
    summary_path = Path(args.summary_file) if args.summary_file else default_analysis_input_path(
        args.run_date, output_path, f"monthly_revenue_summary_{args.run_date}.md"
    )
    reason_path = Path(args.reason_review_file) if args.reason_review_file else default_analysis_input_path(
        args.run_date, output_path, f"performance_reason_review_{args.run_date}.csv"
    )
    combined_signal_path = Path(args.combined_signal_file) if args.combined_signal_file else default_combined_signal_path(args.run_date, output_path)
    airbnb_summary_path = Path(args.airbnb_summary_file) if args.airbnb_summary_file else default_airbnb_summary_path(args.run_date, output_path)
    airbnb_weekly_history_path = (
        Path(args.airbnb_weekly_history_file)
        if args.airbnb_weekly_history_file
        else default_airbnb_weekly_history_path(args.run_date, output_path)
    )
    diagnostic_issue_path = Path(args.diagnostic_issue_file) if args.diagnostic_issue_file else default_diagnostic_issue_path(args.run_date, output_path)
    listing_review_path = Path(args.listing_review_file) if args.listing_review_file else default_listing_review_path(args.run_date, output_path)
    listing_review_markdown_path = default_listing_review_markdown_path(args.run_date, output_path)
    listing_state_snapshot_path = default_listing_state_snapshot_path(args.run_date, output_path)
    listing_visual_snapshot_paths = default_listing_visual_snapshot_paths(args.run_date, output_path)
    competitor_list_path = Path(args.competitor_list_file) if args.competitor_list_file else default_competitor_list_path(args.run_date, output_path)
    competitor_calendar_path = Path(args.competitor_calendar_file) if args.competitor_calendar_file else default_competitor_calendar_path(args.run_date, output_path)
    listing_change_log_path = Path(args.listing_change_log_file) if args.listing_change_log_file else default_listing_change_log_path(output_path)
    active_tests_path = Path(args.active_tests_file) if args.active_tests_file else default_active_tests_path(args.run_date, output_path)
    airbnb_search_visibility_path = (
        Path(args.airbnb_search_visibility_file)
        if args.airbnb_search_visibility_file
        else default_airbnb_search_visibility_path(args.run_date, output_path)
    )
    stayfi_anniversary_summary_path = (
        Path(args.stayfi_anniversary_summary_file)
        if args.stayfi_anniversary_summary_file
        else default_stayfi_anniversary_summary_path(args.run_date, output_path)
    )
    stayfi_anniversary_send_results_path = (
        Path(args.stayfi_anniversary_send_results_file)
        if args.stayfi_anniversary_send_results_file
        else default_stayfi_anniversary_send_results_path(args.run_date, output_path)
    )

    if not summary_path.exists():
        raise FileNotFoundError(f"Monthly revenue summary markdown does not exist: {summary_path}")

    print(f"Email revenue report rolling input: {rolling_path}")
    print(f"Email revenue report summary input: {summary_path}")
    print(f"Email revenue report reason review input: {reason_path}")
    print(f"Email revenue report combined signal input: {combined_signal_path}")
    print(f"Email revenue report Airbnb summary input: {airbnb_summary_path}")
    print(f"Email revenue report Airbnb weekly history input: {airbnb_weekly_history_path}")
    print(f"Email revenue report diagnostic issue input: {diagnostic_issue_path}")
    print(f"Email revenue report listing review input: {listing_review_path}")
    print(f"Email revenue report listing review markdown: {listing_review_markdown_path}")
    print(f"Email revenue report listing state snapshot: {listing_state_snapshot_path}")
    print(f"Email revenue report competitor list input: {competitor_list_path}")
    print(f"Email revenue report competitor calendar input: {competitor_calendar_path}")
    print(f"Email revenue report listing change log input: {listing_change_log_path}")
    print(f"Email revenue report active tests input: {active_tests_path}")
    print(f"Email revenue report Airbnb search visibility input: {airbnb_search_visibility_path}")
    print(f"Email revenue report StayFi anniversary summary input: {stayfi_anniversary_summary_path}")
    print(f"Email revenue report StayFi anniversary send results input: {stayfi_anniversary_send_results_path}")
    print(f"Email revenue report output: {output_path}")

    rows = read_monthly_rows(rolling_path)
    reason_rows = read_reason_rows(reason_path)
    combined_signal_rows = read_combined_signal_rows(combined_signal_path)
    airbnb_summary_rows, airbnb_summary_diagnostics = airbnb_summary_status(airbnb_summary_path)
    airbnb_weekly_history_rows = read_airbnb_weekly_history_rows(airbnb_weekly_history_path)
    diagnostic_issue_rows = read_diagnostic_issue_rows(diagnostic_issue_path)
    listing_review_rows = read_listing_review_rows(listing_review_path)
    competitor_calendar_rows = read_competitor_calendar_rows(competitor_calendar_path)
    listing_change_rows = read_listing_change_rows(listing_change_log_path)
    active_test_rows = read_active_test_rows(active_tests_path)
    airbnb_search_visibility_rows = read_airbnb_search_visibility_rows(airbnb_search_visibility_path)
    stayfi_anniversary_summary_rows = read_stayfi_anniversary_summary_rows(stayfi_anniversary_summary_path)
    stayfi_anniversary_send_result_rows = read_stayfi_anniversary_send_result_rows(stayfi_anniversary_send_results_path)
    write_markdown(
        output_path,
        build_markdown(
            args.run_date,
            rows,
            reason_rows,
            combined_signal_rows,
            airbnb_summary_rows,
            airbnb_summary_diagnostics,
            airbnb_weekly_history_rows,
            airbnb_weekly_history_path,
            diagnostic_issue_rows,
            diagnostic_issue_path.exists(),
            listing_review_rows,
            listing_review_path.exists(),
            listing_review_markdown_path.exists(),
            listing_state_snapshot_path.exists(),
            any(path.exists() for path in listing_visual_snapshot_paths),
            competitor_list_path.exists(),
            competitor_calendar_rows,
            competitor_calendar_path.exists(),
            listing_change_rows,
            listing_change_log_path.exists(),
            active_test_rows,
            active_tests_path.exists(),
            airbnb_search_visibility_rows,
            airbnb_search_visibility_path.exists(),
            stayfi_anniversary_summary_rows,
            stayfi_anniversary_summary_path.exists(),
            stayfi_anniversary_send_result_rows,
            stayfi_anniversary_send_results_path.exists(),
        ),
    )
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)


