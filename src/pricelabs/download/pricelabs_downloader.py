"""PriceLabs downloader entry point.

Default behavior is still skeleton/dry-run mode: create staging/log folders only.
Real download mode is deliberately explicit and currently supports only the
future export target.
"""

from __future__ import annotations

import argparse
import csv
import os
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
FUTURE_EXPORT_TARGET = "future-export"
PRICELABS_FUTURE_EXPORT_URL_ENV = "PRICELABS_FUTURE_EXPORT_URL"


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
        choices=[FUTURE_EXPORT_TARGET],
        help="Explicit real download target. Currently only future-export is supported.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless in real download mode. Default is headed for manual login/MFA.",
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


def download_future_export_with_playwright(staging_path: Path, *, headless: bool) -> None:
    download_url = os.environ.get(PRICELABS_FUTURE_EXPORT_URL_ENV)
    if not download_url:
        raise DownloadError(
            f"{PRICELABS_FUTURE_EXPORT_URL_ENV} is required for future-export download mode."
        )

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
            with page.expect_download(timeout=120_000) as download_info:
                page.goto(download_url, wait_until="domcontentloaded", timeout=120_000)
            download = download_info.value
            download.save_as(temp_download_path)
        finally:
            context.close()
            browser.close()

    shutil.move(str(temp_download_path), staging_path)


def real_download_log_lines(
    *,
    run_date: str,
    target: str,
    staging_path: Path,
    status: str,
    reason: str | None = None,
) -> list[str]:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"PriceLabs downloader started at {timestamp}",
        f"run_date={run_date}",
        f"target={target}",
        "mode=real download",
        f"staging_path={staging_path}",
        "raw_touched=false",
        f"validation_status={status}",
    ]
    if reason:
        lines.append(f"failure_reason={reason}")
    return lines


def run_future_export_download(run_date: str, *, headless: bool) -> Path:
    _, staging_dir, _, log_file = get_run_paths(run_date)
    staging_path = staging_dir / FUTURE_EXPORT_FILENAME

    try:
        download_future_export_with_playwright(staging_path, headless=headless)
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
        )
        + ["Future export downloaded and validated in staging.", "Raw folder was not touched."],
    )
    return log_file


def run(run_date: str, *, target: str | None = None, dry_run: bool = False, headless: bool = False) -> Path:
    if dry_run or target is None:
        return run_skeleton(run_date)
    if target == FUTURE_EXPORT_TARGET:
        return run_future_export_download(run_date, headless=headless)
    raise DownloadError(f"Unsupported download target: {target}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        log_file = run(
            args.run_date,
            target=args.target,
            dry_run=args.dry_run,
            headless=args.headless,
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
