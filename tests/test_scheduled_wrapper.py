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
        assert "monthly_trends.csv" in log_text
        assert "bookings_report.xlsx" in log_text
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
    assert "--target $target" not in script
    assert '"future-export"' not in script
    assert '"settings-snapshot"' not in script
    assert '$env:PYTHONPATH = "src"' in script
    assert "Gmail/send mode is not changed by this wrapper." in script


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
