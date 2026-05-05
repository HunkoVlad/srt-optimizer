"""Manual signal labels from future window summaries."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys


REQUIRED_INPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "window_name",
    "occupancy_vs_market_pct",
    "price_vs_market_75th_pct",
    "low_confidence_booked_days",
)
OUTPUT_COLUMNS = (
    "run_date",
    "listing_id",
    "window_name",
    "pace_status",
    "price_position_status",
    "confidence_note",
    "urgency_flag",
    "short_reason",
)
EXPECTED_WINDOWS = ("days_0_30", "days_31_60", "days_61_90")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create simple V1 future window signal labels.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--summary-file",
        help="Window summary CSV. Defaults to analysis/future_window_summary_<run-date>.csv.",
    )
    parser.add_argument(
        "--output-file",
        help="Signal output CSV. Defaults to analysis/future_window_signals_<run-date>.csv.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Window summary CSV is missing a header row")
    missing = [column for column in REQUIRED_INPUT_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"Window summary CSV is missing required columns: {', '.join(missing)}")


def read_summary_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Window summary CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def parse_decimal(value: str) -> Decimal | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return Decimal(stripped)
    except InvalidOperation:
        return None


def parse_int(value: str) -> int:
    stripped = value.strip()
    if not stripped:
        return 0
    return int(stripped)


def pace_status(value: str) -> str:
    parsed = parse_decimal(value)
    if parsed is None:
        return "unknown_pace"
    if parsed >= Decimal("5.0"):
        return "ahead_of_market"
    if parsed > Decimal("-5.0"):
        return "near_market"
    return "behind_market"


def price_position_status(value: str) -> str:
    parsed = parse_decimal(value)
    if parsed is None:
        return "unknown_price_position"
    if parsed > Decimal("10.0"):
        return "above_75th"
    if parsed >= Decimal("-10.0"):
        return "near_75th"
    return "below_75th"


def confidence_note(value: str) -> str:
    days = parse_int(value)
    if days == 0:
        return "clean"
    if days <= 2:
        return "some_low_confidence_bookings"
    return "many_low_confidence_bookings"


def urgency_flag(window_name: str, pace: str) -> str:
    if window_name == "days_0_30" and pace == "behind_market":
        return "critical_now"
    if window_name in ("days_31_60", "days_61_90") and pace == "behind_market":
        return "advisory"
    return "monitor"


def short_reason(pace: str, price_position: str) -> str:
    pace_text = {
        "ahead_of_market": "Ahead of market pace",
        "near_market": "Near market pace",
        "behind_market": "Behind market pace",
        "unknown_pace": "Unknown market pace",
    }[pace]
    price_text = {
        "above_75th": "price above 75th percentile",
        "near_75th": "price near 75th percentile",
        "below_75th": "price below 75th percentile",
        "unknown_price_position": "price position unknown",
    }[price_position]
    return f"{pace_text}; {price_text}"


def signal_row(row: dict[str, str]) -> dict[str, str]:
    pace = pace_status(row["occupancy_vs_market_pct"])
    price_position = price_position_status(row["price_vs_market_75th_pct"])
    return {
        "run_date": row["run_date"].strip(),
        "listing_id": row["listing_id"].strip(),
        "window_name": row["window_name"].strip(),
        "pace_status": pace,
        "price_position_status": price_position,
        "confidence_note": confidence_note(row["low_confidence_booked_days"]),
        "urgency_flag": urgency_flag(row["window_name"].strip(), pace),
        "short_reason": short_reason(pace, price_position),
    }


def validate_windows(rows: list[dict[str, str]]) -> None:
    window_names = [row["window_name"].strip() for row in rows]
    if window_names != list(EXPECTED_WINDOWS):
        raise ValueError(f"Expected windows in order: {', '.join(EXPECTED_WINDOWS)}")


def write_signal_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    summary_path = Path(args.summary_file or f"analysis/future_window_summary_{args.run_date}.csv")
    output_path = Path(args.output_file or f"analysis/future_window_signals_{args.run_date}.csv")

    summary_rows = read_summary_rows(summary_path)
    if len(summary_rows) != 3:
        raise ValueError("Window signals must be built from exactly 3 summary rows")
    validate_windows(summary_rows)

    signal_rows = [signal_row(row) for row in summary_rows]
    write_signal_rows(output_path, signal_rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
