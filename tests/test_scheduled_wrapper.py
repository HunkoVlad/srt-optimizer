import subprocess
import shutil
from pathlib import Path


def test_scheduled_wrapper_reports_new_required_raw_files_when_missing() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-01-01"
    run_dir = repo_root / "data" / "runs" / run_date
    log_file = run_dir / "logs" / f"scheduled_pipeline_{run_date}.log"

    try:
        if log_file.exists():
            log_file.unlink()

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(repo_root / "scripts" / "run_scheduled_weekly_pipeline.ps1"),
                "-RunDate",
                run_date,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode != 0
        assert log_file.exists()
        log_text = log_file.read_text(encoding="utf-8")
        assert "priceLabs_future_export.csv" in log_text
        assert "price_occ.csv" in log_text
        assert "monthly_trends.csv" in log_text
        assert "bookings_report.xlsx" in log_text
        assert "pricelabs_settings_manual_input.json" not in log_text
        assert "Pipeline not executed because required inputs are incomplete." in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_weekly_with_pricelabs_downloads_wrapper_orders_safe_steps() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_weekly_with_pricelabs_downloads.ps1"

    script = script_path.read_text(encoding="utf-8")

    expected_order = [
        "--download-all",
        "--promote-to-raw",
        "run_weekly_pipeline.ps1",
    ]
    positions = [script.index(token) for token in expected_order]
    assert positions == sorted(positions)
    assert script.count("--download-all") == 1
    assert "--promote-to-raw" in script
    assert "[switch]$UsePersistentSession" in script
    assert "--use-persistent-session" in script
    assert "[switch]$UseLocalCredentials" in script
    assert "--use-local-credentials" in script
    assert "[switch]$Headless" in script
    assert "--headless" in script
    assert "Headless mode requires -UseLocalCredentials" in script
    assert "--target $target" not in script
    assert '"future-export"' not in script
    assert '"settings-snapshot"' not in script
    assert '$env:PYTHONPATH = "src"' in script
    assert "Gmail/send mode is not changed by this wrapper." in script


def test_weekly_with_pricelabs_downloads_wrapper_accepts_today_run_date() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_weekly_with_pricelabs_downloads.ps1"

    script = script_path.read_text(encoding="utf-8")

    assert '$RunDate -eq "today"' in script
    assert 'Get-Date -Format "yyyy-MM-dd"' in script
    assert "RunDate must use YYYY-MM-DD format or today." in script


def test_weekly_pipeline_generates_combined_signal_before_email_report() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "run_weekly_pipeline.ps1").read_text(encoding="utf-8")

    airbnb_position = script.index('"airbnb.run_diagnostics"')
    combined_position = script.index('"analysis.combined_market_listing_signal"')
    diagnostic_position = script.index('"analysis.diagnostic_issue_tracker"')
    competitor_calendar_position = script.index('"pricelabs.transform.competitor_calendar"')
    listing_review_position = script.index('"analysis.listing_competitor_review"')
    listing_snapshot_position = script.index('"analysis.listing_state_snapshot"')
    search_visibility_position = script.index('"analysis.airbnb_search_visibility"')
    email_position = script.index('"pricelabs.transform.email_revenue_report"')
    evidence_position = script.index('"pricelabs.transform.evidence_bundle"')
    html_position = script.index('"pricelabs.transform.email_html_report"')
    draft_position = script.index('"pricelabs.transform.email_draft_file"')

    assert (
        airbnb_position
        < combined_position
        < diagnostic_position
        < competitor_calendar_position
        < listing_review_position
        < listing_snapshot_position
        < search_visibility_position
        < email_position
        < evidence_position
        < html_position
        < draft_position
    )
    assert '"-m", "airbnb.run_diagnostics"' in script
    assert '"-m", "analysis.combined_market_listing_signal"' in script
    assert '"-m", "analysis.diagnostic_issue_tracker"' in script
    assert '"-m", "pricelabs.transform.competitor_calendar"' in script
    assert '"-m", "analysis.listing_competitor_review"' in script
    assert '"-m", "analysis.listing_state_snapshot"' in script
    assert '"-m", "analysis.airbnb_search_visibility"' in script
    assert '"-m", "pricelabs.transform.email_revenue_report"' in script
    assert '"-m", "pricelabs.transform.evidence_bundle"' in script
    assert '$combinedMarketListingSignalFile = Join-Path $analysisDir "combined_market_listing_signal_$RunDate.csv"' in script
    assert '$diagnosticIssueTrackerFile = Join-Path $analysisDir "diagnostic_issue_tracker_$RunDate.csv"' in script
    assert '$pricelabsCompetitorCalendarFile = Join-Path $analysisDir "pricelabs_competitor_calendar_$RunDate.csv"' in script
    assert '$pricelabsCompetitorListFile = Join-Path $rawDir "pricelabs_competitor_list_$RunDate.csv"' in script
    assert '$listingCompetitorReviewFile = Join-Path $analysisDir "listing_competitor_review_$RunDate.md"' in script
    assert '$listingCompetitorReviewCsvFile = Join-Path $analysisDir "listing_competitor_review_$RunDate.csv"' in script
    assert '$listingStateSnapshotFile = Join-Path $analysisDir "listing_state_snapshot_$RunDate.md"' in script
    assert '$airbnbSearchVisibilityFile = Join-Path $analysisDir "airbnb_search_visibility_$RunDate.md"' in script
    assert '"--combined-signal-file", $combinedMarketListingSignalFile' in script
    assert '"--diagnostic-issue-file", $diagnosticIssueTrackerFile' in script
    assert '"--listing-review-file", $listingCompetitorReviewCsvFile' in script
    assert "combined_market_listing_signal output path:" in script
    assert "diagnostic_issue_tracker output path:" in script
    assert "pricelabs_competitor_calendar output path:" in script
    assert "listing_competitor_review output path:" in script
    assert "listing_state_snapshot output path:" in script
    assert "airbnb_search_visibility output path:" in script
    assert "evidence_bundle manifest path:" in script


