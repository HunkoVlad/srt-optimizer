"""Run the optional Airbnb diagnostic parser chain for a weekly run."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from airbnb import (
    compare_daily_to_weekly_avg,
    compare_similar_listings,
    compare_weekly_history,
    extract_daily_wow,
    parse_conversion_html,
    report_conversion,
    summarize_conversion,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run optional Airbnb diagnostic parsing and analysis.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    return parser.parse_args(argv)


def overtime_raw_files(run_dir: Path) -> list[Path]:
    return [run_dir / "raw" / filename for filename, _metric_page in parse_conversion_html.INPUT_SOURCES]


def similar_raw_files(run_dir: Path) -> list[Path]:
    return [run_dir / "raw" / filename for filename, _metric_page, _metric_name in compare_similar_listings.INPUT_SOURCES]


def parsed_conversion_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "raw" / f"airbnb_daily_conversion_parsed_{run_date}.csv"


def has_any_existing(paths: list[Path]) -> bool:
    return any(path.exists() for path in paths)


def run(run_date: str, *, run_dir: Path | None = None) -> list[Path]:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    outputs: list[Path] = []

    parsed_path = parsed_conversion_path(resolved_run_dir, run_date)
    if has_any_existing(overtime_raw_files(resolved_run_dir)):
        outputs.append(parse_conversion_html.run(run_date, run_dir=resolved_run_dir))

    if parsed_path.exists():
        outputs.append(summarize_conversion.run(run_date, run_dir=resolved_run_dir))
        outputs.append(extract_daily_wow.run(run_date, run_dir=resolved_run_dir))
        outputs.append(compare_daily_to_weekly_avg.run(run_date, run_dir=resolved_run_dir))
        outputs.append(compare_weekly_history.run(run_date, runs_dir=resolved_run_dir.parent))

    if has_any_existing(similar_raw_files(resolved_run_dir)):
        summary_path, daily_path = compare_similar_listings.run(run_date, run_dir=resolved_run_dir)
        outputs.extend([summary_path, daily_path])

    weekly_summary = resolved_run_dir / "analysis" / f"airbnb_weekly_conversion_summary_{run_date}.csv"
    if weekly_summary.exists():
        outputs.append(report_conversion.run(run_date, run_dir=resolved_run_dir))

    return outputs


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    outputs = run(args.run_date, run_dir=Path(args.run_dir) if args.run_dir else None)
    if outputs:
        print("Airbnb diagnostics outputs:")
        for output in outputs:
            print(f"- {output}")
    else:
        print("No Airbnb diagnostic raw HTML or parsed CSV inputs found; nothing to run.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
