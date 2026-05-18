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
from datetime import datetime, timezone
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
SETTINGS_SNAPSHOT_FILENAME = "pricelabs_settings_snapshot_from_ui.json"
FUTURE_EXPORT_TARGET = "future-export"
PRICE_OCC_TARGET = "price-occ"
MONTHLY_TRENDS_TARGET = "monthly-trends"
BOOKINGS_REPORT_TARGET = "bookings-report"
SETTINGS_SNAPSHOT_TARGET = "settings-snapshot"
SUPPORTED_TARGETS = [
    FUTURE_EXPORT_TARGET,
    PRICE_OCC_TARGET,
    MONTHLY_TRENDS_TARGET,
    BOOKINGS_REPORT_TARGET,
    SETTINGS_SNAPSHOT_TARGET,
]
DOWNLOAD_ALL_LOGIN_TIMEOUT_MS = 120_000
REPO_ROOT = Path(__file__).resolve().parents[3]
PERSISTENT_SESSION_PROFILE_DIR = REPO_ROOT / ".local" / "pricelabs_browser_profile"
LOCAL_CREDENTIALS_FILE = REPO_ROOT / ".local" / "pricelabs.env"
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
    "When you see the Customization page, return to this terminal and press Enter."
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
CUSTOMIZATION_WELL_SELECTOR = 'div[qa-id="customization-well"]'
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
        required=False,
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
        help="Explicit real download or capture target.",
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
    parser.add_argument(
        "--promote-to-raw",
        action="store_true",
        help="Validate all staged PriceLabs inputs and copy them into raw/ without overwriting existing raw files.",
    )
    parser.add_argument(
        "--download-all",
        action="store_true",
        help="Open one PriceLabs browser session and stage all required downloads after one manual login checkpoint.",
    )
    parser.add_argument(
        "--use-persistent-session",
        action="store_true",
        help="Use a local gitignored Playwright browser profile to reuse PriceLabs login when possible.",
    )
    parser.add_argument(
        "--auth-check",
        action="store_true",
        help="Check whether the local PriceLabs browser session appears logged in without downloading files.",
    )
    parser.add_argument(
        "--use-local-credentials",
        action="store_true",
        help="Use local gitignored .local/pricelabs.env as an optional login fallback.",
    )
    args = parser.parse_args(argv)
    if args.run_date:
        validate_run_date(args.run_date, parser)
    elif not args.auth_check:
        parser.error("--run-date is required unless --auth-check is used.")
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


REQUIRED_SETTINGS_KEYS = (
    "last_minute",
    "orphan_day_prices",
    "booking_recency_factor",
    "minimum_stay_settings",
    "extra_person_fee",
    "occupancy_based_adjustments",
    "custom_seasonality_factor",
    "length_of_stay_based_pricing",
    "demand_factor_sensitivity",
    "far_out_premium",
    "safety_minimum_price",
)


def validate_settings_snapshot_json(json_path: Path) -> None:
    if not json_path.exists():
        raise DownloadError(f"Missing staged file: {json_path}")
    if json_path.stat().st_size <= 0:
        raise DownloadError("Settings snapshot JSON is empty.")

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DownloadError("Settings snapshot is not readable JSON.") from exc

    if not isinstance(payload, dict):
        raise DownloadError("Settings snapshot JSON must be an object.")
    if not str(payload.get("run_date", "")).strip():
        raise DownloadError("Settings snapshot JSON is missing run_date.")
    if not str(payload.get("source", "")).strip():
        raise DownloadError("Settings snapshot JSON is missing source.")
    if str(payload.get("source_url", "")).strip() != PRICELABS_BOOKING_INSIGHTS_URL:
        raise DownloadError("Settings snapshot JSON source_url must be the PriceLabs Booking Insights URL.")
    settings = payload.get("settings")
    if not isinstance(settings, dict):
        raise DownloadError("Settings snapshot JSON is missing settings object.")

    missing_keys = [key for key in REQUIRED_SETTINGS_KEYS if key not in settings]
    if missing_keys:
        raise DownloadError(f"Settings snapshot JSON is missing required settings: {', '.join(missing_keys)}")

    empty_values = []
    for key in REQUIRED_SETTINGS_KEYS:
        setting = settings.get(key)
        if not isinstance(setting, dict):
            empty_values.append(key)
            continue
        value = setting.get("value_text") or setting.get("value")
        if not isinstance(value, str) or not value.strip():
            empty_values.append(key)
    if empty_values:
        raise DownloadError(f"Settings snapshot JSON has empty values for: {', '.join(empty_values)}")

    min_stay_value = settings["minimum_stay_settings"].get("value_text") or settings["minimum_stay_settings"].get("value", "")
    missing_min_stay_parts = [
        part
        for part in ("Default", "Last Minute", "Far Out", "Orphan Gaps", "Lowest Minstay Allowed")
        if part.lower() not in str(min_stay_value).lower()
    ]
    if missing_min_stay_parts:
        raise DownloadError(
            "Settings snapshot minimum_stay_settings appears truncated; missing: "
            + ", ".join(missing_min_stay_parts)
        )

    safety_value = settings["safety_minimum_price"].get("value_text") or settings["safety_minimum_price"].get("value", "")
    if "110%" not in str(safety_value) or "180 days" not in str(safety_value):
        raise DownloadError("Settings snapshot safety_minimum_price appears truncated.")


def wait_for_manual_login_checkpoint(
    *,
    skip_login_pause: bool,
    message: str = CUSTOMIZATION_LOGIN_CHECKPOINT_MESSAGE,
) -> None:
    if skip_login_pause:
        return
    print(message)
    input()


