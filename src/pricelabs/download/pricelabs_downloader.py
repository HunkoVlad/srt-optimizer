"""PriceLabs downloader entry point.

Default behavior is still skeleton/dry-run mode: create staging/log folders only.
Real download mode is deliberately explicit and downloads only into staging.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from pricelabs.transform.historical_monthly_actuals import read_xlsx_rows


PLACEHOLDER_STEPS = [
    "authentication",
    "future export download",
    "price/occupancy download",
    "monthly trends download",
    "bookings report download",
    "staging validation",
    "promotion to raw",
]

FUTURE_EXPORT_FILENAME = "priceLabs_future_export.csv"
PRICE_OCC_FILENAME = "price_occ.csv"
MONTHLY_TRENDS_FILENAME = "monthly_trends.csv"
BOOKINGS_REPORT_FILENAME = "bookings_report.xlsx"
FUTURE_EXPORT_TARGET = "future-export"
PRICE_OCC_TARGET = "price-occ"
MONTHLY_TRENDS_TARGET = "monthly-trends"
BOOKINGS_REPORT_TARGET = "bookings-report"
SUPPORTED_TARGETS = [FUTURE_EXPORT_TARGET, PRICE_OCC_TARGET, MONTHLY_TRENDS_TARGET, BOOKINGS_REPORT_TARGET]
PRICELABS_CUSTOMIZATION_URL = "https://app.pricelabs.co/customization"
PRICELABS_PRICING_URL = (
    "https://app.pricelabs.co/pricing?"
    "listings=650255___717243&pms_name=lodgify&open_calendar=true"
)
PRICELABS_BOOKING_INSIGHTS_URL = (
    "https://app.pricelabs.co/pricing?"
    "listings=650255___717243&pms_name=lodgify&open_bi=true"
)
PRICELABS_ACCOUNT_LABEL = "Lodgify"
FUTURE_EXPORT_MENU_ITEM = "Download CSV Prices"
CUSTOMIZATION_LOGIN_CHECKPOINT_MESSAGE = (
    "Please log in to PriceLabs manually in the opened browser. Complete MFA if required. "
    "When you see the Customizations page, return to this terminal and press Enter."
)
PRICING_LOGIN_CHECKPOINT_MESSAGE = (
    "Please log in to PriceLabs manually in the opened browser. Complete MFA if required. "
    "When you see the pricing page, return to this terminal and press Enter."
)
BOOKING_INSIGHTS_LOGIN_CHECKPOINT_MESSAGE = (
    "Please log in to PriceLabs manually in the opened browser. Complete MFA if required. "
    "When you see the Booking Insights page, return to this terminal and press Enter."
)
NEIGHBOURHOOD_DATA_TAB_SELECTOR = 'button[qa-id="neighbourhood-data-tab"]'
NEIGHBOURHOOD_DATA_TAB_FALLBACK_TEXT = "Neighborhood Data"
PRICE_OCC_DOWNLOAD_BUTTON_SELECTOR = 'button[qa-id="fp-csv-download"]'
PRICE_OCC_DOWNLOAD_BUTTON_ARIA_SELECTOR = 'button[aria-label="CSV Download"]'
BOOKING_INSIGHTS_TAB_SELECTOR = 'button[qa-id="rp-booking-insights"]'
BOOKING_INSIGHTS_TAB_FALLBACK_TEXT = "Booking Insights"
BOOKING_INSIGHTS_PANEL_MARKER_TEXT = "Monthly Performance Trends"
VIEW_ALL_BOOKINGS_BUTTON_SELECTOR = 'button[qa-id="booking-insights-bookings-cta"]'
VIEW_ALL_BOOKINGS_BUTTON_ID_SELECTOR = "button#booking-insights-bookings-cta"
VIEW_ALL_BOOKINGS_BUTTON_TEXT = "View All Bookings"
BOOKINGS_DOWNLOAD_BUTTON_TEXT = "Download"
MONTHLY_TRENDS_DOWNLOAD_BUTTON_SELECTOR = 'button[qa-id="mpt-csv-download"]'
MONTHLY_TRENDS_DOWNLOAD_BUTTON_ID_SELECTOR = 'button#mpt-csv-download'
MONTHLY_TRENDS_DOWNLOAD_BUTTON_TITLE_SELECTOR = 'button[title="CSV"]'


class DownloadError(RuntimeError):
    """Raised when a staged download cannot be completed or validated."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create PriceLabs download staging/logs or download one explicit target."
    )
    parser.add_argument(
        "--run-date",
        required=True,
        help="Run date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Force skeleton mode even when a target is provided.",
    )
    parser.add_argument(
        "--target",
        choices=SUPPORTED_TARGETS,
        help="Explicit real download target. Currently supports future-export and price-occ.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless in real download mode. Default is headed for manual login/MFA.",
    )
    parser.add_argument(
        "--skip-login-pause",
        action="store_true",
        help="Developer-only option to skip the manual login checkpoint.",
    )
    args = parser.parse_args(argv)
    validate_run_date(args.run_date, parser)
    return args


def validate_run_date(run_date: str, parser: argparse.ArgumentParser) -> None:
    try:
        parsed = datetime.strptime(run_date, "%Y-%m-%d")
    except ValueError:
        parser.error("Invalid run date. Expected YYYY-MM-DD.")

    if parsed.strftime("%Y-%m-%d") != run_date:
        parser.error("Invalid run date. Expected YYYY-MM-DD.")


def write_log(log_file: Path, lines: Sequence[str]) -> None:
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def skeleton_log_lines(run_date: str, staging_dir: Path) -> list[str]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"PriceLabs downloader skeleton started at {timestamp}",
        f"run_date={run_date}",
        "mode=dry-run skeleton",
        f"downloads_staging={staging_dir}",
        "No browser opened.",
        "No PriceLabs authentication attempted.",
        "No files downloaded.",
        "No raw files created or modified.",
        "Future placeholder steps:",
    ]
    lines.extend(f"- {step}: not implemented" for step in PLACEHOLDER_STEPS)
    lines.append("Skeleton completed successfully.")
    return lines


def get_run_paths(run_date: str) -> tuple[Path, Path, Path, Path]:
    project_root = Path.cwd()
    run_dir = project_root / "data" / "runs" / run_date
    staging_dir = run_dir / "downloads_staging"
    logs_dir = run_dir / "logs"
    staging_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"pricelabs_download_{run_date}.log"
    return run_dir, staging_dir, logs_dir, log_file


