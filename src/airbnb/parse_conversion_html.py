"""Manual Airbnb diagnostic HTML parser spike.

This module reads locally saved Airbnb diagnostic HTML files only. It does not
log in, download, scrape a live browser, or feed Airbnb values into revenue
pace. Airbnb output is conversion/visibility diagnostic data only.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from html import unescape
from pathlib import Path


COLUMNS = [
    "run_date",
    "report_date",
    "metric_window_start",
    "metric_window_end",
    "comparison_window_start",
    "comparison_window_end",
    "listing_name",
    "airbnb_metric_page",
    "page_views",
    "first_page_search_impressions",
    "similar_listing_page_views",
    "average_overall_conversion_rate",
    "similar_listing_overall_conversion_rate",
    "first_page_search_impression_rate",
    "search_to_listing_conversion_rate",
    "listing_to_booking_conversion_rate",
    "wishlist_additions",
    "similar_listing_wishlist_additions",
    "page_views_change_vs_previous_week",
    "wishlist_additions_change_vs_previous_week",
    "first_page_search_impressions_change_vs_previous_week",
    "overall_conversion_change_vs_previous_week",
    "search_to_listing_change_vs_previous_week",
    "listing_to_booking_change_vs_previous_week",
    "daily_chart_values_json",
    "source_file",
    "extraction_method",
    "data_quality_status",
    "notes",
]

DISALLOWED_OUTPUT_COLUMNS = {
    "adr",
    "occupancy",
    "revenue",
    "booked_nights",
    "booking_value",
    "total_bookings",
    "cleaning_count",
    "monthly_revenue_pace",
}

INPUT_SOURCES = (
    ("airbnb_booking_conversion_daily.html", "booking_conversion"),
    ("airbnb_page_views_daily.html", "page_views"),
    ("airbnb_wishlist_additions_daily.html", "wishlist_additions"),
)
TEMPORARY_AIRBNB_HTML_FILES = tuple(filename for filename, _metric_page in INPUT_SOURCES)

METRIC_LABELS = {
    "page_views": ("average page views", "page views", "listing page views", "views"),
    "first_page_search_impressions": (
        "average first-page search impressions",
        "first-page search impressions",
        "first page search impressions",
    ),
    "similar_listing_page_views": ("similar listing page views", "similar listings page views", "similar page views"),
    "average_overall_conversion_rate": ("average overall conversion rate", "overall conversion rate"),
    "similar_listing_overall_conversion_rate": ("similar listing overall conversion rate", "similar listings overall conversion rate"),
    "first_page_search_impression_rate": ("first-page search impression rate", "first page search impression rate"),
    "search_to_listing_conversion_rate": ("average search-to-listing conversion", "search-to-listing conversion rate", "search to listing conversion rate"),
    "listing_to_booking_conversion_rate": ("average listing-to-booking conversion", "listing-to-booking conversion rate", "listing to booking conversion rate"),
    "wishlist_additions": ("average wishlist additions", "wishlist additions", "wishlists"),
    "similar_listing_wishlist_additions": ("similar listing wishlist additions", "similar listings wishlist additions"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse locally saved Airbnb diagnostic HTML files.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument(
        "--output-file",
        help="Parsed output CSV. Defaults to data/runs/<run-date>/raw/airbnb_daily_conversion_parsed_<run-date>.csv.",
    )
    return parser.parse_args(argv)


def blank_row(run_date: str, metric_page: str, source_file: Path, status: str, notes: str) -> dict[str, str]:
    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "run_date": run_date,
            "airbnb_metric_page": metric_page,
            "source_file": str(source_file),
            "extraction_method": "manual_html",
            "data_quality_status": status,
            "notes": notes,
        }
    )
    return row


def strip_tags(html: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def inner_text(html_fragment: str) -> str:
    return strip_tags(html_fragment)


def data_value(html: str, key: str) -> str:
    patterns = [
        rf"""(?is)<[^>]+data-(?:airbnb-)?(?:metric|field)=["']{re.escape(key)}["'][^>]*>(.*?)</[^>]+>""",
        rf"""(?is)<[^>]+id=["']{re.escape(key)}["'][^>]*>(.*?)</[^>]+>""",
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return inner_text(match.group(1))
    attr_match = re.search(rf"""(?is)data-{re.escape(key)}=["']([^"']+)["']""", html)
    if attr_match:
        return unescape(attr_match.group(1)).strip()
    return ""


def extract_title(html: str, text: str) -> str:
    structured = data_value(html, "listing_name")
    if structured:
        return structured
    h1 = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", html)
    if h1:
        return inner_text(h1.group(1))
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if title:
        return inner_text(title.group(1))
    label = extract_label_value(text, ("listing name", "listing"))
    return label


def extract_label_value(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        pattern = (
            rf"(?i)\b{re.escape(label)}\b\s*[:\-]?\s*"
            r"([A-Za-z0-9][A-Za-z0-9 ._/%-]*?)\s*"
            r"(?=\b\d{4}-\d{2}-\d{2}\b|\b[A-Z][A-Za-z -]{2,}\s*[:\-]|\Z)"
        )
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" .")
    return ""


def extract_metric_value(html: str, text: str, metric: str) -> str:
    structured = data_value(html, metric)
    if structured:
        return normalize_metric_value(structured)
    if metric == "page_views":
        _change, total = extract_change_total_for_label(text, ("average page views",))
        if total:
            return total
    if metric == "first_page_search_impressions":
        _change, total = extract_change_total_for_label(text, ("average first-page search impressions", "average first page search impressions"))
        if total:
            return total
    if metric == "wishlist_additions":
        _change, total = extract_change_total_for_label(text, ("average wishlist additions",))
        if total:
            return total
    for label in METRIC_LABELS[metric]:
        pattern = rf"(?i)\b{re.escape(label)}\b\s*[:\-]\s*([0-9][0-9,]*(?:\.[0-9]+)?%?)"
        match = re.search(pattern, text)
        if match:
            return normalize_metric_value(match.group(1))
        pattern = rf"(?i)(?<![\d-])([0-9][0-9,]*(?:\.[0-9]+)?%?)\s+\b{re.escape(label)}\b"
        match = re.search(pattern, text)
        if match:
            return normalize_metric_value(match.group(1))
    return ""


def extract_change_total_for_label(text: str, labels: tuple[str, ...]) -> tuple[str, str]:
    for label in labels:
        table_match = re.search(
            rf"(?i)\b{re.escape(label)}\b(?P<body>.{{0,240}}?\bChange\b\s+\bTotal\b\s+(?P<change>-?[0-9][0-9,]*(?:\.[0-9]+)?%?)\s+(?P<total>-?[0-9][0-9,]*(?:\.[0-9]+)?%?))",
            text,
        )
        if table_match:
            return normalize_metric_value(table_match.group("change")), normalize_metric_value(table_match.group("total"))
        match = re.search(
            rf"(?i)\b{re.escape(label)}\b(?P<body>.{{0,240}}?\bTotal\b\s*(?:[:=\-]\s*)?(?P<value>-?[0-9][0-9,]*(?:\.[0-9]+)?%?))",
            text,
        )
        if match:
            return "", normalize_metric_value(match.group("value"))
    return "", ""


def extract_previous_week_sentence_change(text: str, metric_phrases: tuple[str, ...]) -> str:
    for phrase in metric_phrases:
        pattern = re.compile(
            rf"(?i)\b{re.escape(phrase)}\b.{{0,120}}?\b(?P<direction>up|down)\s+(?P<value>[0-9][0-9,]*(?:\.[0-9]+)?%?)\s+compared to the previous 7 days"
        )
        match = pattern.search(text)
        if match:
            value = normalize_metric_value(match.group("value"))
            if match.group("direction").lower() == "down" and not value.startswith("-"):
                return f"-{value}"
            return value
    return ""


def normalize_metric_value(value: str) -> str:
    stripped = value.strip().replace(",", "")
    pct = "%" if stripped.endswith("%") else ""
    stripped = stripped.rstrip("%").strip()
    return f"{stripped}{pct}" if stripped else ""


def extract_iso_dates_legacy(html: str, text: str) -> tuple[str, str, str]:
    report_date = data_value(html, "report_date") or extract_label_value(text, ("report date", "date"))
    window_start = data_value(html, "metric_window_start") or data_value(html, "window_start")
    window_end = data_value(html, "metric_window_end") or data_value(html, "window_end")
    range_match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|through|-|–)\s*(\d{4}-\d{2}-\d{2})", text)
    if range_match:
        window_start = window_start or range_match.group(1)
        window_end = window_end or range_match.group(2)
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if not report_date and iso_dates:
        report_date = iso_dates[-1]
    return report_date, window_start, window_end


