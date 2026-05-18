import json
import shutil
import subprocess
import sys
import types
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


def sample_settings_payload(run_date: str = "2099-02-10") -> dict:
    settings = {
        key: {
            "label": label,
            "value": f"{label} configured",
            "value_text": f"{label} configured",
            "value_lines": [f"{label} configured"],
        }
        for key, label in pricelabs_downloader.SETTING_LABELS.items()
    }
    settings["minimum_stay_settings"] = {
        "label": "Minimum Stay Settings",
        "value": (
            "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized "
            "Default : Fixed Weekday: 1 night | Weekend: 2 nights "
            "Last Minute : 1 night Far Out : 3 nights Orphan Gaps : 1 night "
            "Lowest Minstay Allowed : 1 night"
        ),
        "value_text": (
            "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized "
            "Default : Fixed Weekday: 1 night | Weekend: 2 nights "
            "Last Minute : 1 night Far Out : 3 nights Orphan Gaps : 1 night "
            "Lowest Minstay Allowed : 1 night"
        ),
        "value_lines": [
            "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized",
            "Default : Fixed Weekday: 1 night | Weekend: 2 nights",
            "Last Minute : 1 night",
            "Far Out : 3 nights",
            "Orphan Gaps : 1 night",
            "Lowest Minstay Allowed : 1 night",
        ],
    }
    settings["safety_minimum_price"] = {
        "label": "Safety Minimum Price",
        "value": "Set Safety Minimum Price to 110% of last-year-same-day ADR for nights beyond 180 days from today.",
        "value_text": (
            "Set Safety Minimum Price to 110% of last-year-same-day ADR "
            "for nights beyond 180 days from today."
        ),
        "value_lines": [
            "Set Safety Minimum Price to 110% of last-year-same-day ADR for nights beyond 180 days from today."
        ],
    }
    return {
        "run_date": run_date,
        "listing_id": "650255___717243",
        "pms_name": "lodgify",
        "source": "pricelabs_ui_customization_well",
        "source_url": pricelabs_downloader.PRICELABS_BOOKING_INSIGHTS_URL,
        "captured_at_utc": "2099-02-10T00:00:00+00:00",
        "url": pricelabs_downloader.PRICELABS_BOOKING_INSIGHTS_URL,
        "settings": settings,
    }


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


def write_valid_staged_downloads(run_dir: Path, run_date: str) -> None:
    staging_dir = run_dir / "downloads_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "priceLabs_future_export.csv").write_text(
        "Listing ID,Date,Your Price,Min Stay,Available\n"
        "650255___717243,2026-05-14,425,2,True\n",
        encoding="utf-8",
    )
    (staging_dir / "price_occ.csv").write_text(
        "Date,Market Occupancy,Market 25th Percentile Price,Market 50th Percentile Price,Your Booked Occupancy\n"
        "2026-05-14,72,230,275,12\n",
        encoding="utf-8",
    )
    (staging_dir / "monthly_trends.csv").write_text(
        "month_year,Revenue,Occupancy,Booked Occupancy,Blocked Occupancy,ADR\n"
        "May 2026,5357,45,43,2,383\n",
        encoding="utf-8",
    )
    write_xlsx(
        staging_dir / "bookings_report.xlsx",
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
    (staging_dir / "pricelabs_settings_snapshot_from_ui.json").write_text(
        json.dumps(sample_settings_payload(run_date)),
        encoding="utf-8",
    )


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


def test_settings_snapshot_target_is_accepted_in_dry_run() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-10"
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
                "settings-snapshot",
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


def test_settings_snapshot_validation_passes_for_expected_json(tmp_path: Path) -> None:
    json_path = tmp_path / "pricelabs_settings_snapshot_from_ui.json"
    json_path.write_text(json.dumps(sample_settings_payload()), encoding="utf-8")

    pricelabs_downloader.validate_settings_snapshot_json(json_path)


def test_settings_snapshot_validation_fails_for_missing_required_setting(tmp_path: Path) -> None:
    json_path = tmp_path / "pricelabs_settings_snapshot_from_ui.json"
    payload = sample_settings_payload()
    payload["settings"].pop("far_out_premium")
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="missing required settings"):
        pricelabs_downloader.validate_settings_snapshot_json(json_path)


def test_settings_snapshot_validation_fails_for_truncated_min_stay(tmp_path: Path) -> None:
    json_path = tmp_path / "pricelabs_settings_snapshot_from_ui.json"
    payload = sample_settings_payload()
    payload["settings"]["minimum_stay_settings"]["value_text"] = (
        "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized "
        "Default : Fixed Weekday: 1 night | Weekend: 2 nights"
    )
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="minimum_stay_settings appears truncated"):
        pricelabs_downloader.validate_settings_snapshot_json(json_path)


def test_settings_snapshot_validation_fails_for_truncated_safety_minimum(tmp_path: Path) -> None:
    json_path = tmp_path / "pricelabs_settings_snapshot_from_ui.json"
    payload = sample_settings_payload()
    payload["settings"]["safety_minimum_price"]["value_text"] = "Set"
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="safety_minimum_price appears truncated"):
        pricelabs_downloader.validate_settings_snapshot_json(json_path)


