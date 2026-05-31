"""Create a manual listing-state baseline snapshot for diagnostic reviews."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path
import sys


BASE_SNAPSHOT_INPUT_COLUMNS = [
    "snapshot_date",
    "snapshot_reason",
    "related_issue_id",
    "listing_title",
    "cover_photo_description",
    "first_5_photos_summary",
    "opening_description_text",
    "top_amenities_presented",
    "guest_capacity",
    "bedrooms",
    "bathrooms",
    "rating",
    "review_count",
    "cancellation_policy",
    "pet_policy",
    "house_rules_summary",
    "cleaning_fee_visible",
    "visible_price_notes",
    "minimum_stay_visible",
    "main_value_proposition",
    "known_recent_changes",
    "notes",
]

PAGE_COPY_CONTEXT_COLUMNS = [
    "full_description_text",
    "photo_captions_summary",
    "first_10_photos_summary",
    "amenities_full_text",
    "booking_widget_notes",
    "fees_visibility_notes",
    "trust_signal_notes",
    "guest_fit_notes",
    "location_value_notes",
    "booking_friction_notes",
    "competitor_positioning_notes",
]

SNAPSHOT_INPUT_COLUMNS = BASE_SNAPSHOT_INPUT_COLUMNS + PAGE_COPY_CONTEXT_COLUMNS

CHANGE_LOG_COLUMNS = [
    "change_date",
    "run_date",
    "related_issue_id",
    "change_type",
    "old_value",
    "new_value",
    "reason",
    "expected_effect",
    "status",
    "review_after_run_date",
    "notes",
]

VISUAL_SNAPSHOT_FILENAMES = (
    "listing_search_card_{run_date}.png",
    "listing_page_top_{run_date}.png",
    "listing_first_5_photos_{run_date}.png",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a listing-state snapshot markdown report.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--history-file", help="Listing change log path. Defaults to data/history/listing_change_log.csv.")
    return parser.parse_args(argv)


def read_snapshot_input(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        for row in csv.DictReader(csv_file):
            return {key: value or "" for key, value in row.items()}
    return None


def ensure_change_log(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CHANGE_LOG_COLUMNS)
        writer.writeheader()


def default_history_path(run_dir: Path) -> Path:
    try:
        return run_dir.parents[1] / "history" / "listing_change_log.csv"
    except IndexError:
        return Path("data") / "history" / "listing_change_log.csv"


def visual_snapshot_files(analysis_dir: Path, run_date: str) -> list[Path]:
    return [
        analysis_dir / filename.format(run_date=run_date)
        for filename in VISUAL_SNAPSHOT_FILENAMES
        if (analysis_dir / filename.format(run_date=run_date)).exists()
    ]


def format_value(value: str) -> str:
    text = str(value or "").strip()
    return text if text else "-"


def render_markdown(run_date: str, snapshot: dict[str, str] | None, visual_files: list[Path]) -> str:
    lines = [
        f"# Listing State Snapshot - {run_date}",
        "",
        "## Executive Summary",
        "",
    ]
    if snapshot:
        reason = format_value(snapshot.get("snapshot_reason", ""))
        issue_id = format_value(snapshot.get("related_issue_id", ""))
        title = format_value(snapshot.get("listing_title", ""))
        lines.extend(
            [
                f"- Snapshot date: {format_value(snapshot.get('snapshot_date', run_date))}",
                f"- Snapshot reason: {reason}",
                f"- Related diagnostic issue: {issue_id}",
                f"- Listing title: {title}",
                "- Listing snapshot is diagnostic/documentation only and does not create PriceLabs rule recommendations.",
                "",
                "## Related Diagnostic Issue",
                "",
                f"- {issue_id}",
                "",
                "## Structured Listing State",
                "",
            ]
        )
        for column in BASE_SNAPSHOT_INPUT_COLUMNS:
            label = column.replace("_", " ").capitalize()
            lines.append(f"- {label}: {format_value(snapshot.get(column, ''))}")
    else:
        lines.extend(
            [
                "- No manual listing snapshot input was provided for this run.",
                "- Add raw/listing_state_snapshot_input_<run_date>.csv from the template to capture the structured baseline.",
                "- Listing snapshot is diagnostic/documentation only and does not create PriceLabs rule recommendations.",
                "",
                "## Related Diagnostic Issue",
                "",
                "- No related diagnostic issue was supplied in manual snapshot input.",
                "",
                "## Structured Listing State",
                "",
                "- Structured listing state unavailable for this run.",
            ]
        )

    if snapshot:
        page_context_lines = []
        for column in PAGE_COPY_CONTEXT_COLUMNS:
            value = str(snapshot.get(column, "") or "").strip()
            if value:
                label = column.replace("_", " ").capitalize()
                page_context_lines.append(f"- {label}: {value}")
        if page_context_lines:
            lines.extend(["", "## Page Copy And Booking Context", "", *page_context_lines])

    lines.extend(["", "## Visual Snapshot Files", ""])
    if visual_files:
        for path in visual_files:
            lines.append(f"- {path.name}")
    else:
        lines.append("- No visual snapshot files were provided for this run.")
    lines.extend(
        [
            "- If listing_page_top shows the Airbnb hero grid, it can serve as the first-5-photos baseline.",
            "- Search-card screenshots should use consistent parameters each run: Search: Pocono Mountains, PA; date window: same rule each run, such as next full month or target future week; guests/filters: keep consistent; browser size/layout: keep consistent.",
        ]
    )

    lines.extend(
        [
            "",
            "## Notes For Next Comparison",
            "",
            "- Compare future listing-side changes against this baseline before interpreting Airbnb conversion movement.",
            "- Use data/history/listing_change_log.csv to record listing-side changes and expected effects.",
            "- PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.",
            "",
            f"_Generated at {datetime.now(UTC).isoformat()}._",
            "",
        ]
    )
    return "\n".join(lines)


def run(run_date: str, *, run_dir: Path | None = None, history_file: Path | None = None) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    raw_dir = resolved_run_dir / "raw"
    analysis_dir = resolved_run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    resolved_history_file = history_file or default_history_path(resolved_run_dir)
    ensure_change_log(resolved_history_file)

    snapshot_input = read_snapshot_input(raw_dir / f"listing_state_snapshot_input_{run_date}.csv")
    output_path = analysis_dir / f"listing_state_snapshot_{run_date}.md"
    output_path.write_text(
        render_markdown(run_date, snapshot_input, visual_snapshot_files(analysis_dir, run_date)),
        encoding="utf-8",
    )
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