def run_skeleton(run_date: str) -> Path:
    _, staging_dir, _, log_file = get_run_paths(run_date)
    write_log(log_file, skeleton_log_lines(run_date=run_date, staging_dir=staging_dir))
    return log_file


def looks_like_html(text: str) -> bool:
    sample = text.lstrip().lower()
    return sample.startswith("<!doctype html") or sample.startswith("<html")


def looks_like_css_or_style_payload(text: str) -> bool:
    sample = text.lstrip().lower()
    return sample.startswith("--chakra-") or "--chakra-colors" in sample or "text-size-adjust:" in sample


def maybe_json_error_message(text: str) -> str | None:
    sample = text.lstrip()
    if not sample.startswith("{"):
        return None
    try:
        payload = json.loads(sample)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if "error_code" not in payload and "message" not in payload:
        return None
    error_code = payload.get("error_code", "")
    message = payload.get("message", "")
    return f"PriceLabs API error response: error_code={error_code}, message={message}"


def reject_non_csv_payload(sample: str, file_label: str) -> None:
    if looks_like_html(sample):
        raise DownloadError(f"Downloaded {file_label} file looks like an HTML login/error page.")
    json_error = maybe_json_error_message(sample)
    if json_error:
        raise DownloadError(f"Downloaded {file_label} file is not CSV. {json_error}")
    if looks_like_css_or_style_payload(sample):
        raise DownloadError(f"Downloaded {file_label} file looks like page/style content, not CSV.")