def test_settings_snapshot_validation_requires_booking_insights_source_url(tmp_path: Path) -> None:
    json_path = tmp_path / "pricelabs_settings_snapshot_from_ui.json"
    payload = sample_settings_payload()
    payload["source_url"] = pricelabs_downloader.PRICELABS_CUSTOMIZATION_URL
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(pricelabs_downloader.DownloadError, match="source_url"):
        pricelabs_downloader.validate_settings_snapshot_json(json_path)


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


def test_settings_snapshot_ui_flow_uses_customization_well_selector() -> None:
    assert pricelabs_downloader.PRICELABS_CUSTOMIZATION_URL == "https://app.pricelabs.co/customization"
    assert pricelabs_downloader.CUSTOMIZATION_WELL_SELECTOR == 'div[qa-id="customization-well"]'
    assert pricelabs_downloader.SETTING_VALUE_SELECTORS["minimum_stay_settings"] == (
        "#customization-text-min_stay"
    )
    assert pricelabs_downloader.SETTING_VALUE_SELECTORS["safety_minimum_price"] == (
        "#customization-text-safety_minimum"
    )
    assert pricelabs_downloader.SETTING_LABELS["last_minute"] == "Last Minute"
    assert pricelabs_downloader.SETTING_LABELS["far_out_premium"] == "Far Out Premium"


def test_extract_settings_from_customization_well_passes_single_payload() -> None:
    class FakePage:
        def evaluate(self, script: str, payload: dict) -> dict:
            assert "({ selector, labels, valueSelectors, detailStatus })" in script
            assert payload["selector"] == pricelabs_downloader.CUSTOMIZATION_WELL_SELECTOR
            assert payload["labels"]["last_minute"] == "Last Minute"
            assert payload["valueSelectors"]["minimum_stay_settings"] == "#customization-text-min_stay"
            return {
                key: {
                    "label": label,
                    "value": f"{label} configured",
                    "value_text": f"{label} configured",
                    "value_lines": [f"{label} configured"],
                }
                for key, label in payload["labels"].items()
            }

    settings = pricelabs_downloader.extract_settings_from_customization_well(FakePage())

    assert settings["last_minute"]["value_text"] == "Last Minute configured"
    assert settings["minimum_stay_settings"]["value_lines"] == ["Minimum Stay Settings configured"]


def test_extract_settings_from_customization_well_preserves_full_min_stay_and_safety_text() -> None:
    class FakePage:
        def evaluate(self, script: str, payload: dict) -> dict:
            assert "innerText" in script
            assert "value_lines" in script
            settings = {
                key: {
                    "label": label,
                    "value": f"{label} configured",
                    "value_text": f"{label} configured",
                    "value_lines": [f"{label} configured"],
                }
                for key, label in payload["labels"].items()
            }
            settings["minimum_stay_settings"] = {
                "label": "Minimum Stay Settings",
                "value": (
                    "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized "
                    "Default : Fixed Weekday: 1 night | Weekend: 2 nights "
                    "Last Minute : 1 night Far Out : 3 nights Orphan Gaps : 1 night "
                    "Lowest Minstay Allowed : 1 night"
                ),
                "value_text": (
                    "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized "
                    "Default : Fixed Weekday: 1 night | Weekend: 2 nights "
                    "Last Minute : 1 night Far Out : 3 nights Orphan Gaps : 1 night "
                    "Lowest Minstay Allowed : 1 night"
                ),
                "value_lines": [
                    "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized",
                    "Default : Fixed Weekday: 1 night | Weekend: 2 nights",
                    "Last Minute : 1 night",
                    "Far Out : 3 nights",
                    "Orphan Gaps : 1 night",
                    "Lowest Minstay Allowed : 1 night",
                ],
            }
            settings["safety_minimum_price"] = {
                "label": "Safety Minimum Price",
                "value": (
                    "Set Safety Minimum Price to 110% of last-year-same-day ADR "
                    "for nights beyond 180 days from today."
                ),
                "value_text": (
                    "Set Safety Minimum Price to 110% of last-year-same-day ADR "
                    "for nights beyond 180 days from today."
                ),
                "value_lines": [
                    "Set Safety Minimum Price to 110% of last-year-same-day ADR for nights beyond 180 days from today."
                ],
            }
            return settings

    settings = pricelabs_downloader.extract_settings_from_customization_well(FakePage())

    assert "Last Minute" in settings["minimum_stay_settings"]["value_text"]
    assert "Orphan Gaps" in settings["minimum_stay_settings"]["value_text"]
    assert "Lowest Minstay Allowed" in settings["minimum_stay_settings"]["value_text"]
    assert settings["safety_minimum_price"]["value_text"] != "Set"
    assert "110%" in settings["safety_minimum_price"]["value_text"]
    assert "180 days" in settings["safety_minimum_price"]["value_text"]


