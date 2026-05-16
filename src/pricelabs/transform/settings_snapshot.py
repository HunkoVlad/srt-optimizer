"""PriceLabs settings snapshot normalization."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import re
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


def normalize_dash(value: str) -> str:
    return value.replace("\u2013", "-").replace("\u2014", "-")


def parse_percent(value: str) -> int | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*%", value)
    if not match:
        return None
    number = float(match.group(1))
    return int(number) if number.is_integer() else round(number, 2)


def parse_int_after(pattern: str, value: str) -> int | None:
    match = re.search(pattern, value, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def adjustment_from_text(text: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?%)\s*(premium|discount)", text, flags=re.IGNORECASE)
    if not match:
        if re.search(r"\bnone\b", text, flags=re.IGNORECASE):
            return "none"
        return text.strip()
    percent, direction = match.groups()
    return f"{percent} {direction.lower()}"


def parse_weekday_weekend(text: str) -> dict[str, int | None]:
    return {
        "weekday_nights": parse_int_after(r"Weekday:\s*(\d+)", text),
        "weekend_nights": parse_int_after(r"Weekend:\s*(\d+)", text),
    }


def parse_last_minute(text: str) -> dict[str, Any]:
    return {
        "percent": parse_percent(text),
        "type": "premium" if "premium" in text.lower() else "discount" if "discount" in text.lower() else "",
        "within_days": parse_int_after(r"within\s+(\d+)\s+day", text),
        "raw_text": text,
    }


def parse_orphan_day_prices(text: str) -> dict[str, Any]:
    weekday_match = re.search(r"Weekday:\s*([^|]+)", text, flags=re.IGNORECASE)
    weekend_match = re.search(r"Weekend:\s*(.+?)\s+for gaps", text, flags=re.IGNORECASE)
    gap_match = re.search(
        r"gaps between\s+(\d+)\s+and\s+(\d+)\s+night.*?within\s+(\d+)\s+and\s+(\d+)\s+nights",
        text,
        flags=re.IGNORECASE,
    )
    return {
        "weekday": {"adjustment": adjustment_from_text(weekday_match.group(1)) if weekday_match else ""},
        "weekend": {"adjustment": adjustment_from_text(weekend_match.group(1)) if weekend_match else ""},
        "gap_rule": {
            "gap_min_nights": int(gap_match.group(1)) if gap_match else None,
            "gap_max_nights": int(gap_match.group(2)) if gap_match else None,
            "applied_within_min_nights": int(gap_match.group(3)) if gap_match else None,
            "applied_within_max_nights": int(gap_match.group(4)) if gap_match else None,
        },
        "raw_text": text,
    }


def parse_booking_recency_factor(text: str) -> dict[str, Any]:
    return {
        "start_discount_percent": parse_int_after(r"from\s+(\d+)%", text),
        "start_no_booking_days": parse_int_after(r"last\s+(\d+)\s+days\)", text),
        "max_discount_percent": parse_int_after(r"up to\s+(\d+)%", text),
        "max_no_booking_days": parse_int_after(r"last\s+(\d+)\s+days\), affecting", text),
        "affected_next_days": parse_int_after(r"next\s+(\d+)\s+days", text),
        "raw_text": text,
    }


def parse_minimum_stay(lines: list[str], text: str) -> dict[str, Any]:
    normalized_text = normalize_dash("\n".join(lines) if lines else text)
    single_line = " ".join(normalized_text.split())
    profile_match = re.search(r"ACTIVE MINSTAY PROFILE\s*:\s*(.+?)(?:\s+Default\s*:|$)", single_line, re.I)

    def section_text(start_label: str, end_label: str | None = None) -> str:
        pattern = rf"{re.escape(start_label)}\s*:\s*(.+?)"
        if end_label:
            pattern += rf"\s+{re.escape(end_label)}\s*:"
        else:
            pattern += r"$"
        match = re.search(pattern, single_line, flags=re.IGNORECASE)
        return match.group(1).strip() if match else ""

    default_text = section_text("Default", "Last Minute")
    last_minute_text = section_text("Last Minute", "Far Out")
    far_out_text = section_text("Far Out", "Orphan Gaps")
    orphan_text = section_text("Orphan Gaps", "Lowest Minstay Allowed")
    lowest_text = section_text("Lowest Minstay Allowed")

    default_nights = parse_weekday_weekend(default_text)
    last_minute = parse_weekday_weekend(last_minute_text)
    last_minute["within_nights"] = parse_int_after(r"within\s+(\d+)\s+nights?", last_minute_text)
    far_out = parse_weekday_weekend(far_out_text)
    far_out["beyond_nights"] = parse_int_after(r"beyond\s+(\d+)\s+nights?", far_out_text)
    orphan = parse_weekday_weekend(orphan_text)
    gap_match = re.search(r"gaps between\s+(\d+)\s+and\s+(\d+)\s+nights?", orphan_text, flags=re.I)
    orphan["gap_min_nights"] = int(gap_match.group(1)) if gap_match else None
    orphan["gap_max_nights"] = int(gap_match.group(2)) if gap_match else None

    return {
        "profile_name": (profile_match.group(1).strip() if profile_match else ""),
        "default": default_nights,
        "last_minute": last_minute,
        "far_out": far_out,
        "orphan_gaps": orphan,
        "lowest_minstay_allowed": parse_weekday_weekend(lowest_text),
        "raw_text": normalized_text,
    }


def parse_extra_person_fee(text: str) -> dict[str, Any]:
    return {
        "type": "percent" if "%" in text else "",
        "value": parse_percent(text),
        "after_guests": parse_int_after(r"after\s+(\d+)\s+guests?", text),
        "raw_text": text,
    }


def parse_oba_mode(text: str) -> dict[str, str]:
    return {"mode": text, "raw_text": text}


def parse_oba_snapshot(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {"raw_text": text}
    pattern = re.compile(
        r"(?P<adjustment>\d+(?:\.\d+)?%\s+(?:discount|premium))\s+for next\s+"
        r"(?P<start>\d+)\s+to\s+(?P<end>\d+)\s+days\s+"
        r"(?P<note>Occupancy\s+\d+(?:\.\d+)?%\s+(?:below|above)\s+market)",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        key = f"days_{match.group('start')}_{match.group('end')}"
        result[key] = {
            "adjustment": match.group("adjustment").lower(),
            "market_position_note": match.group("note"),
        }
    return result


def parse_los_pricing(setting: Any) -> dict[str, Any]:
    detail_text = ""
    if isinstance(setting, dict):
        detail_text = str(setting.get("detail_text") or "")
        if not detail_text:
            lines = setting.get("detail_lines")
            if isinstance(lines, list):
                detail_text = " ".join(str(line) for line in lines)
    text = detail_text or setting_value(setting)

    thresholds: dict[int, str] = {}
    for stay_length, percent in re.findall(r">(\d+)\s+(-?\d+(?:\.\d+)?)%", text):
        number = float(percent)
        if number > 0:
            value = f"{int(number) if number.is_integer() else number}% premium"
        elif number < 0:
            number = abs(number)
            value = f"{int(number) if number.is_integer() else number}% discount"
        else:
            value = "0%"
        thresholds[int(stay_length)] = value

    return {
        "1_night": thresholds.get(1, ""),
        "2_nights": thresholds.get(2, ""),
        "3_nights": thresholds.get(3, thresholds.get(2, "")),
        "4_plus_nights": thresholds.get(4, ""),
        "raw_text": text,
    }


def parse_far_out_premium(text: str) -> dict[str, Any]:
    return {
        "percent": parse_percent(text),
        "after_days": parse_int_after(r"After\s+(\d+)\s+days", text),
        "raw_text": text,
    }


def parse_safety_minimum(text: str) -> dict[str, Any]:
    return {
        "percent_of_last_year_same_day_adr": parse_percent(text),
        "beyond_days": parse_int_after(r"beyond\s+(\d+)\s+days", text),
        "raw_text": text,
    }


def has_meaningful_value(value: Any) -> bool:
    if value in ("", None, {}):
        return False
    if isinstance(value, dict):
        return any(has_meaningful_value(child) for child in value.values())
    if isinstance(value, list):
        return any(has_meaningful_value(child) for child in value)
    return bool(str(value).strip())


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
    snapshot["last_minute_rule"] = parse_last_minute(setting_value(settings.get("last_minute")))
    snapshot["orphan_day_prices"] = parse_orphan_day_prices(setting_value(settings.get("orphan_day_prices")))
    snapshot["booking_recency_factor"] = parse_booking_recency_factor(setting_value(settings.get("booking_recency_factor")))

    min_stay_setting = settings.get("minimum_stay_settings")
    min_stay_lines = min_stay_setting.get("value_lines", []) if isinstance(min_stay_setting, dict) else []
    min_stay_lines = [str(line) for line in min_stay_lines] if isinstance(min_stay_lines, list) else []
    snapshot["minimum_stay_settings"] = parse_minimum_stay(
        min_stay_lines,
        setting_value(min_stay_setting),
    )
    snapshot["extra_person_fee"] = parse_extra_person_fee(setting_value(settings.get("extra_person_fee")))
    snapshot["occupancy_based_adjustments"] = parse_oba_mode(setting_value(settings.get("occupancy_based_adjustments")))
    snapshot["custom_seasonality_factor"] = {"value": setting_value(settings.get("custom_seasonality_factor"))}
    snapshot["length_of_stay_based_pricing"] = parse_los_pricing(settings.get("length_of_stay_based_pricing"))
    snapshot["demand_factor_sensitivity"] = {"value": setting_value(settings.get("demand_factor_sensitivity"))}
    snapshot["far_out_premium"] = parse_far_out_premium(setting_value(settings.get("far_out_premium")))
    snapshot["safety_minimum_price_rule"] = parse_safety_minimum(setting_value(settings.get("safety_minimum_price")))

    oba = settings.get("occupancy_based_adjustments")
    oba_detail = ""
    if isinstance(oba, dict):
        oba_detail = str(oba.get("detail_text") or "")
    snapshot["occupancy_based_adjustments_snapshot"] = parse_oba_snapshot(oba_detail or setting_value(oba))

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
        if not has_meaningful_value(snapshot.get(field))
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
