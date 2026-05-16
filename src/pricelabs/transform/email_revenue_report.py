"""Email-ready monthly revenue report from the rolling revenue view."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pricelabs.transform.monthly_revenue_summary import (
    build_recommendation_lines,
    format_currency,
    is_actionable_row,
    is_historical_actual_row,
    read_monthly_rows,
    read_reason_rows,
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


def recommendation_section(rows: list[dict[str, str]]) -> list[str]:
    lines = ["## Recommendation Review", ""]
    recommendation_rows = action_rows(rows, "critical_now") + action_rows(rows, "advisory") + protected_rows(rows)
    if not recommendation_rows:
        lines.append("- None.")
        lines.append("")
        return lines

    for action_level in ("critical_now", "advisory", "protect"):
        for line in build_recommendation_lines(rows, action_level):
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
        or row.get("likely_reason", "") in {"insufficient_data", "settings_change_impact"}
    ]
    selected = issue_rows[:2] or reason_rows[:1]
    for row in selected:
        allowed = "yes" if row.get("recommendation_allowed", "").lower() == "true" else "no"
        lines.append(
            "- "
            f"{row.get('scope_name', '')}: {row.get('observed_issue', 'none')} likely "
            f"{row.get('likely_reason', 'insufficient_data')}; "
            f"PriceLabs rule change justified now: {allowed} ({row.get('recommendation_type', 'monitor')})."
        )
    lines.append("")
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


def build_markdown(run_date: str, rows: list[dict[str, str]], reason_rows: list[dict[str, str]] | None = None) -> str:
    sorted_rows = sorted(rows, key=lambda row: row["stay_month"])
    lines = [
        f"Subject: Aloha Poconos Weekly Revenue Snapshot — {run_date}",
        "",
        f"# Aloha Poconos Weekly Revenue Snapshot — {run_date}",
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
    lines.extend(recommendation_section(sorted_rows))
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
    rolling_path = Path(args.rolling_file or f"analysis/rolling_13_month_revenue_view_{args.run_date}.csv")
    summary_path = Path(args.summary_file or f"analysis/monthly_revenue_summary_{args.run_date}.md")
    output_path = Path(args.output_file or f"analysis/email_revenue_report_{args.run_date}.md")
    reason_path = Path(args.reason_review_file or f"analysis/performance_reason_review_{args.run_date}.csv")

    if not summary_path.exists():
        raise FileNotFoundError(f"Monthly revenue summary markdown does not exist: {summary_path}")

    rows = read_monthly_rows(rolling_path)
    reason_rows = read_reason_rows(reason_path)
    write_markdown(output_path, build_markdown(args.run_date, rows, reason_rows))
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
