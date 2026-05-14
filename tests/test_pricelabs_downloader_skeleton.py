import shutil
import subprocess
import sys
from pathlib import Path


def test_pricelabs_downloader_skeleton_creates_staging_and_log_only() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-01"
    run_dir = repo_root / "data" / "runs" / run_date
    staging_dir = run_dir / "downloads_staging"
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pricelabs.download.pricelabs_downloader",
                "--run-date",
                run_date,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert staging_dir.is_dir()
        assert log_file.exists()
        assert not raw_dir.exists()

        log_text = log_file.read_text(encoding="utf-8")
        assert "mode=dry-run skeleton" in log_text
        assert "No browser opened." in log_text
        assert "No files downloaded." in log_text
        assert "No raw files created or modified." in log_text
        assert "authentication: not implemented" in log_text
        assert "promotion to raw: not implemented" in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_pricelabs_downloader_skeleton_rejects_invalid_run_date() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-2-1"
    run_dir = repo_root / "data" / "runs" / run_date

    shutil.rmtree(run_dir, ignore_errors=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pricelabs.download.pricelabs_downloader",
                "--run-date",
                run_date,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode != 0
        assert "Invalid run date. Expected YYYY-MM-DD." in result.stderr
        assert not run_dir.exists()
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
