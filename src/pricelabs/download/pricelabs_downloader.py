"""PriceLabs downloader entry point.

Default behavior is still skeleton/dry-run mode: create staging/log folders only.
Real download mode is deliberately explicit. The future export target has a
known UI path; the price/occupancy target has staging validation in place and a
clear UI placeholder until its PriceLabs navigation path is confirmed.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


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
FUTURE_EXPORT_TARGET = "future-export"
PRICE_OCC_TARGET = "price-occ"
SUPPORTED_TARGETS = [FUTURE_EXPORT_TARGET, PRICE_OCC_TARGET]
PRICELABS_CUSTOMIZATION_URL = "https://app.pricelabs.co/customization"
PRICELABS_ACCOUNT_LABEL = "Lodgify"
FUTURE_EXPORT_MENU_ITEM = "Download CSV Prices"
LOGIN_CHECKPOINT_MESSAGE = (
    "Please log in to PriceLabs manually in the opened browser. Complete MFA if required. "
    "When you see the Customizations page, return to this terminal and press Enter."
)


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


def read_csv_header(csv_path: Path) -> list[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(2048)
        if looks_like_html(sample):
            raise DownloadError("Downloaded file looks like an HTML login/error page.")
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
        if looks_like_html(sample):
            raise DownloadError(f"Downloaded {file_label} file looks like an HTML login/error page.")
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


def wait_for_manual_login_checkpoint(*, skip_login_pause: bool) -> None:
    if skip_login_pause:
        return
    print(LOGIN_CHECKPOINT_MESSAGE)
    input()


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

    shutil.move(str(temp_download_path), staging_path)
    return menu_strategy


def download_price_occ_with_playwright(
    staging_path: Path,
    *,
    logs_dir: Path,
    run_date: str,
    headless: bool,
    skip_login_pause: bool = False,
) -> str:
    """Placeholder for the PriceLabs price/occupancy UI flow.

    The staging filename and validator are ready, but the exact UI navigation
    path for this export has not been verified. Fail clearly instead of
    creating a fake staged file or guessing at selectors.
    """

    if headless and not skip_login_pause:
        raise DownloadError("Headless mode requires --skip-login-pause for price-occ downloads.")

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
            page.wait_for_load_state("networkidle", timeout=120_000)
            validate_visible_customization_page(page)
            raise DownloadError(
                "Price Occ UI download path is not implemented yet. "
                "Selector review is required before downloading price_occ.csv."
            )
        finally:
            context.close()
            browser.close()


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
        menu_strategy = download_price_occ_with_playwright(
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
            menu_strategy=menu_strategy,
        )
        + ["Price Occ export downloaded and validated in staging.", "Raw folder was not touched."],
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
