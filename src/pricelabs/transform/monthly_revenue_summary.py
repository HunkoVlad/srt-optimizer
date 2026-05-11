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
    "month_window_position",
    "data_availability",
    "days_in_scope",
    "month_time_bucket",
    "month_scope_status",
    "booked_nights",
    "booked_revenue_proxy",
    "open_revenue_ask",
    "total_future_revenue_proxy",
    "monthly_target",
    "booked_revenue_pct_of_target",
    "total_future_revenue_pct_of_target",
    "revenue_per_cleaning_proxy",
    "revenue_pace_status",
    "cleaning_efficiency_status",
    "month_action_level",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Markdown monthly revenue summary.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--rolling-file",
        help="Rolling 13-month revenue view CSV. Defaults to analysis/rolling_13_month_revenue_view_<run-date>.csv.",
    )
    parser.add_argument(
        "--monthly-file",
        help="Deprecated alias for --rolling-file.",
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
    if not value.strip():
        return "-"
    amount = parse_decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,}"


def format_percent(value: str) -> str:
    if not value.strip():
        return "-"
    pct = (parse_decimal(value) * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{pct}%"


def format_percent_value(value: str) -> str:
    if not value.strip():
        return "-"
    pct = parse_decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{pct}%"


def divide_currency(numerator: str, denominator: str) -> str:
    denominator_value = parse_decimal(denominator)
    if denominator_value == 0:
        return "-"
    amount = (parse_decimal(numerator) / denominator_value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,}"


def divide_percent(numerator: str, denominator: str) -> str:
    denominator_value = parse_decimal(denominator)
    if denominator_value == 0:
        return "-"
    pct = (parse_decimal(numerator) / denominator_value * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return f"{pct}%"


def historical_total_revenue(row: dict[str, str]) -> str:
    return row.get("historical_total_revenue", "")


def historical_booked_nights(row: dict[str, str]) -> str:
    return row.get("historical_booked_nights", "")


def historical_rental_adr(row: dict[str, str]) -> str:
    return row.get("historical_rental_adr", "")


def historical_occupancy(row: dict[str, str]) -> str:
    return row.get("historical_calendar_occupancy_pct", "")


def table_booked_revenue(row: dict[str, str]) -> str:
    if row["data_availability"] == "historical_actuals":
        return format_currency(historical_total_revenue(row))
    return format_currency(row["booked_revenue_proxy"])


def table_open_ask(row: dict[str, str]) -> str:
    if row["data_availability"] == "historical_actuals":
        return "-"
    return format_currency(row["open_revenue_ask"])


def table_total_future_value(row: dict[str, str]) -> str:
    if row["data_availability"] == "historical_actuals":
        return format_currency(historical_total_revenue(row))
    return format_currency(row["total_future_revenue_proxy"])


def table_booked_nights(row: dict[str, str]) -> str:
    if row["data_availability"] == "historical_actuals":
        return historical_booked_nights(row) or "-"
    return row.get("booked_nights", "") or "-"


def table_occupancy(row: dict[str, str]) -> str:
    if row["data_availability"] == "historical_actuals":
        return format_percent_value(historical_occupancy(row))
    if (
        row["data_availability"] == "available"
        and row["month_window_position"] == "future"
        and row["month_scope_status"] == "full_month"
    ):
        return divide_percent(row.get("booked_nights", ""), row.get("days_in_scope", ""))
    return "-"


def table_adr(row: dict[str, str]) -> str:
    if row["data_availability"] == "historical_actuals":
        return format_currency(historical_rental_adr(row))
    return divide_currency(row.get("booked_revenue_proxy", ""), row.get("booked_nights", ""))


def table_revenue_per_cleaning(row: dict[str, str]) -> str:
    if row["data_availability"] == "historical_actuals":
        return "-"
    return format_currency(row.get("revenue_per_cleaning_proxy", ""))


def find_row(rows: list[dict[str, str]], bucket: str) -> dict[str, str] | None:
    return next(
        (
            row
            for row in rows
            if row["data_availability"] == "available" and row["month_time_bucket"] == bucket
        ),
        None,
    )


def build_executive_summary(rows: list[dict[str, str]]) -> list[str]:
    bullets: list[str] = []
    available_rows = [row for row in rows if row["data_availability"] == "available"]
    historical_no_source = [
        row
        for row in rows
        if row["month_window_position"] == "historical"
        and row["data_availability"] == "no_source_data"
    ]
    historical_actuals = [
        row
        for row in rows
        if row["month_window_position"] == "historical"
        and row["data_availability"] == "historical_actuals"
    ]
    current = find_row(available_rows, "current_month")
    next_month = find_row(available_rows, "next_month")
    protected_far_out = [
        row
        for row in available_rows
        if row["month_time_bucket"] in {"future_month", "far_future_month"}
        and row["revenue_pace_status"] == "protect_open_value"
    ]
    inefficient_months = [
        row["stay_month"]
        for row in available_rows
        if row["cleaning_efficiency_status"] == "inefficient"
        and row["revenue_pace_status"] != "partial_horizon"
    ]

    if historical_actuals:
        months = ", ".join(row["stay_month"] for row in historical_actuals)
        if historical_no_source:
            bullets.append(
                f"Historical actuals are available for {months}; missing historical months remain no_source_data."
            )
        else:
            bullets.append(f"Historical actuals are available for {months}.")
    elif historical_no_source:
        bullets.append("Historical months without source data are shown for context.")
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
    bullets = bullets[:4]
    bullets.append("Market benchmark is context only.")
    return bullets


def available_rows_for_action(rows: list[dict[str, str]], action_level: str) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row["data_availability"] == "available"
        and row["month_action_level"] == action_level
    ]


def build_action_lines(rows: list[dict[str, str]], action_level: str) -> list[str]:
    action_rows = available_rows_for_action(rows, action_level)
    if action_level == "monitor":
        action_rows = [
            row
            for row in action_rows
            if row["revenue_pace_status"] != "partial_horizon"
        ]
    if not action_rows:
        return ["- None."]

    lines = []
    for row in action_rows:
        if action_level in {"critical_now", "advisory"}:
            lines.append(
                "- "
                f"{row['stay_month']}: {row['revenue_pace_status']} - "
                f"booked {format_currency(row['booked_revenue_proxy'])}, "
                f"total calendar value {format_currency(row['total_future_revenue_proxy'])}, "
                f"cleaning {row['cleaning_efficiency_status']}."
            )
        elif action_level == "protect":
            lines.append(
                "- "
                f"{row['stay_month']}: {row['revenue_pace_status']} - "
                f"total calendar value {format_currency(row['total_future_revenue_proxy'])}."
            )
        else:
            lines.append(f"- {row['stay_month']}: {row['revenue_pace_status']}.")
    return lines


def build_executive_decision_view(rows: list[dict[str, str]]) -> list[str]:
    sections = [
        "## Executive Decision View",
        "",
        "### Critical Now",
        "",
        *build_action_lines(rows, "critical_now"),
        "",
        "### Advisory",
        "",
        *build_action_lines(rows, "advisory"),
        "",
        "### Protect",
        "",
        *build_action_lines(rows, "protect"),
        "",
        "### Monitor",
        "",
        *build_action_lines(rows, "monitor"),
        "",
    ]
    return sections


def build_interpretation(rows: list[dict[str, str]]) -> list[str]:
    lines = ["## Interpretation", ""]
    bullets: list[str] = []
    for row in rows:
        if row["data_availability"] == "historical_actuals":
            bullet = (
                "- "
                f"{row['stay_month']}: Historical actuals are available from PriceLabs KPI data: "
                f"total revenue {format_currency(historical_total_revenue(row))}, "
                f"booked nights {historical_booked_nights(row) or '-'}, "
                f"ADR {format_currency(historical_rental_adr(row))}."
            )
            if row.get("historical_data_quality_flag") == "suspicious":
                bullet += (
                    " Data quality flag: suspicious; review PriceLabs historical denominator "
                    "before using occupancy as final truth."
                )
            bullets.append(bullet)
            continue

        if row["data_availability"] != "available":
            continue

        if row["revenue_pace_status"] == "conversion_risk":
            bullets.append(
                "- "
                f"{row['stay_month']}: Booked revenue is low, but total calendar value is above target. "
                "This points to conversion risk rather than weak calendar value."
            )
        elif row["revenue_pace_status"] == "protect_open_value":
            bullets.append(
                "- "
                f"{row['stay_month']}: Open calendar value is healthy for a future month. "
                "This supports protecting premium positioning."
            )
        elif row["revenue_pace_status"] == "partial_horizon":
            bullets.append(
                "- "
                f"{row['stay_month']}: Only part of the month is inside the current export horizon, "
                "so it is not judged against the full monthly target."
            )

        if row["cleaning_efficiency_status"] == "inefficient":
            bullets.append(
                "- "
                f"{row['stay_month']}: Revenue per cleaning is below the current efficiency threshold, "
                "so booking quality should be monitored."
            )

    if not bullets:
        bullets.append("- None.")
    lines.extend(bullets)
    lines.append("")
    return lines


def rule_areas_text(rule_areas: tuple[str, ...]) -> str:
    if not rule_areas:
        return "none"
    return "; ".join(rule_areas)


def recommendation_for_row(row: dict[str, str]) -> str:
    month = row["stay_month"]
    bucket = row["month_time_bucket"]
    revenue_status = row["revenue_pace_status"]
    cleaning_status = row["cleaning_efficiency_status"]

    if bucket == "current_month" and revenue_status == "urgent":
        return (
            f"- {month}: Review current-month revenue weakness. "
            "Rule areas to review: "
            f"{rule_areas_text(('Booking Recency Factor', 'last-minute behavior', 'minimum stay rules'))}. "
            "Avoid automatic base price reduction."
        )
    if bucket == "current_month" and revenue_status == "conversion_risk" and cleaning_status == "inefficient":
        return (
            f"- {month}: Review near-term conversion behavior and booking quality before changing premium positioning. "
            "Rule areas to review: "
            f"{rule_areas_text(('Booking Recency Factor', 'last-minute behavior', '1-night LOS premium'))}. "
            "Avoid broad pricing pressure."
        )
    if bucket == "next_month" and revenue_status == "conversion_risk":
        return (
            f"- {month}: Monitor next-month conversion risk while protecting premium positioning. "
            "Rule areas to review: "
            f"{rule_areas_text(('Booking Recency Factor', 'minimum stay rules', '1-night LOS premium'))}. "
            "Avoid early pricing pressure."
        )
    if bucket == "future_month" and revenue_status == "protect_open_value":
        return (
            f"- {month}: Protect far-out open value; no PriceLabs rule change recommended now. "
            "Rule areas to review: far-out premium only if repeated weakness appears."
        )
    if bucket == "far_future_month" and revenue_status == "protect_open_value":
        return (
            f"- {month}: Protect far-out open value; no PriceLabs rule change recommended now. "
            "Rule areas to review: none unless repeated weak ask value appears."
        )
    if revenue_status == "partial_horizon":
        return f"- {month}: Monitor only; do not judge this partial horizon month against the full monthly target."
    return f"- {month}: Monitor existing diagnostic status."


def recommendation_rows(rows: list[dict[str, str]], action_level: str) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row["data_availability"] == "available"
        and row["month_action_level"] == action_level
    ]


