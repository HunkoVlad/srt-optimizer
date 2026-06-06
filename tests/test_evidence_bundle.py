import csv
import json
from pathlib import Path

from pricelabs.transform.evidence_bundle import run


RUN_DATE = "2026-05-20"


def write_text(path: Path, content: str = "data\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_combined_signal(path: Path, priority: str = "medium") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "run_date",
                "combined_signal_category",
                "investigation_priority",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "run_date": RUN_DATE,
                "combined_signal_category": "outperformance_pricing_efficiency_investigation",
                "investigation_priority": priority,
            }
        )


def create_core_files(run_dir: Path, priority: str = "medium") -> None:
    analysis_dir = run_dir / "analysis"
    write_text(analysis_dir / f"email_revenue_report_{RUN_DATE}.md", "# Report\n")
    write_text(analysis_dir / f"rolling_13_month_revenue_view_{RUN_DATE}.csv")
    write_text(analysis_dir / f"monthly_revenue_summary_{RUN_DATE}.md")
    write_text(analysis_dir / f"performance_reason_review_{RUN_DATE}.csv")
    write_text(analysis_dir / f"future_window_summary_{RUN_DATE}.csv")
    write_text(analysis_dir / f"future_window_signals_{RUN_DATE}.csv")
    write_combined_signal(analysis_dir / f"combined_market_listing_signal_{RUN_DATE}.csv", priority)


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def copied_names(manifest: dict) -> set[str]:
    return {Path(entry["bundled_path"]).name for entry in manifest["files"] if entry["copied"]}


def test_evidence_bundle_folder_and_manifest_are_created(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)

    manifest_path = run(RUN_DATE, run_dir=run_dir)
    manifest = read_manifest(manifest_path)

    assert manifest_path.exists()
    assert manifest_path.parent == run_dir / "analysis" / f"evidence_bundle_{RUN_DATE}"
    assert manifest["run_date"] == RUN_DATE
    assert manifest["attachment_mode"] == "bundle_only"
    assert manifest["status"] == "complete"
    assert manifest["missing_required_files"] == []
    assert len(manifest["files"]) == 26


def test_core_files_are_copied_and_labeled_core(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))

    names = copied_names(manifest)
    assert f"{RUN_DATE}__report__email_revenue_report_{RUN_DATE}.md" in names
    assert f"{RUN_DATE}__pricelabs_core__future_window_signals_{RUN_DATE}.csv" in names
    copied_entries = [entry for entry in manifest["files"] if entry["copied"]]
    assert all(entry["source_of_truth_type"] == "core" for entry in copied_entries)
    assert all(entry["copied"] for entry in manifest["files"] if entry["required"])


def test_high_priority_optional_files_are_copied_only_when_priority_is_high(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir, priority="medium")
    write_text(run_dir / "analysis" / f"airbnb_weekly_history_comparison_{RUN_DATE}.csv")
    write_text(run_dir / "analysis" / f"airbnb_similar_listing_summary_{RUN_DATE}.csv")
    write_text(run_dir / "settings" / f"pricelabs_settings_snapshot_{RUN_DATE}.json", "{}\n")
    write_text(run_dir / "settings" / f"pricelabs_settings_changes_{RUN_DATE}.csv")

    medium_manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    assert all(entry["source_of_truth_type"] == "core" for entry in medium_manifest["files"] if entry["copied"])

    write_combined_signal(run_dir / "analysis" / f"combined_market_listing_signal_{RUN_DATE}.csv", "high")
    high_manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))

    source_types = {entry["source_of_truth_type"] for entry in high_manifest["files"]}
    assert {"core", "combined", "diagnostic", "configuration", "marketing_diagnostic"} == source_types
    names = copied_names(high_manifest)
    assert f"{RUN_DATE}__airbnb_diagnostic__airbnb_weekly_history_comparison_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__settings__pricelabs_settings_snapshot_{RUN_DATE}.json" in names


def test_airbnb_diagnostic_report_is_optional_high_priority_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir, priority="high")
    write_text(run_dir / "analysis" / f"airbnb_conversion_diagnostic_report_{RUN_DATE}.md", "# Airbnb Report\n")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    report_entry = next(
        entry
        for entry in manifest["files"]
        if entry["role"] == "airbnb_funnel_diagnostic_report"
    )

    assert f"{RUN_DATE}__airbnb_diagnostic__airbnb_conversion_diagnostic_report_{RUN_DATE}.md" in names
    assert report_entry["category"] == "airbnb_diagnostic"
    assert report_entry["required"] is False
    assert report_entry["source_of_truth_type"] == "diagnostic"


def test_diagnostic_issue_tracker_is_optional_combined_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(run_dir / "analysis" / f"diagnostic_issue_tracker_{RUN_DATE}.csv")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    issue_entry = next(
        entry
        for entry in manifest["files"]
        if entry["role"] == "open_diagnostic_issue_history"
    )

    assert f"{RUN_DATE}__diagnostic_issue_tracker__diagnostic_issue_tracker_{RUN_DATE}.csv" in names
    assert issue_entry["category"] == "diagnostic_issue_tracker"
    assert issue_entry["required"] is False
    assert issue_entry["source_of_truth_type"] == "combined"


