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


def test_monday_full_report_wrapper_exists_and_orders_steps() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "run_monday_full_report.ps1"

    script = script_path.read_text(encoding="utf-8")

    expected_order = [
        "scheduled weekly pipeline",
        "StayFi anniversary summary",
        "StayFi anniversary email dry-run",
        "StayFi dry-run recipient list",
        "Send these StayFi anniversary emails now? Type SEND to continue",
        "StayFi anniversary email real send",
    ]
    positions = [script.index(token) for token in expected_order]
    assert positions == sorted(positions)
    assert "monday_full_report_$RunDate.log" in script
    assert '[string]$RunDate = (Get-Date -Format "yyyy-MM-dd")' in script
    assert "Resolved RunDate: $RunDate" in script
    assert "run_scheduled_weekly_pipeline.ps1" in script
    assert "send_stayfi_anniversary_emails.ps1" in script
    assert "-DryRun" in script
    assert "[switch]$AutoSendStayFi" in script
    assert "AutoSendStayFi enabled: $($AutoSendStayFi.IsPresent)" in script
    assert '$confirmation -ne "SEND"' in script
    assert "No StayFi anniversary emails to send this week." in script
    assert "Dry-run found no sendable recipients." in script
    assert "Send skipped by user. Dry-run results are available for review." in script
    assert "StayFi send failed due to Gmail OAuth token error." in script
    assert "send_stayfi_anniversary_emails.ps1 -RunDate $RunDate -ResetOAuthToken" in script


def test_send_weekly_revenue_report_script_is_explicit_manual_send_only() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "send_weekly_revenue_report.ps1").read_text(encoding="utf-8")
    pipeline = (repo_root / "run_weekly_pipeline.ps1").read_text(encoding="utf-8")

    assert "pricelabs.transform.email_sender" in script
    assert "--explicit-send" in script
    assert "email_revenue_report_send_result_$RunDate.csv" in script
    assert "send_weekly_revenue_report.ps1" not in pipeline


def test_monday_full_report_wrapper_keeps_airbnb_steps_nonblocking() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_monday_full_report.ps1").read_text(encoding="utf-8")

    assert "default mode never sends StayFi emails without exact SEND confirmation." in script
    assert "& $stayfiSendWrapper -RunDate $RunDate -DryRun" in script
    assert "& $stayfiSendWrapper -RunDate $RunDate 2>&1" in script
    assert "$sendableRows.Count -eq 0" in script
    assert '$confirmation = Read-Host "Send these StayFi anniversary emails now? Type SEND to continue"' in script
    assert "failed_blocking: scheduled weekly pipeline" in script


def test_monday_full_report_wrapper_autosend_sends_only_after_successful_dry_run() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_monday_full_report.ps1").read_text(encoding="utf-8")

    dry_run_position = script.index("started: StayFi anniversary email dry-run")
    sendable_position = script.index("$sendableRows.Count -eq 0")
    autosend_position = script.index("AutoSendStayFi enabled; sending StayFi anniversary emails after successful dry-run.")
    real_send_position = script.index("started: StayFi anniversary email real send")

    assert dry_run_position < sendable_position < autosend_position < real_send_position
    assert "failed_blocking: StayFi anniversary email dry-run" in script
    assert "Test-GmailOAuthErrorText" in script
    assert "Write-GmailOAuthRecovery" in script
    assert "Dry-run found no sendable recipients." in script
    assert "StayFi final send result path: $sendResultsFile" in script


def test_monday_full_report_wrapper_autosend_skips_no_eligible_and_duplicates() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_monday_full_report.ps1").read_text(encoding="utf-8")

    assert "$eligibleGuests -eq 0 -or $draftsPrepared -eq 0" in script
    assert "No StayFi anniversary emails to send this week." in script
    assert '$dryRunRows | Where-Object { $_.send_status -eq "dry_run_would_send" }' in script
    assert "Dry-run found no sendable recipients." in script
    assert "skipped duplicates from permanent log" in script


def test_monday_full_report_wrapper_stops_when_pricelabs_raw_files_missing() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-01"
    run_dir = repo_root / "data" / "runs" / run_date
    log_file = run_dir / "logs" / f"monday_full_report_{run_date}.log"

    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(repo_root / "scripts" / "run_monday_full_report.ps1"),
                "-RunDate",
                run_date,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 2
        assert log_file.exists()
        log_text = log_file.read_text(encoding="utf-8")
        assert "started: scheduled weekly pipeline" in log_text
        assert "failed_blocking: scheduled weekly pipeline exit_code=2" in log_text
        assert "priceLabs_future_export.csv" in log_text
        assert "price_occ.csv" in log_text
        assert "monthly_trends.csv" in log_text
        assert "bookings_report.xlsx" in log_text
        assert "StayFi anniversary email dry-run" not in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_monday_full_report_wrapper_does_not_reference_browser_profile_for_evidence() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_monday_full_report.ps1").read_text(encoding="utf-8")

    assert "Copy-Item" not in script
    assert ".local/browser_profiles" not in script
    assert "credential" not in script.lower()


