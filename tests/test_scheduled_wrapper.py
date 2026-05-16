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
        '"future-export"',
        '"price-occ"',
        '"monthly-trends"',
        '"bookings-report"',
        '"settings-snapshot"',
        "--promote-to-raw",
        "run_weekly_pipeline.ps1",
    ]
    positions = [script.index(token) for token in expected_order]
    assert positions == sorted(positions)
    assert "--promote-to-raw" in script
    assert "--target $target" in script
    assert '$env:PYTHONPATH = "src"' in script
    assert "Gmail/send mode is not changed by this wrapper." in script
