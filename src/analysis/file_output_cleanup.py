"""Plan file cleanup from file output audit results.

Default behavior is dry-run. Deletion requires both --apply and --confirm-delete.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path
import sys


PLAN_COLUMNS = [
    "run_date",
    "file_path",
    "retention_class",
    "size_bytes",
    "cleanup_candidate",
    "delete_candidate",
    "recommended_retention_days",
    "cleanup_precondition",
    "planned_action",
    "reason",
]

REQUIRED_RETENTION_CLASSES = {
    "required_raw_source",
    "required_core_analysis",
    "required_report_output",
    "required_report_reproducibility",
    "required_history",
    "template_reference",
    "optional_marketing_evidence",
}

NEVER_DELETE_PATH_PARTS = {
    ".local",
    "browser_profiles",
    ".venv",
    ".git",
    "history",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or apply a file cleanup plan from audit results.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--audit-file", help="Audit CSV path. Defaults to analysis/file_output_audit_<run-date>.csv.")
    parser.add_argument("--dry-run", action="store_true", help="Write the cleanup plan without deleting files. Default.")
    parser.add_argument("--apply", action="store_true", help="Apply cleanup plan. Requires --confirm-delete.")
    parser.add_argument("--confirm-delete", action="store_true", help="Required with --apply before any deletion occurs.")
    return parser.parse_args(argv)


def truthy(value: str | bool | None) -> bool:
    return str(value or "").strip().lower() == "true"


def read_audit_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Audit file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def is_evidence_bundle_path(file_path: str) -> bool:
    return any(part.startswith("evidence_bundle_") for part in Path(file_path).parts)


def is_browser_profile_path(file_path: str) -> bool:
    parts = set(Path(file_path).parts)
    return ".local" in parts and "browser_profiles" in parts


def path_has_never_delete_part(file_path: str) -> bool:
    return bool(set(Path(file_path).parts) & NEVER_DELETE_PATH_PARTS)


def planned_action_for(row: dict[str, str]) -> tuple[str, str]:
    file_path = row.get("file_path", "")
    retention_class = row.get("retention_class", "")

    if is_browser_profile_path(file_path):
        return "excluded_browser_profile", "Browser profile paths are never cleanup targets."
    if retention_class == "required_history" or "history" in Path(file_path).parts:
        return "excluded_history", "History files are retained indefinitely."
    if is_evidence_bundle_path(file_path):
        return "excluded_evidence_bundle", "Evidence bundles preserve sent-report support files."
    if retention_class in REQUIRED_RETENTION_CLASSES:
        return "excluded_required", f"{retention_class} is not eligible for cleanup."
    if path_has_never_delete_part(file_path):
        return "excluded_required", "Path includes a protected directory."
    if not truthy(row.get("cleanup_candidate")):
        return "excluded_not_cleanup_candidate", "Audit did not mark this file as cleanup_candidate=true."
    return "dry_run_would_delete", "Cleanup candidate from audit; deletion still requires --apply --confirm-delete."


def build_plan_rows(audit_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    plan_rows = []
    for row in audit_rows:
        action, reason = planned_action_for(row)
        plan_rows.append(
            {
                "run_date": row.get("run_date", ""),
                "file_path": row.get("file_path", ""),
                "retention_class": row.get("retention_class", ""),
                "size_bytes": row.get("size_bytes", ""),
                "cleanup_candidate": row.get("cleanup_candidate", ""),
                "delete_candidate": row.get("delete_candidate", ""),
                "recommended_retention_days": row.get("recommended_retention_days", ""),
                "cleanup_precondition": row.get("cleanup_precondition", ""),
                "planned_action": action,
                "reason": reason,
            }
        )
    return plan_rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=PLAN_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def section(lines: list[str], title: str, rows: list[dict[str, str]], *, limit: int = 30) -> None:
    lines.extend(["", f"## {title}", ""])
    if not rows:
        lines.append("- None.")
        return
    for row in rows[:limit]:
        lines.append(f"- {row['file_path']} - {row['planned_action']}: {row['reason']}")
    if len(rows) > limit:
        lines.append(f"- ... {len(rows) - limit} more rows in CSV.")


def render_markdown(run_date: str, plan_rows: list[dict[str, str]], *, apply_requested: bool, confirm_delete: bool, deleted_count: int) -> str:
    eligible = [row for row in plan_rows if row["planned_action"] == "dry_run_would_delete"]
    excluded = [row for row in plan_rows if row["planned_action"] != "dry_run_would_delete"]
    required = [row for row in plan_rows if row["planned_action"] == "excluded_required"]
    evidence = [row for row in plan_rows if row["planned_action"] == "excluded_evidence_bundle"]
    history = [row for row in plan_rows if row["planned_action"] == "excluded_history"]

    lines = [
        f"# File Cleanup Plan - {run_date}",
        "",
        "## Executive Summary",
        "",
        f"- Files reviewed: {len(plan_rows)}",
        f"- Cleanup-eligible files: {len(eligible)}",
        f"- Excluded required files: {len(required)}",
        f"- Excluded evidence bundle files: {len(evidence)}",
        f"- Excluded history files: {len(history)}",
        f"- Apply requested: {'yes' if apply_requested else 'no'}",
        f"- Confirm delete supplied: {'yes' if confirm_delete else 'no'}",
        f"- Files deleted: {deleted_count}",
    ]
    if not eligible:
        lines.append("- No cleanup-eligible files for this run.")
    elif not apply_requested:
        lines.append("- Dry run only; no files were deleted.")
    elif apply_requested and not confirm_delete:
        lines.append("- Apply was requested without --confirm-delete; no files were deleted.")

    section(lines, "Cleanup Eligible Files", eligible)
    section(lines, "Files Excluded From Cleanup", excluded, limit=40)
    lines.extend(
        [
            "",
            "## Safety Guardrails",
            "",
            "- Default mode is dry-run.",
            "- Deletion requires --apply --confirm-delete.",
            "- Only files marked cleanup_candidate=true by file_output_audit are eligible.",
            "- Required raw, core analysis, report output, report reproducibility, history, template, browser profile, .venv, .git, and evidence bundle files are excluded.",
            "",
            "## Next Recommendation",
            "",
        ]
    )
    if eligible:
        lines.append("- Review the cleanup-eligible file list and preconditions before running apply mode.")
    else:
        lines.append("- No cleanup action is recommended for this run.")
    lines.extend(["", f"_Generated at {datetime.now(UTC).isoformat()}._", ""])
    return "\n".join(lines)


def apply_plan(plan_rows: list[dict[str, str]], *, confirm_delete: bool) -> int:
    if not confirm_delete:
        return 0
    deleted_count = 0
    for row in plan_rows:
        if row["planned_action"] != "dry_run_would_delete":
            continue
        path = Path(row["file_path"])
        if path.exists() and path.is_file():
            path.unlink()
            deleted_count += 1
    return deleted_count


def run(
    run_date: str,
    *,
    run_dir: Path | None = None,
    audit_file: Path | None = None,
    apply: bool = False,
    confirm_delete: bool = False,
) -> tuple[Path, Path, int]:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    analysis_dir = resolved_run_dir / "analysis"
    resolved_audit_file = audit_file or analysis_dir / f"file_output_audit_{run_date}.csv"
    plan_rows = build_plan_rows(read_audit_rows(resolved_audit_file))
    deleted_count = apply_plan(plan_rows, confirm_delete=confirm_delete) if apply else 0

    csv_path = analysis_dir / f"file_cleanup_plan_{run_date}.csv"
    md_path = analysis_dir / f"file_cleanup_plan_{run_date}.md"
    write_csv(csv_path, plan_rows)
    md_path.write_text(
        render_markdown(run_date, plan_rows, apply_requested=apply, confirm_delete=confirm_delete, deleted_count=deleted_count),
        encoding="utf-8",
    )
    return csv_path, md_path, deleted_count


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    apply_requested = bool(args.apply)
    csv_path, md_path, deleted_count = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        audit_file=Path(args.audit_file) if args.audit_file else None,
        apply=apply_requested,
        confirm_delete=bool(args.confirm_delete),
    )
    if apply_requested and not args.confirm_delete:
        print("Apply requested without --confirm-delete; no files were deleted.")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print(f"Files deleted: {deleted_count}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