def test_register_monday_full_report_task_script_builds_safe_command() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "register_monday_full_report_task.ps1").read_text(encoding="utf-8")

    assert 'TaskName = "Aloha Poconos Monday Full Report"' in script
    assert '[string]$Time = "09:00"' in script
    assert '[string]$DayOfWeek = "Monday"' in script
    assert "[switch]$AutoSendStayFi" in script
    assert "[switch]$DisableAutoSendStayFi" in script
    assert "powershell.exe" in script
    assert "-NoProfile -ExecutionPolicy Bypass -Command" in script
    assert ".\\.venv\\Scripts\\Activate.ps1" in script
    assert ".\\scripts\\run_monday_full_report.ps1" in script
    assert "-AutoSendStayFi" in script
    assert "New-ScheduledTaskPrincipal" in script
    assert "-LogonType Interactive" in script
    assert "-RunLevel Highest" in script
    assert "Run only when user is logged on." in script
    assert "Run with highest privileges: enabled." in script
    assert "No secrets are printed or inspected." in script


def test_register_monday_full_report_task_script_validates_required_files_and_whatif() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "register_monday_full_report_task.ps1").read_text(encoding="utf-8")

    assert "data\\source\\stayfi\\stayfi_guests_2026.csv" in script
    assert "config\\gmail_oauth_client.json" in script
    assert ".local\\gmail_token.json" in script
    assert "First unattended Gmail send may fail until OAuth token exists." in script
    assert "$WhatIf.IsPresent" in script
    assert "WhatIf: scheduled task was not registered." in script
    assert "Register-ScheduledTask" in script


def test_register_monday_full_report_task_whatif_does_not_register(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    project_root = tmp_path / "project"
    (project_root / ".venv" / "Scripts").mkdir(parents=True)
    (project_root / "scripts").mkdir(parents=True)
    (project_root / "data" / "source" / "stayfi").mkdir(parents=True)
    (project_root / "config").mkdir(parents=True)
    (project_root / ".local").mkdir(parents=True)
    (project_root / ".venv" / "Scripts" / "Activate.ps1").write_text("", encoding="utf-8")
    (project_root / "scripts" / "run_monday_full_report.ps1").write_text("", encoding="utf-8")
    (project_root / "data" / "source" / "stayfi" / "stayfi_guests_2026.csv").write_text("header\n", encoding="utf-8")
    (project_root / "config" / "gmail_oauth_client.json").write_text("{}", encoding="utf-8")
    (project_root / ".local" / "gmail_token.json").write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "scripts" / "register_monday_full_report_task.ps1"),
            "-ProjectRoot",
            str(project_root),
            "-WhatIf",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert "WhatIf: scheduled task was not registered." in result.stdout
    assert "AutoSendStayFi enabled: True" in result.stdout
    assert ".\\scripts\\run_monday_full_report.ps1 -AutoSendStayFi" in result.stdout


def test_check_monday_full_report_task_script_reports_status_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "check_monday_full_report_task.ps1").read_text(encoding="utf-8")

    assert 'TaskName = "Aloha Poconos Monday Full Report"' in script
    assert "Get-ScheduledTask" in script
    assert "Get-ScheduledTaskInfo" in script
    assert "Task exists:" in script
    assert "Next run time:" in script
    assert "Last run time:" in script
    assert "Last task result:" in script
    assert "State:" in script


