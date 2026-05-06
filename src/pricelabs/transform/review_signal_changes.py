"""Manual review of signal changes with settings-change context."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


EXPECTED_WINDOWS = ("days_0_15", "days_16_45", "days_46_90")
REQUIRED_SIGNAL_COLUMNS = (
    "run_date",
    "listing_id",
    "window_name",
    "pace_status",
    "price_position_status",
    "urgency_flag",
)
REQUIRED_SETTINGS_CHANGE_COLUMNS = ("field_name",)
OUTPUT_COLUMNS = (
    "run_date",
    "prior_run_date",
    "listing_id",
    "window_name",
    "previous_pace_status",
    "current_pace_status",
    "previous_price_position_status",
    "current_price_position_status",
    "previous_urgency_flag",
    "current_urgency_flag",
    "changed_settings_count",
    "changed_settings_summary",
    "interpretation_note",
)
PACE_STRENGTH = {
    "behind_market": 0,
    "near_market": 1,
    "ahead_of_market": 2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare future window signals with settings-change context.")
    parser.add_argument("--run-date", required=True, help="Current pipeline run date in YYYY-MM-DD format.")
    parser.add_argument("--prior-run-date", required=True, help="Prior signal run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--current-signal-file",
        help="Current signal CSV. Defaults to analysis/future_window_signals_<run-date>.csv.",
    )
    parser.add_argument(
        "--prior-signal-file",
        help="Prior signal CSV. Defaults to analysis/future_window_signals_<prior-run-date>.csv.",
    )
    parser.add_argument(
        "--settings-changes-file",
        help="Settings changes CSV. Defaults to analysis/pricelabs_settings_changes_<run-date>.csv.",
    )
    parser.add_argument(
        "--output-file",
        help="Review output CSV. Defaults to analysis/future_signal_change_review_<run-date>.csv.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None, required_columns: tuple[str, ...], label: str) -> None:
    if fieldnames is None:
        raise ValueError(f"{label} CSV is missing a header row")
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        raise ValueError(f"{label} CSV is missing required columns: {', '.join(missing)}")


def read_csv_rows(path: Path, required_columns: tuple[str, ...], label: str) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"{label} CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames, required_columns, label)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def signals_by_window(rows: list[dict[str, str]], label: str) -> dict[str, dict[str, str]]:
    by_window: dict[str, dict[str, str]] = {}
    for row in rows:
        window_name = row["window_name"].strip()
        if window_name in by_window:
            raise ValueError(f"{label} signal CSV has duplicate window_name: {window_name}")
        by_window[window_name] = row

    expected = set(EXPECTED_WINDOWS)
    actual = set(by_window)
    if actual != expected:
        raise ValueError(f"{label} signal CSV must contain windows: {', '.join(EXPECTED_WINDOWS)}")
    return by_window


def settings_change_context(rows: list[dict[str, str]]) -> tuple[str, str]:
    field_names = [row["field_name"].strip() for row in rows if row["field_name"].strip()]
    return str(len(rows)), "; ".join(field_names)


def interpretation_note(
    *,
    previous_pace: str,
    current_pace: str,
    previous_price_position: str,
    current_price_position: str,
    previous_urgency: str,
    current_urgency: str,
    changed_settings_count: str,
) -> str:
    if current_pace != previous_pace:
        previous_strength = PACE_STRENGTH.get(previous_pace)
        current_strength = PACE_STRENGTH.get(current_pace)
        if previous_strength is not None and current_strength is not None:
            if current_strength > previous_strength:
                return "Pace improved after settings changes"
            if current_strength < previous_strength:
                return "Pace worsened after settings changes"

    if current_urgency != previous_urgency:
        return "Urgency changed; review settings impact"

    if current_price_position != previous_price_position:
        return "Price position changed; review settings impact"

    if int(changed_settings_count) > 0:
        return "Signals unchanged; settings changed"
    return "No signal or settings changes"


def build_review_rows(
    current_signals: dict[str, dict[str, str]],
    prior_signals: dict[str, dict[str, str]],
    *,
    run_date: str,
    prior_run_date: str,
    changed_settings_count: str,
    changed_settings_summary: str,
) -> list[dict[str, str]]:
    current_listing_ids = {row["listing_id"].strip() for row in current_signals.values()}
    prior_listing_ids = {row["listing_id"].strip() for row in prior_signals.values()}
    if len(current_listing_ids) != 1 or len(prior_listing_ids) != 1:
        raise ValueError("Signal files must each contain exactly one listing_id")
    if current_listing_ids != prior_listing_ids:
        raise ValueError("Current and prior signal files have different listing_id values")

    listing_id = next(iter(current_listing_ids))
    rows: list[dict[str, str]] = []
    for window_name in EXPECTED_WINDOWS:
        current = current_signals[window_name]
        prior = prior_signals[window_name]
        note = interpretation_note(
            previous_pace=prior["pace_status"].strip(),
            current_pace=current["pace_status"].strip(),
            previous_price_position=prior["price_position_status"].strip(),
            current_price_position=current["price_position_status"].strip(),
            previous_urgency=prior["urgency_flag"].strip(),
            current_urgency=current["urgency_flag"].strip(),
            changed_settings_count=changed_settings_count,
        )
        rows.append(
            {
                "run_date": run_date,
                "prior_run_date": prior_run_date,
                "listing_id": listing_id,
                "window_name": window_name,
                "previous_pace_status": prior["pace_status"].strip(),
                "current_pace_status": current["pace_status"].strip(),
                "previous_price_position_status": prior["price_position_status"].strip(),
                "current_price_position_status": current["price_position_status"].strip(),
                "previous_urgency_flag": prior["urgency_flag"].strip(),
                "current_urgency_flag": current["urgency_flag"].strip(),
                "changed_settings_count": changed_settings_count,
                "changed_settings_summary": changed_settings_summary,
                "interpretation_note": note,
            }
        )
    return rows


def write_review(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    current_signal_path = Path(args.current_signal_file or f"analysis/future_window_signals_{args.run_date}.csv")
    prior_signal_path = Path(args.prior_signal_file or f"analysis/future_window_signals_{args.prior_run_date}.csv")
    settings_changes_path = Path(args.settings_changes_file or f"analysis/pricelabs_settings_changes_{args.run_date}.csv")
    output_path = Path(args.output_file or f"analysis/future_signal_change_review_{args.run_date}.csv")

    current_signal_rows = read_csv_rows(current_signal_path, REQUIRED_SIGNAL_COLUMNS, "Current signal")
    prior_signal_rows = read_csv_rows(prior_signal_path, REQUIRED_SIGNAL_COLUMNS, "Prior signal")
    settings_change_rows = read_csv_rows(settings_changes_path, REQUIRED_SETTINGS_CHANGE_COLUMNS, "Settings changes")

    current_signals = signals_by_window(current_signal_rows, "Current")
    prior_signals = signals_by_window(prior_signal_rows, "Prior")
    changed_settings_count, changed_settings_summary = settings_change_context(settings_change_rows)
    review_rows = build_review_rows(
        current_signals,
        prior_signals,
        run_date=args.run_date,
        prior_run_date=args.prior_run_date,
        changed_settings_count=changed_settings_count,
        changed_settings_summary=changed_settings_summary,
    )
    if len(review_rows) != 3:
        raise ValueError("Signal change review must contain exactly 3 rows")

    write_review(output_path, review_rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