def read_csv_header(csv_path: Path) -> list[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        reject_non_csv_payload(sample, "future export")
        handle.seek(0)
        reader = csv.reader(handle)
        for row in reader:
            normalized = [cell.strip() for cell in row]
            lower_cells = {cell.lower() for cell in normalized}
            if "listing id" in lower_cells and "date" in lower_cells:
                return normalized
    raise DownloadError("Could not find a recognizable future export CSV header.")


def read_csv_header_with_columns(csv_path: Path, required_any: set[str], file_label: str) -> list[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        reject_non_csv_payload(sample, file_label)
        handle.seek(0)
        reader = csv.reader(handle)
        for row in reader:
            normalized = [cell.strip() for cell in row]
            lower_cells = {cell.lower() for cell in normalized}
            if lower_cells.intersection(required_any):
                return normalized
    raise DownloadError(f"Could not find a recognizable {file_label} CSV header.")


def validate_future_export_csv(csv_path: Path) -> None:
    if not csv_path.exists():
        raise DownloadError(f"Missing staged file: {csv_path}")
    if csv_path.stat().st_size <= 0:
        raise DownloadError("Downloaded future export is empty.")

    header = read_csv_header(csv_path)
    normalized = {column.strip().lower() for column in header}

    pricing_columns = {
        "recommended price",
        "price with default customization",
        "your price",
    }
    status_columns = {"status", "available", "unbookable"}

    missing_groups = []
    if "listing id" not in normalized:
        missing_groups.append("Listing ID")
    if "date" not in normalized:
        missing_groups.append("Date")
    if "min stay" not in normalized:
        missing_groups.append("Min Stay")
    if not normalized.intersection(pricing_columns):
        missing_groups.append("pricing field")
    if not normalized.intersection(status_columns):
        missing_groups.append("status or availability field")

    if missing_groups:
        missing = ", ".join(missing_groups)
        raise DownloadError(f"Future export missing expected columns: {missing}")


def validate_price_occ_csv(csv_path: Path) -> None:
    if not csv_path.exists():
        raise DownloadError(f"Missing staged file: {csv_path}")
    if csv_path.stat().st_size <= 0:
        raise DownloadError("Downloaded price_occ export is empty.")

    header = read_csv_header_with_columns(csv_path, {"date", "market occupancy"}, "price_occ")
    normalized = {column.strip().lower() for column in header}

    market_percentile_columns = {
        "market 25th percentile price",
        "market 50th percentile price",
        "market 75th percentile price",
        "market 90th percentile price",
    }
    booked_occupancy_columns = {
        "your booked occupancy",
        "booked_occupancy",
        "booked occupancy",
    }

    missing_groups = []
    if "date" not in normalized:
        missing_groups.append("Date")
    if "market occupancy" not in normalized:
        missing_groups.append("Market Occupancy")
    if not normalized.intersection(market_percentile_columns):
        missing_groups.append("market percentile price field")
    if not normalized.intersection(booked_occupancy_columns):
        missing_groups.append("booked occupancy context field")

    if missing_groups:
        missing = ", ".join(missing_groups)
        raise DownloadError(f"Price Occ export missing expected columns: {missing}")


def validate_monthly_trends_csv(csv_path: Path) -> None:
    if not csv_path.exists():
        raise DownloadError(f"Missing staged file: {csv_path}")
    if csv_path.stat().st_size <= 0:
        raise DownloadError("Downloaded monthly_trends export is empty.")

    header = read_csv_header_with_columns(csv_path, {"month_year", "month", "revenue"}, "monthly_trends")
    normalized = {column.strip().lower() for column in header}

    month_columns = {"month_year", "month", "month year", "year & month", "date"}
    revenue_columns = {"revenue", "total revenue", "rental revenue"}
    adr_columns = {"adr", "rental adr"}
    occupancy_columns = {"occupancy", "occupancy %", "booked occupancy", "paid occupancy %"}

    missing_groups = []
    if not normalized.intersection(month_columns):
        missing_groups.append("month/date period field")
    if not normalized.intersection(revenue_columns):
        missing_groups.append("revenue field")
    if not normalized.intersection(adr_columns):
        missing_groups.append("ADR field")
    if not normalized.intersection(occupancy_columns):
        missing_groups.append("occupancy field")

    if missing_groups:
        missing = ", ".join(missing_groups)
        raise DownloadError(f"Monthly Trends export missing expected columns: {missing}")


def validate_bookings_report_xlsx(xlsx_path: Path) -> None:
    if not xlsx_path.exists():
        raise DownloadError(f"Missing staged file: {xlsx_path}")
    if xlsx_path.stat().st_size <= 0:
        raise DownloadError("Downloaded bookings_report export is empty.")

    with xlsx_path.open("rb") as handle:
        sample = handle.read(2048)
    text_sample = sample.decode("utf-8-sig", errors="ignore")
    if looks_like_html(text_sample):
        raise DownloadError("Downloaded bookings_report file looks like an HTML login/error page.")
    json_error = maybe_json_error_message(text_sample)
    if json_error:
        raise DownloadError(f"Downloaded bookings_report file is not XLSX. {json_error}")

    try:
        workbook_rows = read_xlsx_rows(xlsx_path)
    except Exception as exc:
        raise DownloadError("Downloaded bookings_report file is not a readable XLSX workbook.") from exc

    header = find_xlsx_header(workbook_rows)

    normalized = {column.strip().lower() for column in header}
    check_in_columns = {"check-in date", "check in date", "arrival date", "start date"}
    check_out_columns = {"check-out date", "check out date", "departure date", "end date"}
    source_columns = {"booking source", "source", "channel"}
    revenue_columns = {"rental revenue", "total revenue", "booking value", "amount", "revenue"}
    status_or_id_columns = {"booking status", "status", "reservation id", "booking id"}

    missing_groups = []
    if not normalized.intersection(check_in_columns):
        missing_groups.append("check-in/start date field")
    if not normalized.intersection(check_out_columns):
        missing_groups.append("check-out/end date field")
    if not normalized.intersection(source_columns):
        missing_groups.append("booking source/channel field")
    if not normalized.intersection(revenue_columns):
        missing_groups.append("revenue/amount field")
    if not normalized.intersection(status_or_id_columns):
        missing_groups.append("status or booking identifier field")

    if missing_groups:
        missing = ", ".join(missing_groups)
        raise DownloadError(f"Bookings Report export missing expected columns: {missing}")


def find_xlsx_header(rows: list[list[str]]) -> list[str]:
    if not rows:
        raise DownloadError("Bookings Report workbook has no worksheets.")
    for row in rows[:20]:
        values = [str(value or "").strip() for value in row]
        non_empty = [value for value in values if value]
        if len(non_empty) >= 3:
            return values
    raise DownloadError("Bookings Report workbook is missing a header row.")


def wait_for_manual_login_checkpoint(
    *,
    skip_login_pause: bool,
    message: str = CUSTOMIZATION_LOGIN_CHECKPOINT_MESSAGE,
) -> None:
    if skip_login_pause:
        return
    print(message)
    input()


def bookings_date_range_checkpoint_message(run_date: str) -> str:
    parsed_run_date = datetime.strptime(run_date, "%Y-%m-%d").date()
    suggested_from = (parsed_run_date - timedelta(days=30)).isoformat()
    suggested_to = parsed_run_date.isoformat()
    return (
        "Set Booking Date range to the previous 30 days through the run date. "
        "Do not use Stay Date as the main filter. Leave Stay Date broad/default if available. "
        f"Suggested Booking Date range: {suggested_from} to {suggested_to}. "
        "When ready to download, return to this terminal and press Enter."
    )


def download_future_export_with_playwright(
    staging_path: Path,
    *,
    logs_dir: Path,
    run_date: str,
    headless: bool,
    skip_login_pause: bool = False,
) -> str:
    if headless and not skip_login_pause:
        raise DownloadError("Headless mode requires --skip-login-pause for future-export downloads.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    staging_path.parent.mkdir(parents=True, exist_ok=True)
    temp_download_path = staging_path.with_suffix(".download")
    if temp_download_path.exists():
        temp_download_path.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(PRICELABS_CUSTOMIZATION_URL, wait_until="domcontentloaded", timeout=120_000)
            wait_for_manual_login_checkpoint(skip_login_pause=skip_login_pause)
            page.wait_for_load_state("networkidle", timeout=120_000)
            validate_visible_customization_page(page)
            if not headless:
                print("Playwright paused before Lodgify menu lookup. Inspect the page, then resume.")
                page.pause()
            try:
                menu_strategy = trigger_future_export_download(page)
            except DownloadError as exc:
                screenshot_path = save_debug_screenshot(page, logs_dir, run_date)
                raise DownloadError(f"{exc} Debug screenshot saved to {screenshot_path}") from exc
            with page.expect_download(timeout=120_000) as download_info:
                click_download_csv_prices(page)
            download = download_info.value
            download.save_as(temp_download_path)
        finally:
            context.close()
            browser.close()

    replace_file(temp_download_path, staging_path)
    return menu_strategy


def download_price_occ_with_playwright(
    staging_path: Path,
    *,
    logs_dir: Path,
    run_date: str,
    headless: bool,
    skip_login_pause: bool = False,
) -> tuple[str, str]:
    """Download PriceLabs neighborhood price/occupancy CSV into staging."""

    if headless and not skip_login_pause:
        raise DownloadError("Headless mode requires --skip-login-pause for price-occ downloads.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    staging_path.parent.mkdir(parents=True, exist_ok=True)
    temp_download_path = staging_path.with_suffix(".download")
    if temp_download_path.exists():
        temp_download_path.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(PRICELABS_PRICING_URL, wait_until="domcontentloaded", timeout=120_000)
            wait_for_manual_login_checkpoint(
                skip_login_pause=skip_login_pause,
                message=PRICING_LOGIN_CHECKPOINT_MESSAGE,
            )
            if not headless:
                print("Playwright paused immediately after manual login checkpoint. Step through, then resume.")
                page.pause()
            page.goto(PRICELABS_PRICING_URL, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_load_state("networkidle", timeout=120_000)
            validate_visible_pricing_page(page)
            try:
                tab_strategy = click_neighbourhood_data_tab(page)
                wait_for_price_occ_panel(page)
                download_button_strategy = find_price_occ_download_button_strategy(page)
                with page.expect_download(timeout=120_000) as download_info:
                    click_price_occ_download_button(page, download_button_strategy)
                download = download_info.value
                download.save_as(temp_download_path)
            except DownloadError as exc:
                screenshot_path = save_debug_screenshot(page, logs_dir, run_date)
                raise DownloadError(f"{exc} Debug screenshot saved to {screenshot_path}") from exc
        finally:
            context.close()
            browser.close()

    replace_file(temp_download_path, staging_path)
    return tab_strategy, download_button_strategy


def download_monthly_trends_with_playwright(
    staging_path: Path,
    *,
    logs_dir: Path,
    run_date: str,
    headless: bool,
    skip_login_pause: bool = False,
) -> tuple[str, str]:
    """Download PriceLabs monthly trends CSV into staging."""

    if headless and not skip_login_pause:
        raise DownloadError("Headless mode requires --skip-login-pause for monthly-trends downloads.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    staging_path.parent.mkdir(parents=True, exist_ok=True)
    temp_download_path = staging_path.with_suffix(".download")
    if temp_download_path.exists():
        temp_download_path.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(PRICELABS_PRICING_URL, wait_until="domcontentloaded", timeout=120_000)
            wait_for_manual_login_checkpoint(
                skip_login_pause=skip_login_pause,
                message=PRICING_LOGIN_CHECKPOINT_MESSAGE,
            )
            page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_load_state("networkidle", timeout=120_000)
            validate_visible_pricing_page(page)
            tab_strategy = "url-open-bi"
            wait_for_booking_insights_panel_marker(page)
            try:
                wait_for_monthly_trends_panel(page)
                download_button_strategy = find_monthly_trends_download_button_strategy(page)
                try:
                    capture_validated_download(
                        page,
                        staging_path,
                        lambda: click_monthly_trends_download_button(page, download_button_strategy),
                        validate_monthly_trends_csv,
                        file_label="monthly_trends",
                    )
                except DownloadError as exc:
                    if "PriceLabs API error response" not in str(exc):
                        raise
                    export_monthly_trends_table_from_ui(page, staging_path)
                    validate_monthly_trends_csv(staging_path)
                    download_button_strategy = f"{download_button_strategy}+ui-table-fallback"
            except DownloadError as exc:
                screenshot_path = save_debug_screenshot(page, logs_dir, run_date)
                raise DownloadError(f"{exc} Debug screenshot saved to {screenshot_path}") from exc
        finally:
            context.close()
            browser.close()

    return tab_strategy, download_button_strategy


def download_bookings_report_with_playwright(
    staging_path: Path,
    *,
    logs_dir: Path,
    run_date: str,
    headless: bool,
    skip_login_pause: bool = False,
) -> tuple[str, str]:
    """Download PriceLabs bookings report XLSX into staging."""

    if headless and not skip_login_pause:
        raise DownloadError("Headless mode requires --skip-login-pause for bookings-report downloads.")

    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    staging_path.parent.mkdir(parents=True, exist_ok=True)
    temp_download_path = staging_path.with_suffix(".download")
    if temp_download_path.exists():
        temp_download_path.unlink()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
            wait_for_manual_login_checkpoint(
                skip_login_pause=skip_login_pause,
                message=BOOKING_INSIGHTS_LOGIN_CHECKPOINT_MESSAGE,
            )
            page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_load_state("networkidle", timeout=120_000)
            validate_visible_pricing_page(page)
            wait_for_booking_insights_panel_marker(page)
            try:
                view_all_strategy = find_view_all_bookings_button_strategy(page)
                try:
                    with context.expect_page(timeout=30_000) as page_info:
                        click_view_all_bookings_button(page, view_all_strategy)
                    bookings_page = page_info.value
                except PlaywrightTimeoutError:
                    click_view_all_bookings_button(page, view_all_strategy)
                    bookings_page = page

                bookings_page.wait_for_load_state("domcontentloaded", timeout=120_000)
                try:
                    bookings_page.wait_for_load_state("networkidle", timeout=60_000)
                except Exception:
                    pass
                wait_for_manual_login_checkpoint(
                    skip_login_pause=skip_login_pause,
                    message=bookings_date_range_checkpoint_message(run_date),
                )
                download_button_strategy = find_bookings_download_button_strategy(bookings_page)
                with bookings_page.expect_download(timeout=120_000) as download_info:
                    click_bookings_download_button(bookings_page, download_button_strategy)
                download = download_info.value
                download.save_as(temp_download_path)
            except DownloadError as exc:
                active_page = bookings_page if "bookings_page" in locals() else page
                screenshot_path = save_debug_screenshot(active_page, logs_dir, run_date)
                raise DownloadError(f"{exc} Debug screenshot saved to {screenshot_path}") from exc
        finally:
            context.close()
            browser.close()

    replace_file(temp_download_path, staging_path)
    return view_all_strategy, download_button_strategy


def replace_file(source_path: Path, destination_path: Path) -> None:
    if destination_path.exists():
        destination_path.unlink()
    shutil.move(str(source_path), destination_path)


def capture_validated_download(
    page,
    staging_path: Path,
    click_action,
    validator,
    *,
    file_label: str,
) -> None:
    """Capture download candidates and keep the first one that validates.

    Some PriceLabs export buttons can produce an initial API-error payload and
    then a usable browser download. We collect candidates briefly instead of
    assuming the first download-like response is the final export.
    """

    downloads = []
    page.on("download", lambda download: downloads.append(download))
    click_action()

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not downloads:
        page.wait_for_timeout(250)

    if not downloads:
        raise DownloadError(f"No {file_label} download was captured.")

    settle_deadline = time.monotonic() + 5
    while time.monotonic() < settle_deadline:
        page.wait_for_timeout(250)

    validation_errors = []
    candidate_paths = []
    valid_candidate: Path | None = None

    for index, download in enumerate(downloads, start=1):
        candidate_path = staging_path.with_name(f"{staging_path.stem}.candidate-{index}{staging_path.suffix}")
        candidate_paths.append(candidate_path)
        if candidate_path.exists():
            candidate_path.unlink()
        download.save_as(candidate_path)
        try:
            validator(candidate_path)
            valid_candidate = candidate_path
            break
        except DownloadError as exc:
            suggested_name = getattr(download, "suggested_filename", "")
            validation_errors.append(f"candidate {index} ({suggested_name}): {exc}")

    if valid_candidate is not None:
        replace_file(valid_candidate, staging_path)
        for candidate_path in candidate_paths:
            if candidate_path.exists() and candidate_path != staging_path:
                candidate_path.unlink()
        return

    if candidate_paths:
        replace_file(candidate_paths[0], staging_path)
        for candidate_path in candidate_paths[1:]:
            if candidate_path.exists():
                candidate_path.unlink()
    joined_errors = " | ".join(validation_errors)
    raise DownloadError(f"No captured {file_label} download validated as CSV. {joined_errors}")


def export_monthly_trends_table_from_ui(page, staging_path: Path) -> None:
    rows = extract_monthly_trends_rows_from_ui(page)
    if not rows:
        raise DownloadError("Monthly Trends UI table fallback found no usable month rows.")

    staging_path.parent.mkdir(parents=True, exist_ok=True)
    with staging_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("month_year", "Revenue", "Occupancy", "Booked Occupancy", "Blocked Occupancy", "ADR"),
        )
        writer.writeheader()
        writer.writerows(rows)


def extract_monthly_trends_rows_from_ui(page) -> list[dict[str, str]]:
    script = """
    () => {
      const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
      const marker = Array.from(document.querySelectorAll('p'))
        .find((node) => normalize(node.innerText).includes('Monthly Performance Trends'));
      if (!marker) return [];
      const container = marker.closest('div.chakra-card, div') || document.body;
      const rows = [];
      const rowNodes = Array.from(container.querySelectorAll('tr'));
      for (const rowNode of rowNodes) {
        const cells = Array.from(rowNode.querySelectorAll('td, th')).map((cell) => normalize(cell.innerText));
        if (cells.length >= 4 && /^[A-Za-z]{3,9}\\s+\\d{4}$/.test(cells[0])) {
          rows.push({
            month_year: cells[0],
            Revenue: cells[1] || '',
            Occupancy: cells[2] || '',
            'Booked Occupancy': '',
            'Blocked Occupancy': '',
            ADR: cells[3] || '',
          });
        }
      }
      if (rows.length > 0) return rows;

      const textRows = Array.from(container.querySelectorAll('[role="row"], .chakra-table__tr, div'))
        .map((node) => normalize(node.innerText))
        .filter((text) => /^[A-Za-z]{3,9}\\s+\\d{4}\\b/.test(text));
      for (const text of textRows) {
        const match = text.match(/^([A-Za-z]{3,9}\\s+\\d{4})\\s+(.+?)\\s+([0-9.]+%?)\\s+(.+)$/);
        if (match) {
          rows.push({
            month_year: match[1],
            Revenue: match[2],
            Occupancy: match[3],
            'Booked Occupancy': '',
            'Blocked Occupancy': '',
            ADR: match[4],
          });
        }
      }
      return rows;
    }
    """
    rows = page.evaluate(script)
    if not isinstance(rows, list):
        return []
    cleaned_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned_rows.append(
            {
                "month_year": str(row.get("month_year", "")).strip(),
                "Revenue": str(row.get("Revenue", "")).strip(),
                "Occupancy": str(row.get("Occupancy", "")).strip(),
                "Booked Occupancy": str(row.get("Booked Occupancy", "")).strip(),
                "Blocked Occupancy": str(row.get("Blocked Occupancy", "")).strip(),
                "ADR": str(row.get("ADR", "")).strip(),
            }
        )
    return cleaned_rows


def save_debug_screenshot(page, logs_dir: Path, run_date: str) -> Path:
    """Write a screenshot to logs for selector debugging without saving DOM."""

    logs_dir.mkdir(parents=True, exist_ok=True)
    debug_path = logs_dir / f"pricelabs_download_debug_{run_date}.png"
    page.screenshot(path=debug_path, full_page=True)
    return debug_path


def visible_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=10_000)
    except Exception:
        return ""


def validate_visible_customization_page(page) -> None:
    body_text = visible_body_text(page)
    normalized = " ".join(body_text.split()).lower()
    current_url = getattr(page, "url", "")
    if "404" in normalized and "this page could not be found" in normalized:
        raise DownloadError(
            "PriceLabs customization page is showing a 404. "
            f"Current URL: {current_url}. Navigate manually to the working Customizations page, "
            "then rerun or resume after the login checkpoint."
        )
    if "log in" in normalized and PRICELABS_ACCOUNT_LABEL.lower() not in normalized:
        raise DownloadError(
            "PriceLabs still appears to be on a login page after the manual checkpoint. "
            "Complete login/MFA before pressing Enter."
        )


def validate_visible_pricing_page(page) -> None:
    body_text = visible_body_text(page)
    normalized = " ".join(body_text.split()).lower()
    current_url = getattr(page, "url", "")
    if "404" in normalized and "this page could not be found" in normalized:
        raise DownloadError(
            "PriceLabs pricing page is showing a 404. "
            f"Current URL: {current_url}. Confirm the listing pricing URL, then rerun."
        )
    if "log in" in normalized and "pricing" not in normalized and PRICELABS_ACCOUNT_LABEL.lower() not in normalized:
        raise DownloadError(
            "PriceLabs still appears to be on a login page after the manual checkpoint. "
            "Complete login/MFA before pressing Enter."
        )


def click_neighbourhood_data_tab(page) -> str:
    tab = first_existing_locator(page, NEIGHBOURHOOD_DATA_TAB_SELECTOR)
    if tab is not None:
        try:
            tab.click(timeout=30_000)
            return "qa-id-neighbourhood-data-tab"
        except Exception as exc:
            raise DownloadError("Could not click Neighborhood Data tab using qa-id selector.") from exc

    fallback = page.get_by_text(NEIGHBOURHOOD_DATA_TAB_FALLBACK_TEXT, exact=True).first
    try:
        fallback.wait_for(timeout=30_000)
        fallback.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError("Could not click Neighborhood Data tab. PriceLabs layout may have changed.") from exc
    return "text-neighborhood-data"


def wait_for_price_occ_panel(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:
        pass

    selectors = [
        PRICE_OCC_DOWNLOAD_BUTTON_SELECTOR,
        PRICE_OCC_DOWNLOAD_BUTTON_ARIA_SELECTOR,
    ]
    last_error: Exception | None = None
    for selector in selectors:
        button = page.locator(selector).first
        try:
            button.wait_for(state="visible", timeout=60_000)
            button.wait_for(state="attached", timeout=10_000)
            wait_for_enabled(button, selector)
            return
        except Exception as exc:
            last_error = exc

    raise DownloadError(
        "Price Occ panel did not finish loading a visible CSV Download button after clicking "
        "Neighborhood Data."
    ) from last_error


def find_price_occ_download_button_strategy(page) -> str:
    button = first_existing_locator(page, PRICE_OCC_DOWNLOAD_BUTTON_SELECTOR)
    if button is not None:
        return "qa-id-fp-csv-download"

    button = first_existing_locator(page, PRICE_OCC_DOWNLOAD_BUTTON_ARIA_SELECTOR)
    if button is not None:
        return "aria-label-csv-download"

    raise DownloadError("Could not find Price Occ CSV Download button. PriceLabs layout may have changed.")


def click_booking_insights_tab(page) -> str:
    tab = first_existing_locator(page, BOOKING_INSIGHTS_TAB_SELECTOR)
    if tab is not None:
        try:
            tab.click(timeout=30_000)
            return "qa-id-rp-booking-insights"
        except Exception as exc:
            raise DownloadError("Could not click Booking Insights tab using qa-id selector.") from exc

    fallback = page.get_by_text(BOOKING_INSIGHTS_TAB_FALLBACK_TEXT, exact=True).first
    try:
        fallback.wait_for(timeout=30_000)
        fallback.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError("Could not click Booking Insights tab. PriceLabs layout may have changed.") from exc
    return "text-booking-insights"


def wait_for_booking_insights_ready(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:
        pass

    tab = page.locator(BOOKING_INSIGHTS_TAB_SELECTOR).first
    try:
        tab.wait_for(state="visible", timeout=60_000)
        tab.wait_for(state="attached", timeout=10_000)
        wait_for_enabled(tab, BOOKING_INSIGHTS_TAB_SELECTOR)
        return
    except Exception:
        pass

    fallback = page.get_by_text(BOOKING_INSIGHTS_TAB_FALLBACK_TEXT, exact=True).first
    try:
        fallback.wait_for(timeout=60_000)
    except Exception as exc:
        raise DownloadError(
            "Booking Insights tab did not become ready after the pricing page loaded."
        ) from exc


def wait_for_booking_insights_panel_marker(page) -> None:
    marker = page.get_by_text(BOOKING_INSIGHTS_PANEL_MARKER_TEXT, exact=False).first
    try:
        marker.wait_for(state="visible", timeout=60_000)
    except Exception as exc:
        current_url = getattr(page, "url", "")
        raise DownloadError(
            "Booking Insights panel marker did not become visible after clicking the tab. "
            f"Current URL: {current_url}"
        ) from exc


def wait_for_monthly_trends_panel(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=60_000)
    except Exception:
        pass

    selectors = [
        MONTHLY_TRENDS_DOWNLOAD_BUTTON_SELECTOR,
        MONTHLY_TRENDS_DOWNLOAD_BUTTON_ID_SELECTOR,
        MONTHLY_TRENDS_DOWNLOAD_BUTTON_TITLE_SELECTOR,
    ]
    last_error: Exception | None = None
    for selector in selectors:
        button = page.locator(selector).first
        try:
            button.wait_for(state="visible", timeout=60_000)
            button.wait_for(state="attached", timeout=10_000)
            return
        except Exception as exc:
            last_error = exc

    raise DownloadError(
        "Monthly Trends panel did not finish loading a visible CSV Download button after clicking "
        "Booking Insights."
    ) from last_error


def find_monthly_trends_download_button_strategy(page) -> str:
    button = first_existing_locator(page, MONTHLY_TRENDS_DOWNLOAD_BUTTON_SELECTOR)
    if button is not None:
        return "qa-id-mpt-csv-download"

    button = first_existing_locator(page, MONTHLY_TRENDS_DOWNLOAD_BUTTON_ID_SELECTOR)
    if button is not None:
        return "id-mpt-csv-download"

    button = first_existing_locator(page, MONTHLY_TRENDS_DOWNLOAD_BUTTON_TITLE_SELECTOR)
    if button is not None:
        return "title-csv"

    raise DownloadError("Could not find Monthly Trends CSV Download button. PriceLabs layout may have changed.")


def find_view_all_bookings_button_strategy(page) -> str:
    button = first_existing_locator(page, VIEW_ALL_BOOKINGS_BUTTON_SELECTOR)
    if button is not None:
        return "qa-id-booking-insights-bookings-cta"

    button = first_existing_locator(page, VIEW_ALL_BOOKINGS_BUTTON_ID_SELECTOR)
    if button is not None:
        return "id-booking-insights-bookings-cta"

    button = page.get_by_text(VIEW_ALL_BOOKINGS_BUTTON_TEXT, exact=True).first
    try:
        if button.count() > 0:
            return "text-view-all-bookings"
    except Exception:
        pass

    raise DownloadError("Could not find View All Bookings button. PriceLabs layout may have changed.")


def click_view_all_bookings_button(page, strategy: str) -> None:
    if strategy == "qa-id-booking-insights-bookings-cta":
        button = page.locator(VIEW_ALL_BOOKINGS_BUTTON_SELECTOR).first
    elif strategy == "id-booking-insights-bookings-cta":
        button = page.locator(VIEW_ALL_BOOKINGS_BUTTON_ID_SELECTOR).first
    elif strategy == "text-view-all-bookings":
        button = page.get_by_text(VIEW_ALL_BOOKINGS_BUTTON_TEXT, exact=True).first
    else:
        raise DownloadError(f"Unsupported View All Bookings button strategy: {strategy}")

    try:
        button.wait_for(state="visible", timeout=60_000)
        wait_for_enabled(button, strategy)
        button.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError(f"Could not click View All Bookings using strategy '{strategy}'.") from exc


def find_bookings_download_button_strategy(page) -> str:
    button = page.get_by_role("button", name=BOOKINGS_DOWNLOAD_BUTTON_TEXT, exact=True).first
    try:
        if button.count() > 0:
            button.wait_for(state="visible", timeout=60_000)
            wait_for_enabled(button, "role-button-download")
            return "role-button-download"
    except Exception:
        pass

    button = page.get_by_text(BOOKINGS_DOWNLOAD_BUTTON_TEXT, exact=True).first
    try:
        if button.count() > 0:
            button.wait_for(state="visible", timeout=60_000)
            wait_for_enabled(button, "text-download")
            return "text-download"
    except Exception:
        pass

    raise DownloadError("Could not find bookings report Download button. PriceLabs layout may have changed.")


def click_bookings_download_button(page, strategy: str) -> None:
    if strategy == "role-button-download":
        button = page.get_by_role("button", name=BOOKINGS_DOWNLOAD_BUTTON_TEXT, exact=True).first
    elif strategy == "text-download":
        button = page.get_by_text(BOOKINGS_DOWNLOAD_BUTTON_TEXT, exact=True).first
    else:
        raise DownloadError(f"Unsupported bookings report Download button strategy: {strategy}")

    try:
        button.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError(f"Could not click bookings report Download using strategy '{strategy}'.") from exc


def wait_for_enabled(locator, selector: str, *, timeout_ms: int = 60_000) -> None:
    deadline = datetime.now(timezone.utc).timestamp() + (timeout_ms / 1000)
    last_error: Exception | None = None
    while datetime.now(timezone.utc).timestamp() < deadline:
        try:
            if locator.is_enabled(timeout=1_000):
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.25)
    raise DownloadError(f"Element did not become enabled: {selector}") from last_error


def click_monthly_trends_download_button(page, strategy: str) -> None:
    if strategy == "qa-id-mpt-csv-download":
        button = page.locator(MONTHLY_TRENDS_DOWNLOAD_BUTTON_SELECTOR).first
    elif strategy == "id-mpt-csv-download":
        button = page.locator(MONTHLY_TRENDS_DOWNLOAD_BUTTON_ID_SELECTOR).first
    elif strategy == "title-csv":
        button = page.locator(MONTHLY_TRENDS_DOWNLOAD_BUTTON_TITLE_SELECTOR).first
    else:
        raise DownloadError(f"Unsupported Monthly Trends download button strategy: {strategy}")

    try:
        button.wait_for(timeout=30_000)
        button.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError(
            f"Could not click Monthly Trends CSV Download button using strategy '{strategy}'."
        ) from exc


def click_price_occ_download_button(page, strategy: str) -> None:
    if strategy == "qa-id-fp-csv-download":
        button = page.locator(PRICE_OCC_DOWNLOAD_BUTTON_SELECTOR).first
    elif strategy == "aria-label-csv-download":
        button = page.locator(PRICE_OCC_DOWNLOAD_BUTTON_ARIA_SELECTOR).first
    else:
        raise DownloadError(f"Unsupported Price Occ download button strategy: {strategy}")

    try:
        button.wait_for(timeout=30_000)
        button.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError(
            f"Could not click Price Occ CSV Download button using strategy '{strategy}'."
        ) from exc


def trigger_future_export_download(page) -> str:
    """Open the Lodgify account menu that contains Download CSV Prices.

    PriceLabs UI details may change. This function keeps the assumptions in one
    place so future selector fixes do not affect validation or staging behavior.
    """

    account_label = page.get_by_text(PRICELABS_ACCOUNT_LABEL, exact=False).first
    try:
        account_label.wait_for(timeout=120_000)
    except Exception as exc:
        raise DownloadError(
            "Could not find the Lodgify account on the PriceLabs customization page. "
            "Complete manual login/MFA if prompted, then rerun; selector may also need review."
        ) from exc

    menu_button, strategy_name = find_account_menu_button(page, account_label)
    try:
        menu_button.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError(
            "Could not open the Lodgify three-dot menu using "
            f"strategy '{strategy_name}'. PriceLabs page layout may have changed."
        ) from exc
    return strategy_name


def find_account_menu_button(page, account_label):
    """Find a likely menu button near the account label."""

    direct_account_menu = first_existing_locator(
        page,
        'button[qa-id="cust-account-list-context-menu-lodgify"]',
    )
    if direct_account_menu is not None:
        return direct_account_menu, "account-context-menu-qa-id"

    container_selectors = [
        "xpath=ancestor::tr[1]",
        "xpath=ancestor::*[contains(@class, 'card')][1]",
        "xpath=ancestor::*[contains(@class, 'row')][1]",
        "xpath=ancestor::div[1]",
    ]

    containers = []
    for container_selector in container_selectors:
        container = account_label.locator(container_selector)
        try:
            if container.count() > 0:
                containers.append(container)
        except Exception:
            continue

    for container in containers:
        candidate = first_existing_locator(container, "button.chakra-menu__menu-button")
        if candidate is not None:
            return candidate, "chakra-menu-button"

    for container in containers:
        candidate = first_existing_locator(container, 'button[id^="menu-button-"]')
        if candidate is not None:
            return candidate, "menu-button-id-prefix"

    aria_or_title_selectors = [
        "button[aria-label*='menu' i]",
        "button[aria-label*='more' i]",
        "button[aria-label*='options' i]",
        "button[title*='menu' i]",
        "button[title*='more' i]",
        "button[title*='options' i]",
        "[role='button'][aria-label*='menu' i]",
        "[role='button'][aria-label*='more' i]",
        "[role='button'][aria-label*='options' i]",
        "[role='button'][title*='menu' i]",
        "[role='button'][title*='more' i]",
        "[role='button'][title*='options' i]",
    ]
    for container in containers:
        for selector in aria_or_title_selectors:
            candidate = first_existing_locator(container, selector)
            if candidate is not None:
                return candidate, f"aria-title-{selector}"

    for container in containers:
        candidate = last_visible_button(container)
        if candidate is not None:
            return candidate, "last-visible-button"

    debug_candidate = page.locator('xpath=//*[@id="menu-button-:r2g:"]').first
    try:
        if debug_candidate.count() > 0:
            return debug_candidate, "debug-menu-button-r2g"
    except Exception:
        pass

    raise DownloadError(
        "Could not locate a three-dot/menu button near the Lodgify account. "
        "Selector review is required."
    )


def first_existing_locator(container, selector: str):
    candidate = container.locator(selector).first
    try:
        if candidate.count() > 0:
            return candidate
    except Exception:
        return None
    return None


def last_visible_button(container):
    buttons = container.locator("button")
    try:
        count = buttons.count()
    except Exception:
        return None

    for index in range(count - 1, -1, -1):
        candidate = buttons.nth(index)
        try:
            if candidate.is_visible():
                return candidate
        except Exception:
            continue
    return None


def click_download_csv_prices(page) -> None:
    menu_item = page.get_by_text(FUTURE_EXPORT_MENU_ITEM, exact=True).first
    try:
        menu_item.wait_for(timeout=30_000)
        menu_item.click(timeout=30_000)
    except Exception as exc:
        raise DownloadError(
            "Could not click 'Download CSV Prices'. PriceLabs menu text or layout may have changed."
        ) from exc


def real_download_log_lines(
    *,
    run_date: str,
    target: str,
    staging_path: Path,
    status: str,
    menu_strategy: str | None = None,
    pricing_url: str | None = None,
    tab_strategy: str | None = None,
    view_all_bookings_strategy: str | None = None,
    download_button_strategy: str | None = None,
    reason: str | None = None,
) -> list[str]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"PriceLabs downloader started at {timestamp}",
        f"run_date={run_date}",
        f"target={target}",
        "mode=real download",
        f"staging_path={staging_path}",
        "auth_checkpoint=manual login/MFA checkpoint before download",
        "raw_touched=false",
        f"validation_status={status}",
    ]
    if menu_strategy:
        lines.append(f"menu_strategy={menu_strategy}")
    if pricing_url:
        lines.append(f"pricing_url={pricing_url}")
    if tab_strategy:
        lines.append(f"tab_strategy={tab_strategy}")
    if view_all_bookings_strategy:
        lines.append(f"view_all_bookings_strategy={view_all_bookings_strategy}")
    if download_button_strategy:
        lines.append(f"download_button_strategy={download_button_strategy}")
    if reason:
        lines.append(f"failure_reason={reason}")
    return lines


def run_future_export_download(
    run_date: str,
    *,
    headless: bool,
    skip_login_pause: bool = False,
) -> Path:
    _, staging_dir, logs_dir, log_file = get_run_paths(run_date)
    staging_path = staging_dir / FUTURE_EXPORT_FILENAME

    try:
        menu_strategy = download_future_export_with_playwright(
            staging_path,
            logs_dir=logs_dir,
            run_date=run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
        validate_future_export_csv(staging_path)
    except DownloadError as exc:
        write_log(
            log_file,
            real_download_log_lines(
                run_date=run_date,
                target=FUTURE_EXPORT_TARGET,
                staging_path=staging_path,
                status="failed",
                reason=str(exc),
            ),
        )
        raise

    write_log(
        log_file,
        real_download_log_lines(
            run_date=run_date,
            target=FUTURE_EXPORT_TARGET,
            staging_path=staging_path,
            status="passed",
            menu_strategy=menu_strategy,
        )
        + ["Future export downloaded and validated in staging.", "Raw folder was not touched."],
    )
    return log_file


def run_price_occ_download(
    run_date: str,
    *,
    headless: bool,
    skip_login_pause: bool = False,
) -> Path:
    _, staging_dir, logs_dir, log_file = get_run_paths(run_date)
    staging_path = staging_dir / PRICE_OCC_FILENAME

    try:
        tab_strategy, download_button_strategy = download_price_occ_with_playwright(
            staging_path,
            logs_dir=logs_dir,
            run_date=run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
        validate_price_occ_csv(staging_path)
    except DownloadError as exc:
        write_log(
            log_file,
            real_download_log_lines(
                run_date=run_date,
                target=PRICE_OCC_TARGET,
                staging_path=staging_path,
                status="failed",
                pricing_url=PRICELABS_PRICING_URL,
                reason=str(exc),
            ),
        )
        raise

    write_log(
        log_file,
        real_download_log_lines(
            run_date=run_date,
            target=PRICE_OCC_TARGET,
            staging_path=staging_path,
            status="passed",
            pricing_url=PRICELABS_PRICING_URL,
            tab_strategy=tab_strategy,
            download_button_strategy=download_button_strategy,
        )
        + ["Price Occ export downloaded and validated in staging.", "Raw folder was not touched."],
    )
    return log_file


def run_monthly_trends_download(
    run_date: str,
    *,
    headless: bool,
    skip_login_pause: bool = False,
) -> Path:
    _, staging_dir, logs_dir, log_file = get_run_paths(run_date)
    staging_path = staging_dir / MONTHLY_TRENDS_FILENAME

    try:
        tab_strategy, download_button_strategy = download_monthly_trends_with_playwright(
            staging_path,
            logs_dir=logs_dir,
            run_date=run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
        validate_monthly_trends_csv(staging_path)
    except DownloadError as exc:
        write_log(
            log_file,
            real_download_log_lines(
                run_date=run_date,
                target=MONTHLY_TRENDS_TARGET,
                staging_path=staging_path,
                status="failed",
                pricing_url=PRICELABS_BOOKING_INSIGHTS_URL,
                reason=str(exc),
            ),
        )
        raise

    write_log(
        log_file,
        real_download_log_lines(
            run_date=run_date,
            target=MONTHLY_TRENDS_TARGET,
            staging_path=staging_path,
            status="passed",
            pricing_url=PRICELABS_BOOKING_INSIGHTS_URL,
            tab_strategy=tab_strategy,
            download_button_strategy=download_button_strategy,
        )
        + ["Monthly Trends export downloaded and validated in staging.", "Raw folder was not touched."],
    )
    return log_file


def run_bookings_report_download(
    run_date: str,
    *,
    headless: bool,
    skip_login_pause: bool = False,
) -> Path:
    _, staging_dir, logs_dir, log_file = get_run_paths(run_date)
    staging_path = staging_dir / BOOKINGS_REPORT_FILENAME

    try:
        view_all_strategy, download_button_strategy = download_bookings_report_with_playwright(
            staging_path,
            logs_dir=logs_dir,
            run_date=run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
        validate_bookings_report_xlsx(staging_path)
    except DownloadError as exc:
        write_log(
            log_file,
            real_download_log_lines(
                run_date=run_date,
                target=BOOKINGS_REPORT_TARGET,
                staging_path=staging_path,
                status="failed",
                pricing_url=PRICELABS_BOOKING_INSIGHTS_URL,
                reason=str(exc),
            ),
        )
        raise

    write_log(
        log_file,
        real_download_log_lines(
            run_date=run_date,
            target=BOOKINGS_REPORT_TARGET,
            staging_path=staging_path,
            status="passed",
            pricing_url=PRICELABS_BOOKING_INSIGHTS_URL,
            view_all_bookings_strategy=view_all_strategy,
            download_button_strategy=download_button_strategy,
        )
        + ["Bookings Report export downloaded and validated in staging.", "Raw folder was not touched."],
    )
    return log_file


def run(
    run_date: str,
    *,
    target: str | None = None,
    dry_run: bool = False,
    headless: bool = False,
    skip_login_pause: bool = False,
) -> Path:
    if dry_run or target is None:
        return run_skeleton(run_date)
    if target == FUTURE_EXPORT_TARGET:
        return run_future_export_download(
            run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
    if target == PRICE_OCC_TARGET:
        return run_price_occ_download(
            run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
    if target == MONTHLY_TRENDS_TARGET:
        return run_monthly_trends_download(
            run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
    if target == BOOKINGS_REPORT_TARGET:
        return run_bookings_report_download(
            run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
    raise DownloadError(f"Unsupported download target: {target}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        log_file = run(
            args.run_date,
            target=args.target,
            dry_run=args.dry_run,
            headless=args.headless,
            skip_login_pause=args.skip_login_pause,
        )
    except DownloadError as exc:
        print(f"PriceLabs downloader failed: {exc}", file=sys.stderr)
        return 1

    if args.target and not args.dry_run:
        print(f"PriceLabs downloader completed for {args.target}. Log: {log_file}")
    else:
        print(f"PriceLabs downloader skeleton completed. Log: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
