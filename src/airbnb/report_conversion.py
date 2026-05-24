"""Generate a neutral Airbnb conversion diagnostic markdown report."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


FORBIDDEN_RECOMMENDATION_PHRASES = (
    "pricelabs rule change",
    "change pricelabs",
    "pricing problem",
    "market weakness",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Airbnb conversion diagnostic markdown report.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--summary-file", help="Weekly Airbnb conversion summary CSV.")
    parser.add_argument("--daily-file", help="Daily Airbnb week-over-week CSV.")
    parser.add_argument("--daily-average-file", help="Daily Airbnb weekly-average deviation CSV.")
    parser.add_argument("--history-file", help="Airbnb retained weekly history comparison CSV.")
    parser.add_argument("--similar-summary-file", help="Airbnb similar-listing summary CSV.")
    parser.add_argument("--similar-daily-file", help="Airbnb daily similar-listing comparison CSV.")
    parser.add_argument("--output-file", help="Markdown report output path.")
    return parser.parse_args(argv)


def default_summary_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv"


def default_daily_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_daily_week_over_week_conversion_{run_date}.csv"


def default_history_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_weekly_history_comparison_{run_date}.csv"


def default_daily_average_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_daily_week_average_deviation_{run_date}.csv"


def default_similar_summary_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_similar_listing_summary_{run_date}.csv"


def default_similar_daily_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_daily_similar_listing_comparison_{run_date}.csv"


def default_output_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"airbnb_conversion_diagnostic_report_{run_date}.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def read_required_summary(path: Path, run_date: str) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing Airbnb weekly summary. Run: python -m airbnb.summarize_conversion --run-date {run_date}"
        )
    rows = read_csv(path)
    usable_rows = [row for row in rows if any(value for value in row.values())]
    if not usable_rows:
        raise ValueError(
            f"Airbnb weekly summary has no usable row. Run: python -m airbnb.summarize_conversion --run-date {run_date}"
        )
    return usable_rows


def numeric(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value.rstrip("%"))
    except ValueError:
        return None


def format_change(row: dict[str, str]) -> str:
    pct = row.get("percent_change_vs_previous_week", "")
    pct_text = f" ({pct}%)" if pct else ""
    return (
        f"{row.get('report_date', '-')} {row.get('weekday', '')}: "
        f"{row.get('current_value', '-')} vs {row.get('previous_week_value', '-')} "
        f"({row.get('change_vs_previous_week', '-')}{pct_text})"
    ).strip()


def daily_extremes(rows: list[dict[str, str]], metric_page: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    metric_rows = [row for row in rows if row.get("airbnb_metric_page") == metric_page and numeric(row.get("change_vs_previous_week", "")) is not None]
    sorted_rows = sorted(metric_rows, key=lambda row: numeric(row.get("change_vs_previous_week", "")) or 0)
    drops = [row for row in sorted_rows if (numeric(row.get("change_vs_previous_week", "")) or 0) < 0][:3]
    improvements = [row for row in reversed(sorted_rows) if (numeric(row.get("change_vs_previous_week", "")) or 0) > 0][:3]
    return drops, improvements


def weekly_row(summary_rows: list[dict[str, str]]) -> dict[str, str]:
    return summary_rows[0] if summary_rows else {}


def history_context(history_rows: list[dict[str, str]]) -> dict[str, str]:
    statuses = {row.get("history_quality_status", "") for row in history_rows}
    if "recent_baseline_ready" in statuses:
        return {"has_recent_history_baseline": "true", "diagnostic_confidence": "high"}
    if statuses.intersection({"previous_week_only", "limited_history"}):
        return {"has_recent_history_baseline": "false", "diagnostic_confidence": "medium"}
    return {"has_recent_history_baseline": "false", "diagnostic_confidence": ""}


def history_by_metric(history_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("metric_name", ""): row for row in history_rows}


def weekly_signal_lines(row: dict[str, str], history_rows: list[dict[str, str]] | None = None) -> list[str]:
    history = history_by_metric(history_rows or [])
    fields = [
        ("Page views", "page_views", "page_views_change_vs_previous_week"),
        ("First-page search impressions", "first_page_search_impressions", "first_page_search_impressions_change_vs_previous_week"),
        ("Wishlist additions", "wishlist_additions", "wishlist_additions_change_vs_previous_week"),
        ("Average overall conversion rate", "average_overall_conversion_rate", "overall_conversion_change_vs_previous_week"),
        ("First-page search impression rate", "first_page_search_impression_rate", ""),
        ("Search-to-listing conversion rate", "search_to_listing_conversion_rate", "search_to_listing_change_vs_previous_week"),
        ("Listing-to-booking conversion rate", "listing_to_booking_conversion_rate", "listing_to_booking_change_vs_previous_week"),
    ]
    lines = []
    for label, value_key, change_key in fields:
        value = row.get(value_key, "") or "-"
        history_row = history.get(value_key, {})
        change = history_row.get("change_vs_previous_week", "") or (row.get(change_key, "") if change_key else "")
        last_4_week_avg = history_row.get("last_4_week_avg", "") or "-"
        change_vs_last_4_week_avg = history_row.get("change_vs_last_4_week_avg", "") or "-"
        lines.append(f"| {label} | {value} | {change or '-'} | {last_4_week_avg} | {change_vs_last_4_week_avg} |")
    return lines


def neutral_note(row: dict[str, str]) -> str:
    if row.get("diagnostic_confidence") == "low" or row.get("comparison_type") == "none":
        return "Interpretation is limited because comparison data is missing or incomplete."
    page_views_change = numeric(row.get("page_views_change_vs_previous_week", ""))
    intent_changes = [
        numeric(row.get("wishlist_additions_change_vs_previous_week", "")),
        numeric(row.get("search_to_listing_change_vs_previous_week", "")),
        numeric(row.get("listing_to_booking_change_vs_previous_week", "")),
    ]
    mixed_intent = any(value is not None and value >= 0 for value in intent_changes) and any(value is not None and value < 0 for value in intent_changes)
    if page_views_change is not None and page_views_change < 0 and mixed_intent:
        return "Airbnb visibility declined versus the prior week, while guest-intent/conversion signals were mixed."
    return "Airbnb conversion signals are available for the selected week; PriceLabs market context is required before assigning cause."


def average_deviation_extremes(rows: list[dict[str, str]], metric_page: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    metric_rows = [
        row
        for row in rows
        if row.get("airbnb_metric_page") == metric_page and numeric(row.get("difference_vs_week_avg", "")) is not None
    ]
    sorted_rows = sorted(metric_rows, key=lambda row: numeric(row.get("difference_vs_week_avg", "")) or 0)
    below = [row for row in sorted_rows if (numeric(row.get("difference_vs_week_avg", "")) or 0) < 0][:3]
    above = [row for row in reversed(sorted_rows) if (numeric(row.get("difference_vs_week_avg", "")) or 0) > 0][:3]
    return below, above


def format_average_deviation(row: dict[str, str]) -> str:
    pct = row.get("percent_difference_vs_week_avg", "")
    pct_text = f" ({pct}%)" if pct else ""
    return (
        f"{row.get('report_date', '-')} {row.get('weekday', '')}: "
        f"{row.get('daily_value', '-')} vs avg {row.get('current_week_avg', '-')} "
        f"({row.get('difference_vs_week_avg', '-')}{pct_text})"
    ).strip()


def similar_summary_lines(rows: list[dict[str, str]]) -> list[str]:
    lines = []
    for row in rows:
        if row.get("data_quality_status") not in {"parsed", "partial"}:
            continue
        if not row.get("current_value") and not row.get("similar_listing_value"):
            continue
        label = row.get("metric_name", row.get("airbnb_metric_page", "-"))
        lines.append(
            "| "
            + " | ".join(
                [
                    label,
                    row.get("current_value", "") or "-",
                    row.get("similar_listing_value", "") or "-",
                    row.get("difference_vs_similar_listings", "") or "-",
                    row.get("percent_difference_vs_similar_listings", "") or "-",
                ]
            )
            + " |"
        )
    return lines


def similar_daily_extremes(rows: list[dict[str, str]], metric_page: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    metric_rows = [
        row
        for row in rows
        if row.get("airbnb_metric_page") == metric_page and numeric(row.get("difference_vs_similar_listings", "")) is not None
    ]
    sorted_rows = sorted(metric_rows, key=lambda row: numeric(row.get("difference_vs_similar_listings", "")) or 0)
    below = [row for row in sorted_rows if (numeric(row.get("difference_vs_similar_listings", "")) or 0) < 0][:3]
    above = [row for row in reversed(sorted_rows) if (numeric(row.get("difference_vs_similar_listings", "")) or 0) > 0][:3]
    return below, above


def format_similar_daily(row: dict[str, str]) -> str:
    pct = row.get("percent_difference_vs_similar_listings", "")
    pct_text = f" ({pct}%)" if pct else ""
    return (
        f"{row.get('report_date', '-')} {row.get('weekday', '')}: "
        f"{row.get('your_value', '-')} vs similar {row.get('similar_listing_value', '-')} "
        f"({row.get('difference_vs_similar_listings', '-')}{pct_text})"
    ).strip()


def render_report(
    run_date: str,
    summary_rows: list[dict[str, str]],
    daily_rows: list[dict[str, str]],
    history_rows: list[dict[str, str]] | None = None,
    daily_average_rows: list[dict[str, str]] | None = None,
    similar_summary_rows: list[dict[str, str]] | None = None,
    similar_daily_rows: list[dict[str, str]] | None = None,
) -> str:
    row = dict(weekly_row(summary_rows))
    context = history_context(history_rows or [])
    if context.get("diagnostic_confidence"):
        row["diagnostic_confidence"] = context["diagnostic_confidence"]
    row["has_recent_history_baseline"] = context["has_recent_history_baseline"]
    lines = [
        f"# Airbnb Conversion Diagnostic Report - {run_date}",
        "",
        "## Airbnb Diagnostic Snapshot",
        "",
        f"- Metric window: {row.get('metric_window_start', '-') or '-'} to {row.get('metric_window_end', '-') or '-'}",
        f"- Comparison window: {row.get('comparison_window_start', '-') or '-'} to {row.get('comparison_window_end', '-') or '-'}",
        f"- Data quality status: {row.get('airbnb_data_quality_status', '-') or '-'}",
        f"- Diagnostic confidence: {row.get('diagnostic_confidence', '-') or '-'}",
        f"- Recent history baseline: {row.get('has_recent_history_baseline', '-') or '-'}",
        f"- Parsed metric pages: {row.get('parsed_metric_pages', '-') or '-'}",
        "",
        "## Weekly Funnel Signals",
        "",
        "| Signal | Value | WoW Change | 4-Week Avg | vs 4-Week Avg |",
        "| --- | ---: | ---: | ---: | ---: |",
        *weekly_signal_lines(row, history_rows or []),
        "",
        "## Daily Week-over-Week Movement",
        "",
    ]
    for metric_page in ("page_views", "wishlist_additions", "booking_conversion"):
        drops, improvements = daily_extremes(daily_rows, metric_page)
        lines.append(f"### {metric_page}")
        if not drops and not improvements:
            lines.append("- Daily movement is unavailable because no paired daily comparison rows were found.")
        else:
            lines.append("- Largest drops:")
            lines.extend(f"  - {format_change(item)}" for item in drops) if drops else lines.append("  - None")
            lines.append("- Largest improvements:")
            lines.extend(f"  - {format_change(item)}" for item in improvements) if improvements else lines.append("  - None")
        lines.append("")
    lines.append("## Daily Movement vs Weekly Average")
    lines.append("")
    for metric_page in ("page_views", "wishlist_additions", "booking_conversion"):
        below, above = average_deviation_extremes(daily_average_rows or [], metric_page)
        lines.append(f"### {metric_page}")
        if not below and not above:
            lines.append("- Daily weekly-average deviation rows are unavailable.")
        else:
            lines.append("- Largest below-average days:")
            lines.extend(f"  - {format_average_deviation(item)}" for item in below) if below else lines.append("  - None")
            lines.append("- Largest above-average days:")
            lines.extend(f"  - {format_average_deviation(item)}" for item in above) if above else lines.append("  - None")
        lines.append("")
    lines.append("## Similar Listings Benchmark")
    lines.append("")
    summary_lines = similar_summary_lines(similar_summary_rows or [])
    if summary_lines:
        lines.append("| Signal | Your Value | Similar Listings | Difference | % Difference |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        lines.extend(summary_lines)
    else:
        lines.append("- Similar-listing benchmark rows are unavailable.")
    lines.append("")
    lines.append("## Daily Similar Listings Movement")
    lines.append("")
    for metric_page in ("page_views", "wishlist_additions", "booking_conversion"):
        below, above = similar_daily_extremes(similar_daily_rows or [], metric_page)
        lines.append(f"### {metric_page}")
        if not below and not above:
            lines.append("- Daily similar-listing comparison rows are unavailable.")
        else:
            lines.append("- Largest days below similar listings:")
            lines.extend(f"  - {format_similar_daily(item)}" for item in below) if below else lines.append("  - None")
            lines.append("- Largest days above similar listings:")
            lines.extend(f"  - {format_similar_daily(item)}" for item in above) if above else lines.append("  - None")
        lines.append("")
    lines.extend(
        [
            "## Neutral Diagnostic Notes",
            "",
            f"- {neutral_note(row)}",
            "- These daily deviations show intra-week movement only. PriceLabs market context is required before assigning cause.",
            "- Similar listings data is an Airbnb diagnostic benchmark only. Do not infer revenue performance, occupancy, ADR, or PriceLabs rule changes from this data alone.",
            "- Do not infer a pricing issue or market cause from Airbnb data alone.",
            "- PriceLabs market context is required before assigning cause.",
            "",
            "## Data Boundary",
            "",
            "Airbnb data is used only for visibility and conversion diagnostics. PriceLabs remains the source of truth for occupancy, ADR, revenue, booked nights, booking totals, cleaning count, and monthly revenue pace.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_report_text(text: str) -> None:
    lower = text.lower()
    for phrase in FORBIDDEN_RECOMMENDATION_PHRASES:
        if phrase in lower and phrase not in {"pricing problem", "market weakness"}:
            raise ValueError(f"Airbnb report includes forbidden recommendation wording: {phrase}")


def write_report(path: Path, text: str) -> None:
    if not text.startswith("# Airbnb Conversion Diagnostic Report"):
        raise ValueError("Airbnb markdown report must start with its markdown title.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as report_file:
        report_file.write(text)


def run(
    run_date: str,
    *,
    run_dir: Path | None = None,
    summary_file: Path | None = None,
    daily_file: Path | None = None,
    daily_average_file: Path | None = None,
    history_file: Path | None = None,
    similar_summary_file: Path | None = None,
    similar_daily_file: Path | None = None,
    output_file: Path | None = None,
) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    resolved_summary = summary_file or default_summary_path(resolved_run_dir, run_date)
    resolved_daily = daily_file or default_daily_path(resolved_run_dir, run_date)
    resolved_daily_average = daily_average_file or default_daily_average_path(resolved_run_dir, run_date)
    resolved_history = history_file or default_history_path(resolved_run_dir, run_date)
    resolved_similar_summary = similar_summary_file or default_similar_summary_path(resolved_run_dir, run_date)
    resolved_similar_daily = similar_daily_file or default_similar_daily_path(resolved_run_dir, run_date)
    resolved_output = output_file or default_output_path(resolved_run_dir, run_date)
    text = render_report(
        run_date,
        read_required_summary(resolved_summary, run_date),
        read_csv(resolved_daily),
        read_csv(resolved_history),
        read_csv(resolved_daily_average),
        read_csv(resolved_similar_summary),
        read_csv(resolved_similar_daily),
    )
    write_report(resolved_output, text)
    return resolved_output


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        summary_file=Path(args.summary_file) if args.summary_file else None,
        daily_file=Path(args.daily_file) if args.daily_file else None,
        daily_average_file=Path(args.daily_average_file) if args.daily_average_file else None,
        history_file=Path(args.history_file) if args.history_file else None,
        similar_summary_file=Path(args.similar_summary_file) if args.similar_summary_file else None,
        similar_daily_file=Path(args.similar_daily_file) if args.similar_daily_file else None,
        output_file=Path(args.output_file) if args.output_file else None,
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
