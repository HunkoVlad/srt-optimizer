"""Persistent diagnostic issue tracker for recurring weekly signals."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path
import re
import sys


COLUMNS = [
    "issue_id",
    "issue_title",
    "first_seen_run_date",
    "last_seen_run_date",
    "status",
    "severity",
    "source_type",
    "signal_type",
    "current_value",
    "previous_value",
    "wow_change",
    "four_week_average",
    "weeks_open",
    "evidence_summary",
    "suspected_cause",
    "recommended_investigation",
    "blocked_recommendation_reason",
    "resolution_rule",
    "notes",
]

ISSUE_ID = "airbnb_visibility_up_conversion_down"
SIGNAL_TYPE = "visibility_up_conversion_down"
ISSUE_TITLE = "Airbnb visibility up, conversion down"
BLOCKED_REASON = "Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation."
SUSPECTED_CAUSE = "listing competitiveness / value perception / booking friction"
RECOMMENDED_INVESTIGATION = "Review listing against competitors before changing PriceLabs rules."
RESOLUTION_RULE = "Resolve after conversion improves for 2 consecutive runs."
RELEVANT_RULE_CHANGE_TOKENS = (
    "base_price",
    "minimum_price",
    "min_price",
    "minimum_stay",
    "min_stay",
    "los",
    "orphan",
    "last_minute",
    "booking_recency",
)
CONVERSION_METRICS = (
    "average_overall_conversion_rate",
    "search_to_listing_conversion_rate",
    "listing_to_booking_conversion_rate",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create persistent diagnostic issue tracker CSVs.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--history-file", help="Rolling history CSV. Defaults to data/history/diagnostic_issue_tracker.csv.")
    return parser.parse_args(argv)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in COLUMNS} for row in rows])


def parse_number(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace("$", "").replace(",", "").rstrip("%"))
    except ValueError:
        return None


def rows_by_metric(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("metric_name", ""): row for row in rows if row.get("metric_name", "")}


def meaningful_pricelabs_rule_change(settings_rows: list[dict[str, str]]) -> bool:
    for row in settings_rows:
        if str(row.get("changed_flag", "")).strip().lower() not in {"true", "1", "yes"}:
            continue
        field_name = row.get("field_name", "").strip().lower()
        if any(token in field_name for token in RELEVANT_RULE_CHANGE_TOKENS):
            return True
    return False


def conversion_weakened(metric_rows: dict[str, dict[str, str]]) -> tuple[bool, list[str]]:
    weakened: list[str] = []
    for metric in CONVERSION_METRICS:
        row = metric_rows.get(metric, {})
        change = parse_number(row.get("change_vs_previous_week", ""))
        current = parse_number(row.get("current_value", ""))
        previous = parse_number(row.get("previous_week_value", ""))
        if change is not None and change < 0:
            weakened.append(metric)
        elif current is not None and previous is not None and current < previous:
            weakened.append(metric)
    return bool(weakened), weakened


def conversion_improved(metric_rows: dict[str, dict[str, str]]) -> tuple[bool, list[str]]:
    # Conservative V1 resolution signal: at least 2 conversion metrics improve week over week.
    improved: list[str] = []
    for metric in CONVERSION_METRICS:
        row = metric_rows.get(metric, {})
        change = parse_number(row.get("change_vs_previous_week", ""))
        current = parse_number(row.get("current_value", ""))
        previous = parse_number(row.get("previous_week_value", ""))
        if change is not None and change > 0:
            improved.append(metric)
        elif current is not None and previous is not None and current > previous:
            improved.append(metric)
    return len(improved) >= 2, improved


def visibility_up_more_than_3x(row: dict[str, str]) -> bool:
    current = parse_number(row.get("current_value", ""))
    previous = parse_number(row.get("previous_week_value", ""))
    if current is None or previous is None or previous <= 0:
        return False
    return current > previous * 3


def default_history_path(run_dir: Path) -> Path:
    # Expected default shape is data/runs/<run_date>; history is data/history.
    try:
        return run_dir.parents[1] / "history" / "diagnostic_issue_tracker.csv"
    except IndexError:
        return Path("data") / "history" / "diagnostic_issue_tracker.csv"


def existing_unresolved_issue(history_rows: list[dict[str, str]], run_date: str) -> dict[str, str] | None:
    for row in reversed(history_rows):
        if row.get("last_seen_run_date") == run_date:
            continue
        if row.get("issue_id") == ISSUE_ID and row.get("status") in {"open", "improving", "monitoring"}:
            return row
    return None


def increment_weeks_open(existing: dict[str, str] | None) -> str:
    if not existing:
        return "1"
    value = parse_number(existing.get("weeks_open", ""))
    return str(int(value or 0) + 1)


def improvement_streak(row: dict[str, str] | None) -> int:
    if not row:
        return 0
    notes = row.get("notes", "")
    match = re.search(r"improvement_streak=(\d+)", notes)
    if not match:
        return 0
    return int(match.group(1))


def copy_existing_issue(
    run_date: str,
    existing: dict[str, str],
    *,
    status: str,
    notes: str,
    metric_rows: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    row = {column: existing.get(column, "") for column in COLUMNS}
    row["last_seen_run_date"] = run_date
    row["weeks_open"] = increment_weeks_open(existing)
    row["status"] = status
    row["resolution_rule"] = RESOLUTION_RULE
    row["notes"] = notes
    if metric_rows:
        impression_row = metric_rows.get("first_page_search_impressions", {})
        if impression_row:
            row["current_value"] = impression_row.get("current_value", row["current_value"])
            row["previous_value"] = impression_row.get("previous_week_value", row["previous_value"])
            row["wow_change"] = impression_row.get("change_vs_previous_week", row["wow_change"])
            row["four_week_average"] = impression_row.get("last_4_week_avg", row["four_week_average"])
    return row


def build_issue_row(
    run_date: str,
    *,
    impression_row: dict[str, str],
    weakened_metrics: list[str],
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    current = impression_row.get("current_value", "")
    previous = impression_row.get("previous_week_value", "")
    change = impression_row.get("change_vs_previous_week", "")
    four_week_average = impression_row.get("last_4_week_avg", "")
    first_seen = existing.get("first_seen_run_date", "") if existing else run_date
    weeks_open = increment_weeks_open(existing)
    metrics_text = ", ".join(metric.replace("_", " ") for metric in weakened_metrics) or "one or more conversion rates"
    evidence_summary = (
        f"First-page search impressions increased sharply: {current} vs {previous}. "
        f"Conversion weakened / remained weak ({metrics_text}). "
        "PriceLabs rules did not materially change."
    )
    return {
        "issue_id": ISSUE_ID,
        "issue_title": ISSUE_TITLE,
        "first_seen_run_date": first_seen,
        "last_seen_run_date": run_date,
        "status": "open",
        "severity": "high",
        "source_type": "airbnb_diagnostic",
        "signal_type": SIGNAL_TYPE,
        "current_value": current,
        "previous_value": previous,
        "wow_change": change,
        "four_week_average": four_week_average,
        "weeks_open": weeks_open,
        "evidence_summary": evidence_summary,
        "suspected_cause": SUSPECTED_CAUSE,
        "recommended_investigation": RECOMMENDED_INVESTIGATION,
        "blocked_recommendation_reason": BLOCKED_REASON,
        "resolution_rule": RESOLUTION_RULE,
        "notes": "Diagnostic issue only; no recommendation action is created.",
    }


def detect_airbnb_visibility_issue(
    run_date: str,
    *,
    airbnb_history_rows: list[dict[str, str]],
    settings_rows: list[dict[str, str]],
    history_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    metric_rows = rows_by_metric(airbnb_history_rows)
    impression_row = metric_rows.get("first_page_search_impressions", {})
    visibility_triggered = visibility_up_more_than_3x(impression_row)
    conversion_triggered, weakened_metrics = conversion_weakened(metric_rows)
    conversion_is_improving, improved_metrics = conversion_improved(metric_rows)
    rule_change_explains = meaningful_pricelabs_rule_change(settings_rows)
    existing = existing_unresolved_issue(history_rows, run_date)

    if visibility_triggered and conversion_triggered and not rule_change_explains:
        return [build_issue_row(run_date, impression_row=impression_row, weakened_metrics=weakened_metrics, existing=existing)]
    if existing:
        if not airbnb_history_rows:
            existing_status = existing.get("status", "open")
            status = existing_status if existing_status in {"open", "improving", "monitoring"} else "monitoring"
            streak = improvement_streak(existing)
            return [
                copy_existing_issue(
                    run_date,
                    existing,
                    status=status,
                    notes=(
                        "Carried forward; resolution could not be evaluated because Airbnb diagnostics were missing. "
                        f"improvement_streak={streak}"
                    ),
                )
            ]
        if conversion_is_improving:
            streak = improvement_streak(existing) + 1
            metrics_text = ", ".join(metric.replace("_", " ") for metric in improved_metrics)
            if streak >= 2:
                return [
                    copy_existing_issue(
                        run_date,
                        existing,
                        status="resolved",
                        notes=(
                            "Resolved after conversion improved for 2 consecutive runs "
                            f"({metrics_text}). improvement_streak={streak}"
                        ),
                        metric_rows=metric_rows,
                    )
                ]
            return [
                copy_existing_issue(
                    run_date,
                    existing,
                    status="improving",
                    notes=(
                        "Conversion is improving, but one more confirming run is required before resolution "
                        f"({metrics_text}). improvement_streak={streak}"
                    ),
                    metric_rows=metric_rows,
                )
            ]
        return [
            copy_existing_issue(
                run_date,
                existing,
                status="monitoring",
                notes="Carried forward; resolution criteria are not met. improvement_streak=0",
                metric_rows=metric_rows,
            )
        ]
    return []


def merge_history(history_rows: list[dict[str, str]], current_rows: list[dict[str, str]], run_date: str) -> list[dict[str, str]]:
    without_current = [row for row in history_rows if row.get("last_seen_run_date") != run_date]
    return without_current + current_rows


def run(run_date: str, *, run_dir: Path | None = None, history_file: Path | None = None) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    analysis_dir = resolved_run_dir / "analysis"
    settings_dir = resolved_run_dir / "settings"
    resolved_history_file = history_file or default_history_path(resolved_run_dir)
    output_path = analysis_dir / f"diagnostic_issue_tracker_{run_date}.csv"

    airbnb_history_rows = read_csv_rows(analysis_dir / f"airbnb_weekly_history_comparison_{run_date}.csv")
    settings_rows = read_csv_rows(settings_dir / f"pricelabs_settings_changes_{run_date}.csv")
    history_rows = read_csv_rows(resolved_history_file)
    current_rows = detect_airbnb_visibility_issue(
        run_date,
        airbnb_history_rows=airbnb_history_rows,
        settings_rows=settings_rows,
        history_rows=history_rows,
    )
    write_rows(output_path, current_rows)
    write_rows(resolved_history_file, merge_history(history_rows, current_rows, run_date))
    return output_path


def main() -> int:
    args = parse_args()
    output = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        history_file=Path(args.history_file) if args.history_file else None,
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