DOWNLOAD_ALL_LOGIN_CHECKPOINT_MESSAGE = (
    "Please log in to PriceLabs manually in the opened browser. Complete MFA if required. "
    "The downloader will continue automatically when the logged-in PriceLabs page is visible."
)
HEADLESS_LOGIN_INTERACTIVE_REQUIRED_MESSAGE = (
    "Headless login could not complete because interactive verification appears required."
)


def wait_for_download_all_login_ready(
    page,
    *,
    skip_login_pause: bool,
    use_local_credentials: bool = False,
    headless: bool = False,
) -> None:
    if skip_login_pause:
        return
    if is_download_all_login_ready(page, timeout_ms=3_000):
        return
    if headless and not use_local_credentials:
        raise DownloadError("Headless mode requires --use-local-credentials; manual login is unavailable in headless mode.")
    if use_local_credentials:
        credentials = read_local_credentials()
        print(
            "\n".join(
                credential_login_log_lines(
                    requested=True,
                    file_found=credentials is not None,
                    attempted=credentials is not None,
                    mfa_manual_checkpoint=False,
                )
            )
        )
        if credentials is None and headless:
            raise DownloadError("Headless login could not complete because local credentials were not found or incomplete.")
        if credentials is not None and attempt_local_credential_login(page, credentials):
            if is_download_all_login_ready(page, timeout_ms=10_000):
                return
            if headless:
                raise DownloadError(HEADLESS_LOGIN_INTERACTIVE_REQUIRED_MESSAGE)
            print(
                "\n".join(
                    credential_login_log_lines(
                        requested=True,
                        file_found=True,
                        attempted=True,
                        mfa_manual_checkpoint=True,
                    )
                )
            )
            print("Complete PriceLabs MFA manually in the opened browser. The downloader will continue after login.")
            wait_for_download_all_login_state(page, timeout_ms=DOWNLOAD_ALL_LOGIN_TIMEOUT_MS)
            return
        if headless:
            raise DownloadError(HEADLESS_LOGIN_INTERACTIVE_REQUIRED_MESSAGE)
    print(DOWNLOAD_ALL_LOGIN_CHECKPOINT_MESSAGE)
    wait_for_download_all_login_state(page, timeout_ms=DOWNLOAD_ALL_LOGIN_TIMEOUT_MS)


def is_download_all_login_ready(page, *, timeout_ms: int) -> bool:
    try:
        wait_for_download_all_login_state(page, timeout_ms=timeout_ms)
        return True
    except DownloadError:
        return False


def wait_for_download_all_login_state(page, *, timeout_ms: int) -> None:
    try:
        page.wait_for_function(
            """
            () => {
              const text = (document.body && document.body.innerText || '').replace(/\\s+/g, ' ').toLowerCase();
              const url = window.location.href.toLowerCase();
              const loggedInMarker = text.includes('aloha poconos')
                || text.includes('applied customizations')
                || text.includes('booking insights')
                || text.includes('lodgify');
              const loginMarker = text.includes('log in') || text.includes('sign in');
              return url.includes('app.pricelabs.co') && loggedInMarker && !loginMarker;
            }
            """,
            timeout=timeout_ms,
        )
    except Exception as exc:
        raise DownloadError(
            "Timed out after 2 minutes waiting for manual PriceLabs login to complete. "
            "Complete login/MFA in the browser and make sure a logged-in PriceLabs page is visible."
        ) from exc


def read_local_credentials(path: Path = LOCAL_CREDENTIALS_FILE) -> dict[str, str] | None:
    if not path.exists():
        return None
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    email = values.get("PRICELABS_EMAIL", "").strip()
    password = values.get("PRICELABS_PASSWORD", "").strip()
    if not email or not password:
        return None
    return {"email": email, "password": password}


def credential_login_log_lines(
    *,
    requested: bool,
    file_found: bool,
    attempted: bool,
    mfa_manual_checkpoint: bool,
) -> list[str]:
    return [
        f"local_credentials_requested={'true' if requested else 'false'}",
        f"local_credentials_file_found={'true' if file_found else 'false'}",
        f"credential_login_attempted={'true' if attempted else 'false'}",
        f"mfa_manual_checkpoint={'true' if mfa_manual_checkpoint else 'false'}",
    ]


def first_visible_locator(page, selectors: Sequence[str], *, timeout_ms: int = 5_000):
    last_error: Exception | None = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except Exception as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise DownloadError("No selectors provided.")


def attempt_local_credential_login(page, credentials: dict[str, str]) -> bool:
    try:
        email = first_visible_locator(
            page,
            (
                'input[type="email"]',
                'input[name*="email" i]',
                'input[placeholder*="email" i]',
                'input[autocomplete="username"]',
            ),
        )
        password = first_visible_locator(
            page,
            (
                'input[type="password"]',
                'input[name*="password" i]',
                'input[placeholder*="password" i]',
                'input[autocomplete="current-password"]',
            ),
        )
        email.fill(credentials["email"])
        password.fill(credentials["password"])
        submit = first_visible_locator(
            page,
            (
                'input[type="submit"][name="commit"][value="Sign in"]',
                'input[type="submit"][value="Sign in"]',
                'input[name="commit"]',
                'button[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Continue")',
                'text="Sign in"',
            ),
        )
        submit.click()
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        return True
    except Exception:
        return False