def test_weekly_with_pricelabs_downloads_cleans_staging_only_after_success() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_weekly_with_pricelabs_downloads.ps1"

    script = script_path.read_text(encoding="utf-8")

    pipeline_position = script.index('Invoke-WorkflowStep "Weekly revenue pipeline"')
    cleanup_position = script.index("Cleaned downloads_staging after successful workflow.")
    remove_position = script.index("Remove-Item -LiteralPath $stagingDir -Recurse -Force")

    assert pipeline_position < remove_position < cleanup_position
    assert "[switch]$KeepStaging" in script
    assert "KeepStaging requested; downloads_staging preserved." in script
    assert "Join-Path $runRoot \"downloads_staging\"" in script
    assert "Remove-Item -LiteralPath $stagingDir -Recurse -Force" in script
    assert "raw" not in script[remove_position : remove_position + 120].lower()
    assert "logs" not in script[remove_position : remove_position + 120].lower()
    assert "analysis" not in script[remove_position : remove_position + 120].lower()
    assert "settings" not in script[remove_position : remove_position + 120].lower()


def test_pricelabs_production_scheduler_task_is_documented() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    scheduler_doc = (
        repo_root / "docs" / "windows-task-scheduler-setup-v1.md"
    ).read_text(encoding="utf-8")
    runbook_doc = (repo_root / "docs" / "runbook-weekly-pricelabs.md").read_text(
        encoding="utf-8"
    )

    for doc in (scheduler_doc, runbook_doc):
        assert "Aloha Poconos Weekly PriceLabs Headless Pipeline" in doc
        assert "-RunDate today -UseLocalCredentials -Headless" in doc
        assert "C:\\Users\\Volodymyr\\srt-optimizer" in doc
        assert ".local/pricelabs.env" in doc
        assert "MFA" in doc
        assert "Gmail/send mode" in doc


def test_scheduled_wrapper_checks_evidence_bundle_manifest_output() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_scheduled_weekly_pipeline.ps1").read_text(encoding="utf-8")

    assert 'analysis\\evidence_bundle_$RunDate\\evidence_manifest_$RunDate.json' in script
    assert 'analysis\\diagnostic_issue_tracker_$RunDate.csv' in script
    assert 'raw\\pricelabs_competitor_list_$RunDate.csv' in script
    assert 'analysis\\pricelabs_competitor_calendar_$RunDate.csv' in script
    assert 'analysis\\listing_competitor_review_$RunDate.md' in script
    assert 'analysis\\listing_competitor_review_$RunDate.csv' in script
    assert 'analysis\\listing_state_snapshot_$RunDate.md' in script
    assert 'analysis\\email_revenue_report_$RunDate.md' in script
    assert script.index('analysis\\diagnostic_issue_tracker_$RunDate.csv') < script.index('analysis\\pricelabs_competitor_calendar_$RunDate.csv')
    assert script.index('analysis\\pricelabs_competitor_calendar_$RunDate.csv') < script.index('analysis\\listing_competitor_review_$RunDate.md')
    assert script.index('analysis\\listing_competitor_review_$RunDate.csv') < script.index('analysis\\listing_state_snapshot_$RunDate.md')
    assert script.index('analysis\\listing_state_snapshot_$RunDate.md') < script.index('analysis\\email_revenue_report_$RunDate.md')
    assert script.index('analysis\\email_revenue_report_$RunDate.md') < script.index(
        'analysis\\evidence_bundle_$RunDate\\evidence_manifest_$RunDate.json'
    )


def test_scheduled_wrapper_required_raw_inputs_match_current_pricelabs_sources() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_scheduled_weekly_pipeline.ps1").read_text(encoding="utf-8")
    required_block = script.split("$requiredRawFiles = @(", 1)[1].split("\n)", 1)[0]

    assert "priceLabs_future_export.csv" in required_block
    assert "price_occ.csv" in required_block
    assert "monthly_trends.csv" in required_block
    assert "bookings_report.xlsx" in required_block
    assert "pricelabs_settings_manual_input.json" not in required_block
    assert "pricelabs_settings_snapshot_from_ui.json" not in required_block
    assert "Competitor Calendar.csv" not in required_block
    assert "airbnb_" not in required_block
