"""Manual PriceLabs settings change tracking."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any


REQUIRED_SNAPSHOT_FIELDS = ("run_date", "listing_id")
IGNORED_FIELDS = {"run_date", "source_file"}
OUTPUT_COLUMNS = (
    "run_date",
    "prior_run_date",
    "listing_id",
    "field_name",
    "previous_value",
    "current_value",
    "changed_flag",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two manual PriceLabs settings snapshots.")
    parser.add_argument("--run-date", required=True, help="Current pipeline run date in YYYY-MM-DD format.")
    parser.add_argument("--prior-run-date", required=True, help="Prior snapshot run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--current-snapshot-file",
        help="Current snapshot JSON. Defaults to analysis/pricelabs_settings_snapshot_<run-date>.json.",
    )
    parser.add_argument(
        "--prior-snapshot-file",
        help="Prior snapshot JSON. Defaults to analysis/pricelabs_settings_snapshot_<prior-run-date>.json.",
    )
    parser.add_argument(
        "--output-file",
        help="Settings changes CSV. Defaults to analysis/pricelabs_settings_changes_<run-date>.csv.",
    )
    return parser.parse_args()


def read_snapshot(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} settings snapshot does not exist: {path}")
    with path.open("r", encoding="utf-8-sig") as json_file:
        data = json.load(json_file)
    if not isinstance(data, dict):
        raise ValueError(f"{label} settings snapshot must be a JSON object")
    missing = [field for field in REQUIRED_SNAPSHOT_FIELDS if field not in data]
    if missing:
        raise ValueError(f"{label} settings snapshot is missing required fields: {', '.join(missing)}")
    return data


def stable_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if value is None:
        return ""
    return str(value)


def comparable_fields(current: dict[str, Any], prior: dict[str, Any]) -> list[str]:
    fields = (set(current) | set(prior)) - IGNORED_FIELDS
    return sorted(fields)


def build_change_rows(
    current: dict[str, Any],
    prior: dict[str, Any],
    *,
    run_date: str,
    prior_run_date: str,
) -> list[dict[str, str]]:
    if current["listing_id"] != prior["listing_id"]:
        raise ValueError("Current and prior settings snapshots have different listing_id values")

    rows: list[dict[str, str]] = []
    for field_name in comparable_fields(current, prior):
        current_value = stable_value(current.get(field_name))
        previous_value = stable_value(prior.get(field_name))
        if current_value == previous_value:
            continue
        rows.append(
            {
                "run_date": run_date,
                "prior_run_date": prior_run_date,
                "listing_id": str(current["listing_id"]),
                "field_name": field_name,
                "previous_value": previous_value,
                "current_value": current_value,
                "changed_flag": "true",
            }
        )
    return rows


def write_changes(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    current_path = Path(args.current_snapshot_file or f"analysis/pricelabs_settings_snapshot_{args.run_date}.json")
    prior_path = Path(args.prior_snapshot_file or f"analysis/pricelabs_settings_snapshot_{args.prior_run_date}.json")
    output_path = Path(args.output_file or f"analysis/pricelabs_settings_changes_{args.run_date}.csv")

    current = read_snapshot(current_path, "Current")
    prior = read_snapshot(prior_path, "Prior")
    rows = build_change_rows(current, prior, run_date=args.run_date, prior_run_date=args.prior_run_date)
    write_changes(output_path, rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
