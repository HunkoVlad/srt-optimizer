"""Parse Airbnb similar-listing benchmark HTML into diagnostic CSV outputs."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

from airbnb.parse_conversion_html import extract_dates, extract_title, normalize_metric_value, strip_tags


SUMMARY_COLUMNS = [
    "run_date",
    "metric_window_start",
    "metric_window_end",
    "airbnb_metric_page",
    "metric_name",
    "current_value",
    "similar_listing_value",
    "difference_vs_similar_listings",
    "percent_difference_vs_similar_listings",
    "benchmark_mode",
    "data_quality_status",
    "notes",
]

DAILY_COLUMNS = [
    "run_date",
    "metric_window_start",
    "metric_window_end",
    "report_date",
    "weekday",
    "airbnb_metric_page",
    "metric_name",
    "your_value",
    "similar_listing_value",
    "difference_vs_similar_listings",
    "percent_difference_vs_similar_listings",
    "benchmark_mode",
    "data_quality_status",
    "notes",
]

INPUT_SOURCES = (
    ("airbnb_booking_conversion_similar.html", "booking_conversion", "average_overall_conversion_rate"),
    ("airbnb_page_views_similar.html", "page_views", "page_views"),
    ("airbnb_wishlist_additions_similar.html", "wishlist_additions", "wishlist_additions"),
)

DISALLOWED_COLUMNS = {
    "adr",
    "occupancy",
    "revenue",
    "booked_nights",
    "booking_value",
    "total_bookings",
    "cleaning_count",
    "monthly_revenue_pace",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse Airbnb similar-listing benchmark HTML files.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--summary-output", help="Similar-listing summary output CSV.")
    parser.add_argument("--daily-output", help="Daily similar-listing comparison output CSV.")
    return parser.parse_args(argv)


def numeric(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value.rstrip("%"))
    except ValueError:
        return None


def format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def percent_difference(your_value: str, similar_value: str) -> str:
    your = numeric(your_value)
    similar = numeric(similar_value)
    if your is None or similar in {None, 0}:
        return ""
    return format_number(((your - similar) / similar) * 100)


def difference(your_value: str, similar_value: str) -> str:
    your = numeric(your_value)
    similar = numeric(similar_value)
    if your is None or similar is None:
        return ""
    return format_number(your - similar)


def is_real_similar_listing_html(html: str, text: str) -> bool:
    lower_html = html.lower()
    lower_text = text.lower()
    has_mode_signal = "ctype=market" in lower_html or "similar listings" in lower_text
    has_your_signal = "your listings" in lower_text or "your performance" in lower_text
    has_value_signal = bool(re.search(r"(?i)\byour listings\b\s*(?:=|:|-)?\s*[0-9]", text)) and bool(
        re.search(r"(?i)\bsimilar listings\b\s*(?:=|:|-)?\s*[0-9]", text)
    )
    has_daily_pair_signal = bool(
        re.search(r"(?i)\b[A-Za-z]{3,9}\.?\s+\d{1,2}\b[^\n\r]{0,120}\byour listings\b\s*(?:=|:|-)?\s*[0-9]", text)
        and re.search(r"(?i)\b[A-Za-z]{3,9}\.?\s+\d{1,2}\b[^\n\r]{0,120}\bsimilar listings\b\s*(?:=|:|-)?\s*[0-9]", text)
    )
    has_comparison_phrase = "higher than similar listings" in lower_text or "lower than similar listings" in lower_text
    return has_mode_signal and has_your_signal and (has_value_signal or has_daily_pair_signal or has_comparison_phrase)


def extract_summary_values(text: str) -> tuple[str, str]:
    your_match = re.search(r"(?i)\b(?:weekly|average|summary)\s+your listings\b\s*[:\-]?\s*([0-9][0-9,]*(?:\.[0-9]+)?%?)", text)
    similar_match = re.search(r"(?i)\b(?:weekly|average|summary)\s+similar listings\b\s*[:\-]?\s*([0-9][0-9,]*(?:\.[0-9]+)?%?)", text)
    return (
        normalize_metric_value(your_match.group(1)) if your_match else "",
        normalize_metric_value(similar_match.group(1)) if similar_match else "",
    )


def extract_daily_pairs(text: str, *, run_date: str) -> list[tuple[str, str, str]]:
    year = datetime.strptime(run_date, "%Y-%m-%d").year
    month_pattern = r"Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December"
    month_numbers = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }
    pattern = re.compile(
        rf"(?i)\b({month_pattern})\.?\s+(\d{{1,2}})\b(?!\s*(?:-|–|—|to))"
        rf"(?:(?!\b(?:{month_pattern})\.?\s+\d{{1,2}}\b).){{0,240}}?"
        rf"\byour listings\b\s*(?:=|:|-)?\s*([0-9][0-9,]*(?:\.[0-9]+)?%?)"
        rf"(?:(?!\b(?:{month_pattern})\.?\s+\d{{1,2}}\b).){{0,240}}?"
        rf"\bsimilar listings\b\s*(?:=|:|-)?\s*([0-9][0-9,]*(?:\.[0-9]+)?%?)"
    )
    pairs: list[tuple[str, str, str]] = []
    for match in pattern.finditer(text):
        month = month_numbers[match.group(1).lower().rstrip(".")]
        report_date = datetime(year, month, int(match.group(2))).strftime("%Y-%m-%d")
        pairs.append((report_date, normalize_metric_value(match.group(3)), normalize_metric_value(match.group(4))))
    if pairs:
        return pairs
    grouped: dict[str, dict[str, str]] = {}
    observation_pattern = re.compile(
        rf"(?i)\b({month_pattern})\.?\s+(\d{{1,2}})\b"
        rf"\s*(?:-|–|—|:)?\s*"
        rf"\b(?P<label>your listings|your performance|similar listings)\b"
        rf"\s*(?:=|:|-|–|—)?\s*"
        rf"(?P<value>[0-9][0-9,]*(?:\.[0-9]+)?%?)"
    )
    for match in observation_pattern.finditer(text):
        month = month_numbers[match.group(1).lower().rstrip(".")]
        report_date = datetime(year, month, int(match.group(2))).strftime("%Y-%m-%d")
        label = match.group("label").lower()
        key = "similar" if label == "similar listings" else "your"
        grouped.setdefault(report_date, {})[key] = normalize_metric_value(match.group("value"))
    for report_date in sorted(grouped):
        values = grouped[report_date]
        if values.get("your") and values.get("similar"):
            pairs.append((report_date, values["your"], values["similar"]))
    return pairs


def infer_window_from_daily_pairs(daily_pairs: list[tuple[str, str, str]]) -> tuple[str, str]:
    if not daily_pairs:
        return "", ""
    dates = sorted(day for day, _your, _similar in daily_pairs)
    return dates[0], dates[-1]


def average(values: list[str]) -> str:
    numbers = [numeric(value) for value in values]
    clean = [value for value in numbers if value is not None]
    if not clean:
        return ""
    return format_number(sum(clean) / len(clean))


def blank_summary(run_date: str, metric_page: str, metric_name: str, status: str, notes: str) -> dict[str, str]:
    row = {column: "" for column in SUMMARY_COLUMNS}
    row.update(
        {
            "run_date": run_date,
            "airbnb_metric_page": metric_page,
            "metric_name": metric_name,
            "benchmark_mode": "similar_listings",
            "data_quality_status": status,
            "notes": notes,
        }
    )
    return row


def parse_file(path: Path, *, run_date: str, metric_page: str, metric_name: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    if not path.exists():
        return blank_summary(run_date, metric_page, metric_name, "missing_source", "Optional Airbnb similar-listing HTML was not present."), []
    html = path.read_text(encoding="utf-8-sig", errors="replace")
    text = strip_tags(html)
    report_date, window_start, window_end, _ranges = extract_dates(html, text, run_date=run_date)
    if not is_real_similar_listing_html(html, text):
        row = blank_summary(run_date, metric_page, metric_name, "unsupported_structure", "No actual similar-listing benchmark values were found.")
        row["metric_window_start"] = window_start
        row["metric_window_end"] = window_end
        return row, []

    current_value, similar_value = extract_summary_values(text)
    daily_pairs = extract_daily_pairs(text, run_date=run_date)
    inferred_start, inferred_end = infer_window_from_daily_pairs(daily_pairs)
    window_start = window_start or inferred_start
    window_end = window_end or inferred_end
    notes = "Parsed Airbnb similar-listing benchmark values."
    if (not current_value or not similar_value) and daily_pairs:
        current_value = average([your_value for _day, your_value, _similar_value in daily_pairs])
        similar_value = average([similar_value for _day, _your_value, similar_value in daily_pairs])
        notes = "Summary calculated from daily similar-listing chart values."
    summary = blank_summary(run_date, metric_page, metric_name, "parsed", "Parsed Airbnb similar-listing benchmark values.")
    summary.update(
        {
            "metric_window_start": window_start,
            "metric_window_end": window_end,
            "current_value": current_value,
            "similar_listing_value": similar_value,
            "difference_vs_similar_listings": difference(current_value, similar_value),
            "percent_difference_vs_similar_listings": percent_difference(current_value, similar_value),
            "notes": notes,
        }
    )
    if not current_value or not similar_value:
        summary["data_quality_status"] = "partial"
        summary["notes"] = "Similar-listing mode detected, but weekly summary benchmark values were incomplete."
    daily_rows = []
    for day, your_value, day_similar_value in daily_pairs:
        weekday = datetime.strptime(day, "%Y-%m-%d").strftime("%A")
        daily_rows.append(
            {
                "run_date": run_date,
                "metric_window_start": window_start,
                "metric_window_end": window_end,
                "report_date": day,
                "weekday": weekday,
                "airbnb_metric_page": metric_page,
                "metric_name": metric_name,
                "your_value": your_value,
                "similar_listing_value": day_similar_value,
                "difference_vs_similar_listings": difference(your_value, day_similar_value),
                "percent_difference_vs_similar_listings": percent_difference(your_value, day_similar_value),
                "benchmark_mode": "similar_listings",
                "data_quality_status": "parsed",
                "notes": "Daily Airbnb similar-listing benchmark comparison only.",
            }
        )
    return summary, daily_rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    forbidden = [column for column in fieldnames if column in DISALLOWED_COLUMNS]
    if forbidden:
        raise ValueError(f"Airbnb similar-listing output includes disallowed truth fields: {', '.join(forbidden)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def cleanup_parsed_similar_html(parsed_sources: list[tuple[Path, str]]) -> None:
    for path, status in parsed_sources:
        if status == "parsed" and path.exists():
            path.unlink()
            print(f"Deleted parsed Airbnb similar-listing HTML: {path}")
        elif status != "missing_source":
            print(f"Kept Airbnb similar-listing HTML ({status}): {path}")


def run(
    run_date: str,
    *,
    run_dir: Path | None = None,
    summary_output: Path | None = None,
    daily_output: Path | None = None,
) -> tuple[Path, Path]:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    raw_dir = resolved_run_dir / "raw"
    summaries: list[dict[str, str]] = []
    daily_rows: list[dict[str, str]] = []
    parsed_sources: list[tuple[Path, str]] = []
    for filename, metric_page, metric_name in INPUT_SOURCES:
        source_path = raw_dir / filename
        summary, rows = parse_file(source_path, run_date=run_date, metric_page=metric_page, metric_name=metric_name)
        summaries.append(summary)
        daily_rows.extend(rows)
        parsed_sources.append((source_path, summary["data_quality_status"]))
    resolved_summary = summary_output or resolved_run_dir / "analysis" / f"airbnb_similar_listing_summary_{run_date}.csv"
    resolved_daily = daily_output or resolved_run_dir / "analysis" / f"airbnb_daily_similar_listing_comparison_{run_date}.csv"
    write_csv(resolved_summary, SUMMARY_COLUMNS, summaries)
    write_csv(resolved_daily, DAILY_COLUMNS, daily_rows)
    cleanup_parsed_similar_html(parsed_sources)
    return resolved_summary, resolved_daily


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary, daily = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        summary_output=Path(args.summary_output) if args.summary_output else None,
        daily_output=Path(args.daily_output) if args.daily_output else None,
    )
    print(f"Wrote {summary}")
    print(f"Wrote {daily}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
