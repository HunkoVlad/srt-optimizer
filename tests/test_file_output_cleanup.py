import csv
from pathlib import Path

from analysis import file_output_cleanup


RUN_DATE = "2026-06-01"


def write_audit(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            full_row = {field: "" for field in fieldnames}
            full_row.update(
                {
                    "run_date": RUN_DATE,
                    "size_bytes": "4",
                    "delete_candidate": "false",
                    "cleanup_candidate": "false",
                }
            )
            full_row.update(row)
            writer.writerow(full_row)


def read_plan(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def test_dry_run_creates_cleanup_plan(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(run_dir / "raw" / "price_occ.csv"),
                "retention_class": "required_raw_source",
            }
        ],
    )

    csv_path, md_path, deleted_count = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)

    assert csv_path.exists()
    assert md_path.exists()
    assert deleted_count == 0
    assert "Files deleted: 0" in md_path.read_text(encoding="utf-8")


def test_no_cleanup_candidates_markdown_says_none(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(run_dir / "analysis" / f"email_revenue_report_{RUN_DATE}.md"),
                "retention_class": "required_report_output",
            }
        ],
    )

    _, md_path, _ = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)

    assert "No cleanup-eligible files for this run." in md_path.read_text(encoding="utf-8")


def test_required_raw_files_are_excluded(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(run_dir / "raw" / "price_occ.csv"),
                "retention_class": "required_raw_source",
                "cleanup_candidate": "true",
            }
        ],
    )

    csv_path, _, _ = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)
    rows = read_plan(csv_path)

    assert rows[0]["planned_action"] == "excluded_required"


def test_evidence_bundle_files_are_excluded(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    evidence_path = run_dir / "analysis" / f"evidence_bundle_{RUN_DATE}" / "copy.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(evidence_path),
                "retention_class": "required_report_reproducibility",
                "cleanup_candidate": "true",
            }
        ],
    )

    csv_path, _, _ = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)
    rows = read_plan(csv_path)

    assert rows[0]["planned_action"] == "excluded_evidence_bundle"


def test_stayfi_marketing_outputs_are_excluded_even_if_cleanup_candidate_true(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(run_dir / "analysis" / f"stayfi_anniversary_email_send_results_{RUN_DATE}.csv"),
                "retention_class": "optional_marketing_evidence",
                "cleanup_candidate": "true",
            }
        ],
    )

    csv_path, _, _ = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)
    rows = read_plan(csv_path)

    assert rows[0]["planned_action"] == "excluded_required"


def test_stayfi_debug_file_can_be_cleanup_candidate(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(run_dir / "analysis" / f"stayfi_anniversary_email_debug_{RUN_DATE}.csv"),
                "retention_class": "optional_debug",
                "cleanup_candidate": "true",
                "recommended_retention_days": "30",
            }
        ],
    )

    csv_path, _, _ = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)
    rows = read_plan(csv_path)

    assert rows[0]["planned_action"] == "dry_run_would_delete"
    assert rows[0]["recommended_retention_days"] == "30"


def test_browser_profile_paths_are_excluded(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    browser_path = tmp_path / ".local" / "browser_profiles" / "airbnb" / "Cookies"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(browser_path),
                "retention_class": "staging_promoted_safe_cleanup",
                "cleanup_candidate": "true",
            }
        ],
    )

    csv_path, _, _ = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)
    rows = read_plan(csv_path)

    assert rows[0]["planned_action"] == "excluded_browser_profile"


def test_apply_without_confirm_delete_deletes_nothing(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    staged_file = run_dir / "downloads_staging" / "airbnb" / "old.html"
    staged_file.parent.mkdir(parents=True, exist_ok=True)
    staged_file.write_text("old", encoding="utf-8")
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(staged_file),
                "retention_class": "staging_promoted_safe_cleanup",
                "cleanup_candidate": "true",
            }
        ],
    )

    _, md_path, deleted_count = file_output_cleanup.run(RUN_DATE, run_dir=run_dir, apply=True, confirm_delete=False)

    assert staged_file.exists()
    assert deleted_count == 0
    assert "Apply was requested without --confirm-delete; no files were deleted." in md_path.read_text(encoding="utf-8")


def test_apply_confirm_delete_deletes_only_cleanup_candidates(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    staged_file = run_dir / "downloads_staging" / "airbnb" / "old.html"
    required_file = run_dir / "raw" / "price_occ.csv"
    staged_file.parent.mkdir(parents=True, exist_ok=True)
    required_file.parent.mkdir(parents=True, exist_ok=True)
    staged_file.write_text("old", encoding="utf-8")
    required_file.write_text("required", encoding="utf-8")
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(
        audit_file,
        [
            {
                "file_path": str(staged_file),
                "retention_class": "staging_promoted_safe_cleanup",
                "cleanup_candidate": "true",
            },
            {
                "file_path": str(required_file),
                "retention_class": "required_raw_source",
                "cleanup_candidate": "true",
            },
        ],
    )

    csv_path, _, deleted_count = file_output_cleanup.run(RUN_DATE, run_dir=run_dir, apply=True, confirm_delete=True)
    rows = read_plan(csv_path)

    assert deleted_count == 1
    assert not staged_file.exists()
    assert required_file.exists()
    assert {row["planned_action"] for row in rows} == {"dry_run_would_delete", "excluded_required"}


def test_plan_csv_uses_expected_columns(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    audit_file = run_dir / "analysis" / f"file_output_audit_{RUN_DATE}.csv"
    write_audit(audit_file, [])

    csv_path, _, _ = file_output_cleanup.run(RUN_DATE, run_dir=run_dir)

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        columns = next(csv.reader(csv_file))

    assert columns == file_output_cleanup.PLAN_COLUMNS