def classify_auth_status(page) -> str:
    try:
        body_text = visible_body_text(page)
    except Exception:
        body_text = ""
    normalized = " ".join(body_text.split()).lower()
    if (
        "aloha poconos" in normalized
        or "applied customizations" in normalized
        or "booking insights" in normalized
        or "lodgify" in normalized
    ) and "log in" not in normalized and "sign in" not in normalized:
        return "logged_in"
    if any(marker in normalized for marker in ("log in", "sign in", "password", "email")):
        return "login_required"
    return "unknown"


def auth_check_log_lines(*, profile_path: Path, profile_exists: bool, auth_status: str) -> list[str]:
    return [
        f"persistent_profile_path={profile_path}",
        f"persistent_profile_exists={'true' if profile_exists else 'false'}",
        f"auth_status={auth_status}",
    ]


def bookings_date_range_checkpoint_message(run_date: str) -> str:
    datetime.strptime(run_date, "%Y-%m-%d")
    return (
        "Confirm the page shows a one-month Booking Date range. "
        "Do not use Stay Date as the main filter. Leave Stay Date broad/default if available. "
        "If the Booking Date range looks correct, return to this terminal and press Enter. "
        "Only adjust it manually if the default range is wrong."
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


def capture_settings_snapshot_with_playwright(
    staging_path: Path,
    *,
    logs_dir: Path,
    run_date: str,
    headless: bool,
    skip_login_pause: bool = False,
) -> int:
    """Capture visible PriceLabs customization-well settings into JSON."""

    if headless and not skip_login_pause:
        raise DownloadError("Headless mode requires --skip-login-pause for settings-snapshot captures.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    staging_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(PRICELABS_CUSTOMIZATION_URL, wait_until="domcontentloaded", timeout=120_000)
            wait_for_manual_login_checkpoint(skip_login_pause=skip_login_pause)
            page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_load_state("networkidle", timeout=120_000)
            validate_visible_pricing_page(page)
            try:
                expand_applied_customizations_well(page)
                wait_for_customization_well(page)
                expand_collapsed_customization_sections(page)
                settings = extract_settings_from_customization_well(page)
                capture_settings_popover_details(page, settings)
                payload = {
                    "run_date": run_date,
                    "listing_id": "650255___717243",
                    "pms_name": "lodgify",
                    "source": "pricelabs_ui_customization_well",
                    "source_url": PRICELABS_BOOKING_INSIGHTS_URL,
                    "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "url": PRICELABS_BOOKING_INSIGHTS_URL,
                    "settings": settings,
                }
                staging_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except DownloadError as exc:
                screenshot_path = save_debug_screenshot(page, logs_dir, run_date)
                raise DownloadError(f"{exc} Debug screenshot saved to {screenshot_path}") from exc
        finally:
            context.close()
            browser.close()

    return len(settings)


def download_future_export_in_session(page, staging_path: Path) -> str:
    temp_download_path = staging_path.with_suffix(".download")
    if temp_download_path.exists():
        temp_download_path.unlink()

    page.goto(PRICELABS_CUSTOMIZATION_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_load_state("networkidle", timeout=120_000)
    validate_visible_customization_page(page)
    menu_strategy = trigger_future_export_download(page)
    with page.expect_download(timeout=120_000) as download_info:
        click_download_csv_prices(page)
    download_info.value.save_as(temp_download_path)
    replace_file(temp_download_path, staging_path)
    return menu_strategy


def download_price_occ_in_session(page, staging_path: Path) -> tuple[str, str]:
    temp_download_path = staging_path.with_suffix(".download")
    if temp_download_path.exists():
        temp_download_path.unlink()

    page.goto(PRICELABS_PRICING_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_load_state("networkidle", timeout=120_000)
    validate_visible_pricing_page(page)
    tab_strategy = click_neighbourhood_data_tab(page)
    wait_for_price_occ_panel(page)
    download_button_strategy = find_price_occ_download_button_strategy(page)
    with page.expect_download(timeout=120_000) as download_info:
        click_price_occ_download_button(page, download_button_strategy)
    download_info.value.save_as(temp_download_path)
    replace_file(temp_download_path, staging_path)
    return tab_strategy, download_button_strategy


def download_monthly_trends_in_session(page, staging_path: Path) -> tuple[str, str]:
    page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_load_state("networkidle", timeout=120_000)
    validate_visible_pricing_page(page)
    tab_strategy = "url-open-bi"
    wait_for_booking_insights_panel_marker(page)
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
    return tab_strategy, download_button_strategy


def download_bookings_report_in_session(context, page, staging_path: Path) -> tuple[str, str]:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    temp_download_path = staging_path.with_suffix(".download")
    if temp_download_path.exists():
        temp_download_path.unlink()

    page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_load_state("networkidle", timeout=120_000)
    validate_visible_pricing_page(page)
    wait_for_booking_insights_panel_marker(page)
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
    download_button_strategy = find_bookings_download_button_strategy(bookings_page)
    with bookings_page.expect_download(timeout=120_000) as download_info:
        click_bookings_download_button(bookings_page, download_button_strategy)
    download_info.value.save_as(temp_download_path)
    replace_file(temp_download_path, staging_path)
    return_to_primary_page(page, bookings_page)
    return view_all_strategy, download_button_strategy


def return_to_primary_page(primary_page, secondary_page=None) -> None:
    """Bring the original PriceLabs page back before the next one-session step."""

    if secondary_page is not None and secondary_page is not primary_page:
        try:
            secondary_page.close()
        except Exception:
            pass
    try:
        primary_page.bring_to_front()
    except Exception:
        pass


def capture_settings_snapshot_in_session(page, staging_path: Path, *, run_date: str) -> int:
    page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_load_state("networkidle", timeout=120_000)
    validate_visible_pricing_page(page)
    expand_applied_customizations_well(page)
    wait_for_customization_well(page)
    expand_collapsed_customization_sections(page)
    settings = extract_settings_from_customization_well(page)
    capture_settings_popover_details(page, settings)
    payload = {
        "run_date": run_date,
        "listing_id": "650255___717243",
        "pms_name": "lodgify",
        "source": "pricelabs_ui_customization_well",
        "source_url": PRICELABS_BOOKING_INSIGHTS_URL,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "url": PRICELABS_BOOKING_INSIGHTS_URL,
        "settings": settings,
    }
    staging_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return len(settings)


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


def wait_for_customization_well(page) -> None:
    well = page.locator(CUSTOMIZATION_WELL_SELECTOR).first
    try:
        well.wait_for(state="visible", timeout=120_000)
    except Exception as exc:
        raise DownloadError("Could not find visible PriceLabs customization well.") from exc


def expand_applied_customizations_well(page) -> int:
    """Open the outer Applied Customizations well if it is collapsed."""

    try:
        if page.locator(CUSTOMIZATION_WELL_SELECTOR).first.is_visible(timeout=1_000):
            return 0
    except Exception:
        pass

    try:
        header = page.locator('div[qa-id="applied-cust-well"], #re-aplied-customizations').first
        header.wait_for(state="visible", timeout=10_000)
        header.click(timeout=10_000, position={"x": 24, "y": 24})
        page.wait_for_timeout(750)
        try:
            if page.locator(CUSTOMIZATION_WELL_SELECTOR).first.is_visible(timeout=3_000):
                return 1
        except Exception:
            pass
    except Exception:
        pass

    script = """
    () => {
      const header = document.querySelector('div[qa-id="applied-cust-well"], #re-aplied-customizations');
      if (!header) return 0;

      const isVisible = (element) => {
        if (!element) return false;
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.visibility !== 'hidden'
          && style.display !== 'none'
          && rect.width > 0
          && rect.height > 0;
      };

      const collapsedCaret = header.querySelector('svg[data-icon="caret-right"], svg.fa-caret-right');
      if (!collapsedCaret || !isVisible(collapsedCaret) || !isVisible(header)) return 0;

      const clickTarget = collapsedCaret.closest('button,[role="button"],[aria-expanded]') || header;
      clickTarget.scrollIntoView({ block: 'center', inline: 'nearest' });
      clickTarget.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
      clickTarget.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
      clickTarget.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
      return 1;
    }
    """
    expanded_count = page.evaluate(script)
    try:
        page.wait_for_timeout(500)
    except Exception:
        pass
    return int(expanded_count or 0)


def expand_collapsed_customization_sections(page) -> int:
    """Expand visible collapsed sections before reading customization text."""

    script = """
    (selector) => {
      const well = document.querySelector(selector);
      if (!well) return 0;

      const isVisible = (element) => {
        if (!element) return false;
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.visibility !== 'hidden'
          && style.display !== 'none'
          && rect.width > 0
          && rect.height > 0;
      };

      const collapsedPath = 'M246.6 278.6c12.5-12.5 12.5-32.8 0-45.3l-128-128c-9.2-9.2-22.9-11.9-34.9-6.9s-19.8 16.6-19.8 29.6l0 256c0 12.9 7.8 24.6 19.8 29.6s25.7 2.2 34.9-6.9l128-128z';
      const candidates = new Set();

      const addCandidateChain = (element) => {
        if (!element || !isVisible(element)) return;
        const svg = element.closest('svg');
        if (svg && isVisible(svg)) candidates.add(svg);
        const explicit = element.closest('button,[role="button"],[aria-expanded="false"]');
        if (explicit && isVisible(explicit)) candidates.add(explicit);

        let current = element.parentElement;
        for (let depth = 0; current && depth < 8; depth += 1) {
          if (well.contains(current) && isVisible(current)) {
            const style = window.getComputedStyle(current);
            const hasClickHint = style.cursor === 'pointer'
              || current.hasAttribute('onclick')
              || current.getAttribute('role') === 'button'
              || current.hasAttribute('aria-expanded');
            if (hasClickHint) candidates.add(current);
          }
          current = current.parentElement;
        }
      };

      for (const path of Array.from(well.querySelectorAll('path'))) {
        const d = (path.getAttribute('d') || '').trim();
        if (d !== collapsedPath || !isVisible(path)) continue;
        addCandidateChain(path);
      }

      for (const svg of Array.from(well.querySelectorAll('svg[data-icon="caret-right"], svg.fa-caret-right'))) {
        addCandidateChain(svg);
      }

      for (const button of Array.from(well.querySelectorAll('button[aria-expanded="false"],[role="button"][aria-expanded="false"],[aria-expanded="false"]'))) {
        if (isVisible(button)) candidates.add(button);
      }

      let clicked = 0;
      for (const candidate of candidates) {
        try {
          candidate.scrollIntoView({ block: 'center', inline: 'nearest' });
          candidate.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
          candidate.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
          candidate.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
          clicked += 1;
        } catch (_error) {}
      }
      return clicked;
    }
    """
    expanded_count = page.evaluate(script, CUSTOMIZATION_WELL_SELECTOR)
    try:
        page.wait_for_timeout(500)
    except Exception:
        pass
    return int(expanded_count or 0)


SETTING_LABELS = {
    "last_minute": "Last Minute",
    "orphan_day_prices": "Orphan Day Prices",
    "booking_recency_factor": "Booking Recency Factor",
    "minimum_stay_settings": "Minimum Stay Settings",
    "extra_person_fee": "Extra Person Fee",
    "occupancy_based_adjustments": "Occupancy Based Adjustments",
    "custom_seasonality_factor": "Custom Seasonality Factor",
    "length_of_stay_based_pricing": "Length-of-stay Based Pricing",
    "demand_factor_sensitivity": "Demand Factor Sensitivity",
    "far_out_premium": "Far Out Premium",
    "safety_minimum_price": "Safety Minimum Price",
}

SETTING_VALUE_SELECTORS = {
    "minimum_stay_settings": "#customization-text-min_stay",
    "safety_minimum_price": "#customization-text-safety_minimum",
}

SETTING_DETAIL_STATUS = {
    "length_of_stay_based_pricing": "not_captured",
    "occupancy_based_adjustments": "not_captured",
}

SETTING_DETAIL_KEYS = tuple(SETTING_DETAIL_STATUS.keys())


def extract_settings_from_customization_well(page) -> dict[str, dict[str, object]]:
    script = """
    ({ selector, labels, valueSelectors, detailStatus }) => {
      const normalizeText = (value) => (value || '').replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n');
      const normalizeLine = (value) => (value || '').replace(/\\s+/g, ' ').trim();
      const valueLines = (value) => normalizeText(value)
        .split('\\n')
        .map((line) => normalizeLine(line))
        .filter(Boolean);
      const singleLine = (value) => valueLines(value).join(' ');
      const well = document.querySelector(selector);
      if (!well) return {};

      const labelValues = Object.values(labels);
      const allLines = valueLines(well.innerText);
      const findFallbackLines = (label) => {
        const start = allLines.findIndex((line) => line === label || line.startsWith(label + ' '));
        if (start < 0) return [];
        const firstLine = allLines[start] === label ? '' : allLines[start].slice(label.length).trim();
        const lines = firstLine ? [firstLine] : [];
        for (let index = start + 1; index < allLines.length; index += 1) {
          const line = allLines[index];
          if (labelValues.some((candidate) => line === candidate || line.startsWith(candidate + ' '))) break;
          lines.push(line);
        }
        return lines.filter(Boolean);
      };

      const result = {};
      for (const [key, label] of Object.entries(labels)) {
        let lines = [];
        const directSelector = valueSelectors[key];
        if (directSelector) {
          const directElement = well.querySelector(directSelector);
          if (directElement) {
            lines = valueLines(directElement.innerText);
          }
        }
        if (lines.length === 0) {
          const labelNode = Array.from(well.querySelectorAll('[qa-id$="-label"], p, span, div'))
            .find((node) => normalizeLine(node.innerText) === label);
          const block = labelNode ? labelNode.closest('[qa-id], .chakra-stack, .chakra-card, div') : null;
          const text = block ? block.innerText : '';
          const blockLines = valueLines(text).filter((line) => line !== label);
          if (blockLines.length > 0 && blockLines.some((line) => line !== label)) {
            lines = blockLines;
          }
        }
        if (lines.length === 0) {
          lines = findFallbackLines(label);
        }
        const valueText = lines.join(' ');
        result[key] = {
          label,
          value: valueText,
          value_text: valueText,
          value_lines: lines,
        };
        if (detailStatus[key]) {
          result[key].detail_capture_status = detailStatus[key];
        }
      }
      return result;
    }
    """
    extracted = page.evaluate(
        script,
        {
            "selector": CUSTOMIZATION_WELL_SELECTOR,
            "labels": SETTING_LABELS,
            "valueSelectors": SETTING_VALUE_SELECTORS,
            "detailStatus": SETTING_DETAIL_STATUS,
        },
    )
    if not isinstance(extracted, dict):
        raise DownloadError("Customization well settings parser returned an unexpected shape.")
    settings = {}
    for key, label in SETTING_LABELS.items():
        setting = extracted.get(key, {})
        if not isinstance(setting, dict):
            setting = {}
        value_lines = setting.get("value_lines")
        if not isinstance(value_lines, list):
            value_lines = []
        cleaned_lines = [str(line).strip() for line in value_lines if str(line).strip()]
        value_text = str(setting.get("value_text") or setting.get("value") or " ".join(cleaned_lines)).strip()
        result = {
            "label": str(setting.get("label") or label).strip(),
            "value": value_text,
            "value_text": value_text,
            "value_lines": cleaned_lines,
        }
        detail_status = setting.get("detail_capture_status")
        if isinstance(detail_status, str) and detail_status.strip():
            result["detail_capture_status"] = detail_status.strip()
        settings[key] = result
    return settings


def capture_settings_popover_details(page, settings: dict[str, dict[str, object]]) -> None:
    """Best-effort capture for setting popovers without failing the snapshot."""

    script = """
    async ({ selector, labels, keys }) => {
      const normalizeText = (value) => (value || '').replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n');
      const normalizeLine = (value) => (value || '').replace(/\\s+/g, ' ').trim();
      const linesFromText = (value) => normalizeText(value)
        .split('\\n')
        .map((line) => normalizeLine(line))
        .filter(Boolean);
      const isVisible = (element) => {
        if (!element) return false;
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.visibility !== 'hidden'
          && style.display !== 'none'
          && rect.width > 0
          && rect.height > 0;
      };
      const hoverElement = (element) => {
        element.scrollIntoView({ block: 'center', inline: 'nearest' });
        const rect = element.getBoundingClientRect();
        const x = rect.left + Math.max(1, rect.width / 2);
        const y = rect.top + Math.max(1, rect.height / 2);
        for (const eventType of ['pointerover', 'pointerenter', 'mouseover', 'mouseenter', 'mousemove']) {
          element.dispatchEvent(new MouseEvent(eventType, {
            bubbles: true,
            cancelable: true,
            view: window,
            clientX: x,
            clientY: y,
          }));
        }
      };
      const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
      const well = document.querySelector(selector);
      const result = {};
      if (!well) return result;

      const visiblePopoverTexts = () => Array.from(document.querySelectorAll(
        '[role="dialog"], .chakra-popover__content, [data-popper-placement], [id^="popover-content-"]'
      ))
        .filter((node) => isVisible(node) && !well.contains(node))
        .map((node) => linesFromText(node.innerText))
        .filter((lines) => lines.length > 0);

      for (const key of keys) {
        const label = labels[key];
        result[key] = { detail_capture_status: 'not_captured' };
        try {
          const labelNode = Array.from(well.querySelectorAll('[qa-id$="-label"], p, span, div'))
            .find((node) => normalizeLine(node.innerText) === label);
          if (!labelNode) continue;

          const candidateBlocks = [];
          let current = labelNode;
          for (let depth = 0; current && depth < 8; depth += 1) {
            if (well.contains(current)) candidateBlocks.push(current);
            current = current.parentElement;
          }

          let trigger = null;
          for (const block of candidateBlocks) {
            trigger = Array.from(block.querySelectorAll(
              '[aria-haspopup="dialog"], [aria-controls], [id^="popover-trigger-"], [class*="customization-popover-trigger"]'
            )).find((node) => isVisible(node) && normalizeLine(node.innerText) !== label);
            if (trigger) break;
          }
          if (!trigger) continue;

          const before = visiblePopoverTexts().map((lines) => lines.join(' '));
          hoverElement(trigger);
          await wait(1000);

          const controlledId = trigger.getAttribute('aria-controls');
          const controlledPopover = controlledId ? document.getElementById(controlledId) : null;
          const controlledLines = isVisible(controlledPopover) ? linesFromText(controlledPopover.innerText) : [];
          const candidates = (controlledLines.length > 0 ? [controlledLines] : visiblePopoverTexts())
            .filter((lines) => !before.includes(lines.join(' ')))
            .sort((left, right) => right.join(' ').length - left.join(' ').length);
          const detailLines = candidates[0] || [];
          if (detailLines.length === 0) continue;

          result[key] = {
            detail_capture_status: 'captured',
            detail_text: detailLines.join(' '),
            detail_lines: detailLines,
          };
          document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
          await wait(100);
        } catch (_error) {
          result[key] = { detail_capture_status: 'not_captured' };
        }
      }
      return result;
    }
    """
    try:
        captured = page.evaluate(
            script,
            {
                "selector": CUSTOMIZATION_WELL_SELECTOR,
                "labels": SETTING_LABELS,
                "keys": list(SETTING_DETAIL_KEYS),
            },
        )
    except Exception:
        captured = {}

    if not isinstance(captured, dict):
        captured = {}

    for key in SETTING_DETAIL_KEYS:
        setting = settings.setdefault(key, {})
        detail = captured.get(key, {})
        if not isinstance(detail, dict):
            detail = {}
        detail_status = str(detail.get("detail_capture_status") or "not_captured").strip() or "not_captured"
        detail_lines = detail.get("detail_lines")
        if not isinstance(detail_lines, list):
            detail_lines = []
        cleaned_lines = [str(line).strip() for line in detail_lines if str(line).strip()]
        detail_text = str(detail.get("detail_text") or " ".join(cleaned_lines)).strip()
        if detail_status == "captured" and detail_text:
            setting["detail_capture_status"] = "captured"
            setting["detail_text"] = detail_text
            setting["detail_lines"] = cleaned_lines or [detail_text]
        else:
            setting["detail_capture_status"] = "not_captured"


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
    settings_count: int | None = None,
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
    if settings_count is not None:
        lines.append(f"settings_count={settings_count}")
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


def run_settings_snapshot_capture(
    run_date: str,
    *,
    headless: bool,
    skip_login_pause: bool = False,
) -> Path:
    _, staging_dir, logs_dir, log_file = get_run_paths(run_date)
    staging_path = staging_dir / SETTINGS_SNAPSHOT_FILENAME

    try:
        settings_count = capture_settings_snapshot_with_playwright(
            staging_path,
            logs_dir=logs_dir,
            run_date=run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
        )
        validate_settings_snapshot_json(staging_path)
    except DownloadError as exc:
        write_log(
            log_file,
            real_download_log_lines(
                run_date=run_date,
                target=SETTINGS_SNAPSHOT_TARGET,
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
            target=SETTINGS_SNAPSHOT_TARGET,
            staging_path=staging_path,
            status="passed",
            settings_count=settings_count,
        )
        + ["Settings snapshot captured and validated in staging.", "Raw folder was not touched."],
    )
    return log_file


DOWNLOAD_ALL_TARGETS = (
    FUTURE_EXPORT_TARGET,
    PRICE_OCC_TARGET,
    MONTHLY_TRENDS_TARGET,
    SETTINGS_SNAPSHOT_TARGET,
    BOOKINGS_REPORT_TARGET,
)


def download_all_log_lines(
    *,
    run_date: str,
    staging_dir: Path,
    status: str,
    completed_targets: Sequence[str],
    raw_touched: bool = False,
    reason: str | None = None,
) -> list[str]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"PriceLabs download-all started at {timestamp}",
        f"run_date={run_date}",
        "download_all_started=true",
        "mode=one-session download-all",
        f"downloads_staging={staging_dir}",
        f"raw_touched={str(raw_touched).lower()}",
        f"download_all_status={status}",
        "target_sequence:",
    ]
    lines.extend(f"- {target}" for target in DOWNLOAD_ALL_TARGETS)
    lines.append("completed_targets:")
    lines.extend(f"- {target}" for target in completed_targets)
    if reason:
        lines.append(f"failure_reason={reason}")
    return lines


def execute_download_all_sequence(context, page, staging_dir: Path, run_date: str) -> list[str]:
    completed_targets: list[str] = []

    future_export_path = staging_dir / FUTURE_EXPORT_FILENAME
    download_future_export_in_session(page, future_export_path)
    validate_future_export_csv(future_export_path)
    completed_targets.append(FUTURE_EXPORT_TARGET)

    price_occ_path = staging_dir / PRICE_OCC_FILENAME
    download_price_occ_in_session(page, price_occ_path)
    validate_price_occ_csv(price_occ_path)
    completed_targets.append(PRICE_OCC_TARGET)

    monthly_trends_path = staging_dir / MONTHLY_TRENDS_FILENAME
    download_monthly_trends_in_session(page, monthly_trends_path)
    validate_monthly_trends_csv(monthly_trends_path)
    completed_targets.append(MONTHLY_TRENDS_TARGET)

    settings_path = staging_dir / SETTINGS_SNAPSHOT_FILENAME
    capture_settings_snapshot_in_session(page, settings_path, run_date=run_date)
    validate_settings_snapshot_json(settings_path)
    completed_targets.append(SETTINGS_SNAPSHOT_TARGET)

    bookings_report_path = staging_dir / BOOKINGS_REPORT_FILENAME
    download_bookings_report_in_session(context, page, bookings_report_path)
    validate_bookings_report_xlsx(bookings_report_path)
    completed_targets.append(BOOKINGS_REPORT_TARGET)
    return_to_primary_page(page)

    return completed_targets


def launch_download_all_browser(playwright, *, headless: bool, use_persistent_session: bool):
    """Launch the download-all browser context.

    Persistent mode must use Playwright's persistent context directly so cookies,
    local storage, and session state survive across runs.
    """

    browser = None
    if use_persistent_session:
        PERSISTENT_SESSION_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PERSISTENT_SESSION_PROFILE_DIR),
            headless=headless,
            accept_downloads=True,
        )
        page = context.pages[0] if context.pages else context.new_page()
        return context, browser, page

    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    return context, browser, page


def run_download_all(
    run_date: str,
    *,
    headless: bool,
    skip_login_pause: bool = False,
    use_persistent_session: bool = False,
    use_local_credentials: bool = False,
) -> Path:
    if headless and not use_local_credentials:
        raise DownloadError("Headless mode requires --use-local-credentials for download-all.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    _, staging_dir, logs_dir, log_file = get_run_paths(run_date)
    completed_targets: list[str] = []

    try:
        with sync_playwright() as playwright:
            context, browser, page = launch_download_all_browser(
                playwright,
                headless=headless,
                use_persistent_session=use_persistent_session,
            )
            try:
                page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
                wait_for_download_all_login_ready(
                    page,
                    skip_login_pause=skip_login_pause,
                    use_local_credentials=use_local_credentials,
                    headless=headless,
                )
                completed_targets = execute_download_all_sequence(context, page, staging_dir, run_date)
            except DownloadError as exc:
                screenshot_path = save_debug_screenshot(page, logs_dir, run_date)
                raise DownloadError(f"{exc} Debug screenshot saved to {screenshot_path}") from exc
            finally:
                context.close()
                if browser is not None:
                    browser.close()
    except DownloadError as exc:
        write_log(
            log_file,
            download_all_log_lines(
                run_date=run_date,
                staging_dir=staging_dir,
                status="failed",
                completed_targets=completed_targets,
                raw_touched=False,
                reason=str(exc),
            ),
        )
        raise

    write_log(
        log_file,
        download_all_log_lines(
            run_date=run_date,
            staging_dir=staging_dir,
            status="passed",
            completed_targets=completed_targets,
            raw_touched=False,
        )
        + ["All download-all staged files validated.", "Raw folder was not touched."],
    )
    return log_file


def run_auth_check(*, headless: bool, use_persistent_session: bool = False) -> Path:
    if not use_persistent_session:
        raise DownloadError("--auth-check requires --use-persistent-session so it can inspect the reusable profile.")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise DownloadError("Playwright is not installed in this environment.") from exc

    profile_exists = PERSISTENT_SESSION_PROFILE_DIR.exists()
    auth_status = "unknown"
    with sync_playwright() as playwright:
        context, browser, page = launch_download_all_browser(
            playwright,
            headless=headless,
            use_persistent_session=True,
        )
        try:
            page.goto(PRICELABS_BOOKING_INSIGHTS_URL, wait_until="domcontentloaded", timeout=120_000)
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:
                pass
            auth_status = classify_auth_status(page)
        finally:
            context.close()
            if browser is not None:
                browser.close()

    for line in auth_check_log_lines(
        profile_path=PERSISTENT_SESSION_PROFILE_DIR,
        profile_exists=profile_exists,
        auth_status=auth_status,
    ):
        print(line)
    return PERSISTENT_SESSION_PROFILE_DIR


PROMOTION_FILES = (
    (FUTURE_EXPORT_FILENAME, validate_future_export_csv),
    (PRICE_OCC_FILENAME, validate_price_occ_csv),
    (MONTHLY_TRENDS_FILENAME, validate_monthly_trends_csv),
    (BOOKINGS_REPORT_FILENAME, validate_bookings_report_xlsx),
    (SETTINGS_SNAPSHOT_FILENAME, validate_settings_snapshot_json),
)


def promotion_log_lines(
    *,
    run_date: str,
    staging_dir: Path,
    raw_dir: Path,
    status: str,
    checked_files: Sequence[str],
    raw_targets: Sequence[Path],
    raw_touched: bool,
    reason: str | None = None,
) -> list[str]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"PriceLabs downloader promotion started at {timestamp}",
        f"run_date={run_date}",
        "promotion_started=true",
        f"downloads_staging={staging_dir}",
        f"raw_dir={raw_dir}",
        f"promotion_status={status}",
        f"raw_touched={str(raw_touched).lower()}",
        "staged_files_checked:",
    ]
    lines.extend(f"- {filename}: validation_checked" for filename in checked_files)
    lines.append("raw_target_paths:")
    lines.extend(f"- {path}" for path in raw_targets)
    if reason:
        lines.append(f"failure_reason={reason}")
    return lines


def run_promote_to_raw(run_date: str) -> Path:
    run_dir, staging_dir, _, log_file = get_run_paths(run_date)
    raw_dir = run_dir / "raw"
    temp_dir = run_dir / "raw_promotion_tmp"
    staged_paths = [(filename, staging_dir / filename, raw_dir / filename, validator) for filename, validator in PROMOTION_FILES]
    checked_files = [filename for filename, _staged, _raw, _validator in staged_paths]
    raw_targets = [raw_path for _filename, _staged, raw_path, _validator in staged_paths]

    try:
        missing = [str(staged_path) for _filename, staged_path, _raw_path, _validator in staged_paths if not staged_path.exists()]
        if missing:
            raise DownloadError("Missing staged files for promotion: " + ", ".join(missing))

        for filename, staged_path, _raw_path, validator in staged_paths:
            try:
                validator(staged_path)
            except DownloadError as exc:
                raise DownloadError(f"Staged file failed validation before promotion: {filename}: {exc}") from exc

        existing_raw = [str(raw_path) for _filename, _staged_path, raw_path, _validator in staged_paths if raw_path.exists()]
        if existing_raw:
            raise DownloadError("Raw target already exists; refusing to overwrite: " + ", ".join(existing_raw))

        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=False)

        for filename, staged_path, _raw_path, _validator in staged_paths:
            shutil.copy2(staged_path, temp_dir / filename)

        raw_dir.mkdir(parents=True, exist_ok=True)
        created_targets: list[Path] = []
        try:
            for filename, _staged_path, raw_path, _validator in staged_paths:
                shutil.move(str(temp_dir / filename), raw_path)
                created_targets.append(raw_path)
        except Exception:
            for created_target in created_targets:
                if created_target.exists():
                    created_target.unlink()
            raise
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
    except Exception as exc:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        reason = str(exc)
        write_log(
            log_file,
            promotion_log_lines(
                run_date=run_date,
                staging_dir=staging_dir,
                raw_dir=raw_dir,
                status="failed",
                checked_files=checked_files,
                raw_targets=raw_targets,
                raw_touched=False,
                reason=reason,
            ),
        )
        if isinstance(exc, DownloadError):
            raise
        raise DownloadError(f"Promotion to raw failed: {reason}") from exc

    write_log(
        log_file,
        promotion_log_lines(
            run_date=run_date,
            staging_dir=staging_dir,
            raw_dir=raw_dir,
            status="passed",
            checked_files=checked_files,
            raw_targets=raw_targets,
            raw_touched=True,
        )
        + ["Validated staged files promoted to raw.", "Existing raw files were protected from overwrite."],
    )
    return log_file


