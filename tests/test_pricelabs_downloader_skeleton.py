import shutil
import subprocess
import sys
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
from pathlib import Path

import pytest

from pricelabs.download import pricelabs_downloader


BOOKINGS_REPORT_HEADERS = (
    "Listing Name",
    "Check-in Date",
    "Check-out Date",
    "Booked Date",
    "Average Daily Rate",
    "Rental Revenue",
    "Total Revenue",
    "Booking Source",
    "Booking Status",
    "Length of Stay (Days)",
    "Booking Window (Days)",
    "Reservation ID",
    "Listing ID",
)


def write_xlsx(path: Path, rows: list[tuple[str, ...]]) -> None:
    def column_name(index: int) -> str:
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name

    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            reference = f"{column_name(column_index)}{row_index}"
            cells.append(
                f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml)
        workbook.writestr("_rels/.rels", rels_xml)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)


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


def test_monthly_trends_target_is_accepted_in_dry_run() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-05"
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
                "monthly-trends",
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


def test_bookings_report_target_is_accepted_in_dry_run() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-08"
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
                "bookings-report",
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


def test_monthly_trends_validation_passes_for_expected_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "monthly_trends.csv"
    csv_path.write_text(
        "month_year,Revenue,Occupancy,Booked Occupancy,Blocked Occupancy,ADR\n"
        "May 2026,5357,45,43,2,383\n",
        encoding="utf-8",
    )

    pricelabs_downloader.validate_monthly_trends_csv(csv_path)


def test_monthly_trends_validation_fails_for_empty_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "monthly_trends.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="empty"):
        pricelabs_downloader.validate_monthly_trends_csv(csv_path)


def test_monthly_trends_validation_fails_for_html_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "monthly_trends.csv"
    csv_path.write_text("<html><body>login</body></html>", encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="HTML"):
        pricelabs_downloader.validate_monthly_trends_csv(csv_path)


def test_monthly_trends_validation_fails_for_json_error_payload(tmp_path: Path) -> None:
    csv_path = tmp_path / "monthly_trends.csv"
    csv_path.write_text(
        '{"error_code":50004,"message":"An unexpected error occurred."}',
        encoding="utf-8",
    )

    with pytest.raises(pricelabs_downloader.DownloadError, match="PriceLabs API error response"):
        pricelabs_downloader.validate_monthly_trends_csv(csv_path)


def test_monthly_trends_validation_fails_for_style_payload(tmp_path: Path) -> None:
    csv_path = tmp_path / "monthly_trends.csv"
    csv_path.write_text(
        "text-size-adjust: 100%;\n--chakra-colors-black: #000000;\n",
        encoding="utf-8",
    )

    with pytest.raises(pricelabs_downloader.DownloadError, match="page/style content"):
        pricelabs_downloader.validate_monthly_trends_csv(csv_path)


def test_monthly_trends_validation_fails_when_key_columns_are_missing(tmp_path: Path) -> None:
    csv_path = tmp_path / "monthly_trends.csv"
    csv_path.write_text(
        "month_year,Some Value\n"
        "May 2026,5357\n",
        encoding="utf-8",
    )

    with pytest.raises(pricelabs_downloader.DownloadError, match="missing expected columns"):
        pricelabs_downloader.validate_monthly_trends_csv(csv_path)


