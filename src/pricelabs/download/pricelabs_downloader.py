"""Skeleton PriceLabs downloader.

This module intentionally does not open a browser, authenticate, or download files.
It only creates the future staging/log structure and records skeleton progress.
"""

from __future__ import annotations

import argparse
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the skeleton folder/log structure for future PriceLabs downloads."
    )
    parser.add_argument(
        "--run-date",
        required=True,
        help="Run date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Skeleton mode. This is currently always dry-run behavior.",
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


def write_log(log_file: Path, run_date: str, staging_dir: Path) -> None:
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
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(run_date: str) -> Path:
    project_root = Path.cwd()
    run_dir = project_root / "data" / "runs" / run_date
    staging_dir = run_dir / "downloads_staging"
    logs_dir = run_dir / "logs"

    staging_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / f"pricelabs_download_{run_date}.log"
    write_log(log_file=log_file, run_date=run_date, staging_dir=staging_dir)
    return log_file


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    log_file = run(args.run_date)
    print(f"PriceLabs downloader skeleton completed. Log: {log_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
