"""Manual Airbnb search visibility diagnostic report."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


COLUMNS = [
    "run_date",
    "search_timestamp",
    "browser_mode",
    "logged_in_status",
    "search_location",
    "date_rule",
    "check_in",
    "check_out",
    "guest_count",
    "scenario_name",
    "filters_used",
    "found_status",
    "max_pages_checked",
    "page_number",
    "position_on_page",
    "visible_price",
    "visible_cover_photo",
    "cover_photo_status",
    "visible_badges",
    "visible_title",
    "result_count",
    "competitor_context_notes",
    "notes",
]

OUTPUT_COLUMNS = COLUMNS + ["classifications"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Airbnb search visibility diagnostic outputs.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    return parser.parse_args(argv)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in OUTPUT_COLUMNS} for row in rows])


def parse_number(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def is_found(row: dict[str, str]) -> bool:
    return row.get("found_status", "").strip().lower() == "found"


def is_not_found(row: dict[str, str]) -> bool:
    return row.get("found_status", "").strip().lower() == "not_found"


def classify_row(row: dict[str, str]) -> list[str]:
    classifications: list[str] = []
    scenario = row.get("scenario_name", "").strip()
    page_number = parse_number(row.get("page_number", ""))
    max_pages = parse_number(row.get("max_pages_checked", ""))
    cover_photo_status = row.get("cover_photo_status", "").strip().lower()

    if scenario == "broad_no_filters":
        if is_not_found(row) and max_pages is not None and max_pages >= 10:
            classifications.append("broad_not_found")
        elif is_found(row) and page_number is not None and page_number > 10:
            classifications.append("broad_found_deep")
        elif is_found(row) and page_number is not None and page_number <= 10:
            classifications.append("broad_found_top_10_pages")

    if scenario == "broad_high_intent_filters":
        if is_found(row):
            classifications.append("high_intent_found")
            if page_number is not None and page_number > 3:
                classifications.append("high_intent_found_deep")
        elif is_not_found(row):
            classifications.append("high_intent_not_found")

    if cover_photo_status == "old_cover_after_change":
        classifications.append("possible_cover_photo_cache_issue")
    return classifications


def add_cross_scenario_classifications(rows: list[dict[str, str]], classifications_by_index: list[list[str]]) -> None:
    broad_missing = any(row.get("scenario_name") == "broad_no_filters" and is_not_found(row) for row in rows)
    filtered_found = any(row.get("scenario_name") != "broad_no_filters" and is_found(row) for row in rows)
    if broad_missing and filtered_found:
        for index, row in enumerate(rows):
            if row.get("scenario_name") != "broad_no_filters" and is_found(row):
                classifications_by_index[index].append("filtered_visibility_improved")


def classified_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    classifications_by_index = [classify_row(row) for row in rows]
    add_cross_scenario_classifications(rows, classifications_by_index)
    output_rows: list[dict[str, str]] = []
    for row, classifications in zip(rows, classifications_by_index, strict=True):
        output = {column: row.get(column, "") for column in COLUMNS}
        output["classifications"] = ";".join(dict.fromkeys(classifications))
        output_rows.append(output)
    return output_rows


def first_row(rows: list[dict[str, str]], scenario_name: str) -> dict[str, str] | None:
    return next((row for row in rows if row.get("scenario_name") == scenario_name), None)


def best_filtered_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    found_rows = [
        row
        for row in rows
        if row.get("scenario_name") != "broad_no_filters" and is_found(row)
    ]
    return min(
        found_rows,
        key=lambda row: (
            parse_number(row.get("page_number", "")) or 9999,
            parse_number(row.get("position_on_page", "")) or 9999,
        ),
        default=None,
    )


def status_text(row: dict[str, str] | None) -> str:
    if not row:
        return "unavailable"
    scenario = row.get("scenario_name", "scenario")
    found = row.get("found_status", "unknown")
    page = row.get("page_number", "")
    position = row.get("position_on_page", "")
    if found == "found":
        detail = f"found on page {page or 'unknown'}"
        if position:
            detail += f", position {position}"
        return f"{scenario}: {detail}"
    return f"{scenario}: {found or 'unknown'} after {row.get('max_pages_checked', '') or 'unknown'} pages checked"


def render_markdown(run_date: str, rows: list[dict[str, str]]) -> str:
    broad = first_row(rows, "broad_no_filters")
    high_intent = first_row(rows, "broad_high_intent_filters")
    best_filtered = best_filtered_row(rows)
    all_classes = sorted({item for row in rows for item in row.get("classifications", "").split(";") if item})
    cover_rows = [row for row in rows if row.get("cover_photo_status", "")]
    lines = [
        f"# Airbnb Search Visibility Diagnostic - {run_date}",
        "",
        "## Executive Summary",
        "",
        f"- Broad no-filter status: {status_text(broad)}.",
        f"- High-intent filter status: {status_text(high_intent)}.",
        f"- Best filtered scenario found: {status_text(best_filtered)}.",
        f"- Classifications: {', '.join(all_classes) if all_classes else 'none'}.",
        "",
        "## Broad Search Visibility",
        "",
        f"- {status_text(broad)}.",
        "",
        "## High-Intent Filter Visibility",
        "",
        f"- {status_text(high_intent)}.",
        "",
        "## Filter Impact",
        "",
        f"- Best filtered scenario found: {status_text(best_filtered)}.",
        "",
        "## Cover Photo Status",
        "",
    ]
    if cover_rows:
        for row in cover_rows:
            lines.append(f"- {row.get('scenario_name', 'scenario')}: {row.get('cover_photo_status', '')}.")
    else:
        lines.append("- Cover photo status unavailable.")
    lines.extend(
        [
            "",
            "## Improvement Hypotheses",
            "",
            "- Track whether listing-side improvements move broad search visibility, high-intent filtered visibility, or cover-photo freshness over future weekly runs.",
            "- Filtered visibility can improve before broad visibility; treat this as diagnostic context, not a pricing signal.",
            "",
            "## Guardrails",
            "",
            "- Airbnb search visibility is diagnostic only and does not create a PriceLabs rule recommendation.",
            "- PriceLabs remains the source of truth for revenue, occupancy, ADR, bookings, cleaning count, and revenue pace.",
            "",
        ]
    )
    return "\n".join(lines)


def run(run_date: str, *, run_dir: Path | None = None) -> tuple[Path | None, Path | None]:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    input_path = resolved_run_dir / "raw" / f"airbnb_search_visibility_input_{run_date}.csv"
    rows = read_rows(input_path)
    if not rows:
        return None, None
    output_rows = classified_rows(rows)
    analysis_dir = resolved_run_dir / "analysis"
    csv_path = analysis_dir / f"airbnb_search_visibility_{run_date}.csv"
    md_path = analysis_dir / f"airbnb_search_visibility_{run_date}.md"
    write_rows(csv_path, output_rows)
    md_path.write_text(render_markdown(run_date, output_rows), encoding="utf-8")
    return csv_path, md_path


def main() -> int:
    args = parse_args()
    csv_path, md_path = run(args.run_date, run_dir=Path(args.run_dir) if args.run_dir else None)
    if csv_path and md_path:
        print(f"Wrote {csv_path}")
        print(f"Wrote {md_path}")
    else:
        print(f"No Airbnb search visibility input found for {args.run_date}; skipping optional diagnostic.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