def test_listing_competitor_review_outputs_are_optional_diagnostic_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(run_dir / "analysis" / f"listing_competitor_review_{RUN_DATE}.md", "# Listing Review\n")
    write_text(run_dir / "analysis" / f"listing_competitor_review_{RUN_DATE}.csv")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    entries = [
        entry
        for entry in manifest["files"]
        if entry["category"] == "listing_competitor_review" and entry["copied"]
    ]

    assert f"{RUN_DATE}__listing_competitor_review__listing_competitor_review_{RUN_DATE}.md" in names
    assert f"{RUN_DATE}__listing_competitor_review__listing_competitor_review_{RUN_DATE}.csv" in names
    assert len(entries) == 2
    assert all(entry["role"] == "listing_side_investigation" for entry in entries)
    assert all(entry["required"] is False for entry in entries)
    assert all(entry["source_of_truth_type"] == "diagnostic" for entry in entries)


def test_listing_state_snapshot_outputs_are_optional_diagnostic_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(run_dir / "analysis" / f"listing_state_snapshot_{RUN_DATE}.md", "# Listing Snapshot\n")
    write_text(run_dir / "analysis" / f"listing_search_card_{RUN_DATE}.png", "png")
    write_text(run_dir / "analysis" / f"listing_page_top_{RUN_DATE}.png", "png")
    write_text(run_dir / "analysis" / f"listing_first_5_photos_{RUN_DATE}.png", "png")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    entries = [
        entry
        for entry in manifest["files"]
        if entry["category"] == "listing_state_snapshot" and entry["copied"]
    ]

    assert f"{RUN_DATE}__listing_state_snapshot__listing_state_snapshot_{RUN_DATE}.md" in names
    assert f"{RUN_DATE}__listing_state_snapshot__listing_search_card_{RUN_DATE}.png" in names
    assert f"{RUN_DATE}__listing_state_snapshot__listing_page_top_{RUN_DATE}.png" in names
    assert f"{RUN_DATE}__listing_state_snapshot__listing_first_5_photos_{RUN_DATE}.png" in names
    assert {entry["role"] for entry in entries} == {"listing_state_baseline", "listing_visual_baseline"}
    assert all(entry["required"] is False for entry in entries)
    assert all(entry["source_of_truth_type"] == "diagnostic" for entry in entries)


def test_listing_change_log_is_optional_diagnostic_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(tmp_path / "data" / "history" / "listing_change_log.csv", "change_date,run_date\n")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    entry = next(
        entry
        for entry in manifest["files"]
        if entry["role"] == "listing_change_history"
    )

    assert f"{RUN_DATE}__listing_change_log__listing_change_log.csv" in names
    assert entry["category"] == "listing_change_log"
    assert entry["required"] is False
    assert entry["source_of_truth_type"] == "diagnostic"


def test_pricelabs_competitor_list_is_optional_listing_review_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(run_dir / "raw" / f"pricelabs_competitor_list_{RUN_DATE}.csv")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    competitor_entry = next(
        entry
        for entry in manifest["files"]
        if entry["role"] == "manually_selected_pricelabs_competitor_set"
    )

    assert f"{RUN_DATE}__listing_competitor_review__pricelabs_competitor_list_{RUN_DATE}.csv" in names
    assert competitor_entry["category"] == "listing_competitor_review"
    assert competitor_entry["required"] is False
    assert competitor_entry["source_of_truth_type"] == "diagnostic"


def test_normalized_competitor_calendar_is_optional_diagnostic_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(run_dir / "analysis" / f"pricelabs_competitor_calendar_{RUN_DATE}.csv")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    calendar_entry = next(
        entry
        for entry in manifest["files"]
        if entry["role"] == "pricelabs_competitor_price_min_stay_availability_context_90_day"
    )

    assert f"{RUN_DATE}__competitor_calendar__pricelabs_competitor_calendar_{RUN_DATE}.csv" in names
    assert calendar_entry["category"] == "competitor_calendar"
    assert calendar_entry["required"] is False
    assert calendar_entry["source_of_truth_type"] == "diagnostic"


def test_airbnb_search_visibility_outputs_are_optional_diagnostic_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(run_dir / "raw" / f"airbnb_search_visibility_input_{RUN_DATE}.csv")
    write_text(run_dir / "analysis" / f"airbnb_search_visibility_{RUN_DATE}.csv")
    write_text(run_dir / "analysis" / f"airbnb_search_visibility_{RUN_DATE}.md")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    entries = [
        entry
        for entry in manifest["files"]
        if entry["category"] == "airbnb_search_visibility" and entry["copied"]
    ]

    assert f"{RUN_DATE}__airbnb_search_visibility__airbnb_search_visibility_input_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__airbnb_search_visibility__airbnb_search_visibility_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__airbnb_search_visibility__airbnb_search_visibility_{RUN_DATE}.md" in names
    assert len(entries) == 3
    assert all(entry["role"] == "broad_and_high_intent_search_discovery_diagnostic" for entry in entries)
    assert all(entry["source_of_truth_type"] == "diagnostic" for entry in entries)


