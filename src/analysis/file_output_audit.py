"""Audit generated run outputs without deleting anything."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sys


AUDIT_COLUMNS = [
    "run_date",
    "file_path",
    "file_name",
    "folder_area",
    "file_type",
    "size_bytes",
    "last_modified",
    "source_category",
    "downstream_usage",
    "evidence_bundle_included",
    "retention_class",
    "delete_candidate",
    "cleanup_candidate",
    "redundancy_reason",
    "required_for_report",
    "required_for_trend_history",
    "required_for_reproducibility",
    "recommended_retention_days",
    "cleanup_precondition",
    "notes",
]

REQUIRED_RAW_NAMES = {
    "priceLabs_future_export.csv",
    "price_occ.csv",
    "monthly_trends.csv",
    "bookings_report.xlsx",
    "pricelabs_settings_manual_input.json",
}

REQUIRED_ANALYSIS_PREFIXES = (
    "future_daily_pricing_",
    "future_daily_pricing_enriched_",
    "bookings_report_normalized_",
    "rolling_13_month_revenue_view_",
    "monthly_revenue_summary_",
    "monthly_booking_metrics_",
    "monthly_revenue_pace_",
    "monthly_trends_normalized_",
    "performance_reason_review_",
    "future_signal_change_review_",
    "future_window_summary_",
    "future_window_signals_",
    "combined_market_listing_signal_",
    "diagnostic_issue_tracker_",
    "airbnb_daily_conversion_",
    "airbnb_daily_conversion_parsed_",
    "airbnb_daily_week_over_week_conversion_",
    "airbnb_daily_week_average_deviation_",
    "airbnb_daily_similar_listing_comparison_",
    "airbnb_weekly_conversion_summary_",
    "airbnb_weekly_history_comparison_",
    "airbnb_similar_listing_summary_",
    "airbnb_search_visibility_",
    "airbnb_search_screening_",
)

OPTIONAL_EVIDENCE_PREFIXES = (
    "listing_state_snapshot_",
    "listing_search_card_",
    "listing_page_top_",
    "listing_first_5_photos_",
    "listing_competitor_review_",
    "airbnb_conversion_diagnostic_report_",
)

STAYFI_MARKETING_OUTPUT_PREFIXES = (
    "stayfi_anniversary_email_candidates_",
    "stayfi_anniversary_email_drafts_",
    "stayfi_anniversary_email_summary_",
    "stayfi_anniversary_gmail_draft_results_",
    "stayfi_anniversary_email_send_results_",
)

REPORT_PREFIXES = (
    "email_revenue_report_",
    "evidence_manifest_",
)

HISTORY_REQUIRED_NAMES = {
    "diagnostic_issue_tracker.csv",
    "listing_change_log.csv",
}

DO_NOT_AUDIT_DIRS = {".venv", ".git", ".local"}


@dataclass(frozen=True)
class AuditPaths:
    run_date: str
    run_dir: Path
    history_dir: Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit generated run outputs without deleting files.")
    parser.add_argument("--run-date", help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--all-runs", action="store_true", help="Write a history-level audit summary for all run folders.")
    return parser.parse_args(argv)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def file_type(path: Path) -> str:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "no_extension"


def folder_area(path: Path, paths: AuditPaths) -> str:
    try:
        relative = path.relative_to(paths.run_dir)
        return relative.parts[0] if relative.parts else "run_root"
    except ValueError:
        try:
            path.relative_to(paths.history_dir)
            return "history"
        except ValueError:
            return "outside_run"


def load_evidence_sources(run_dir: Path, run_date: str) -> set[str]:
    manifest_path = run_dir / "analysis" / f"evidence_bundle_{run_date}" / f"evidence_manifest_{run_date}.json"
    if not manifest_path.exists():
        return set()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    sources = set()
    for entry in manifest.get("files", []):
        if entry.get("exists") and entry.get("copied") and entry.get("source_path"):
            sources.add(str(Path(entry["source_path"]).resolve()).lower())
    return sources


def has_promoted_copy(path: Path, paths: AuditPaths) -> bool:
    name = path.name
    if path.suffix.lower() == ".html" and "downloads_staging" in path.parts:
        return (paths.run_dir / "raw" / name).exists()
    if path.suffix.lower() == ".png" and "downloads_staging" in path.parts:
        return (paths.run_dir / "analysis" / name).exists()
    if name == "Competitor Calendar.csv" and "downloads_staging" in path.parts:
        return (paths.run_dir / "analysis" / f"pricelabs_competitor_calendar_{paths.run_date}.csv").exists()
    return False


def classify(path: Path, paths: AuditPaths, evidence_sources: set[str]) -> dict[str, str]:
    name = path.name
    area = folder_area(path, paths)
    suffix = path.suffix.lower()
    relative = relative_to_project(path)
    evidence_included = str(path.resolve()).lower() in evidence_sources

    result = {
        "source_category": "generated_output",
        "downstream_usage": "not_detected",
        "evidence_bundle_included": bool_text(evidence_included),
        "retention_class": "unknown_review",
        "delete_candidate": "false",
        "cleanup_candidate": "false",
        "redundancy_reason": "",
        "required_for_report": "false",
        "required_for_trend_history": "false",
        "required_for_reproducibility": "false",
        "recommended_retention_days": "",
        "cleanup_precondition": "Manual review required.",
        "notes": "Usage not matched to known pipeline output pattern; review before changing generation or retention.",
    }

    if area == "outside_run" and "sample_data" in path.parts:
        result.update(
            source_category="template_or_reference",
            downstream_usage="tests_or_manual_input_template",
            retention_class="template_reference",
            cleanup_precondition="Do not delete automatically.",
            notes="Template/reference file used for tests, examples, or manual input structure.",
        )
        return result

    if area == "history":
        result.update(
            source_category="history",
            downstream_usage="trend_or_issue_tracking",
            retention_class="required_history" if name in HISTORY_REQUIRED_NAMES else "required_history",
            required_for_trend_history="true",
            recommended_retention_days="indefinite",
            cleanup_precondition="Do not delete automatically.",
            notes="Persistent history file for cross-run comparison or manual tracking.",
        )
        return result

    if area == "raw":
        if (
            name in REQUIRED_RAW_NAMES
            or name.startswith("airbnb_") and suffix in {".html", ".csv"}
            or name.startswith("pricelabs_settings_snapshot_from_ui")
        ):
            result.update(
                source_category="raw_source",
                downstream_usage="weekly_analysis_input",
                retention_class="required_raw_source",
                required_for_reproducibility="true",
                recommended_retention_days="indefinite",
                cleanup_precondition="Do not delete automatically.",
                notes="Raw source input; never delete automatically.",
            )
            return result
        if name == f"airbnb_search_visibility_input_{paths.run_date}.csv":
            result.update(
                source_category="manual_airbnb_diagnostic_input",
                downstream_usage="airbnb_search_visibility",
                retention_class="required_raw_source",
                required_for_reproducibility="true",
                recommended_retention_days="indefinite",
                cleanup_precondition="Do not delete automatically.",
                notes="Manual diagnostic source input; retain for reproducibility.",
            )
            return result
        if name == f"listing_state_snapshot_input_{paths.run_date}.csv":
            result.update(
                source_category="manual_listing_snapshot_input",
                downstream_usage="listing_state_snapshot",
                retention_class="required_raw_source",
                required_for_reproducibility="true",
                recommended_retention_days="indefinite",
                cleanup_precondition="Do not delete automatically.",
                notes="Manual listing baseline source input; retain for reproducibility.",
            )
            return result
        if name == f"pricelabs_competitor_list_{paths.run_date}.csv":
            result.update(
                source_category="diagnostic_competitor_input",
                downstream_usage="listing_competitor_review_and_evidence",
                retention_class="required_raw_source",
                required_for_reproducibility="true",
                recommended_retention_days="indefinite",
                cleanup_precondition="Do not delete automatically.",
                notes="Generated competitor list used by listing review/evidence.",
            )
            return result

    if area == "analysis":
        if name.startswith("file_output_audit_"):
            result.update(
                source_category="audit_output",
                downstream_usage="file_retention_review",
                retention_class="optional_debug",
                recommended_retention_days="90",
                cleanup_precondition="Retain for retention review; archive or review before cleanup.",
                notes="Audit output generated for file retention and cleanup planning.",
            )
            return result
        if name.startswith(REPORT_PREFIXES) or (name.startswith(f"evidence_bundle_{paths.run_date}") and path.is_dir()):
            result.update(
                source_category="report_output",
                downstream_usage="weekly_email_or_evidence_bundle",
                retention_class="required_report_output",
                required_for_report="true",
                recommended_retention_days="365",
                cleanup_precondition="Retain at least 12 months; prefer indefinite retention for sent reports.",
                notes="Final report/evidence output.",
            )
            return result
        if name.startswith(REQUIRED_ANALYSIS_PREFIXES):
            result.update(
                source_category="analysis_output",
                downstream_usage="weekly_report_or_metric_reproducibility",
                retention_class="required_core_analysis",
                required_for_report="true",
                required_for_reproducibility="true",
                required_for_trend_history=bool_text("history" in name or "diagnostic_issue_tracker" in name),
                recommended_retention_days="indefinite",
                cleanup_precondition="Do not delete automatically.",
                notes="Core or intermediate analysis output used to reproduce report metrics or debug calculations.",
            )
            return result
        if name.startswith(OPTIONAL_EVIDENCE_PREFIXES):
            result.update(
                source_category="diagnostic_evidence",
                downstream_usage="evidence_bundle_or_manual_review",
                retention_class="optional_diagnostic_evidence",
                required_for_reproducibility="true",
                recommended_retention_days="indefinite",
                cleanup_precondition="Retain while tied to open issue, active listing test, or report evidence.",
                notes="Optional diagnostic evidence; retain when tied to an open issue or listing test.",
            )
            return result
        if name.startswith(STAYFI_MARKETING_OUTPUT_PREFIXES):
            result.update(
                source_category="stayfi_marketing_output",
                downstream_usage="stayfi_anniversary_email_report_support",
                retention_class="optional_marketing_evidence",
                required_for_reproducibility="true",
                recommended_retention_days="365",
                cleanup_precondition="Do not delete automatically; retain for marketing send/draft audit trail.",
                notes="StayFi anniversary marketing output used for report support, draft/send review, or duplicate-prevention audit.",
            )
            return result
        if name.startswith("stayfi_anniversary_email_debug_"):
            result.update(
                source_category="stayfi_marketing_debug",
                downstream_usage="stayfi_anniversary_email_debugging",
                retention_class="optional_debug",
                cleanup_candidate="true",
                recommended_retention_days="30",
                cleanup_precondition="Cleanup only after 30 days and after confirming no StayFi investigation needs the debug rows.",
                notes="StayFi anniversary debug output; keep short-term unless needed for investigation.",
            )
            return result
        if any(part.startswith("evidence_bundle_") for part in path.parts):
            result.update(
                source_category="evidence_bundle_copy",
                downstream_usage="evidence_bundle_attachment",
                retention_class="required_report_reproducibility",
                required_for_report="true",
                required_for_reproducibility="true",
                recommended_retention_days="365",
                cleanup_precondition="Retain at least 12 months; preserve sent-report support files.",
                notes="Evidence bundle copy preserves the exact files included with or supporting a sent report.",
            )
            return result

    if area == "downloads_staging":
        promoted = has_promoted_copy(path, paths)
        if promoted:
            result.update(
                source_category="staging",
                downstream_usage="promoted_copy_exists",
                retention_class="staging_promoted_safe_cleanup",
                cleanup_candidate="true",
                recommended_retention_days="7",
                cleanup_precondition="Only after validation, promotion, and run review confirm promoted copy exists.",
                notes="Staged file appears to have a promoted copy; safe cleanup candidate after successful run review.",
            )
            return result
        result.update(
            source_category="staging",
            downstream_usage="capture_or_transform_staging",
            retention_class="staging_failed_keep_short_term",
            cleanup_candidate="false",
            recommended_retention_days="30",
            cleanup_precondition="Keep for debugging unless a later successful promoted capture supersedes it.",
            notes="Staging file without detected promoted copy; keep short-term for debugging.",
        )
        return result

    if area == "logs":
        result.update(
            source_category="debug_log",
            downstream_usage="operational_debug",
            retention_class="optional_debug",
            recommended_retention_days="90",
            cleanup_precondition="Keep recent operational logs; archive or review before cleanup.",
            notes="Operational log; suggested retention is 90 days.",
        )
        return result

    return result


def iter_audited_files(paths: AuditPaths) -> list[Path]:
    roots = [
        paths.run_dir / "raw",
        paths.run_dir / "analysis",
        paths.run_dir / "downloads_staging",
        paths.run_dir / "logs",
        paths.history_dir,
        Path("sample_data"),
    ]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if any(part in DO_NOT_AUDIT_DIRS for part in path.parts):
                continue
            if path.is_file():
                files.append(path)
    return sorted(files, key=lambda value: str(value).lower())


def build_rows(run_date: str, run_dir: Path | None = None) -> list[dict[str, str]]:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    history_dir = resolved_run_dir.parents[1] / "history" if len(resolved_run_dir.parents) > 1 else Path("data") / "history"
    paths = AuditPaths(run_date=run_date, run_dir=resolved_run_dir, history_dir=history_dir)
    evidence_sources = load_evidence_sources(resolved_run_dir, run_date)
    rows = []
    for path in iter_audited_files(paths):
        stat = path.stat()
        row = {
            "run_date": run_date,
            "file_path": relative_to_project(path),
            "file_name": path.name,
            "folder_area": folder_area(path, paths),
            "file_type": file_type(path),
            "size_bytes": str(stat.st_size),
            "last_modified": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        }
        row.update(classify(path, paths, evidence_sources))
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def section(lines: list[str], title: str, rows: list[dict[str, str]], *, limit: int = 30) -> None:
    lines.extend(["", f"## {title}", ""])
    if not rows:
        lines.append("- None found.")
        return
    for row in rows[:limit]:
        detail = row["file_path"]
        if row.get("redundancy_reason"):
            detail += f" - {row['redundancy_reason']}"
        elif row.get("notes"):
            detail += f" - {row['notes']}"
        lines.append(f"- {detail}")
    if len(rows) > limit:
        lines.append(f"- ... {len(rows) - limit} more rows in CSV.")


def render_markdown(run_date: str, rows: list[dict[str, str]]) -> str:
    required = [
        row
        for row in rows
        if row["retention_class"]
        in {
            "required_raw_source",
            "required_core_analysis",
            "required_report_output",
            "required_report_reproducibility",
        }
    ]
    history = [row for row in rows if row["retention_class"] == "required_history"]
    optional = [row for row in rows if row["retention_class"] == "optional_diagnostic_evidence"]
    cleanup = [row for row in rows if row["cleanup_candidate"] == "true"]
    redundant = [row for row in rows if row["retention_class"] == "redundant_candidate_review"]
    templates = [row for row in rows if row["retention_class"] == "template_reference"]
    report_reproducibility = [row for row in rows if row["retention_class"] == "required_report_reproducibility"]
    reclassified = [
        row
        for row in rows
        if row["retention_class"] == "required_core_analysis"
        and (
            row["file_name"].startswith("airbnb_daily_")
            or row["file_name"].startswith("bookings_report_normalized_")
            or row["file_name"].startswith("future_daily_pricing_")
            or row["file_name"].startswith("monthly_")
        )
    ]
    unknown = [row for row in rows if row["retention_class"] == "unknown_review"]
    not_safe_to_delete = [row for row in rows if row["delete_candidate"] == "false" and row["cleanup_candidate"] == "false"]

    lines = [
        f"# File Output Audit - {run_date}",
        "",
        "## Executive Summary",
        "",
        f"- Files audited: {len(rows)}",
        f"- Required files: {len(required)}",
        f"- Required history files: {len(history)}",
        f"- Optional diagnostic evidence files: {len(optional)}",
        f"- Template/reference files: {len(templates)}",
        f"- Required report reproducibility files: {len(report_reproducibility)}",
        f"- Cleanup candidates: {len(cleanup)}",
        f"- Redundant candidates for review: {len(redundant)}",
        f"- Unknown usage files: {len(unknown)}",
        "- No files were deleted by this audit.",
    ]
    section(lines, "Required Files For Weekly Analysis", required)
    section(lines, "Required Files For Historical Trend / Issue Tracking", history)
    section(lines, "Optional Evidence Files", optional)
    section(lines, "Template And Reference Files", templates)
    section(lines, "Safe Cleanup Candidates After Promotion", cleanup)
    section(lines, "Files Reclassified From Unknown", reclassified)
    section(lines, "Redundant Candidate Outputs To Review", redundant)
    section(lines, "Remaining Unknown Files", unknown)
    section(lines, "Files Not Safe To Delete", not_safe_to_delete, limit=40)
    lines.extend(
        [
            "",
            "## Recommended Retention Policy",
            "",
            "- Raw source files: keep indefinitely.",
            "- History files: keep indefinitely.",
            "- Evidence bundles and sent-report support files: keep indefinitely or at least 12 months.",
            "- Successful promoted staging files: cleanup after 7 days, only after validation, promotion, and run review confirm the promoted copy exists.",
            "- Failed staging/debug files: keep 30 days for diagnosis unless superseded by a later successful capture.",
            "- Logs: keep 90 days.",
            "- Template/reference files: keep indefinitely while tests or manual inputs depend on them.",
            "- Do not delete required raw source, core analysis, report output, report reproducibility, or history files automatically.",
            "",
            "## Do-Not-Delete List",
            "",
            "- PriceLabs raw source files: priceLabs_future_export.csv, price_occ.csv, monthly_trends.csv, bookings_report.xlsx.",
            "- Promoted Airbnb raw HTML used by diagnostics.",
            "- Weekly report outputs and evidence manifests.",
            "- data/history/diagnostic_issue_tracker.csv and data/history/listing_change_log.csv.",
            "- Any file tied to an open diagnostic issue, active listing test, or reproducibility need.",
            "",
            f"_Generated at {datetime.now(UTC).isoformat()}._",
            "",
        ]
    )
    return "\n".join(lines)


def run(run_date: str, *, run_dir: Path | None = None) -> tuple[Path, Path]:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    analysis_dir = resolved_run_dir / "analysis"
    rows = build_rows(run_date, resolved_run_dir)
    csv_path = analysis_dir / f"file_output_audit_{run_date}.csv"
    md_path = analysis_dir / f"file_output_audit_{run_date}.md"
    write_csv(csv_path, rows)
    md_path.write_text(render_markdown(run_date, rows), encoding="utf-8")
    return csv_path, md_path


def run_all_runs(runs_root: Path = Path("data") / "runs", history_dir: Path = Path("data") / "history") -> tuple[Path, Path]:
    rows: list[dict[str, str]] = []
    if runs_root.exists():
        for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            rows.extend(build_rows(run_dir.name, run_dir))
    csv_path = history_dir / "file_output_audit_summary.csv"
    md_path = history_dir / "file_output_audit_summary.md"
    write_csv(csv_path, rows)
    md_path.write_text(render_markdown("all-runs", rows), encoding="utf-8")
    return csv_path, md_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.all_runs:
        csv_path, md_path = run_all_runs()
    else:
        if not args.run_date:
            raise ValueError("--run-date is required unless --all-runs is used")
        csv_path, md_path = run(args.run_date, run_dir=Path(args.run_dir) if args.run_dir else None)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
