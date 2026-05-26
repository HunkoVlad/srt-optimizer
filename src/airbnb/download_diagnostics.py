"""Skeleton for future Airbnb diagnostic downloads.

This module prepares or validates the Airbnb diagnostics staging folder only.
It does not open a browser, log in, download pages, or promote files to raw.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


EXPECTED_FILES = [
    "airbnb_booking_conversion_daily.html",
    "airbnb_page_views_daily.html",
    "airbnb_wishlist_additions_daily.html",
    "airbnb_booking_conversion_similar.html",
    "airbnb_page_views_similar.html",
    "airbnb_wishlist_additions_similar.html",
]

SUPPORTED_MODES = {"dry-run", "validate-staged", "promote-staged", "cleanup-staging", "capture-headed", "capture-headed-and-validate"}

AIRBNB_CONVERSION_URL = "https://www.airbnb.com/performance/conversion/conversion_rate"
AIRBNB_LOGIN_START_URL = "https://www.airbnb.com/performance/occupancy/occupancy_rate"
AIRBNB_CONVERSION_PATH = "/performance/conversion/conversion_rate"
AIRBNB_VALID_CONVERSION_PATHS = (
    "/performance/conversion/conversion_rate",
    "/performance/conversion/p3_impressions",
    "/performance/conversion/wishlist",
)
AIRBNB_PERFORMANCE_PATH = "/performance"
CONVERSION_LINK_SELECTOR = 'a[href="/performance/conversion/conversion_rate"]'
DATE_RANGE_SELECTOR = 'div[data-testid="dsSelector"]'
START_DATE_INPUT_SELECTOR = "input#startDateString"
END_DATE_INPUT_SELECTOR = "input#endDateString"
DATE_RANGE_APPLY_SELECTOR = 'button[data-testid="dsDropdownApply"]'
COMPARE_SELECTOR = 'select[name="chart-compare"][aria-label="Compare"]'


@dataclass(frozen=True)
class CaptureTarget:
    filename: str
    metric_name: str
    metric_link_name: str
    expected_metric_text: str
    report_mode: str
    compare_value: str
    prompt: str


CAPTURE_TARGETS = [
    CaptureTarget(
        "airbnb_booking_conversion_daily.html",
        "Booking conversion",
        "Booking conversion",
        "Booking conversion",
        "over_time",
        "YOY",
        "Open Booking conversion for Aloha Poconos with the target weekly date range and Over time / previous-week comparison.",
    ),
    CaptureTarget(
        "airbnb_page_views_daily.html",
        "Views",
        "Views",
        "Views",
        "over_time",
        "YOY",
        "Open Page views for Aloha Poconos with the same weekly date range and Over time / previous-week comparison.",
    ),
    CaptureTarget(
        "airbnb_wishlist_additions_daily.html",
        "Wishlist additions",
        "Wishlist additions",
        "Wishlist additions",
        "over_time",
        "YOY",
        "Open Wishlist additions for Aloha Poconos with the same weekly date range and Over time / previous-week comparison.",
    ),
    CaptureTarget(
        "airbnb_booking_conversion_similar.html",
        "Booking conversion",
        "Booking conversion",
        "Booking conversion",
        "similar_listings",
        "MARKET",
        "Switch Booking conversion to Similar listings and confirm actual Your listings / Similar listings values are visible.",
    ),
    CaptureTarget(
        "airbnb_page_views_similar.html",
        "Views",
        "Views",
        "Views",
        "similar_listings",
        "MARKET",
        "Switch Page views to Similar listings and confirm actual Your listings / Similar listings values are visible.",
    ),
    CaptureTarget(
        "airbnb_wishlist_additions_similar.html",
        "Wishlist additions",
        "Wishlist additions",
        "Wishlist additions",
        "similar_listings",
        "MARKET",
        "Switch Wishlist additions to Similar listings and confirm actual Your listings / Similar listings values are visible.",
    ),
]


def calculate_airbnb_reporting_window(run_date: date) -> tuple[date, date]:
    """Return the most recent completed Sunday-to-Sunday Airbnb reporting window."""
    days_since_sunday = (run_date.weekday() + 1) % 7
    window_end = run_date - timedelta(days=days_since_sunday)
    return window_end - timedelta(days=7), window_end


def format_airbnb_date_input(value: date) -> str:
    return value.strftime("%m/%d/%Y")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Airbnb diagnostics download staging.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--mode",
        default="dry-run",
        help="Downloader mode. Supported modes: dry-run, validate-staged, promote-staged, cleanup-staging, capture-headed, capture-headed-and-validate.",
    )
    parser.add_argument(
        "--run-dir",
        help="Optional run directory. Defaults to data/runs/<run-date>.",
    )
    args = parser.parse_args(argv)
    if args.mode not in SUPPORTED_MODES:
        parser.error("unsupported --mode. Supported modes: dry-run, validate-staged, promote-staged, cleanup-staging, capture-headed, capture-headed-and-validate.")
    return args


def staging_dir(run_dir: Path) -> Path:
    return run_dir / "downloads_staging" / "airbnb"


def manifest_path(staging_path: Path, run_date: str) -> Path:
    return staging_path / f"airbnb_download_manifest_{run_date}.json"


def build_manifest(run_date: str, mode: str, staging_path: Path) -> dict[str, object]:
    return {
        "run_date": run_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "status": "dry_run",
        "staging_path": str(staging_path),
        "expected_files": EXPECTED_FILES,
        "downloaded_files": [],
        "missing_files": EXPECTED_FILES,
        "promoted_files": [],
        "notes": [
            "Dry run only. No browser was opened.",
            "No Airbnb pages were downloaded.",
            "No files were promoted to raw.",
            "No cookies, tokens, credentials, browser state, screenshots, or raw HTML were written.",
        ],
    }


def looks_like_html(text: str) -> bool:
    lower = text[:2000].lower()
    return "<html" in lower or "<!doctype html" in lower or ("<body" in lower and "</" in lower)


def looks_like_login_page(text: str) -> bool:
    lower = text.lower()
    login_markers = ("log in", "login", "sign in", "email", "password")
    airbnb_marker = "airbnb" in lower
    return airbnb_marker and "password" in lower and any(marker in lower for marker in login_markers)


def looks_like_error_page(text: str) -> bool:
    lower = text.lower()
    error_patterns = (
        "access denied",
        "forbidden",
        "not authorized",
        "something went wrong",
        "page not found",
        "error 403",
        "error 404",
        "temporarily unavailable",
    )
    return any(pattern in lower for pattern in error_patterns)


def has_strong_performance_indicators(text: str) -> bool:
    lower = text.lower()
    indicators = (
        "booking conversion",
        "page views",
        "wishlist additions",
        "dsselector",
        "chart-compare",
        "performance",
        "similar listings",
        "over time",
        "conversion_rate",
        "/performance/conversion/conversion_rate",
    )
    return "airbnb" in lower and any(indicator in lower for indicator in indicators)


def has_diagnostic_hints(filename: str, text: str) -> bool:
    lower = text.lower()
    if "airbnb" not in lower:
        return False
    if has_strong_performance_indicators(text):
        return True
    common = any(marker in lower for marker in ("performance", "insights", "conversion", "page views", "wishlist", "similar listings"))
    if not common:
        return False
    if "booking_conversion" in filename:
        return "conversion" in lower or "listing-to-booking" in lower or "search-to-listing" in lower
    if "page_views" in filename:
        return "page views" in lower or "first-page search" in lower or "first page search" in lower
    if "wishlist_additions" in filename:
        return "wishlist" in lower
    if "_similar" in filename:
        return "similar listings" in lower and ("your listings" in lower or "your performance" in lower)
    return common


def validate_staged_file(path: Path) -> dict[str, object]:
    entry: dict[str, object] = {
        "filename": path.name,
        "exists": path.exists(),
        "size_bytes": 0,
        "validation_status": "missing",
        "validation_errors": [],
    }
    errors: list[str] = []
    if not path.exists():
        errors.append("file is missing")
        entry["validation_errors"] = errors
        return entry

    size = path.stat().st_size
    entry["size_bytes"] = size
    if size == 0:
        entry["validation_status"] = "empty"
        entry["validation_errors"] = ["file is empty"]
        return entry

    text = path.read_text(encoding="utf-8", errors="ignore")
    if not looks_like_html(text):
        entry["validation_status"] = "not_html"
        entry["validation_errors"] = ["file does not look like HTML"]
        return entry
    collapsed_text = re.sub(r"\s+", " ", text)
    has_performance_content = has_strong_performance_indicators(collapsed_text)
    if looks_like_login_page(text) and not has_performance_content:
        entry["validation_status"] = "login_page"
        entry["validation_errors"] = ["file looks like an Airbnb login page"]
        return entry
    if looks_like_error_page(text):
        entry["validation_status"] = "error_page"
        entry["validation_errors"] = ["file looks like an access denied or error page"]
        return entry
    if not has_diagnostic_hints(path.name, collapsed_text):
        entry["validation_status"] = "unknown_airbnb_content"
        entry["validation_errors"] = ["file does not contain enough Airbnb diagnostic hints"]
        return entry

    entry["validation_status"] = "valid"
    entry["validation_errors"] = []
    return entry


def build_validate_manifest(run_date: str, staging_path: Path) -> dict[str, object]:
    files = [validate_staged_file(staging_path / filename) for filename in EXPECTED_FILES]
    valid_files = [entry["filename"] for entry in files if entry["validation_status"] == "valid"]
    missing_files = [entry["filename"] for entry in files if entry["validation_status"] == "missing"]
    if len(valid_files) == len(EXPECTED_FILES):
        status = "valid_staged"
    elif valid_files:
        status = "partial_staged"
    else:
        status = "invalid_staged"
    return {
        "run_date": run_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "validate-staged",
        "status": status,
        "staging_path": str(staging_path),
        "expected_files": EXPECTED_FILES,
        "downloaded_files": valid_files,
        "missing_files": missing_files,
        "promoted_files": [],
        "files": files,
        "notes": [
            "Validated staged Airbnb diagnostic HTML files only.",
            "No browser was opened.",
            "No files were promoted to raw.",
            "No cookies, tokens, credentials, browser state, screenshots, or raw HTML were copied.",
        ],
    }


def raw_dir(run_dir: Path) -> Path:
    return run_dir / "raw"


def build_promote_manifest(run_date: str, run_dir: Path, staging_path: Path) -> dict[str, object]:
    manifest = build_validate_manifest(run_date, staging_path)
    raw_path = raw_dir(run_dir)
    promoted_files: list[str] = []
    skipped_files: list[dict[str, str]] = []

    valid_entries = [entry for entry in manifest["files"] if entry["validation_status"] == "valid"]
    if valid_entries:
        raw_path.mkdir(parents=True, exist_ok=True)

    for entry in manifest["files"]:
        filename = str(entry["filename"])
        source = staging_path / filename
        target = raw_path / filename
        entry["raw_target_path"] = str(target)
        entry["promotion_status"] = "not_promoted"
        if entry["validation_status"] != "valid":
            skipped_files.append({"filename": filename, "reason": str(entry["validation_status"])})
            entry["promotion_status"] = f"skipped_{entry['validation_status']}"
            continue
        if target.exists():
            skipped_files.append({"filename": filename, "reason": "skipped_existing"})
            entry["promotion_status"] = "skipped_existing"
            continue
        shutil.copy2(source, target)
        promoted_files.append(filename)
        entry["promotion_status"] = "promoted"

    if len(promoted_files) == len(valid_entries) and valid_entries:
        status = "promoted_all_valid"
    elif promoted_files:
        status = "promoted_partial"
    else:
        status = "nothing_promoted"

    manifest.update(
        {
            "mode": "promote-staged",
            "status": status,
            "promoted_files": promoted_files,
            "skipped_files": skipped_files,
            "notes": [
                "Validated staged Airbnb diagnostic HTML files before promotion.",
                "Only files with validation_status=valid were eligible for promotion.",
                "Existing raw files were not overwritten.",
                "No browser was opened.",
                "No cookies, tokens, credentials, browser state, screenshots, or logs were written to raw.",
            ],
        }
    )
    return manifest


def airbnb_diagnostics_succeeded(run_date: str, run_dir: Path) -> bool:
    analysis_dir = run_dir / "analysis"
    diagnostic_outputs = (
        analysis_dir / f"airbnb_weekly_conversion_summary_{run_date}.csv",
        analysis_dir / f"airbnb_conversion_diagnostic_report_{run_date}.md",
        analysis_dir / f"airbnb_weekly_history_comparison_{run_date}.csv",
        analysis_dir / f"airbnb_similar_listing_summary_{run_date}.csv",
    )
    return any(path.exists() for path in diagnostic_outputs)


def build_cleanup_manifest(run_date: str, run_dir: Path, staging_path: Path) -> dict[str, object]:
    existing_manifest_path = manifest_path(staging_path, run_date)
    previous_manifest: dict[str, object] = {}
    if existing_manifest_path.exists():
        try:
            previous_manifest = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous_manifest = {}

    previous_status = str(previous_manifest.get("status", ""))
    promoted_files = [str(filename) for filename in previous_manifest.get("promoted_files", [])]
    promotion_succeeded = previous_status == "promoted_all_valid" and set(promoted_files) == set(EXPECTED_FILES)
    diagnostics_succeeded = airbnb_diagnostics_succeeded(run_date, run_dir)
    deleted_files: list[str] = []
    kept_files: list[dict[str, str]] = []

    if promotion_succeeded and diagnostics_succeeded:
        for filename in EXPECTED_FILES:
            path = staging_path / filename
            if path.exists():
                path.unlink()
                deleted_files.append(filename)
            else:
                kept_files.append({"filename": filename, "reason": "missing"})
        status = "cleanup_complete" if deleted_files else "nothing_to_cleanup"
        notes = [
            "Explicit cleanup-staging mode only.",
            "Prior staged Airbnb HTML promotion was successful.",
            "Airbnb diagnostics output was present.",
            "Deleted only expected staged Airbnb HTML files.",
            "Kept manifest, raw promoted files, and analysis outputs.",
        ]
    else:
        status = "cleanup_skipped"
        reason = "promotion_missing_or_failed" if not promotion_succeeded else "diagnostics_missing_or_failed"
        kept_files = [{"filename": filename, "reason": reason} for filename in EXPECTED_FILES if (staging_path / filename).exists()]
        notes = [
            "Explicit cleanup-staging mode only.",
            "Cleanup skipped because successful promotion and diagnostics output are both required.",
            "No staged HTML files were deleted.",
            "Raw promoted files and analysis outputs were not touched.",
        ]

    return {
        "run_date": run_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "cleanup-staging",
        "status": status,
        "staging_path": str(staging_path),
        "raw_target_path": str(raw_dir(run_dir)),
        "expected_files": EXPECTED_FILES,
        "downloaded_files": [],
        "missing_files": [filename for filename in EXPECTED_FILES if not (staging_path / filename).exists()],
        "promoted_files": promoted_files,
        "previous_manifest_status": previous_status,
        "promotion_succeeded": promotion_succeeded,
        "diagnostics_succeeded": diagnostics_succeeded,
        "deleted_files": deleted_files,
        "kept_files": kept_files,
        "notes": notes,
    }


def launch_headed_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for Airbnb capture modes. Install Playwright before using capture-headed.") from exc

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    page = browser.new_page()
    try:
        page.goto(AIRBNB_LOGIN_START_URL)
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    return playwright, browser, page


def close_headed_browser(playwright, browser) -> None:
    try:
        browser.close()
    finally:
        playwright.stop()


def prompt_user(message: str) -> str:
    return input(message)


def capture_page_html(page, output_path: Path) -> None:
    output_path.write_text(page.content(), encoding="utf-8")


def debug_date_range_pause_enabled() -> bool:
    return os.environ.get("AIRBNB_DEBUG_PAUSE_DATE_RANGE", "").strip().lower() in {"1", "true", "yes"}


def pause_for_date_setting(page, message: str) -> None:
    print(message)
    page.pause()


def write_date_picker_debug_dom(page, output_path: Path) -> str:
    try:
        snippet = page.evaluate(
            """() => {
                const start = document.querySelector('#startDateString');
                const end = document.querySelector('#endDateString');
                const selector = document.querySelector('div[data-testid="dsSelector"]');
                const apply = document.querySelector('button[data-testid="dsDropdownApply"]');
                const root = start?.closest('[role="dialog"]') || start?.closest('form') || start?.parentElement?.parentElement || document.body;
                return [
                    '<!-- Airbnb date picker debug DOM snippet: no cookies/tokens/session storage included by script -->',
                    '<section data-debug="selector">',
                    selector ? selector.outerHTML : '<!-- selector missing -->',
                    '</section>',
                    '<section data-debug="start-input">',
                    start ? start.outerHTML : '<!-- start input missing -->',
                    '</section>',
                    '<section data-debug="end-input">',
                    end ? end.outerHTML : '<!-- end input missing -->',
                    '</section>',
                    '<section data-debug="apply">',
                    apply ? apply.outerHTML : '<!-- apply button missing -->',
                    '</section>',
                    '<section data-debug="date-picker-root">',
                    root ? root.outerHTML : '<!-- root missing -->',
                    '</section>',
                ].join('\\n');
            }"""
        )
        output_path.write_text(str(snippet), encoding="utf-8")
        return str(output_path)
    except Exception as exc:
        output_path.write_text(f"date picker debug DOM dump failed: {exc}\n", encoding="utf-8")
        return str(output_path)


def dump_date_picker_debug_dom(page, staging_path: Path, run_date: str) -> str:
    return write_date_picker_debug_dom(page, staging_path / f"airbnb_date_picker_debug_dom_{run_date}.html")


def wait_for_page_idle(page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass


def current_page_url(page) -> str:
    try:
        return str(page.url)
    except Exception:
        return ""


def is_airbnb_conversion_url(url: str) -> bool:
    return any(path in url for path in AIRBNB_VALID_CONVERSION_PATHS)


def safe_goto(page, target_url: str) -> tuple[bool, str]:
    try:
        page.goto(target_url)
        wait_for_page_idle(page)
        return True, ""
    except Exception as exc:
        error = str(exc)
        if "interrupted by another navigation" in error.lower():
            wait_for_page_idle(page)
            if is_airbnb_conversion_url(current_page_url(page)):
                return True, ""
        return False, error


def wait_for_performance_page_indicator(page) -> bool:
    selectors = [
        COMPARE_SELECTOR,
        DATE_RANGE_SELECTOR,
        'text="Booking conversion"',
        'text="Performance"',
    ]
    for selector in selectors:
        try:
            page.locator(selector).first.wait_for(state="visible", timeout=3000)
            return True
        except Exception:
            continue
    return False


def wait_for_visible(page, selector: str, timeout: int = 5000) -> tuple[bool, str]:
    try:
        page.locator(selector).first.wait_for(state="visible", timeout=timeout)
    except Exception as exc:
        return False, str(exc)
    return True, ""


def wait_for_base_report_controls(page) -> tuple[bool, str]:
    required = [
        DATE_RANGE_SELECTOR,
        COMPARE_SELECTOR,
        'text="Booking conversion"',
    ]
    errors: list[str] = []
    for selector in required:
        ok, error = wait_for_visible(page, selector)
        if not ok:
            errors.append(f"{selector}: {error}")
    return not errors, "; ".join(errors)


def wait_for_report_ready(page) -> tuple[bool, str]:
    wait_for_page_idle(page)
    return wait_for_base_report_controls(page)


def wait_for_compare_value(page, compare_value: str) -> tuple[bool, str]:
    try:
        selected = page.locator(COMPARE_SELECTOR).input_value(timeout=3000)
    except Exception as exc:
        return False, str(exc)
    if selected != compare_value:
        return False, f"compare dropdown value is {selected!r}, expected {compare_value!r}"
    return True, ""


def page_visible_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        try:
            return re.sub(r"\s+", " ", page.content())
        except Exception:
            return ""


def date_selector_visible_text(page) -> str:
    try:
        return page.locator(DATE_RANGE_SELECTOR).inner_text(timeout=3000)
    except Exception:
        return ""


def select_airbnb_metric(page, metric_link_name: str, expected_metric_text: str | None = None) -> tuple[bool, str]:
    try:
        page.get_by_role("link", name=metric_link_name).click(timeout=5000)
        wait_for_page_idle(page)
    except Exception as exc:
        return False, str(exc)
    if expected_metric_text:
        return assert_airbnb_metric_ready(page, expected_metric_text)
    return True, ""


def assert_airbnb_metric_ready(page, expected_metric_text: str) -> tuple[bool, str]:
    if not is_airbnb_conversion_url(current_page_url(page)):
        return False, f"current URL is not Airbnb Performance / Conversion: {current_page_url(page)}"
    return wait_for_visible(page, f'text="{expected_metric_text}"')


def assert_airbnb_date_range_applied(page, start_date: date, end_date: date) -> tuple[bool, str, str]:
    text = date_selector_visible_text(page)
    start_input = format_airbnb_date_input(start_date)
    end_input = format_airbnb_date_input(end_date)
    short_start = start_date.strftime("%b %-d") if sys.platform != "win32" else start_date.strftime("%b %#d")
    short_end = end_date.strftime("%b %-d") if sys.platform != "win32" else end_date.strftime("%b %#d")
    has_start = short_start in text
    has_end = short_end in text
    if has_start and has_end:
        return True, "passed_visible_short_format", ""
    if text:
        return False, "failed_visible_range_mismatch", f"visible date selector text {text!r} does not include {short_start} and {short_end}"
    return False, "failed", f"visible date selector text is unavailable; expected {short_start} and {short_end}"


def select_airbnb_compare_mode(page, compare_value: str) -> tuple[bool, str]:
    try:
        page.get_by_label("Compare").select_option(compare_value, timeout=5000)
        wait_for_page_idle(page)
    except Exception as exc:
        return False, str(exc)
    return True, ""


def assert_airbnb_compare_mode(page, compare_value: str) -> tuple[bool, str]:
    return wait_for_compare_value(page, compare_value)


def assert_airbnb_capture_ready(page, target: CaptureTarget, start_date: date, end_date: date) -> dict[str, object]:
    result: dict[str, object] = {
        "metric_navigation_status": "not_checked",
        "metric_assertion_status": "not_checked",
        "date_range_assertion_status": "not_checked",
        "compare_assertion_status": "not_checked",
        "report_ready_before_capture": False,
        "assertion_error": "",
    }
    errors: list[str] = []
    metric_ok, metric_error = assert_airbnb_metric_ready(page, target.expected_metric_text)
    result["metric_assertion_status"] = "passed" if metric_ok else "failed"
    if not metric_ok:
        errors.append(metric_error)

    date_selector_ok, date_selector_error = wait_for_visible(page, DATE_RANGE_SELECTOR)
    compare_selector_ok, compare_selector_error = wait_for_visible(page, COMPARE_SELECTOR)
    if not date_selector_ok:
        errors.append(date_selector_error)
    if not compare_selector_ok:
        errors.append(compare_selector_error)

    date_ok, date_status, date_error = assert_airbnb_date_range_applied(page, start_date, end_date)
    result["date_range_assertion_status"] = date_status
    if not date_ok:
        errors.append(date_error)

    compare_ok, compare_error = assert_airbnb_compare_mode(page, target.compare_value)
    result["compare_assertion_status"] = "passed" if compare_ok else "failed"
    if not compare_ok:
        errors.append(compare_error)

    result["report_ready_before_capture"] = metric_ok and date_selector_ok and compare_selector_ok and date_ok and compare_ok
    result["assertion_error"] = "; ".join(error for error in errors if error)
    return result


def is_airbnb_performance_page_confirmed(page) -> bool:
    url = current_page_url(page)
    if is_airbnb_conversion_url(url) and wait_for_performance_page_indicator(page):
        return True
    return wait_for_performance_page_indicator(page)


def ensure_airbnb_conversion_page(page) -> tuple[bool, str]:
    url = current_page_url(page)
    if is_airbnb_conversion_url(url):
        wait_for_page_idle(page)
        return True, ""

    if AIRBNB_PERFORMANCE_PATH in url:
        try:
            page.locator(CONVERSION_LINK_SELECTOR).first.click(timeout=3000)
            wait_for_page_idle(page)
            if is_airbnb_conversion_url(current_page_url(page)) or is_airbnb_performance_page_confirmed(page):
                return True, ""
        except Exception:
            pass

    return safe_goto(page, AIRBNB_CONVERSION_URL)


def navigate_to_conversion_page(page) -> None:
    ok, error = ensure_airbnb_conversion_page(page)
    if not ok:
        raise RuntimeError(error or "Could not navigate to Airbnb conversion page.")
    wait_for_page_idle(page)
    try:
        page.locator(CONVERSION_LINK_SELECTOR).first.click(timeout=3000)
        wait_for_page_idle(page)
    except Exception:
        pass


def read_input_value(locator) -> str:
    try:
        return str(locator.input_value(timeout=1000))
    except Exception:
        return ""


def clear_masked_date_input(locator) -> None:
    locator.click(timeout=3000)
    try:
        locator.press("ControlOrMeta+A", timeout=1000)
    except Exception:
        locator.press("Control+A", timeout=1000)
    locator.press("Backspace", timeout=1000)


def set_masked_date_input(locator, value: str) -> tuple[bool, str, str]:
    strategies = (
        ("fill_clear", lambda: locator.fill(value, timeout=3000)),
        ("type_clear", lambda: locator.type(value, timeout=3000)),
        (
            "dom_events",
            lambda: locator.evaluate(
                """(element, value) => {
                    element.value = value;
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                    element.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                value,
            ),
        ),
    )
    for strategy, action in strategies:
        try:
            clear_masked_date_input(locator)
            action()
            current = read_input_value(locator)
            if current == value:
                return True, strategy, current
        except Exception:
            continue
    return False, "failed", read_input_value(locator)


