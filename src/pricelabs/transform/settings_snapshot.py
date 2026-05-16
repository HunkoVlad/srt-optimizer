"""PriceLabs settings snapshot normalization."""

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
UI_SNAPSHOT_SOURCE = "pricelabs_ui_snapshot"
MANUAL_FALLBACK_SOURCE = "deprecated_manual_fallback"
UI_SETTING_TO_OUTPUT_FIELD = {
    "last_minute": "last_minute_rule",
    "orphan_day_prices": "orphan_day_prices",
    "booking_recency_factor": "booking_recency_factor",
    "minimum_stay_settings": "minimum_stay_settings",
    "extra_person_fee": "extra_person_fee",
    "occupancy_based_adjustments": "occupancy_based_adjustments",
    "custom_seasonality_factor": "custom_seasonality_factor",
    "length_of_stay_based_pricing": "length_of_stay_based_pricing",
    "demand_factor_sensitivity": "demand_factor_sensitivity",
    "far_out_premium": "far_out_premium",
    "safety_minimum_price": "safety_minimum_price_rule",
}
PREFERRED_STRUCTURED_FIELDS = (
    "orphan_day_prices",
    "minimum_stay_settings",
    "occupancy_based_adjustments",
    "occupancy_based_adjustments_snapshot",
    "length_of_stay_based_pricing",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a PriceLabs settings snapshot.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--input-file",
        default="sample_data/pricelabs_settings_manual_input.json",
        help="PriceLabs UI settings snapshot JSON input, or deprecated manual fallback JSON.",
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


def is_ui_snapshot(data: dict[str, Any]) -> bool:
    return isinstance(data.get("settings"), dict) and data.get("source") == "pricelabs_ui_customization_well"


def setting_value(setting: Any) -> str:
    if isinstance(setting, dict):
        value = setting.get("value_text") or setting.get("value")
        if value is None:
            value_lines = setting.get("value_lines")
            if isinstance(value_lines, list):
                value = " ".join(str(line).strip() for line in value_lines if str(line).strip())
        return str(value or "").strip()
    return str(setting or "").strip()


def normalize_ui_settings(data: dict[str, Any], *, run_date: str, source_file: Path) -> dict[str, Any]:
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("PriceLabs UI settings snapshot is missing settings object")

    snapshot: dict[str, Any] = {
        "run_date": run_date,
        "listing_id": str(data.get("listing_id", "")).strip(),
        "pms_account": str(data.get("pms_name") or data.get("pms_account") or "").strip(),
        "listing_name": str(data.get("listing_name", "")).strip(),
        "base_price": data.get("base_price", ""),
        "settings_source": UI_SNAPSHOT_SOURCE,
        "source_file": str(source_file),
        "source_url": data.get("source_url") or data.get("url") or "",
        "captured_at_utc": data.get("captured_at_utc", ""),
        "raw_ui_settings": settings,
    }
    for ui_key, output_field in UI_SETTING_TO_OUTPUT_FIELD.items():
        snapshot[output_field] = setting_value(settings.get(ui_key))

    oba = settings.get("occupancy_based_adjustments")
    if isinstance(oba, dict) and oba.get("detail_text"):
        snapshot["occupancy_based_adjustments_snapshot"] = oba["detail_text"]
    else:
        snapshot["occupancy_based_adjustments_snapshot"] = snapshot["occupancy_based_adjustments"]

    missing = [
        field
        for field in (
            "listing_id",
            "last_minute_rule",
            "orphan_day_prices",
            "booking_recency_factor",
            "minimum_stay_settings",
            "extra_person_fee",
            "occupancy_based_adjustments",
            "custom_seasonality_factor",
            "length_of_stay_based_pricing",
            "demand_factor_sensitivity",
            "far_out_premium",
            "safety_minimum_price_rule",
        )
        if not str(snapshot.get(field, "")).strip()
    ]
    if missing:
        raise ValueError(f"PriceLabs UI settings snapshot is missing normalized fields: {', '.join(missing)}")
    return snapshot


def build_snapshot(data: dict[str, Any], *, run_date: str, source_file: Path) -> dict[str, Any]:
    if is_ui_snapshot(data):
        return normalize_ui_settings(data, run_date=run_date, source_file=source_file)

    require_fields(data)
    snapshot: dict[str, Any] = {"run_date": run_date}
    for field in REQUIRED_INPUT_FIELDS:
        # Preserve nested setting sections exactly as provided for traceable diffs.
        snapshot[field] = data[field]
    snapshot["settings_source"] = MANUAL_FALLBACK_SOURCE
    snapshot["source_file"] = str(source_file)
    return snapshot


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered_fields = [
        "run_date",
        *REQUIRED_INPUT_FIELDS,
        "settings_source",
        "source_file",
        "source_url",
        "captured_at_utc",
        "raw_ui_settings",
    ]
    ordered_snapshot = {field: snapshot[field] for field in ordered_fields if field in snapshot}
    for field, value in snapshot.items():
        if field not in ordered_snapshot:
            ordered_snapshot[field] = value
    with path.open("w", encoding="utf-8") as json_file:
        json.dump(ordered_snapshot, json_file, indent=2)
        json_file.write("\n")


def run() -> int:
    args = parse_args()
    run_date = date.fromisoformat(args.run_date).isoformat()
    input_path = Path(args.input_file)
    output_path = Path(args.output_file or f"analysis/pricelabs_settings_snapshot_{run_date}.json")

    data = read_input(input_path)
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