def run(
    run_date: str | None,
    *,
    target: str | None = None,
    dry_run: bool = False,
    headless: bool = False,
    skip_login_pause: bool = False,
    promote_to_raw: bool = False,
    download_all: bool = False,
    use_persistent_session: bool = False,
    auth_check: bool = False,
    use_local_credentials: bool = False,
) -> Path:
    if auth_check:
        return run_auth_check(headless=headless, use_persistent_session=use_persistent_session)
    if run_date is None:
        raise DownloadError("--run-date is required for this downloader mode.")
    if download_all:
        log_file = run_download_all(
            run_date,
            headless=headless,
            skip_login_pause=skip_login_pause,
            use_persistent_session=use_persistent_session,
            use_local_credentials=use_local_credentials,
        )
        if promote_to_raw:
            return run_promote_to_raw(run_date)
        return log_file
    if promote_to_raw:
        return run_promote_to_raw(run_date)
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
    if target == SETTINGS_SNAPSHOT_TARGET:
        return run_settings_snapshot_capture(
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
            promote_to_raw=args.promote_to_raw,
            download_all=args.download_all,
            use_persistent_session=args.use_persistent_session,
            auth_check=args.auth_check,
            use_local_credentials=args.use_local_credentials,
        )
    except DownloadError as exc:
        print(f"PriceLabs downloader failed: {exc}", file=sys.stderr)
        return 1

    if args.auth_check:
        print("PriceLabs persistent auth check completed.")
    elif args.download_all and args.promote_to_raw:
        print(f"PriceLabs downloader completed download-all and promoted staged files to raw. Log: {log_file}")
    elif args.download_all:
        print(f"PriceLabs downloader completed download-all. Log: {log_file}")
    elif args.promote_to_raw:
        print(f"PriceLabs downloader promoted staged files to raw. Log: {log_file}")
    elif args.target and not args.dry_run:
        print(f"PriceLabs downloader completed for {args.target}. Log: {log_file}")
    else:
        print(f"PriceLabs downloader skeleton completed. Log: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