def open_airbnb_date_selector(page) -> None:
    try:
        page.locator(DATE_RANGE_SELECTOR).click(timeout=3000)
    except Exception:
        page.get_by_role("button", name=re.compile("Filters applied")).click(timeout=3000)


def airbnb_date_query_url(current_url: str, start_date: date, end_date: date, anchor_date: date) -> str:
    parts = urlsplit(current_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["ds-start"] = str((start_date - anchor_date).days)
    query["ds-end"] = str((end_date - anchor_date).days)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def apply_airbnb_date_query_fallback(page, start_date: date, end_date: date, anchor_date: date) -> tuple[bool, str]:
    try:
        target_url = airbnb_date_query_url(current_page_url(page), start_date, end_date, anchor_date)
        ok, error = safe_goto(page, target_url)
        if not ok:
            return False, error
        date_ok, _date_status, date_error = assert_airbnb_date_range_applied(page, start_date, end_date)
        if not date_ok:
            return False, date_error
    except Exception as exc:
        return False, str(exc)
    return True, ""


def set_airbnb_reporting_window(page, start_date: date, end_date: date, anchor_date: date, debug_dom_path: Path | None = None) -> dict[str, object]:
    details: dict[str, object] = {
        "date_range_automation_status": "failed",
        "date_range_automation_error": "",
        "date_input_strategy_used": "failed",
        "start_input_value_after_set": "",
        "end_input_value_after_set": "",
        "apply_clicked": False,
        "visible_date_text_after_apply": "",
        "date_query_fallback_url": "",
    }
    start_value = format_airbnb_date_input(start_date)
    end_value = format_airbnb_date_input(end_date)
    try:
        open_airbnb_date_selector(page)
        if debug_dom_path is not None:
            write_date_picker_debug_dom(page, debug_dom_path)
        start_locator = page.get_by_role("textbox", name="START DATE")
        end_locator = page.get_by_role("textbox", name="END DATE")
        start_locator.wait_for(state="visible", timeout=3000)
        end_locator.wait_for(state="visible", timeout=3000)
        start_ok, start_strategy, start_after = set_masked_date_input(start_locator, start_value)
        end_ok, end_strategy, end_after = set_masked_date_input(end_locator, end_value)
        details["start_input_value_after_set"] = start_after
        details["end_input_value_after_set"] = end_after
        details["date_input_strategy_used"] = start_strategy if start_strategy == end_strategy else f"{start_strategy}+{end_strategy}"
        if not start_ok or not end_ok:
            details["date_range_automation_error"] = f"date inputs not confirmed: start={start_after!r}, end={end_after!r}"
            return details
        page.get_by_test_id("dsDropdownApply").click(timeout=3000)
        details["apply_clicked"] = True
        wait_for_page_idle(page)
    except Exception as exc:
        details["date_range_automation_error"] = str(exc)
        return details
    details["visible_date_text_after_apply"] = date_selector_visible_text(page)
    date_asserted, _date_status, date_error = assert_airbnb_date_range_applied(page, start_date, end_date)
    if date_asserted:
        details["date_range_automation_status"] = "applied"
        return details
    fallback_url = airbnb_date_query_url(current_page_url(page), start_date, end_date, anchor_date)
    details["date_query_fallback_url"] = fallback_url
    fallback_ok, fallback_error = apply_airbnb_date_query_fallback(page, start_date, end_date, anchor_date)
    details["visible_date_text_after_apply"] = date_selector_visible_text(page)
    if fallback_ok:
        details["date_range_automation_status"] = "applied_url_query"
        details["date_range_automation_error"] = ""
        return details
    details["date_range_automation_status"] = "failed"
    details["date_range_automation_error"] = f"{date_error}; URL query fallback failed: {fallback_error}"
    return details


def select_compare_mode(page, compare_value: str) -> None:
    page.locator(COMPARE_SELECTOR).select_option(compare_value, timeout=5000)
    wait_for_page_idle(page)


def build_capture_manifest(
    run_date: str,
    mode: str,
    staging_path: Path,
    captured_files: list[str],
    skipped_files: list[dict[str, str]],
    reporting_window_start: date,
    reporting_window_end: date,
    date_range_automation_status: str,
    date_range_automation_error: str,
    date_input_strategy_used: str = "",
    start_input_value_after_set: str = "",
    end_input_value_after_set: str = "",
    apply_clicked: bool = False,
    visible_date_text_after_apply: str = "",
    date_query_fallback_url: str = "",
    report_controls_ready: bool = False,
    capture_results: list[dict[str, object]] | None = None,
    navigation_status: str = "not_attempted",
    navigation_error: str = "",
    performance_page_confirmed: bool = False,
    status_override: str = "",
    validation_manifest: dict[str, object] | None = None,
) -> dict[str, object]:
    status = status_override or ("captured_all" if len(captured_files) == len(CAPTURE_TARGETS) else ("partial_capture" if captured_files else "capture_failed"))
    manifest: dict[str, object] = {
        "run_date": run_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "status": status,
        "staging_path": str(staging_path),
        "conversion_url": AIRBNB_CONVERSION_URL,
        "reporting_window_start": reporting_window_start.isoformat(),
        "reporting_window_end": reporting_window_end.isoformat(),
        "requested_start_date": reporting_window_start.isoformat(),
        "requested_end_date": reporting_window_end.isoformat(),
        "requested_start_date_input": format_airbnb_date_input(reporting_window_start),
        "requested_end_date_input": format_airbnb_date_input(reporting_window_end),
        "navigation_status": navigation_status,
        "performance_page_confirmed": performance_page_confirmed,
        "report_controls_ready": report_controls_ready,
        "date_range_automation_status": date_range_automation_status,
        "date_input_strategy_used": date_input_strategy_used,
        "start_input_value_after_set": start_input_value_after_set,
        "end_input_value_after_set": end_input_value_after_set,
        "apply_clicked": apply_clicked,
        "visible_date_text_after_apply": visible_date_text_after_apply,
        "date_query_fallback_url": date_query_fallback_url,
        "expected_files": EXPECTED_FILES,
        "downloaded_files": captured_files,
        "captured_files": captured_files,
        "missing_files": [target.filename for target in CAPTURE_TARGETS if target.filename not in captured_files],
        "skipped_files": skipped_files,
        "capture_results": capture_results or [],
        "promoted_files": [],
        "notes": [
            "Headed Airbnb capture with automated conversion-page navigation and compare-mode selection.",
            "Date range selection uses Airbnb date inputs and Apply button when available.",
            "No files were promoted to raw.",
            "No screenshots, cookies, tokens, credentials, browser state, HAR files, or unrelated HTML were saved.",
        ],
    }
    if date_range_automation_error:
        manifest["date_range_automation_error"] = date_range_automation_error
        manifest["notes"].append(f"Date range automation status detail: {date_range_automation_error}")
    if navigation_error:
        manifest["navigation_error"] = navigation_error
        manifest["notes"].append(f"Airbnb conversion page navigation failed: {navigation_error}")
    if validation_manifest is not None:
        manifest["validation_summary"] = {
            "status": validation_manifest.get("status", ""),
            "valid_files": validation_manifest.get("downloaded_files", []),
            "missing_files": validation_manifest.get("missing_files", []),
        }
        manifest["files"] = validation_manifest.get("files", [])
    return manifest


def capture_headed(run_date: str, mode: str, staging_path: Path) -> dict[str, object]:
    captured_files: list[str] = []
    skipped_files: list[dict[str, str]] = []
    reporting_window_start, reporting_window_end = calculate_airbnb_reporting_window(datetime.strptime(run_date, "%Y-%m-%d").date())
    date_range_automation_status = "not_attempted"
    date_range_automation_error = ""
    date_input_strategy_used = ""
    start_input_value_after_set = ""
    end_input_value_after_set = ""
    apply_clicked = False
    visible_date_text_after_apply = ""
    date_query_fallback_url = ""
    navigation_status = "not_attempted"
    navigation_error = ""
    performance_page_confirmed = False
    report_controls_ready = False
    capture_results: list[dict[str, object]] = []
    status_override = ""
    playwright = browser = page = None
    try:
        playwright, browser, page = launch_headed_browser()
        prompt_user(
            "Please log in to Airbnb manually in the opened browser. Complete MFA if required. "
            "When you can see the Airbnb performance/insights area for Aloha Poconos, return to this terminal and press Enter."
        )
        navigation_ok, navigation_error = ensure_airbnb_conversion_page(page)
        navigation_status = "ok" if navigation_ok else "failed"
        performance_page_confirmed = navigation_ok and is_airbnb_performance_page_confirmed(page)
        report_controls_ready, report_controls_error = wait_for_base_report_controls(page) if performance_page_confirmed else (False, "")
        if not performance_page_confirmed:
            prompt_user("Please make sure the Airbnb Performance > Conversion page is visible, then press Enter.")
            navigation_ok, navigation_error = ensure_airbnb_conversion_page(page)
            navigation_status = "ok" if navigation_ok else "failed"
            performance_page_confirmed = navigation_ok and is_airbnb_performance_page_confirmed(page)
            report_controls_ready, report_controls_error = wait_for_base_report_controls(page) if performance_page_confirmed else (False, "")
        if performance_page_confirmed and not report_controls_ready:
            prompt_user("Please wait until Airbnb Performance > Conversion controls are visible, then press Enter.")
            report_controls_ready, report_controls_error = wait_for_base_report_controls(page)
        if not performance_page_confirmed:
            status_override = "navigation_failed" if navigation_status == "failed" else "auth_required"
            return build_capture_manifest(
                run_date,
                mode,
                staging_path,
                captured_files,
                skipped_files,
                reporting_window_start,
                reporting_window_end,
                date_range_automation_status,
                date_range_automation_error,
                date_input_strategy_used,
                start_input_value_after_set,
                end_input_value_after_set,
                apply_clicked,
                visible_date_text_after_apply,
                date_query_fallback_url,
                report_controls_ready,
                capture_results,
                navigation_status,
                navigation_error,
                performance_page_confirmed,
                status_override,
            )
        if not report_controls_ready:
            status_override = "report_not_ready"
            skipped_files = [{"filename": target.filename, "reason": "report_controls_not_ready"} for target in CAPTURE_TARGETS]
            capture_results = [
                {
                    "filename": target.filename,
                    "metric_name": target.metric_name,
                    "metric_link_name": target.metric_link_name,
                    "expected_metric_text": target.expected_metric_text,
                    "compare_value": target.compare_value,
                    "requested_start_date": reporting_window_start.isoformat(),
                    "requested_end_date": reporting_window_end.isoformat(),
                    "metric_navigation_status": "not_checked",
                    "metric_assertion_status": "not_checked",
                    "date_range_assertion_status": "not_checked",
                    "compare_assertion_status": "not_checked",
                    "capture_status": "skipped_not_ready",
                    "report_ready_before_capture": False,
                    "final_url": current_page_url(page),
                    "assertion_error": report_controls_error,
                    "capture_error": "",
                }
                for target in CAPTURE_TARGETS
            ]
            return build_capture_manifest(
                run_date,
                mode,
                staging_path,
                captured_files,
                skipped_files,
                reporting_window_start,
                reporting_window_end,
                date_range_automation_status,
                date_range_automation_error,
                date_input_strategy_used,
                start_input_value_after_set,
                end_input_value_after_set,
                apply_clicked,
                visible_date_text_after_apply,
                date_query_fallback_url,
                report_controls_ready,
                capture_results,
                navigation_status,
                navigation_error,
                performance_page_confirmed,
                status_override,
            )
        report_controls_ready, report_controls_error = wait_for_report_ready(page)
        for target in CAPTURE_TARGETS:
            result: dict[str, object] = {
                "filename": target.filename,
                "metric_name": target.metric_name,
                "metric_link_name": target.metric_link_name,
                "expected_metric_text": target.expected_metric_text,
                "compare_value": target.compare_value,
                "requested_start_date": reporting_window_start.isoformat(),
                "requested_end_date": reporting_window_end.isoformat(),
                "metric_navigation_status": "not_checked",
                "metric_assertion_status": "not_checked",
                "date_range_assertion_status": "not_checked",
                "compare_assertion_status": "not_checked",
                "date_range_automation_status": "not_attempted",
                "date_input_strategy_used": "",
                "start_input_value_after_set": "",
                "end_input_value_after_set": "",
                "apply_clicked": False,
                "visible_date_text_after_apply": "",
                "date_query_fallback_url": "",
                "capture_status": "failed",
                "report_ready_before_capture": False,
                "final_url": current_page_url(page),
                "assertion_error": "",
                "capture_error": "",
            }
            try:
                metric_selected, metric_select_error = select_airbnb_metric(page, target.metric_link_name, target.expected_metric_text)
                result["metric_navigation_status"] = "passed" if metric_selected else "failed"
                date_details = set_airbnb_reporting_window(
                    page,
                    reporting_window_start,
                    reporting_window_end,
                    datetime.strptime(run_date, "%Y-%m-%d").date(),
                    staging_path / f"airbnb_date_picker_debug_dom_{run_date}.html" if debug_date_range_pause_enabled() else None,
                )
                date_range_automation_status = str(date_details["date_range_automation_status"])
                date_range_automation_error = str(date_details["date_range_automation_error"])
                date_input_strategy_used = str(date_details["date_input_strategy_used"])
                start_input_value_after_set = str(date_details["start_input_value_after_set"])
                end_input_value_after_set = str(date_details["end_input_value_after_set"])
                apply_clicked = bool(date_details["apply_clicked"])
                visible_date_text_after_apply = str(date_details["visible_date_text_after_apply"])
                date_query_fallback_url = str(date_details["date_query_fallback_url"])
                result["date_range_automation_status"] = date_range_automation_status
                result["date_input_strategy_used"] = date_input_strategy_used
                result["start_input_value_after_set"] = start_input_value_after_set
                result["end_input_value_after_set"] = end_input_value_after_set
                result["apply_clicked"] = apply_clicked
                result["visible_date_text_after_apply"] = visible_date_text_after_apply
                result["date_query_fallback_url"] = date_query_fallback_url
                if date_range_automation_status != "applied" and date_range_automation_status != "applied_url_query":
                    result["date_range_assertion_status"] = "failed_visible_range_mismatch" if apply_clicked else "failed"
                    result["capture_status"] = "skipped_not_ready"
                    result["assertion_error"] = date_range_automation_error
                    result["final_url"] = current_page_url(page)
                    skipped_files.append({"filename": target.filename, "reason": f"date_range_not_applied: {date_range_automation_error}"})
                    capture_results.append(result)
                    continue
                compare_selected, compare_select_error = select_airbnb_compare_mode(page, target.compare_value)
                ready_result = assert_airbnb_capture_ready(page, target, reporting_window_start, reporting_window_end)
                result.update(ready_result)
                if not compare_selected and result["compare_assertion_status"] == "passed":
                    result["compare_assertion_status"] = "failed"
                result["final_url"] = current_page_url(page)
                if not result["report_ready_before_capture"]:
                    error = "; ".join(
                        part
                        for part in [
                            metric_select_error,
                            compare_select_error,
                            str(result.get("assertion_error", "")),
                        ]
                        if part
                    )
                    result["capture_status"] = "skipped_not_ready"
                    result["assertion_error"] = error
                    skipped_files.append({"filename": target.filename, "reason": f"skipped_not_ready: {error}"})
                    capture_results.append(result)
                    continue
                capture_page_html(page, staging_path / target.filename)
                captured_files.append(target.filename)
                result["capture_status"] = "captured"
                capture_results.append(result)
            except Exception as exc:
                result["capture_error"] = str(exc)
                skipped_files.append({"filename": target.filename, "reason": f"capture_failed: {exc}"})
                capture_results.append(result)
                continue
    finally:
        if playwright is not None and browser is not None:
            close_headed_browser(playwright, browser)

    validation_manifest = build_validate_manifest(run_date, staging_path) if mode == "capture-headed-and-validate" else None
    return build_capture_manifest(
        run_date,
        mode,
        staging_path,
        captured_files,
        skipped_files,
        reporting_window_start,
        reporting_window_end,
        date_range_automation_status,
        date_range_automation_error,
        date_input_strategy_used,
        start_input_value_after_set,
        end_input_value_after_set,
        apply_clicked,
        visible_date_text_after_apply,
        date_query_fallback_url,
        report_controls_ready,
        capture_results,
        navigation_status,
        navigation_error,
        performance_page_confirmed,
        status_override,
        validation_manifest,
    )


def write_manifest(manifest: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def run(run_date: str, mode: str = "dry-run", run_dir: Path | None = None) -> Path:
    if mode not in SUPPORTED_MODES:
        raise ValueError("unsupported mode. Supported modes: dry-run, validate-staged, promote-staged, cleanup-staging, capture-headed, capture-headed-and-validate.")
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    resolved_staging_dir = staging_dir(resolved_run_dir)
    resolved_staging_dir.mkdir(parents=True, exist_ok=True)
    resolved_manifest_path = manifest_path(resolved_staging_dir, run_date)
    if mode in {"capture-headed", "capture-headed-and-validate"}:
        manifest = capture_headed(run_date, mode, resolved_staging_dir)
    elif mode == "promote-staged":
        manifest = build_promote_manifest(run_date, resolved_run_dir, resolved_staging_dir)
    elif mode == "cleanup-staging":
        manifest = build_cleanup_manifest(run_date, resolved_run_dir, resolved_staging_dir)
    elif mode == "validate-staged":
        manifest = build_validate_manifest(run_date, resolved_staging_dir)
    else:
        manifest = build_manifest(run_date, mode, resolved_staging_dir)
    write_manifest(manifest, resolved_manifest_path)
    return resolved_manifest_path


def main() -> int:
    args = parse_args()
    output = run(args.run_date, args.mode, Path(args.run_dir) if args.run_dir else None)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