def test_capture_settings_popover_details_adds_los_and_occupancy_detail_text() -> None:
    class FakePage:
        def evaluate(self, script: str, payload: dict) -> dict:
            assert "aria-haspopup" in script
            assert "pointerover" in script
            assert "mouseover" in script
            assert "aria-controls" in script
            assert "getElementById" in script
            assert ".chakra-popover__content" in script
            assert payload["selector"] == pricelabs_downloader.CUSTOMIZATION_WELL_SELECTOR
            assert payload["keys"] == list(pricelabs_downloader.SETTING_DETAIL_KEYS)
            return {
                "length_of_stay_based_pricing": {
                    "detail_capture_status": "captured",
                    "detail_text": "LOS pricing 7 nights 10% monthly 20%",
                    "detail_lines": ["LOS pricing", "7 nights 10%", "monthly 20%"],
                },
                "occupancy_based_adjustments": {
                    "detail_capture_status": "captured",
                    "detail_text": "Market driven occupancy adjustment details",
                    "detail_lines": ["Market driven occupancy adjustment details"],
                },
            }

    settings = {
        "length_of_stay_based_pricing": {
            "label": "Length-of-stay Based Pricing",
            "value": "Custom",
            "value_text": "Custom",
            "value_lines": ["Custom"],
            "detail_capture_status": "not_captured",
        },
        "occupancy_based_adjustments": {
            "label": "Occupancy Based Adjustments",
            "value": "Market Driven",
            "value_text": "Market Driven",
            "value_lines": ["Market Driven"],
            "detail_capture_status": "not_captured",
        },
    }

    pricelabs_downloader.capture_settings_popover_details(FakePage(), settings)

    assert settings["length_of_stay_based_pricing"]["detail_capture_status"] == "captured"
    assert settings["length_of_stay_based_pricing"]["detail_text"] == "LOS pricing 7 nights 10% monthly 20%"
    assert settings["length_of_stay_based_pricing"]["detail_lines"] == [
        "LOS pricing",
        "7 nights 10%",
        "monthly 20%",
    ]
    assert settings["occupancy_based_adjustments"]["detail_capture_status"] == "captured"
    assert settings["occupancy_based_adjustments"]["detail_text"] == "Market driven occupancy adjustment details"


def test_capture_settings_popover_details_does_not_fail_when_unavailable() -> None:
    class FakePage:
        def evaluate(self, _script: str, _payload: dict) -> dict:
            raise RuntimeError("popover unavailable")

    settings = {
        "length_of_stay_based_pricing": {
            "label": "Length-of-stay Based Pricing",
            "value": "Custom",
            "value_text": "Custom",
            "value_lines": ["Custom"],
        },
        "occupancy_based_adjustments": {
            "label": "Occupancy Based Adjustments",
            "value": "Market Driven",
            "value_text": "Market Driven",
            "value_lines": ["Market Driven"],
        },
    }

    pricelabs_downloader.capture_settings_popover_details(FakePage(), settings)

    assert settings["length_of_stay_based_pricing"]["value_text"] == "Custom"
    assert settings["length_of_stay_based_pricing"]["detail_capture_status"] == "not_captured"
    assert settings["occupancy_based_adjustments"]["detail_capture_status"] == "not_captured"


def test_expand_applied_customizations_well_clicks_outer_header() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.waited = False

        def evaluate(self, script: str) -> int:
            assert 'div[qa-id="applied-cust-well"]' in script
            assert "#re-aplied-customizations" in script
            assert 'svg[data-icon="caret-right"]' in script
            assert "dispatchEvent(new MouseEvent('click'" in script
            return 1

        def wait_for_timeout(self, milliseconds: int) -> None:
            assert milliseconds == 500
            self.waited = True

    page = FakePage()

    assert pricelabs_downloader.expand_applied_customizations_well(page) == 1
    assert page.waited is True


def test_expand_collapsed_customization_sections_uses_collapsed_arrow_path() -> None:
    class FakePage:
        def __init__(self) -> None:
            self.waited = False

        def evaluate(self, script: str, selector: str) -> int:
            assert "M246.6 278.6c12.5-12.5" in script
            assert 'svg[data-icon="caret-right"]' in script
            assert "dispatchEvent(new MouseEvent('click'" in script
            assert 'aria-expanded="false"' in script
            assert selector == pricelabs_downloader.CUSTOMIZATION_WELL_SELECTOR
            return 3

        def wait_for_timeout(self, milliseconds: int) -> None:
            assert milliseconds == 500
            self.waited = True

    page = FakePage()

    assert pricelabs_downloader.expand_collapsed_customization_sections(page) == 3
    assert page.waited is True


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


