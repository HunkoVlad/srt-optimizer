import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pricelabs.download import pricelabs_downloader


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


def test_future_export_validation_passes_for_expected_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "priceLabs_future_export.csv"
    csv_path.write_text(
        "Listing ID,Date,Recommended Price,Min Stay,Status\n"
        "650255___717243,2026-05-14,425,2,Available\n",
        encoding="utf-8",
    )

    pricelabs_downloader.validate_future_export_csv(csv_path)


def test_future_export_validation_fails_for_empty_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "priceLabs_future_export.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="empty"):
        pricelabs_downloader.validate_future_export_csv(csv_path)


def test_future_export_validation_fails_for_html_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "priceLabs_future_export.csv"
    csv_path.write_text("<html><body>login</body></html>", encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="HTML"):
        pricelabs_downloader.validate_future_export_csv(csv_path)


def test_future_export_validation_fails_when_key_columns_are_missing(tmp_path: Path) -> None:
    csv_path = tmp_path / "priceLabs_future_export.csv"
    csv_path.write_text(
        "Listing ID,Date,Some Other Price\n"
        "650255___717243,2026-05-14,425\n",
        encoding="utf-8",
    )

    with pytest.raises(pricelabs_downloader.DownloadError, match="missing expected columns"):
        pricelabs_downloader.validate_future_export_csv(csv_path)


def test_price_occ_target_is_accepted_in_dry_run() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-03"
    run_dir = repo_root / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"

    shutil.rmtree(run_dir, ignore_errors=True)

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pricelabs.download.pricelabs_downloader",
                "--run-date",
                run_date,
                "--target",
                "price-occ",
                "--dry-run",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert (run_dir / "downloads_staging").is_dir()
        assert not raw_dir.exists()
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_price_occ_validation_passes_for_expected_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "price_occ.csv"
    csv_path.write_text(
        "Date,Market Occupancy,Market 25th Percentile Price,"
        "Market 50th Percentile Price,Your Booked Occupancy\n"
        "2026-05-14,72,230,275,12\n",
        encoding="utf-8",
    )

    pricelabs_downloader.validate_price_occ_csv(csv_path)


def test_price_occ_validation_fails_for_empty_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "price_occ.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="empty"):
        pricelabs_downloader.validate_price_occ_csv(csv_path)


def test_price_occ_validation_fails_for_html_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "price_occ.csv"
    csv_path.write_text("<html><body>login</body></html>", encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="HTML"):
        pricelabs_downloader.validate_price_occ_csv(csv_path)


def test_price_occ_validation_fails_when_key_columns_are_missing(tmp_path: Path) -> None:
    csv_path = tmp_path / "price_occ.csv"
    csv_path.write_text(
        "Date,Some Market Column\n"
        "2026-05-14,72\n",
        encoding="utf-8",
    )

    with pytest.raises(pricelabs_downloader.DownloadError, match="missing expected columns"):
        pricelabs_downloader.validate_price_occ_csv(csv_path)


def test_price_occ_ui_flow_uses_confirmed_stable_selectors() -> None:
    assert pricelabs_downloader.PRICELABS_PRICING_URL == (
        "https://app.pricelabs.co/pricing?"
        "listings=650255___717243&pms_name=lodgify&open_calendar=true"
    )
    assert pricelabs_downloader.NEIGHBOURHOOD_DATA_TAB_SELECTOR == (
        'button[qa-id="neighbourhood-data-tab"]'
    )
    assert pricelabs_downloader.PRICE_OCC_DOWNLOAD_BUTTON_SELECTOR == (
        'button[qa-id="fp-csv-download"]'
    )
    assert not hasattr(pricelabs_downloader, "save_debug_dom")


def test_future_export_real_mode_uses_staging_only_with_mocked_download(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-02"
    run_dir = repo_root / "data" / "runs" / run_date
    staging_file = run_dir / "downloads_staging" / "priceLabs_future_export.csv"
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)

    def fake_download(
        staging_path: Path,
        *,
        logs_dir: Path,
        run_date: str,
        headless: bool,
        skip_login_pause: bool = False,
    ) -> str:
        assert staging_path == staging_file
        assert logs_dir == run_dir / "logs"
        assert run_date == "2099-02-02"
        assert headless is True
        assert skip_login_pause is True
        staging_path.write_text(
            "Listing ID,Date,Your Price,Min Stay,Available\n"
            "650255___717243,2026-05-14,425,2,True\n",
            encoding="utf-8",
        )
        return "mocked-menu-strategy"

    monkeypatch.setattr(
        pricelabs_downloader,
        "download_future_export_with_playwright",
        fake_download,
    )

    try:
        result_log = pricelabs_downloader.run(
            run_date,
            target="future-export",
            headless=True,
            skip_login_pause=True,
        )

        assert result_log == log_file
        assert staging_file.exists()
        assert log_file.exists()
        assert not raw_dir.exists()
        assert list((run_dir / "downloads_staging").glob("*.html")) == []
        log_text = log_file.read_text(encoding="utf-8")
        assert "target=future-export" in log_text
        assert "validation_status=passed" in log_text
        assert "menu_strategy=mocked-menu-strategy" in log_text
        assert "Raw folder was not touched." in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_price_occ_real_mode_uses_staging_only_with_mocked_download(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-04"
    run_dir = repo_root / "data" / "runs" / run_date
    staging_file = run_dir / "downloads_staging" / "price_occ.csv"
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)

    def fake_download(
        staging_path: Path,
        *,
        logs_dir: Path,
        run_date: str,
        headless: bool,
        skip_login_pause: bool = False,
    ) -> str:
        assert staging_path == staging_file
        assert logs_dir == run_dir / "logs"
        assert run_date == "2099-02-04"
        assert headless is True
        assert skip_login_pause is True
        staging_path.write_text(
            "Date,Market Occupancy,Market 50th Percentile Price,Your Booked Occupancy\n"
            "2026-05-14,72,275,12\n",
            encoding="utf-8",
        )
        return "mocked-tab-strategy", "mocked-button-strategy"

    monkeypatch.setattr(
        pricelabs_downloader,
        "download_price_occ_with_playwright",
        fake_download,
    )

    try:
        result_log = pricelabs_downloader.run(
            run_date,
            target="price-occ",
            headless=True,
            skip_login_pause=True,
        )

        assert result_log == log_file
        assert staging_file.exists()
        assert log_file.exists()
        assert not raw_dir.exists()
        assert list((run_dir / "downloads_staging").glob("*.html")) == []
        log_text = log_file.read_text(encoding="utf-8")
        assert "target=price-occ" in log_text
        assert "pricing_url=https://app.pricelabs.co/pricing?listings=650255___717243" in log_text
        assert "validation_status=passed" in log_text
        assert "tab_strategy=mocked-tab-strategy" in log_text
        assert "download_button_strategy=mocked-button-strategy" in log_text
        assert "Raw folder was not touched." in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_manual_login_checkpoint_prints_instruction_and_waits_for_enter(monkeypatch, capsys) -> None:
    entered = False

    def fake_input() -> str:
        nonlocal entered
        entered = True
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    pricelabs_downloader.wait_for_manual_login_checkpoint(skip_login_pause=False)

    captured = capsys.readouterr()
    assert entered is True
    assert "Please log in to PriceLabs manually" in captured.out
    assert "Complete MFA if required" in captured.out
    assert "press Enter" in captured.out
