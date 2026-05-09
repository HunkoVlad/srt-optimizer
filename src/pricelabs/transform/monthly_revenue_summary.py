"""Markdown report from monthly revenue pace diagnostics."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import sys


REQUIRED_INPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_month",
    "month_time_bucket",
    "month_scope_status",
    "booked_revenue_proxy",
    "open_revenue_ask",
    "total_future_revenue_proxy",
    "monthly_target",
    "booked_revenue_pct_of_target",
    "total_future_revenue_pct_of_target",
    "revenue_pace_status",
    "cleaning_efficiency_status",
    "month_action_level",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Markdown monthly revenue summary.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--monthly-file",
        help="Monthly revenue pace CSV. Defaults to analysis/monthly_revenue_pace_<run-date>.csv.",
    )
    parser.add_argument(
        "--output-file",
        help="Markdown output file. Defaults to analysis/monthly_revenue_summary_<run-date>.md.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Monthly revenue pace CSV is missing a header row")
    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"Monthly revenue pace CSV is missing required columns: {', '.join(missing)}")


def read_monthly_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Monthly revenue pace CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def parse_decimal(value: str) -> Decimal:
    stripped = value.strip()
    if not stripped:
        return Decimal("0")
    try:
        return Decimal(stripped.replace("$", "").replace(",", ""))
    except InvalidOperation:
        return Decimal("0")


def format_currency(value: str) -> str:
    amount = parse_decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,}"


def format_percent(value: str) -> str:
    pct = (parse_decimal(value) * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{pct}%"


def find_row(rows: list[dict[str, str]], bucket: str) -> dict[str, str] | None:
    return next((row for row in rows if row["month_time_bucket"] == bucket), None)


def build_executive_summary(rows: list[dict[str, str]]) -> list[str]:
    bullets: list[str] = []
    current = find_row(rows, "current_month")
    next_month = find_row(rows, "next_month")
    protected_far_out = [
        row
        for row in rows
        if row["month_time_bucket"] in {"future_month", "far_future_month"}
        and row["revenue_pace_status"] == "protect_open_value"
    ]
    inefficient_months = [
        row["stay_month"]
        for row in rows
        if row["cleaning_efficiency_status"] == "inefficient"
        and row["revenue_pace_status"] != "partial_horizon"
    ]

    if current:
        bullets.append(
            f"Current month {current['stay_month']} revenue pace is {current['revenue_pace_status']}."
        )
    if next_month:
        bullets.append(f"Next month {next_month['stay_month']} revenue pace is {next_month['revenue_pace_status']}.")
    if protected_far_out:
        months = ", ".join(row["stay_month"] for row in protected_far_out)
        bullets.append(f"Far-out open value is protected in {months}.")
    if inefficient_months:
        bullets.append(f"Cleaning efficiency concern in {', '.join(inefficient_months)}.")
    bullets.append("Market benchmark is context only.")
    return bullets[:5]


def build_markdown(run_date: str, rows: list[dict[str, str]]) -> str:
    sorted_rows = sorted(rows, key=lambda row: row["stay_month"])
    lines = [
        f"# Monthly Revenue Summary - {run_date}",
        "",
        "## Executive Summary",
        "",
    ]
    lines.extend(f"- {bullet}" for bullet in build_executive_summary(sorted_rows))
    lines.extend(
        [
            "",
            "## Monthly Revenue Pace",
            "",
            "| Month | Bucket | Scope | Booked Revenue | Open Ask | Total Future Value | Target | Booked % | Total % | Revenue Status | Cleaning Status | Action Level |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )

    for row in sorted_rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    row["stay_month"],
                    row["month_time_bucket"],
                    row["month_scope_status"],
                    format_currency(row["booked_revenue_proxy"]),
                    format_currency(row["open_revenue_ask"]),
                    format_currency(row["total_future_revenue_proxy"]),
                    format_currency(row["monthly_target"]),
                    format_percent(row["booked_revenue_pct_of_target"]),
                    format_percent(row["total_future_revenue_pct_of_target"]),
                    row["revenue_pace_status"],
                    row["cleaning_efficiency_status"],
                    row["month_action_level"],
                )
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Key Diagnostics",
            "",
            "- `conversion_risk` means enough total future value exists, but booked revenue is still low.",
            "- `protect_open_value` means far-out calendar value is healthy and should not be pushed too early.",
            "- `partial_horizon` means only part of the month is inside the current future export window, so it is not judged against the full monthly target.",
            "- `inefficient` cleaning status means booked revenue per cleaning is below the current efficiency threshold.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run() -> int:
    args = parse_args()
    monthly_path = Path(args.monthly_file or f"analysis/monthly_revenue_pace_{args.run_date}.csv")
    output_path = Path(args.output_file or f"analysis/monthly_revenue_summary_{args.run_date}.md")

    rows = read_monthly_rows(monthly_path)
    write_markdown(output_path, build_markdown(args.run_date, rows))
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