def test_weekly_pipeline_generates_combined_signal_before_email_report() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "run_weekly_pipeline.ps1").read_text(encoding="utf-8")

    airbnb_capture_position = script.index('"airbnb.download_diagnostics"')
    airbnb_promote_position = script.index('"promote-staged"')
    airbnb_position = script.index('"airbnb.run_diagnostics"')
    combined_position = script.index('"analysis.combined_market_listing_signal"')
    diagnostic_position = script.index('"analysis.diagnostic_issue_tracker"')
    competitor_calendar_position = script.index('"pricelabs.transform.competitor_calendar"')
    listing_review_position = script.index('"analysis.listing_competitor_review"')
    listing_snapshot_position = script.index('"analysis.listing_state_snapshot"')
    search_visibility_position = script.index('"analysis.airbnb_search_visibility"')
    active_tests_position = script.index('"analysis.active_tests"')
    stayfi_anniversary_position = script.index('"marketing.stayfi_anniversary_email"')
    email_position = script.index('"pricelabs.transform.email_revenue_report"')
    evidence_position = script.index('"pricelabs.transform.evidence_bundle"')
    html_position = script.index('"pricelabs.transform.email_html_report"')
    draft_position = script.index('"pricelabs.transform.email_draft_file"')

    assert (
        airbnb_capture_position
        < airbnb_promote_position
        < airbnb_position
        < combined_position
        < diagnostic_position
        < competitor_calendar_position
        < listing_review_position
        < listing_snapshot_position
        < search_visibility_position
        < active_tests_position
        < stayfi_anniversary_position
        < email_position
        < evidence_position
        < html_position
        < draft_position
    )
    assert "[switch]$SkipAirbnb" in script
    assert "[switch]$ForceAirbnbCapture" in script
    assert "== Airbnb auto diagnostics ==" in script
    assert "Airbnb raw inputs found:" in script
    assert "Airbnb analysis outputs found:" in script
    assert "Airbnb capture required:" in script
    assert "Airbnb capture status:" in script
    assert "Airbnb promotion status:" in script
    assert "Airbnb diagnostics status:" in script
    assert '"-m", "airbnb.download_diagnostics"' in script
    assert '"capture-headed-and-validate"' in script
    assert '"promote-staged"' in script
    assert '"-m", "airbnb.run_diagnostics"' in script
    assert "Use -ForceAirbnbCapture to recapture." in script
    assert "Airbnb auto diagnostics skipped because -SkipAirbnb was provided." in script
    assert '"-m", "analysis.combined_market_listing_signal"' in script
    assert '"-m", "analysis.diagnostic_issue_tracker"' in script
    assert '"-m", "pricelabs.transform.competitor_calendar"' in script
    assert '"-m", "analysis.listing_competitor_review"' in script
    assert '"-m", "analysis.listing_state_snapshot"' in script
    assert '"-m", "analysis.airbnb_search_visibility"' in script
    assert '"-m", "analysis.active_tests"' in script
    assert '"-m", "marketing.stayfi_anniversary_email"' in script
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
    assert '$activeTestsFile = Join-Path $analysisDir "active_tests_$RunDate.csv"' in script
    assert '$stayfiAnniversarySummaryFile = Join-Path $analysisDir "stayfi_anniversary_email_summary_$RunDate.csv"' in script
    assert '"--combined-signal-file", $combinedMarketListingSignalFile' in script
    assert '"--diagnostic-issue-file", $diagnosticIssueTrackerFile' in script
    assert '"--listing-review-file", $listingCompetitorReviewCsvFile' in script
    assert '"--active-tests-file", $activeTestsFile' in script
    assert "combined_market_listing_signal output path:" in script
    assert "diagnostic_issue_tracker output path:" in script
    assert "pricelabs_competitor_calendar output path:" in script
    assert "listing_competitor_review output path:" in script
    assert "listing_state_snapshot output path:" in script
    assert "airbnb_search_visibility output path:" in script
    assert "active_tests output path:" in script
    assert "stayfi_anniversary_email_summary output path:" in script
    assert "evidence_bundle manifest path:" in script
    assert "Airbnb funnel diagnostics require manual MFA capture before final email report." in script
    assert "Airbnb report integration: included" in script
    assert "Airbnb report integration: unavailable" in script
    assert "Airbnb report integration: unavailable, root cause date_range_not_able_to_set_up" in script
    assert "Email markdown Airbnb section: included" in script


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
    assert 'analysis\\active_tests_$RunDate.csv' in script
    assert 'analysis\\airbnb_weekly_conversion_summary_$RunDate.csv' in script
    assert 'analysis\\airbnb_weekly_history_comparison_$RunDate.csv' in script
    assert 'analysis\\email_revenue_report_$RunDate.md' in script
    assert script.index('analysis\\diagnostic_issue_tracker_$RunDate.csv') < script.index('analysis\\pricelabs_competitor_calendar_$RunDate.csv')
    assert script.index('analysis\\pricelabs_competitor_calendar_$RunDate.csv') < script.index('analysis\\listing_competitor_review_$RunDate.md')
    assert script.index('analysis\\listing_competitor_review_$RunDate.csv') < script.index('analysis\\listing_state_snapshot_$RunDate.md')
    assert script.index('analysis\\listing_state_snapshot_$RunDate.md') < script.index('analysis\\active_tests_$RunDate.csv')
    assert script.index('analysis\\active_tests_$RunDate.csv') < script.index('analysis\\email_revenue_report_$RunDate.md')
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