def test_stayfi_anniversary_outputs_are_optional_marketing_evidence(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    write_text(run_dir / "analysis" / f"stayfi_anniversary_email_candidates_{RUN_DATE}.csv")
    write_text(run_dir / "analysis" / f"stayfi_anniversary_email_drafts_{RUN_DATE}.csv")
    write_text(run_dir / "analysis" / f"stayfi_anniversary_email_summary_{RUN_DATE}.csv")
    write_text(run_dir / "analysis" / f"stayfi_anniversary_gmail_draft_results_{RUN_DATE}.csv")
    write_text(run_dir / "analysis" / f"stayfi_anniversary_email_send_results_{RUN_DATE}.csv")
    write_text(tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv", "email,first_name\n")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    names = copied_names(manifest)
    entries = [
        entry
        for entry in manifest["files"]
        if entry["category"] == "stayfi_anniversary_email" and entry["copied"]
    ]

    assert f"{RUN_DATE}__stayfi_anniversary_email__stayfi_anniversary_email_candidates_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__stayfi_anniversary_email__stayfi_anniversary_email_drafts_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__stayfi_anniversary_email__stayfi_anniversary_email_summary_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__stayfi_anniversary_email__stayfi_anniversary_gmail_draft_results_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__stayfi_anniversary_email__stayfi_anniversary_email_send_results_{RUN_DATE}.csv" in names
    assert f"{RUN_DATE}__stayfi_anniversary_email__stayfi_anniversary_email_log.csv" in names
    assert {entry["source_of_truth_type"] for entry in entries} == {"marketing_diagnostic"}
    assert all(entry["required"] is False for entry in entries)


def test_missing_high_priority_optional_files_do_not_fail(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir, priority="high")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))

    assert manifest["status"] == "complete"
    assert manifest["missing_required_files"] == []
    assert len(manifest["missing_optional_files"]) == 24
    assert any("diagnostic_issue_tracker" in path for path in manifest["missing_optional_files"])
    assert any("listing_competitor_review" in path for path in manifest["missing_optional_files"])
    assert any("listing_state_snapshot" in path for path in manifest["missing_optional_files"])
    assert any("listing_change_log" in path for path in manifest["missing_optional_files"])
    assert any("pricelabs_competitor_list" in path for path in manifest["missing_optional_files"])
    assert any("pricelabs_competitor_calendar" in path for path in manifest["missing_optional_files"])
    assert any("airbnb_search_visibility" in path for path in manifest["missing_optional_files"])
    assert any("airbnb_conversion_diagnostic_report" in path for path in manifest["missing_optional_files"])
    assert any("airbnb_weekly_history_comparison" in path for path in manifest["missing_optional_files"])
    assert any("stayfi_anniversary_email" in path for path in manifest["missing_optional_files"])


def test_missing_required_core_file_sets_partial_status(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir)
    (run_dir / "analysis" / f"future_window_summary_{RUN_DATE}.csv").unlink()

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))

    assert manifest["status"] == "partial"
    assert any("future_window_summary" in path for path in manifest["missing_required_files"])
    missing_entry = next(entry for entry in manifest["files"] if "future_window_summary" in entry["source_path"])
    assert missing_entry["required"] is True
    assert missing_entry["exists"] is False
    assert missing_entry["copied"] is False


def test_raw_staging_logs_and_browser_state_are_never_copied(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    create_core_files(run_dir, priority="high")
    write_text(run_dir / "raw" / "priceLabs_future_export.csv")
    write_text(run_dir / "downloads_staging" / "monthly_trends.csv")
    write_text(run_dir / "logs" / "pricelabs_download_debug.png")
    write_text(tmp_path / ".local" / "pricelabs_browser_profile" / "Cookies", "secret")
    write_text(tmp_path / ".local" / "browser_profiles" / "airbnb" / "Cookies", "secret")

    manifest = read_manifest(run(RUN_DATE, run_dir=run_dir))
    bundled_text = "\n".join(copied_names(manifest)).lower()
    manifest_text = json.dumps(manifest).lower()

    assert "pricelabs_future_export" not in bundled_text
    assert "monthly_trends" not in bundled_text
    assert "debug" not in bundled_text
    assert "cookies" not in manifest_text
    assert "browser_profiles" not in manifest_text
    assert "downloads_staging" not in manifest_text
    assert "priceLabs_future_export.csv".lower() not in manifest_text
    assert "/raw/" not in manifest_text