def test_settings_snapshot_real_mode_uses_staging_only_with_mocked_capture(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-11"
    run_dir = repo_root / "data" / "runs" / run_date
    staging_file = run_dir / "downloads_staging" / "pricelabs_settings_snapshot_from_ui.json"
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)

    def fake_capture(
        staging_path: Path,
        *,
        logs_dir: Path,
        run_date: str,
        headless: bool,
        skip_login_pause: bool = False,
    ) -> int:
        assert staging_path == staging_file
        assert logs_dir == run_dir / "logs"
        assert run_date == "2099-02-11"
        assert headless is True
        assert skip_login_pause is True
        staging_path.write_text(json.dumps(sample_settings_payload(run_date)), encoding="utf-8")
        return len(pricelabs_downloader.SETTING_LABELS)

    monkeypatch.setattr(
        pricelabs_downloader,
        "capture_settings_snapshot_with_playwright",
        fake_capture,
    )

    try:
        result_log = pricelabs_downloader.run(
            run_date,
            target="settings-snapshot",
            headless=True,
            skip_login_pause=True,
        )

        assert result_log == log_file
        assert staging_file.exists()
        assert log_file.exists()
        assert not raw_dir.exists()
        assert list((run_dir / "downloads_staging").glob("*.html")) == []
        log_text = log_file.read_text(encoding="utf-8")
        assert "target=settings-snapshot" in log_text
        assert "validation_status=passed" in log_text
        assert f"settings_count={len(pricelabs_downloader.SETTING_LABELS)}" in log_text
        assert "Raw folder was not touched." in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_promote_to_raw_succeeds_when_all_staged_files_are_valid() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-12"
    run_dir = repo_root / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        write_valid_staged_downloads(run_dir, run_date)

        result_log = pricelabs_downloader.run(run_date, promote_to_raw=True)

        assert result_log == log_file
        assert (raw_dir / "priceLabs_future_export.csv").exists()
        assert (raw_dir / "price_occ.csv").exists()
        assert (raw_dir / "monthly_trends.csv").exists()
        assert (raw_dir / "bookings_report.xlsx").exists()
        assert (raw_dir / "pricelabs_settings_snapshot_from_ui.json").exists()
        assert not (raw_dir / "pricelabs_settings_manual_input.json").exists()
        assert list(raw_dir.glob("*.html")) == []
        assert not (run_dir / "raw_promotion_tmp").exists()
        log_text = log_file.read_text(encoding="utf-8")
        assert "promotion_started=true" in log_text
        assert "promotion_status=passed" in log_text
        assert "raw_touched=true" in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_promote_to_raw_fails_when_staged_file_is_missing() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-13"
    run_dir = repo_root / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        write_valid_staged_downloads(run_dir, run_date)
        (run_dir / "downloads_staging" / "price_occ.csv").unlink()

        with pytest.raises(pricelabs_downloader.DownloadError, match="Missing staged files"):
            pricelabs_downloader.run(run_date, promote_to_raw=True)

        assert not raw_dir.exists()
        log_text = log_file.read_text(encoding="utf-8")
        assert "promotion_status=failed" in log_text
        assert "raw_touched=false" in log_text
        assert "price_occ.csv" in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_promote_to_raw_fails_when_staged_file_is_invalid_without_partial_copy() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-14"
    run_dir = repo_root / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        write_valid_staged_downloads(run_dir, run_date)
        (run_dir / "downloads_staging" / "monthly_trends.csv").write_text(
            "<html><body>login</body></html>",
            encoding="utf-8",
        )

        with pytest.raises(pricelabs_downloader.DownloadError, match="failed validation"):
            pricelabs_downloader.run(run_date, promote_to_raw=True)

        assert not raw_dir.exists()
        assert not (run_dir / "raw_promotion_tmp").exists()
        log_text = log_file.read_text(encoding="utf-8")
        assert "promotion_status=failed" in log_text
        assert "raw_touched=false" in log_text
        assert "monthly_trends.csv" in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_promote_to_raw_fails_if_any_raw_target_exists_without_overwrite() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-15"
    run_dir = repo_root / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)
    try:
        write_valid_staged_downloads(run_dir, run_date)
        raw_dir.mkdir(parents=True)
        existing_raw = raw_dir / "price_occ.csv"
        existing_raw.write_text("trusted raw should remain\n", encoding="utf-8")

        with pytest.raises(pricelabs_downloader.DownloadError, match="refusing to overwrite"):
            pricelabs_downloader.run(run_date, promote_to_raw=True)

        assert existing_raw.read_text(encoding="utf-8") == "trusted raw should remain\n"
        assert not (raw_dir / "priceLabs_future_export.csv").exists()
        assert not (raw_dir / "monthly_trends.csv").exists()
        log_text = log_file.read_text(encoding="utf-8")
        assert "promotion_status=failed" in log_text
        assert "raw_touched=false" in log_text
        assert "Raw target already exists" in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_download_all_sequence_calls_each_target_handler_once(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_future(_page, staging_path: Path) -> str:
        calls.append("future-export")
        staging_path.write_text(
            "Listing ID,Date,Your Price,Min Stay,Available\n"
            "650255___717243,2026-05-14,425,2,True\n",
            encoding="utf-8",
        )
        return "future"

    def fake_price_occ(_page, staging_path: Path) -> tuple[str, str]:
        calls.append("price-occ")
        staging_path.write_text(
            "Date,Market Occupancy,Market 50th Percentile Price,Your Booked Occupancy\n"
            "2026-05-14,72,275,12\n",
            encoding="utf-8",
        )
        return "tab", "button"

    def fake_monthly_trends(_page, staging_path: Path) -> tuple[str, str]:
        calls.append("monthly-trends")
        staging_path.write_text(
            "month_year,Revenue,Occupancy,ADR\n"
            "May 2026,5357,45,383\n",
            encoding="utf-8",
        )
        return "tab", "button"

    def fake_bookings(_context, _page, staging_path: Path) -> tuple[str, str]:
        calls.append("bookings-report")
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
        return "view", "download"

    def fake_settings(_page, staging_path: Path, *, run_date: str) -> int:
        calls.append("settings-snapshot")
        staging_path.write_text(json.dumps(sample_settings_payload(run_date)), encoding="utf-8")
        return len(pricelabs_downloader.SETTING_LABELS)

    def fake_return_to_primary_page(_primary_page, _secondary_page=None) -> None:
        calls.append("return-to-primary-page")

    monkeypatch.setattr(pricelabs_downloader, "download_future_export_in_session", fake_future)
    monkeypatch.setattr(pricelabs_downloader, "download_price_occ_in_session", fake_price_occ)
    monkeypatch.setattr(pricelabs_downloader, "download_monthly_trends_in_session", fake_monthly_trends)
    monkeypatch.setattr(pricelabs_downloader, "download_bookings_report_in_session", fake_bookings)
    monkeypatch.setattr(pricelabs_downloader, "capture_settings_snapshot_in_session", fake_settings)
    monkeypatch.setattr(pricelabs_downloader, "return_to_primary_page", fake_return_to_primary_page)

    completed = pricelabs_downloader.execute_download_all_sequence(
        object(),
        object(),
        tmp_path,
        "2099-02-16",
    )

    assert completed == list(pricelabs_downloader.DOWNLOAD_ALL_TARGETS)
    assert calls == [
        "future-export",
        "price-occ",
        "monthly-trends",
        "settings-snapshot",
        "bookings-report",
        "return-to-primary-page",
    ]
    assert (tmp_path / "priceLabs_future_export.csv").exists()
    assert (tmp_path / "price_occ.csv").exists()
    assert (tmp_path / "monthly_trends.csv").exists()
    assert (tmp_path / "bookings_report.xlsx").exists()
    assert (tmp_path / "pricelabs_settings_snapshot_from_ui.json").exists()


def test_download_all_sequence_stops_after_target_failure(monkeypatch, tmp_path: Path) -> None:
    calls = []

    def fake_future(_page, staging_path: Path) -> str:
        calls.append("future-export")
        staging_path.write_text(
            "Listing ID,Date,Your Price,Min Stay,Available\n"
            "650255___717243,2026-05-14,425,2,True\n",
            encoding="utf-8",
        )
        return "future"

    def fake_price_occ(_page, _staging_path: Path) -> tuple[str, str]:
        calls.append("price-occ")
        raise pricelabs_downloader.DownloadError("price-occ failed")

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("download-all should stop after the first failed target")

    monkeypatch.setattr(pricelabs_downloader, "download_future_export_in_session", fake_future)
    monkeypatch.setattr(pricelabs_downloader, "download_price_occ_in_session", fake_price_occ)
    monkeypatch.setattr(pricelabs_downloader, "download_monthly_trends_in_session", fail_if_called)
    monkeypatch.setattr(pricelabs_downloader, "download_bookings_report_in_session", fail_if_called)
    monkeypatch.setattr(pricelabs_downloader, "capture_settings_snapshot_in_session", fail_if_called)

    with pytest.raises(pricelabs_downloader.DownloadError, match="price-occ failed"):
        pricelabs_downloader.execute_download_all_sequence(object(), object(), tmp_path, "2099-02-17")

    assert calls == ["future-export", "price-occ"]


def test_download_all_mode_is_accepted_without_touching_raw(monkeypatch) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    run_date = "2099-02-18"
    run_dir = repo_root / "data" / "runs" / run_date
    raw_dir = run_dir / "raw"
    log_file = run_dir / "logs" / f"pricelabs_download_{run_date}.log"

    shutil.rmtree(run_dir, ignore_errors=True)

    def fake_download_all(
        run_date: str,
        *,
        headless: bool,
        skip_login_pause: bool = False,
        use_persistent_session: bool = False,
        use_local_credentials: bool = False,
    ) -> Path:
        assert run_date == "2099-02-18"
        assert headless is True
        assert skip_login_pause is True
        assert use_persistent_session is False
        assert use_local_credentials is False
        _run_dir, staging_dir, _logs_dir, log_file = pricelabs_downloader.get_run_paths(run_date)
        write_valid_staged_downloads(_run_dir, run_date)
        pricelabs_downloader.write_log(
            log_file,
            pricelabs_downloader.download_all_log_lines(
                run_date=run_date,
                staging_dir=staging_dir,
                status="passed",
                completed_targets=pricelabs_downloader.DOWNLOAD_ALL_TARGETS,
                raw_touched=False,
            ),
        )
        return log_file

    monkeypatch.setattr(pricelabs_downloader, "run_download_all", fake_download_all)

    try:
        result_log = pricelabs_downloader.run(
            run_date,
            download_all=True,
            headless=True,
            skip_login_pause=True,
        )

        assert result_log == log_file
        assert not raw_dir.exists()
        assert (run_dir / "downloads_staging" / "price_occ.csv").exists()
        log_text = log_file.read_text(encoding="utf-8")
        assert "download_all_started=true" in log_text
        assert "raw_touched=false" in log_text
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_headless_download_all_requires_local_credentials() -> None:
    with pytest.raises(pricelabs_downloader.DownloadError, match="requires --use-local-credentials"):
        pricelabs_downloader.run_download_all(
            "2099-02-19",
            headless=True,
            use_local_credentials=False,
        )


def test_headless_download_all_flag_is_accepted_with_local_credentials() -> None:
    args = pricelabs_downloader.parse_args(
        [
            "--run-date",
            "2099-02-19",
            "--download-all",
            "--headless",
            "--use-local-credentials",
        ]
    )

    assert args.download_all is True
    assert args.headless is True
    assert args.use_local_credentials is True


def test_persistent_session_flag_is_accepted_and_passed_to_download_all(monkeypatch) -> None:
    calls = []

    def fake_download_all(
        run_date: str,
        *,
        headless: bool,
        skip_login_pause: bool = False,
        use_persistent_session: bool = False,
        use_local_credentials: bool = False,
    ) -> Path:
        calls.append(
            {
                "run_date": run_date,
                "headless": headless,
                "skip_login_pause": skip_login_pause,
                "use_persistent_session": use_persistent_session,
                "use_local_credentials": use_local_credentials,
            }
        )
        return Path("data/runs/2099-02-19/logs/pricelabs_download_2099-02-19.log")

    monkeypatch.setattr(pricelabs_downloader, "run_download_all", fake_download_all)

    args = pricelabs_downloader.parse_args(
        [
            "--run-date",
            "2099-02-19",
            "--download-all",
            "--use-persistent-session",
            "--use-local-credentials",
            "--headless",
            "--skip-login-pause",
        ]
    )
    assert args.use_persistent_session is True
    assert args.use_local_credentials is True

    pricelabs_downloader.run(
        args.run_date,
        download_all=args.download_all,
        headless=args.headless,
        skip_login_pause=args.skip_login_pause,
        use_persistent_session=args.use_persistent_session,
        use_local_credentials=args.use_local_credentials,
    )

    assert calls == [
        {
            "run_date": "2099-02-19",
            "headless": True,
            "skip_login_pause": True,
            "use_persistent_session": True,
            "use_local_credentials": True,
        }
    ]


def test_persistent_session_path_is_local_and_not_in_run_data() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    path = pricelabs_downloader.PERSISTENT_SESSION_PROFILE_DIR
    path_text = path.relative_to(repo_root).as_posix()

    assert path_text == ".local/pricelabs_browser_profile"
    assert "data/runs" not in path_text
    assert path.is_absolute()


def test_local_session_path_is_gitignored() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    gitignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert ".local/" in gitignore_text


def test_persistent_mode_uses_launch_persistent_context_not_new_context(monkeypatch, tmp_path: Path) -> None:
    calls = []

    class FakeContext:
        pages = []

        def new_page(self):
            calls.append("persistent-new-page")
            return object()

    class FakeBrowser:
        def new_context(self, **_kwargs):
            raise AssertionError("persistent mode must not create a fresh incognito context")

    class FakeChromium:
        def launch_persistent_context(self, *, user_data_dir: str, headless: bool, accept_downloads: bool):
            calls.append(("launch_persistent_context", Path(user_data_dir), headless, accept_downloads))
            return FakeContext()

        def launch(self, **_kwargs):
            calls.append("launch")
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    profile_dir = tmp_path / ".local" / "pricelabs_browser_profile"
    monkeypatch.setattr(pricelabs_downloader, "PERSISTENT_SESSION_PROFILE_DIR", profile_dir)

    context, browser, page = pricelabs_downloader.launch_download_all_browser(
        FakePlaywright(),
        headless=False,
        use_persistent_session=True,
    )

    assert isinstance(context, FakeContext)
    assert browser is None
    assert page is not None
    assert calls == [("launch_persistent_context", profile_dir, False, True), "persistent-new-page"]
    assert profile_dir.exists()


def test_non_persistent_mode_uses_regular_browser_context() -> None:
    calls = []

    class FakeContext:
        pages = []

        def new_page(self):
            calls.append("new-page")
            return object()

    class FakeBrowser:
        def new_context(self, *, accept_downloads: bool):
            calls.append(("new_context", accept_downloads))
            return FakeContext()

    class FakeChromium:
        def launch_persistent_context(self, **_kwargs):
            raise AssertionError("non-persistent mode must not use the persistent profile")

        def launch(self, *, headless: bool):
            calls.append(("launch", headless))
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    context, browser, page = pricelabs_downloader.launch_download_all_browser(
        FakePlaywright(),
        headless=True,
        use_persistent_session=False,
    )

    assert isinstance(context, FakeContext)
    assert isinstance(browser, FakeBrowser)
    assert page is not None
    assert calls == [("launch", True), ("new_context", True), "new-page"]


def test_auth_check_flag_is_accepted_without_run_date() -> None:
    args = pricelabs_downloader.parse_args(["--auth-check", "--use-persistent-session"])

    assert args.auth_check is True
    assert args.use_persistent_session is True
    assert args.run_date is None


def test_auth_check_requires_persistent_session() -> None:
    try:
        pricelabs_downloader.run(None, auth_check=True, headless=True)
    except pricelabs_downloader.DownloadError as exc:
        assert "--auth-check requires --use-persistent-session" in str(exc)
    else:
        raise AssertionError("auth-check without persistent session should fail clearly")


def test_auth_check_uses_persistent_profile_without_run_artifacts(monkeypatch, tmp_path: Path, capsys) -> None:
    calls = []
    profile_dir = tmp_path / ".local" / "pricelabs_browser_profile"
    run_data_dir = tmp_path / "data" / "runs"

    class FakePage:
        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            calls.append(("goto", url, wait_until, timeout))

        def wait_for_load_state(self, state: str, timeout: int) -> None:
            calls.append(("wait_for_load_state", state, timeout))

    class FakeContext:
        pages = []

        def new_page(self):
            calls.append("new-page")
            return FakePage()

        def close(self):
            calls.append("context-close")

    class FakeChromium:
        def launch_persistent_context(self, *, user_data_dir: str, headless: bool, accept_downloads: bool):
            calls.append(("launch_persistent_context", Path(user_data_dir), headless, accept_downloads))
            return FakeContext()

        def launch(self, **_kwargs):
            raise AssertionError("auth-check must not use non-persistent browser launch")

    class FakeSyncPlaywright:
        def __enter__(self):
            return type("FakePlaywright", (), {"chromium": FakeChromium()})()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(pricelabs_downloader, "PERSISTENT_SESSION_PROFILE_DIR", profile_dir)
    fake_module = types.ModuleType("playwright.sync_api")
    fake_module.sync_playwright = lambda: FakeSyncPlaywright()
    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        fake_module,
    )
    monkeypatch.setattr(pricelabs_downloader, "classify_auth_status", lambda _page: "logged_in")

    result = pricelabs_downloader.run_auth_check(headless=True, use_persistent_session=True)

    output = capsys.readouterr().out
    assert result == profile_dir
    assert ("launch_persistent_context", profile_dir, True, True) in calls
    assert "persistent_profile_path=" in output
    assert "persistent_profile_exists=false" in output
    assert "auth_status=logged_in" in output
    assert "cookie" not in output.lower()
    assert "token" not in output.lower()
    assert "localstorage" not in output.lower()
    assert not run_data_dir.exists()