MONTH_NUMBERS = {
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


def normalize_range_separators(text: str) -> str:
    return (
        text.replace("→", " to ")
        .replace("â†’", " to ")
        .replace("–", "-")
        .replace("—", "-")
        .replace("â€“", "-")
    )


def extract_named_date_ranges(text: str, *, run_date: str) -> list[tuple[str, str]]:
    year = datetime.strptime(run_date, "%Y-%m-%d").year
    months = "|".join(sorted(MONTH_NUMBERS, key=len, reverse=True))
    pattern = re.compile(
        rf"\b({months})\.?\s+(\d{{1,2}})\s*(?:to|-)\s*(?:({months})\.?\s*)?(\d{{1,2}})\b",
        re.IGNORECASE,
    )
    ranges: list[tuple[str, str]] = []
    for match in pattern.finditer(normalize_range_separators(text)):
        start_month = MONTH_NUMBERS[match.group(1).lower().rstrip(".")]
        end_month = MONTH_NUMBERS[(match.group(3) or match.group(1)).lower().rstrip(".")]
        start = datetime(year, start_month, int(match.group(2)))
        end = datetime(year, end_month, int(match.group(4)))
        ranges.append((start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
    return ranges


def validate_sunday_to_sunday(start_date: str, end_date: str) -> str:
    if not start_date or not end_date:
        return "date range missing; expected a selected Sunday-to-Sunday weekly range."
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return "date range could not be parsed as ISO dates."
    issues = []
    if start.weekday() != 6:
        issues.append("start date is not Sunday")
    if end.weekday() != 6:
        issues.append("end date is not Sunday")
    if (end - start).days != 7:
        issues.append("range is not one full week")
    return "; ".join(issues)


def extract_dates(html: str, text: str, *, run_date: str) -> tuple[str, str, str, list[tuple[str, str]]]:
    report_date = data_value(html, "report_date") or extract_label_value(text, ("report date", "date"))
    window_start = data_value(html, "metric_window_start") or data_value(html, "window_start")
    window_end = data_value(html, "metric_window_end") or data_value(html, "window_end")
    normalized_text = normalize_range_separators(text)
    range_match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:to|through|-)\s*(\d{4}-\d{2}-\d{2})", normalized_text)
    if range_match:
        window_start = window_start or range_match.group(1)
        window_end = window_end or range_match.group(2)
    named_ranges = extract_named_date_ranges(text, run_date=run_date)
    if named_ranges:
        window_start = window_start or named_ranges[0][0]
        window_end = window_end or named_ranges[0][1]
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if not report_date and iso_dates:
        report_date = iso_dates[-1]
    return report_date, window_start, window_end, named_ranges


def previous_comparison_range(
    chart_ranges: list[tuple[str, str]],
    metric_window_start: str,
    metric_window_end: str,
) -> tuple[str, str]:
    for start, end in chart_ranges:
        if start == metric_window_start and end == metric_window_end:
            continue
        return start, end
    return "", ""


def extract_daily_chart_values(html: str, *, run_date: str) -> str:
    dl_match = re.search(r"(?is)<dl[^>]*>(.*?)</dl>", html)
    if not dl_match:
        return ""
    pairs = re.findall(r"(?is)<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", dl_match.group(1))
    if not pairs:
        return ""
    year = datetime.strptime(run_date, "%Y-%m-%d").year
    values = []
    for raw_date, raw_value in pairs:
        date_text = inner_text(raw_date)
        value = normalize_metric_value(inner_text(raw_value))
        match = re.search(r"(?i)\b([A-Za-z]{3,9})\.?\s+(\d{1,2})\b", date_text)
        if not match or not value:
            continue
        month = MONTH_NUMBERS.get(match.group(1).lower().rstrip("."))
        if not month:
            continue
        parsed_date = datetime(year, month, int(match.group(2))).strftime("%Y-%m-%d")
        values.append({"date": parsed_date, "value": value})
    return json.dumps(values, separators=(",", ":")) if values else ""


def parse_airbnb_html(html: str, *, run_date: str, metric_page: str, source_file: Path) -> dict[str, str]:
    text = strip_tags(html)
    row = blank_row(run_date, metric_page, source_file, "unsupported_structure", "No recognizable Airbnb diagnostic metrics found.")
    report_date, window_start, window_end, chart_ranges = extract_dates(html, text, run_date=run_date)
    row["report_date"] = report_date
    row["metric_window_start"] = window_start
    row["metric_window_end"] = window_end
    comparison_start, comparison_end = previous_comparison_range(chart_ranges, window_start, window_end)
    row["comparison_window_start"] = comparison_start
    row["comparison_window_end"] = comparison_end
    row["listing_name"] = extract_title(html, text)
    row["daily_chart_values_json"] = extract_daily_chart_values(html, run_date=run_date)

    metric_count = 0
    for metric in METRIC_LABELS:
        value = extract_metric_value(html, text, metric)
        row[metric] = value
        if value:
            metric_count += 1
    change_mappings = {
        "page_views_change_vs_previous_week": ("average page views",),
        "first_page_search_impressions_change_vs_previous_week": (
            "average first-page search impressions",
            "average first page search impressions",
        ),
        "wishlist_additions_change_vs_previous_week": ("average wishlist additions",),
        "overall_conversion_change_vs_previous_week": ("average overall conversion rate", "overall conversion rate"),
        "search_to_listing_change_vs_previous_week": (
            "average search-to-listing conversion",
            "search-to-listing conversion rate",
            "search to listing conversion rate",
        ),
        "listing_to_booking_change_vs_previous_week": (
            "average listing-to-booking conversion",
            "listing-to-booking conversion rate",
            "listing to booking conversion rate",
        ),
    }
    for field, labels in change_mappings.items():
        change, _total = extract_change_total_for_label(text, labels)
        row[field] = change
    sentence_change_mappings = {
        "page_views_change_vs_previous_week": ("total page views", "page views"),
        "wishlist_additions_change_vs_previous_week": ("total wishlist additions", "wishlist additions"),
    }
    for field, phrases in sentence_change_mappings.items():
        if not row[field]:
            row[field] = extract_previous_week_sentence_change(text, phrases)

    if metric_count:
        row["data_quality_status"] = "parsed" if row["listing_name"] and (report_date or window_start) else "partial"
        notes = [f"Parsed {metric_count} Airbnb diagnostic metric(s) from saved HTML."]
        date_warning = validate_sunday_to_sunday(window_start, window_end)
        if date_warning:
            row["data_quality_status"] = "date_range_warning"
            notes.append(date_warning)
        if len(chart_ranges) > 1:
            formatted = ", ".join(f"{start} to {end}" for start, end in chart_ranges[:3])
            notes.append(f"Chart legend ranges detected: {formatted}.")
        row["notes"] = " ".join(notes)
    return row


def rows_for_run(run_date: str, run_dir: Path) -> list[dict[str, str]]:
    raw_dir = run_dir / "raw"
    rows: list[dict[str, str]] = []
    for filename, metric_page in INPUT_SOURCES:
        source_file = raw_dir / filename
        if not source_file.exists():
            rows.append(blank_row(run_date, metric_page, source_file, "missing_source", "Optional Airbnb diagnostic HTML was not present."))
            continue
        html = source_file.read_text(encoding="utf-8-sig", errors="replace")
        rows.append(parse_airbnb_html(html, run_date=run_date, metric_page=metric_page, source_file=source_file))
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    forbidden = [column for column in COLUMNS if column in DISALLOWED_OUTPUT_COLUMNS]
    if forbidden:
        raise ValueError(f"Airbnb diagnostic output includes disallowed truth fields: {', '.join(forbidden)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_existing_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def legacy_analysis_output_path(run_dir: Path, run_date: str) -> Path:
    # Deprecated: detailed Airbnb extraction used to live under analysis/.
    # Use it only as a migration source when the new raw parsed CSV is absent.
    return run_dir / "analysis" / f"airbnb_daily_conversion_{run_date}.csv"


def existing_rows_for_preservation(parsed_output: Path, run_dir: Path, run_date: str) -> list[dict[str, str]]:
    if parsed_output.exists():
        return read_existing_rows(parsed_output)
    return read_existing_rows(legacy_analysis_output_path(run_dir, run_date))


def merge_with_existing_rows(new_rows: list[dict[str, str]], existing_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    existing_by_page = {row.get("airbnb_metric_page", ""): row for row in existing_rows}
    merged: list[dict[str, str]] = []
    for row in new_rows:
        metric_page = row.get("airbnb_metric_page", "")
        existing = existing_by_page.get(metric_page)
        if row.get("data_quality_status") == "missing_source" and existing and existing.get("data_quality_status") != "missing_source":
            merged.append({column: existing.get(column, "") for column in COLUMNS})
        else:
            merged.append(row)
    return merged


def cleanup_temporary_airbnb_html(run_dir: Path) -> list[Path]:
    raw_dir = run_dir / "raw"
    deleted: list[Path] = []
    for filename in TEMPORARY_AIRBNB_HTML_FILES:
        path = raw_dir / filename
        if path.exists():
            path.unlink()
            deleted.append(path)
    return deleted


def run(run_date: str, *, run_dir: Path | None = None, output_file: Path | None = None) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    resolved_output = output_file or resolved_run_dir / "raw" / f"airbnb_daily_conversion_parsed_{run_date}.csv"
    rows = merge_with_existing_rows(
        rows_for_run(run_date, resolved_run_dir),
        existing_rows_for_preservation(resolved_output, resolved_run_dir, run_date),
    )
    write_rows(resolved_output, rows)
    if not resolved_output.exists():
        raise FileNotFoundError(f"Airbnb diagnostic output was not created: {resolved_output}")
    deleted = cleanup_temporary_airbnb_html(resolved_run_dir)
    if deleted:
        print("Deleted temporary Airbnb HTML files:")
        for path in deleted:
            print(f"- {path}")
    return resolved_output


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
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
