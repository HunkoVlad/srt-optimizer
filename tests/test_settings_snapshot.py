import json
from pathlib import Path

import pytest

from pricelabs.transform import settings_snapshot
from pricelabs.transform import settings_changes


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
    settings["last_minute"]["value_text"] = "10% premium within 1 day (Flat)"
    settings["orphan_day_prices"]["value_text"] = (
        "Weekday: 10% Discount | Weekend: None for gaps between 1 and 1 night "
        "applied within 0 and 999 nights"
    )
    settings["booking_recency_factor"]["value_text"] = (
        "Gradual discount from 5% (no bookings in the last 15 days) up to 15% "
        "(no bookings in the last 45 days), affecting prices for the next 30 days."
    )
    settings["minimum_stay_settings"] = {
        "label": "Minimum Stay Settings",
        "value_text": (
            "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized Default : "
            "Fixed Weekday: 1 night | Weekend: 2 nights Last Minute : Weekday: 1 night | "
            "Weekend: 1 night within 7 nights Far Out : Weekday: 2 nights | Weekend: 2 nights "
            "beyond 61 nights Orphan Gaps : Weekday: 1 nights | Weekend: 1 nights for gaps "
            "between 1 and 2 nights Lowest Minstay Allowed : Weekday: 1| Weekend: 1"
        ),
        "value_lines": [
            "ACTIVE MINSTAY PROFILE : EffortSaver - Revenue Optimized",
            "Default :",
            "Fixed Weekday: 1 night | Weekend: 2 nights",
            "Last Minute :",
            "Weekday: 1 night | Weekend: 1 night within 7 nights",
            "Far Out :",
            "Weekday: 2 nights | Weekend: 2 nights beyond 61 nights",
            "Orphan Gaps :",
            "Weekday: 1 nights | Weekend: 1 nights for gaps between 1 and 2 nights",
            "Lowest Minstay Allowed :",
            "Weekday: 1| Weekend: 1",
        ],
    }
    settings["extra_person_fee"]["value_text"] = "10% after 6 guests"
    settings["occupancy_based_adjustments"]["value_text"] = "Market Driven"
    settings["occupancy_based_adjustments"]["detail_text"] = (
        "8% discount for next 0 to 15 days Occupancy 9% below market "
        "14% discount for next 16 to 30 days Occupancy 16% below market "
        "14% discount for next 31 to 60 days Occupancy 15% below market"
    )
    settings["custom_seasonality_factor"]["value_text"] = "Recommended"
    settings["demand_factor_sensitivity"]["value_text"] = "Recommended"
    settings["far_out_premium"]["value_text"] = "After 90 days, flat premium of 5.0%"
    settings["safety_minimum_price"]["value_text"] = (
        "Set Safety Minimum Price to 110% of last-year-same-day ADR for nights beyond 180 days from today."
    )
    settings["length_of_stay_based_pricing"] = {
        "label": "Length-of-stay Based Pricing",
        "value_text": "Custom",
        "detail_text": "Length of Stay Setting Stay Length Premium/Discount >1 10% >2 0% >4 -10%",
        "detail_lines": [
            "Length of Stay Setting",
            "Stay Length",
            "Premium/Discount",
            ">1",
            "10%",
            ">2",
            "0%",
            ">4",
            "-10%",
        ],
    }
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
    assert snapshot["last_minute_rule"]["percent"] == 10
    assert snapshot["last_minute_rule"]["within_days"] == 1
    assert snapshot["minimum_stay_settings"]["profile_name"] == "EffortSaver - Revenue Optimized"
    assert snapshot["minimum_stay_settings"]["last_minute"]["within_nights"] == 7
    assert snapshot["minimum_stay_settings"]["orphan_gaps"]["gap_max_nights"] == 2
    assert snapshot["safety_minimum_price_rule"]["percent_of_last_year_same_day_adr"] == 110
    assert snapshot["safety_minimum_price_rule"]["beyond_days"] == 180
    assert snapshot["occupancy_based_adjustments"]["mode"] == "Market Driven"
    assert snapshot["occupancy_based_adjustments_snapshot"]["days_0_15"]["adjustment"] == "8% discount"
    assert snapshot["length_of_stay_based_pricing"]["1_night"] == "10% premium"
    assert snapshot["length_of_stay_based_pricing"]["4_plus_nights"] == "10% discount"
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
        "Custom"
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


def test_settings_changes_ignores_ui_metadata_fields() -> None:
    prior = settings_snapshot.build_snapshot(
        ui_settings_payload(),
        run_date="2026-05-13",
        source_file=Path("prior.json"),
    )
    current = settings_snapshot.build_snapshot(
        ui_settings_payload(),
        run_date="2026-05-14",
        source_file=Path("current.json"),
    )
    current["captured_at_utc"] = "changed timestamp"
    current["source_url"] = "changed url"
    current["settings_source"] = "changed source"
    current["raw_ui_settings"] = {"changed": True}

    rows = settings_changes.build_change_rows(
        current,
        prior,
        run_date="2026-05-14",
        prior_run_date="2026-05-13",
    )

    assert rows == []


def test_settings_changes_detects_normalized_oba_and_far_out_changes() -> None:
    prior = settings_snapshot.build_snapshot(
        ui_settings_payload(),
        run_date="2026-05-13",
        source_file=Path("prior.json"),
    )
    current_payload = ui_settings_payload()
    current_payload["settings"]["occupancy_based_adjustments"]["detail_text"] = (
        "10% premium for next 0 to 15 days Occupancy 12% above market "
        "14% discount for next 16 to 30 days Occupancy 16% below market "
        "14% discount for next 31 to 60 days Occupancy 15% below market"
    )
    current_payload["settings"]["far_out_premium"]["value_text"] = "After 90 days, flat premium of 10.0%"
    current = settings_snapshot.build_snapshot(
        current_payload,
        run_date="2026-05-14",
        source_file=Path("current.json"),
    )

    rows = settings_changes.build_change_rows(
        current,
        prior,
        run_date="2026-05-14",
        prior_run_date="2026-05-13",
    )
    changed_fields = {row["field_name"] for row in rows}

    assert "occupancy_based_adjustments_snapshot" in changed_fields
    assert "far_out_premium" in changed_fields
    assert "raw_ui_settings" not in changed_fields


def test_settings_changes_compares_normalized_los_not_custom_summary() -> None:
    prior = settings_snapshot.build_snapshot(
        ui_settings_payload(),
        run_date="2026-05-13",
        source_file=Path("prior.json"),
    )
    current = settings_snapshot.build_snapshot(
        ui_settings_payload(),
        run_date="2026-05-14",
        source_file=Path("current.json"),
    )

    rows = settings_changes.build_change_rows(
        current,
        prior,
        run_date="2026-05-14",
        prior_run_date="2026-05-13",
    )

    assert rows == []
    assert current["length_of_stay_based_pricing"]["raw_text"] != "Custom"