def build_recommendation_lines(rows: list[dict[str, str]], action_level: str) -> list[str]:
    rows_for_action = recommendation_rows(rows, action_level)
    if not rows_for_action:
        return ["- None."]
    return [recommendation_for_row(row) for row in rows_for_action]


def build_recommendation_review(rows: list[dict[str, str]]) -> list[str]:
    return [
        "## Recommendation Review",
        "",
        "### Critical Now",
        "",
        *build_recommendation_lines(rows, "critical_now"),
        "",
        "### Advisory",
        "",
        *build_recommendation_lines(rows, "advisory"),
        "",
        "### Protect / No Change",
        "",
        *build_recommendation_lines(rows, "protect"),
        "",
        "### Monitor",
        "",
        *build_recommendation_lines(rows, "monitor"),
        "",
    ]


def build_markdown(run_date: str, rows: list[dict[str, str]]) -> str:
    sorted_rows = sorted(rows, key=lambda row: row["stay_month"])
    lines = [
        f"# Monthly Revenue Summary - {run_date}",
        "",
        "## Executive Summary",
        "",
    ]
    lines.extend(f"- {bullet}" for bullet in build_executive_summary(sorted_rows))
    lines.extend(["", *build_executive_decision_view(sorted_rows)])
    lines.extend(build_interpretation(sorted_rows))
    lines.extend(build_recommendation_review(sorted_rows))
    lines.extend(
        [
            "## Monthly Revenue Pace",
            "",
            "| Month | Position | Bucket | Scope | Data | Revenue Captured | Open Ask | Total Calendar Value | Target | Booked % | Total % | Booked Nights | Occupancy | ADR | Revenue / Cleaning | Revenue Status | Cleaning Status | Action Level |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )

    for row in sorted_rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    row["stay_month"],
                    row["month_window_position"],
                    row["month_time_bucket"],
                    row["month_scope_status"],
                    row["data_availability"],
                    table_booked_revenue(row),
                    table_open_ask(row),
                    table_total_future_value(row),
                    format_currency(row["monthly_target"]),
                    format_percent(row["booked_revenue_pct_of_target"]),
                    format_percent(row["total_future_revenue_pct_of_target"]),
                    table_booked_nights(row),
                    table_occupancy(row),
                    table_adr(row),
                    table_revenue_per_cleaning(row),
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
            "- `conversion_risk` means enough total calendar value exists, but booked revenue is still low.",
            "- `protect_open_value` means far-out calendar value is healthy and should not be pushed too early.",
            "- `historical_actuals` means the month was filled from PriceLabs KPI On The Books historical data.",
            "- `suspicious` means the historical KPI row passed through but has a data-quality warning, usually because the PriceLabs denominator looks unusual.",
            "- Historical occupancy is calculated from booked nights divided by calendar days in month for single-listing analysis.",
            "- Future full-month occupancy is calculated from booked nights divided by days in scope.",
            "- Current and partial horizon month occupancy is hidden to avoid misleading partial-month interpretation.",
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
    monthly_path = Path(
        args.rolling_file
        or args.monthly_file
        or f"analysis/rolling_13_month_revenue_view_{args.run_date}.csv"
    )
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
