"""Manual PriceLabs settings snapshot capture."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any


REQUIRED_INPUT_FIELDS = (
    "listing_id",
    "pms_account",
    "listing_name",
    "base_price",
    "last_minute_rule",
    "orphan_day_prices",
    "booking_recency_factor",
    "minimum_stay_settings",
    "extra_person_fee",
    "occupancy_based_adjustments",
    "occupancy_based_adjustments_snapshot",
    "custom_seasonality_factor",
    "length_of_stay_based_pricing",
    "demand_factor_sensitivity",
    "far_out_premium",
    "safety_minimum_price_rule",
)
OUTPUT_FIELDS = ("run_date", *REQUIRED_INPUT_FIELDS, "source_file")
PREFERRED_STRUCTURED_FIELDS = (
    "orphan_day_prices",
    "minimum_stay_settings",
    "occupancy_based_adjustments",
    "occupancy_based_adjustments_snapshot",
    "length_of_stay_based_pricing",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a manual PriceLabs settings snapshot.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--input-file",
        default="sample_data/pricelabs_settings_manual_input.json",
        help="Manual PriceLabs settings JSON input.",
    )
    parser.add_argument(
        "--output-file",
        help="Settings snapshot JSON. Defaults to analysis/pricelabs_settings_snapshot_<run-date>.json.",
    )
    return parser.parse_args()


def read_input(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Settings input JSON does not exist: {path}")
    with path.open("r", encoding="utf-8-sig") as json_file:
        data = json.load(json_file)
    if not isinstance(data, dict):
        raise ValueError("Settings input JSON must be an object")
    return data


def require_fields(data: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_INPUT_FIELDS if field not in data]
    if missing:
        raise ValueError(f"Settings input JSON is missing required fields: {', '.join(missing)}")


def build_snapshot(data: dict[str, Any], *, run_date: str, source_file: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"run_date": run_date}
    for field in REQUIRED_INPUT_FIELDS:
        # Preserve nested setting sections exactly as provided for traceable diffs.
        snapshot[field] = data[field]
    snapshot["source_file"] = str(source_file)
    return snapshot


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered_snapshot = {field: snapshot[field] for field in OUTPUT_FIELDS}
    with path.open("w", encoding="utf-8") as json_file:
        json.dump(ordered_snapshot, json_file, indent=2)
        json_file.write("\n")


def run() -> int:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date).isoformat()
    input_path = Path(args.input_file)
    output_path = Path(args.output_file or f"analysis/pricelabs_settings_snapshot_{run_date}.json")

    data = read_input(input_path)
    require_fields(data)
    snapshot = build_snapshot(data, run_date=run_date, source_file=input_path)
    write_snapshot(output_path, snapshot)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
