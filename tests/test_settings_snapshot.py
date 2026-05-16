import json
from pathlib import Path

import pytest

from pricelabs.transform import settings_snapshot


def ui_settings_payload() -> dict:
    labels = {
        "last_minute": "Last Minute",
        "orphan_day_prices": "Orphan Day Prices",
        "booking_recency_factor": "Booking Recency Factor",
        "minimum_stay_settings": "Minimum Stay Settings",
        "extra_person_fee": "Extra Person Fee",
        "occupancy_based_adjustments": "Occupancy Based Adjustments",
        "custom_seasonality_factor": "Custom Seasonality Factor",
        "length_of_stay_based_pricing": "Length-of-stay Based Pricing",
        "demand_factor_sensitivity": "Demand Factor Sensitivity",
        "far_out_premium": "Far Out Premium",
        "safety_minimum_price": "Safety Minimum Price",
    }
    settings = {
        key: {
            "label": label,
            "value": f"{label} value",
            "value_text": f"{label} value",
            "value_lines": [f"{label} value"],
        }
        for key, label in labels.items()
    }
    settings["occupancy_based_adjustments"]["detail_text"] = "Occupancy detail from popover"
    return {
        "run_date": "2026-05-14",
        "listing_id": "650255___717243",
        "pms_name": "lodgify",
        "source": "pricelabs_ui_customization_well",
        "source_url": "https://app.pricelabs.co/pricing?listings=650255___717243&pms_name=lodgify&open_bi=true",
        "captured_at_utc": "2026-05-14T12:00:00+00:00",
        "settings": settings,
    }


def manual_settings_payload() -> dict:
    return {
        "listing_id": "650255___717243",
        "pms_account": "lodgify",
        "listing_name": "Aloha Poconos",
        "base_price": 425,
        "last_minute_rule": "manual last minute",
        "orphan_day_prices": "manual orphan",
        "booking_recency_factor": "manual recency",
        "minimum_stay_settings": "manual min stay",
        "extra_person_fee": "manual extra person",
        "occupancy_based_adjustments": "manual occupancy",
        "occupancy_based_adjustments_snapshot": "manual occupancy snapshot",
        "custom_seasonality_factor": "manual seasonality",
        "length_of_stay_based_pricing": "manual los",
        "demand_factor_sensitivity": "manual demand",
        "far_out_premium": "manual far out",
        "safety_minimum_price_rule": "manual safety minimum",
    }


def test_ui_settings_snapshot_normalizes_to_generated_snapshot(tmp_path: Path) -> None:
    input_path = tmp_path / "pricelabs_settings_snapshot_from_ui.json"
    snapshot = settings_snapshot.build_snapshot(
        ui_settings_payload(),
        run_date="2026-05-14",
        source_file=input_path,
    )

    assert snapshot["settings_source"] == "pricelabs_ui_snapshot"
    assert snapshot["source_file"] == str(input_path)
    assert snapshot["listing_id"] == "650255___717243"
    assert snapshot["pms_account"] == "lodgify"
    assert snapshot["last_minute_rule"] == "Last Minute value"
    assert snapshot["minimum_stay_settings"] == "Minimum Stay Settings value"
    assert snapshot["safety_minimum_price_rule"] == "Safety Minimum Price value"
    assert snapshot["occupancy_based_adjustments_snapshot"] == "Occupancy detail from popover"
    assert "raw_ui_settings" in snapshot


def test_manual_settings_snapshot_is_deprecated_fallback(tmp_path: Path) -> None:
    input_path = tmp_path / "pricelabs_settings_manual_input.json"
    snapshot = settings_snapshot.build_snapshot(
        manual_settings_payload(),
        run_date="2026-05-14",
        source_file=input_path,
    )

    assert snapshot["settings_source"] == "deprecated_manual_fallback"
    assert snapshot["last_minute_rule"] == "manual last minute"
    assert snapshot["source_file"] == str(input_path)


def test_ui_settings_snapshot_write_preserves_source_metadata(tmp_path: Path) -> None:
    input_path = tmp_path / "pricelabs_settings_snapshot_from_ui.json"
    output_path = tmp_path / "settings" / "pricelabs_settings_snapshot_2026-05-14.json"
    snapshot = settings_snapshot.build_snapshot(
        ui_settings_payload(),
        run_date="2026-05-14",
        source_file=input_path,
    )

    settings_snapshot.write_snapshot(output_path, snapshot)

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["settings_source"] == "pricelabs_ui_snapshot"
    assert written["source_url"].startswith("https://app.pricelabs.co/pricing?")
    assert written["raw_ui_settings"]["length_of_stay_based_pricing"]["value_text"] == (
        "Length-of-stay Based Pricing value"
    )


def test_ui_settings_snapshot_fails_when_required_setting_missing(tmp_path: Path) -> None:
    payload = ui_settings_payload()
    payload["settings"].pop("far_out_premium")

    with pytest.raises(ValueError, match="missing normalized fields"):
        settings_snapshot.build_snapshot(
            payload,
            run_date="2026-05-14",
            source_file=tmp_path / "pricelabs_settings_snapshot_from_ui.json",
        )
