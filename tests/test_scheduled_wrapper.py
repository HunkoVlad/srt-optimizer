import subprocess
from pathlib import Path


def test_scheduled_wrapper_reports_new_required_raw_files_when_missing() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-01-01"
    log_file = repo_root / "data" / "runs" / run_date / "logs" / f"scheduled_pipeline_{run_date}.log"
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
