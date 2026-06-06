import csv
from pathlib import Path

from analysis import file_output_audit


RUN_DATE = "2026-06-01"


def rows_by_name(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["file_name"]: row for row in rows}


def write_file(path: Path, content: bytes | str = "data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def test_file_output_audit_runs_for_run_date(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_file(run_dir / "raw" / "price_occ.csv")

    csv_path, md_path = file_output_audit.run(RUN_DATE, run_dir=run_dir)

    assert csv_path.exists()
    assert md_path.exists()
    assert "File Output Audit - 2026-06-01" in md_path.read_text(encoding="utf-8")


def test_known_raw_pricelabs_files_are_required_raw_source(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_file(run_dir / "raw" / "priceLabs_future_export.csv")
    write_file(run_dir / "raw" / "price_occ.csv")
    write_file(run_dir / "raw" / "monthly_trends.csv")
    write_file(run_dir / "raw" / "bookings_report.xlsx", b"xlsx")

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    for name in [
        "priceLabs_future_export.csv",
        "price_occ.csv",
        "monthly_trends.csv",
        "bookings_report.xlsx",
    ]:
        assert rows[name]["retention_class"] == "required_raw_source"
        assert rows[name]["delete_candidate"] == "false"
        assert rows[name]["required_for_reproducibility"] == "true"


def test_email_report_classifies_as_required_report_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_file(run_dir / "analysis" / f"email_revenue_report_{RUN_DATE}.md")

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows[f"email_revenue_report_{RUN_DATE}.md"]
    assert row["retention_class"] == "required_report_output"
    assert row["required_for_report"] == "true"


def test_history_listing_change_log_classifies_as_required_history(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "listing_change_log.csv"
    write_file(history_file, "change_date,run_date\n")

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows["listing_change_log.csv"]
    assert row["folder_area"] == "history"
    assert row["retention_class"] == "required_history"
    assert row["required_for_trend_history"] == "true"


def test_promoted_staging_html_classifies_as_cleanup_candidate(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filename = "airbnb_booking_conversion_daily.html"
    write_file(run_dir / "downloads_staging" / "airbnb" / filename, "<html></html>")
    write_file(run_dir / "raw" / filename, "<html></html>")

    rows = file_output_audit.build_rows(RUN_DATE, run_dir)
    row = next(row for row in rows if row["file_name"] == filename and row["folder_area"] == "downloads_staging")
    assert row["folder_area"] == "downloads_staging"
    assert row["retention_class"] == "staging_promoted_safe_cleanup"
    assert row["cleanup_candidate"] == "true"
    assert row["delete_candidate"] == "false"


def test_promoted_staging_png_classifies_as_cleanup_candidate(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filename = f"listing_search_card_{RUN_DATE}.png"
    write_file(run_dir / "downloads_staging" / "airbnb_listing_state" / filename, b"png")
    write_file(run_dir / "analysis" / filename, b"png")

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    staging_rows = [row for row in rows.values() if row["folder_area"] == "downloads_staging"]
    assert staging_rows[0]["retention_class"] == "staging_promoted_safe_cleanup"
    assert staging_rows[0]["cleanup_candidate"] == "true"


def test_unknown_files_are_unknown_review_not_delete(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_file(run_dir / "analysis" / "experimental_output.tmp")

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows["experimental_output.tmp"]
    assert row["retention_class"] == "unknown_review"
    assert row["delete_candidate"] == "false"


def test_evidence_bundle_copies_are_report_reproducibility_but_not_delete(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    bundle_file = run_dir / "analysis" / f"evidence_bundle_{RUN_DATE}" / f"{RUN_DATE}__report__email_revenue_report_{RUN_DATE}.md"
    write_file(bundle_file)

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows[bundle_file.name]
    assert row["retention_class"] == "required_report_reproducibility"
    assert row["delete_candidate"] == "false"
    assert row["required_for_reproducibility"] == "true"
    assert row["recommended_retention_days"] == "365"


def test_markdown_includes_do_not_delete_list(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_file(run_dir / "raw" / "price_occ.csv")

    _, md_path = file_output_audit.run(RUN_DATE, run_dir=run_dir)
    markdown = md_path.read_text(encoding="utf-8")

    assert "## Do-Not-Delete List" in markdown
    assert "## Recommended Retention Policy" in markdown
    assert "No files were deleted by this audit." in markdown


def test_written_csv_uses_expected_columns(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_file(run_dir / "raw" / "price_occ.csv")

    csv_path, _ = file_output_audit.run(RUN_DATE, run_dir=run_dir)

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        columns = next(reader)

    assert columns == file_output_audit.AUDIT_COLUMNS


def test_future_daily_pricing_enriched_classifies_as_required_for_reproducibility(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filename = f"future_daily_pricing_enriched_{RUN_DATE}.csv"
    write_file(run_dir / "analysis" / filename)

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows[filename]
    assert row["retention_class"] == "required_core_analysis"
    assert row["required_for_reproducibility"] == "true"
    assert "reproduce report metrics" in row["notes"]


def test_bookings_report_normalized_classifies_as_required_for_reproducibility(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filename = f"bookings_report_normalized_{RUN_DATE}.csv"
    write_file(run_dir / "analysis" / filename)

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows[filename]
    assert row["retention_class"] == "required_core_analysis"
    assert row["required_for_reproducibility"] == "true"


def test_airbnb_daily_comparison_files_classify_as_required_for_reproducibility(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filenames = [
        f"airbnb_daily_week_over_week_conversion_{RUN_DATE}.csv",
        f"airbnb_daily_week_average_deviation_{RUN_DATE}.csv",
        f"airbnb_daily_conversion_{RUN_DATE}.csv",
    ]
    for filename in filenames:
        write_file(run_dir / "analysis" / filename)

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    for filename in filenames:
        assert rows[filename]["retention_class"] == "required_core_analysis"
        assert rows[filename]["required_for_reproducibility"] == "true"


def test_stayfi_anniversary_marketing_outputs_are_not_unknown_or_cleanup_candidates(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filenames = [
        f"stayfi_anniversary_email_candidates_{RUN_DATE}.csv",
        f"stayfi_anniversary_email_drafts_{RUN_DATE}.csv",
        f"stayfi_anniversary_email_summary_{RUN_DATE}.csv",
        f"stayfi_anniversary_gmail_draft_results_{RUN_DATE}.csv",
        f"stayfi_anniversary_email_send_results_{RUN_DATE}.csv",
    ]
    for filename in filenames:
        write_file(run_dir / "analysis" / filename)

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    for filename in filenames:
        assert rows[filename]["retention_class"] == "optional_marketing_evidence"
        assert rows[filename]["source_category"] == "stayfi_marketing_output"
        assert rows[filename]["cleanup_candidate"] == "false"
        assert rows[filename]["delete_candidate"] == "false"


def test_stayfi_anniversary_debug_file_keeps_30_days_and_can_be_cleanup_candidate(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filename = f"stayfi_anniversary_email_debug_{RUN_DATE}.csv"
    write_file(run_dir / "analysis" / filename)

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows[filename]
    assert row["retention_class"] == "optional_debug"
    assert row["source_category"] == "stayfi_marketing_debug"
    assert row["cleanup_candidate"] == "true"
    assert row["recommended_retention_days"] == "30"


def test_sample_data_templates_classify_as_template_reference(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_file(tmp_path / "sample_data" / "listing_state_snapshot_input_template.csv", "header\n")
    write_file(tmp_path / "sample_data" / "airbnb_search_visibility_input_template.csv", "header\n")

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    assert rows["listing_state_snapshot_input_template.csv"]["retention_class"] == "template_reference"
    assert rows["airbnb_search_visibility_input_template.csv"]["delete_candidate"] == "false"
    assert rows["airbnb_search_visibility_input_template.csv"]["cleanup_candidate"] == "false"


def test_unpromoted_staging_file_keeps_short_term(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filename = "airbnb_booking_conversion_daily.html"
    write_file(run_dir / "downloads_staging" / "airbnb" / filename, "<html></html>")

    rows = rows_by_name(file_output_audit.build_rows(RUN_DATE, run_dir))

    row = rows[filename]
    assert row["retention_class"] == "staging_failed_keep_short_term"
    assert row["cleanup_candidate"] == "false"
    assert row["recommended_retention_days"] == "30"