def test_auth_status_classification() -> None:
    class FakePage:
        def __init__(self, body_text: str) -> None:
            self.body_text = body_text

        def locator(self, selector: str):
            assert selector == "body"
            page = self

            class FakeLocator:
                def inner_text(self, timeout: int) -> str:
                    return page.body_text

            return FakeLocator()

    assert pricelabs_downloader.classify_auth_status(FakePage("Aloha Poconos Booking Insights")) == "logged_in"
    assert pricelabs_downloader.classify_auth_status(FakePage("Log in Email Password")) == "login_required"
    assert pricelabs_downloader.classify_auth_status(FakePage("Loading")) == "unknown"


def test_auth_check_log_lines_are_safe() -> None:
    lines = pricelabs_downloader.auth_check_log_lines(
        profile_path=Path("C:/repo/.local/pricelabs_browser_profile"),
        profile_exists=True,
        auth_status="login_required",
    )
    text = "\n".join(lines).lower()

    assert "persistent_profile_path=" in text
    assert "persistent_profile_exists=true" in text
    assert "auth_status=login_required" in text
    assert "cookie" not in text
    assert "token" not in text
    assert "sessionstorage" not in text
    assert "localstorage" not in text


def test_local_credentials_parser_reads_gitignored_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / "pricelabs.env"
    env_file.write_text(
        "# local only\nPRICELABS_EMAIL=owner@example.com\nPRICELABS_PASSWORD='super-secret'\n",
        encoding="utf-8",
    )

    credentials = pricelabs_downloader.read_local_credentials(env_file)

    assert credentials == {"email": "owner@example.com", "password": "super-secret"}