def test_bookings_report_validation_passes_for_expected_workbook(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "bookings_report.xlsx"
    write_xlsx(
        xlsx_path,
        [
            BOOKINGS_REPORT_HEADERS,
            (
                "Aloha Poconos",
                "2026-05-14",
                "2026-05-16",
                "2026-04-01",
                "425",
                "850",
                "900",
                "Airbnb",
                "Booked",
                "2",
                "43",
                "ABC123",
                "650255___717243",
            ),
        ],
    )

    pricelabs_downloader.validate_bookings_report_xlsx(xlsx_path)


def test_bookings_report_validation_fails_for_empty_file(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "bookings_report.xlsx"
    xlsx_path.write_bytes(b"")

    with pytest.raises(pricelabs_downloader.DownloadError, match="empty"):
        pricelabs_downloader.validate_bookings_report_xlsx(xlsx_path)


def test_bookings_report_validation_fails_for_html_file(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "bookings_report.xlsx"
    xlsx_path.write_text("<html><body>login</body></html>", encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="HTML"):
        pricelabs_downloader.validate_bookings_report_xlsx(xlsx_path)


def test_bookings_report_validation_fails_when_key_columns_are_missing(tmp_path: Path) -> None:
    xlsx_path = tmp_path / "bookings_report.xlsx"
    write_xlsx(
        xlsx_path,
        [
            ("Listing Name", "Some Date", "Some Amount"),
            ("Aloha Poconos", "2026-05-14", "900"),
        ],
    )

    with pytest.raises(pricelabs_downloader.DownloadError, match="missing expected columns"):
        pricelabs_downloader.validate_bookings_report_xlsx(xlsx_path)


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


def test_monthly_trends_ui_flow_uses_confirmed_stable_selectors() -> None:
    assert pricelabs_downloader.PRICELABS_BOOKING_INSIGHTS_URL == (
        "https://app.pricelabs.co/pricing?"
        "listings=650255___717243&pms_name=lodgify&open_bi=true"
    )
    assert pricelabs_downloader.BOOKING_INSIGHTS_TAB_SELECTOR == (
        'button[qa-id="rp-booking-insights"]'
    )
    assert pricelabs_downloader.MONTHLY_TRENDS_DOWNLOAD_BUTTON_SELECTOR == (
        'button[qa-id="mpt-csv-download"]'
    )
    assert pricelabs_downloader.MONTHLY_TRENDS_DOWNLOAD_BUTTON_ID_SELECTOR == (
        "button#mpt-csv-download"
    )
    assert pricelabs_downloader.BOOKING_INSIGHTS_PANEL_MARKER_TEXT == "Monthly Performance Trends"


def test_bookings_report_ui_flow_uses_confirmed_stable_selectors() -> None:
    assert pricelabs_downloader.VIEW_ALL_BOOKINGS_BUTTON_SELECTOR == (
        'button[qa-id="booking-insights-bookings-cta"]'
    )
    assert pricelabs_downloader.VIEW_ALL_BOOKINGS_BUTTON_ID_SELECTOR == (
        "button#booking-insights-bookings-cta"
    )
    assert pricelabs_downloader.VIEW_ALL_BOOKINGS_BUTTON_TEXT == "View All Bookings"
    assert pricelabs_downloader.BOOKINGS_DOWNLOAD_BUTTON_TEXT == "Download"


def test_bookings_report_date_range_instruction_uses_booking_date() -> None:
    message = pricelabs_downloader.bookings_date_range_checkpoint_message("2026-05-14")

    assert "one-month Booking Date range" in message
    assert "Do not use Stay Date as the main filter" in message
    assert "If the Booking Date range looks correct" in message
    assert "Only adjust it manually if the default range is wrong" in message


def test_dom_debug_helper_is_not_enabled() -> None:
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


def test_monthly_trends_real_mode_uses_staging_only_with_mocked_download(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-06"
    run_dir = repo_root / "data" / "runs" / run_date
    staging_file = run_dir / "downloads_staging" / "monthly_trends.csv"
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
        assert run_date == "2099-02-06"
        assert headless is True
        assert skip_login_pause is True
        staging_path.write_text(
            "month_year,Revenue,Occupancy,ADR\n"
            "May 2026,5357,45,383\n",
            encoding="utf-8",
        )
        return "mocked-booking-insights-tab", "mocked-monthly-trends-button"

    monkeypatch.setattr(
        pricelabs_downloader,
        "download_monthly_trends_with_playwright",
        fake_download,
    )

    try:
        result_log = pricelabs_downloader.run(
            run_date,
            target="monthly-trends",
            headless=True,
            skip_login_pause=True,
        )

        assert result_log == log_file
        assert staging_file.exists()
        assert log_file.exists()
        assert not raw_dir.exists()
        assert list((run_dir / "downloads_staging").glob("*.html")) == []
        log_text = log_file.read_text(encoding="utf-8")
        assert "target=monthly-trends" in log_text
        assert "pricing_url=https://app.pricelabs.co/pricing?listings=650255___717243" in log_text
        assert "open_bi=true" in log_text
        assert "validation_status=passed" in log_text
        assert "tab_strategy=mocked-booking-insights-tab" in log_text
        assert "download_button_strategy=mocked-monthly-trends-button" in log_text
        assert "Raw folder was not touched." in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_bookings_report_real_mode_uses_staging_only_with_mocked_download(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-09"
    run_dir = repo_root / "data" / "runs" / run_date
    staging_file = run_dir / "downloads_staging" / "bookings_report.xlsx"
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
        assert run_date == "2099-02-09"
        assert headless is True
        assert skip_login_pause is True
        write_xlsx(
            staging_path,
            [
                BOOKINGS_REPORT_HEADERS,
                (
                    "Aloha Poconos",
                    "2026-05-14",
                    "2026-05-16",
                    "2026-04-01",
                    "425",
                    "850",
                    "900",
                    "Airbnb",
                    "Booked",
                    "2",
                    "43",
                    "ABC123",
                    "650255___717243",
                ),
            ],
        )
        return "mocked-view-all-bookings", "mocked-download-button"

    monkeypatch.setattr(
        pricelabs_downloader,
        "download_bookings_report_with_playwright",
        fake_download,
    )

    try:
        result_log = pricelabs_downloader.run(
            run_date,
            target="bookings-report",
            headless=True,
            skip_login_pause=True,
        )

        assert result_log == log_file
        assert staging_file.exists()
        assert log_file.exists()
        assert not raw_dir.exists()
        assert list((run_dir / "downloads_staging").glob("*.html")) == []
        log_text = log_file.read_text(encoding="utf-8")
        assert "target=bookings-report" in log_text
        assert "pricing_url=https://app.pricelabs.co/pricing?listings=650255___717243" in log_text
        assert "open_bi=true" in log_text
        assert "validation_status=passed" in log_text
        assert "view_all_bookings_strategy=mocked-view-all-bookings" in log_text
        assert "download_button_strategy=mocked-download-button" in log_text
        assert "Raw folder was not touched." in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_monthly_trends_capture_keeps_first_valid_download_candidate(tmp_path: Path) -> None:
    class FakeDownload:
        def __init__(self, suggested_filename: str, content: str) -> None:
            self.suggested_filename = suggested_filename
            self.content = content

        def save_as(self, path: Path) -> None:
            path.write_text(self.content, encoding="utf-8")

    class FakePage:
        def __init__(self) -> None:
            self.download_handler = None

        def on(self, event_name: str, handler) -> None:
            assert event_name == "download"
            self.download_handler = handler

        def wait_for_timeout(self, _milliseconds: int) -> None:
            return

    page = FakePage()
    staging_path = tmp_path / "monthly_trends.csv"

    def click_action() -> None:
        assert page.download_handler is not None
        page.download_handler(
            FakeDownload(
                "monthly_trends.csv",
                '{"error_code":50004,"message":"An unexpected error occurred."}',
            )
        )
        page.download_handler(
            FakeDownload(
                "monthly_trends.csv",
                "month_year,Revenue,Occupancy,ADR\nMay 2026,5357,45,383\n",
            )
        )

    pricelabs_downloader.capture_validated_download(
        page,
        staging_path,
        click_action,
        pricelabs_downloader.validate_monthly_trends_csv,
        file_label="monthly_trends",
    )

    assert staging_path.read_text(encoding="utf-8").startswith("month_year,Revenue")
    assert list(tmp_path.glob("*.candidate-*.csv")) == []


def test_monthly_trends_ui_table_fallback_writes_required_shape(tmp_path: Path) -> None:
    class FakePage:
        def evaluate(self, _script: str):
            return [
                {
                    "month_year": "Feb 2026",
                    "Revenue": "8.65K",
                    "Occupancy": "68%",
                    "ADR": "455.32",
                }
            ]

    staging_path = tmp_path / "monthly_trends.csv"

    pricelabs_downloader.export_monthly_trends_table_from_ui(FakePage(), staging_path)

    rows = staging_path.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "month_year,Revenue,Occupancy,Booked Occupancy,Blocked Occupancy,ADR"
    assert rows[1] == "Feb 2026,8.65K,68%,,,455.32"
    pricelabs_downloader.validate_monthly_trends_csv(staging_path)


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