def test_local_credentials_parser_returns_none_when_missing_or_incomplete(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.env"
    incomplete_file = tmp_path / "pricelabs.env"
    incomplete_file.write_text("PRICELABS_EMAIL=owner@example.com\n", encoding="utf-8")

    assert pricelabs_downloader.read_local_credentials(missing_file) is None
    assert pricelabs_downloader.read_local_credentials(incomplete_file) is None


def test_credential_login_log_lines_do_not_include_secrets() -> None:
    lines = pricelabs_downloader.credential_login_log_lines(
        requested=True,
        file_found=True,
        attempted=True,
        mfa_manual_checkpoint=True,
    )
    text = "\n".join(lines)

    assert "local_credentials_requested=true" in text
    assert "local_credentials_file_found=true" in text
    assert "credential_login_attempted=true" in text
    assert "mfa_manual_checkpoint=true" in text
    assert "owner@example.com" not in text
    assert "super-secret" not in text
    assert "PRICELABS_PASSWORD" not in text


def test_missing_local_credentials_falls_back_to_manual_login(monkeypatch, capsys) -> None:
    calls = []

    class FakePage:
        def wait_for_function(self, _script: str, timeout: int) -> None:
            calls.append(("wait_for_function", timeout))
            raise pricelabs_downloader.DownloadError("not logged in")

    monkeypatch.setattr(pricelabs_downloader, "read_local_credentials", lambda: None)

    try:
        pricelabs_downloader.wait_for_download_all_login_ready(
            FakePage(),
            skip_login_pause=False,
            use_local_credentials=True,
        )
    except pricelabs_downloader.DownloadError:
        pass

    output = capsys.readouterr().out
    assert "local_credentials_requested=true" in output
    assert "local_credentials_file_found=false" in output
    assert "credential_login_attempted=false" in output
    assert "Please log in to PriceLabs manually" in output


def test_headless_missing_local_credentials_fails_without_manual_pause(monkeypatch, capsys) -> None:
    input_called = False

    def fake_input() -> str:
        nonlocal input_called
        input_called = True
        return ""

    class FakePage:
        def wait_for_function(self, _script: str, timeout: int) -> None:
            raise RuntimeError("not logged in")

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(pricelabs_downloader, "read_local_credentials", lambda: None)

    with pytest.raises(pricelabs_downloader.DownloadError, match="local credentials were not found"):
        pricelabs_downloader.wait_for_download_all_login_ready(
            FakePage(),
            skip_login_pause=False,
            use_local_credentials=True,
            headless=True,
        )

    output = capsys.readouterr().out
    assert input_called is False
    assert "Please log in to PriceLabs manually" not in output
    assert "local_credentials_file_found=false" in output


def test_headless_mfa_requirement_fails_clearly(monkeypatch) -> None:
    class FakePage:
        def wait_for_function(self, _script: str, timeout: int) -> None:
            raise RuntimeError("not logged in")

    monkeypatch.setattr(
        pricelabs_downloader,
        "read_local_credentials",
        lambda: {"email": "owner@example.com", "password": "super-secret"},
    )
    monkeypatch.setattr(pricelabs_downloader, "attempt_local_credential_login", lambda _page, _credentials: True)

    with pytest.raises(pricelabs_downloader.DownloadError, match="interactive verification appears required"):
        pricelabs_downloader.wait_for_download_all_login_ready(
            FakePage(),
            skip_login_pause=False,
            use_local_credentials=True,
            headless=True,
        )


def test_local_credential_login_includes_pricelabs_sign_in_submit_selector(monkeypatch) -> None:
    requested_selectors = []

    class FakeLocator:
        def fill(self, _value: str) -> None:
            return

        def click(self) -> None:
            return

    def fake_first_visible_locator(_page, selectors, *, timeout_ms=5_000):
        requested_selectors.append(tuple(selectors))
        return FakeLocator()

    monkeypatch.setattr(pricelabs_downloader, "first_visible_locator", fake_first_visible_locator)

    assert pricelabs_downloader.attempt_local_credential_login(
        object(),
        {"email": "owner@example.com", "password": "super-secret"},
    ) is True

    submit_selectors = requested_selectors[2]
    assert submit_selectors[0] == 'input[type="submit"][name="commit"][value="Sign in"]'
    assert 'input[type="submit"][value="Sign in"]' in submit_selectors
    assert 'input[name="commit"]' in submit_selectors
    assert 'text="Sign in"' in submit_selectors


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


def test_download_all_login_waits_for_browser_ready_without_enter(monkeypatch, capsys) -> None:
    input_called = False

    def fake_input() -> str:
        nonlocal input_called
        input_called = True
        return ""

    class FakePage:
        def __init__(self) -> None:
            self.waited = False

        def wait_for_function(self, script: str, timeout: int) -> None:
            assert "aloha poconos" in script
            assert "booking insights" in script
            assert timeout == pricelabs_downloader.DOWNLOAD_ALL_LOGIN_TIMEOUT_MS
            assert timeout == 120_000
            self.waited = True

    monkeypatch.setattr("builtins.input", fake_input)
    page = FakePage()

    pricelabs_downloader.wait_for_download_all_login_ready(page, skip_login_pause=False)

    captured = capsys.readouterr()
    assert input_called is False
    assert page.waited is True
    assert "continue automatically" in captured.out
    assert "press Enter" not in captured.out
