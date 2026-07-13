import csv
from pathlib import Path

from analysis import active_tests


RUN_DATE = "2026-06-29"


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return list(csv.DictReader(csv_file))


def active_row(
    test_id: str,
    test_type: str,
    status: str,
    *,
    change_date: str = "2026-06-22",
    review_after_run_date: str = "2026-07-14",
    source: str = "manual_log",
) -> dict[str, str]:
    return {
        "test_id": test_id,
        "canonical_test_id": test_id,
        "test_type": test_type,
        "duplicate_group_key": test_id,
        "change_date": change_date,
        "run_date_started": change_date,
        "related_issue_id": "",
        "change_area": test_id,
        "old_value": "old",
        "new_value": "new",
        "reason": "reason",
        "expected_effect": "expected",
        "primary_success_metrics": "metric",
        "guardrails": "guardrail",
        "review_after_run_date": review_after_run_date,
        "status": status,
        "review_due": "false",
        "source": source,
        "merged_from_test_ids": "",
        "supporting_changes": "",
        "notes": "",
    }


def write_active_history(path: Path) -> None:
    write_csv(
        path,
        [
            active_row("title_photo_search_card_test", "listing", "active", review_after_run_date="2026-07-07"),
            active_row("pricelabs_los_pricing_test", "pricelabs", "superseded", review_after_run_date="2026-07-14"),
            active_row(
                "competitiveness_booking_friction_test",
                "pricelabs",
                "active",
                change_date="2026-06-29",
                review_after_run_date="2026-07-21",
                source="user_declared",
            ),
        ],
        active_tests.COLUMNS,
    )


def test_active_tests_history_is_priority_source_and_preserves_expected_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "active_tests.csv"
    write_active_history(history_file)

    output = active_tests.run(RUN_DATE, run_dir=run_dir, history_file=history_file)
    rows = read_csv(output)

    assert [(row["test_id"], row["test_type"], row["status"], row["review_after_run_date"]) for row in rows] == [
        ("title_photo_search_card_test", "listing", "active", "2026-07-07"),
        ("pricelabs_los_pricing_test", "pricelabs", "superseded", "2026-07-14"),
        ("competitiveness_booking_friction_test", "pricelabs", "active", "2026-07-21"),
    ]


def test_superseded_history_row_cannot_be_reactivated_by_listing_log_fallback(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "active_tests.csv"
    listing_log_file = tmp_path / "data" / "history" / "listing_change_log.csv"
    write_active_history(history_file)
    write_csv(
        listing_log_file,
        [
            {
                "change_date": "2026-06-22",
                "run_date": "2026-06-29",
                "related_issue_id": "multinight_value_friction_no_cleaning_fee",
                "change_type": "pricelabs_los_pricing_test",
                "old_value": "old",
                "new_value": "1 night +15%",
                "reason": "old fallback",
                "expected_effect": "old effect",
                "status": "active",
                "review_after_run_date": "2026-07-14",
                "notes": "",
            }
        ],
        [
            "change_date",
            "run_date",
            "related_issue_id",
            "change_type",
            "old_value",
            "new_value",
            "reason",
            "expected_effect",
            "status",
            "review_after_run_date",
            "notes",
        ],
    )

    output = active_tests.run(RUN_DATE, run_dir=run_dir, history_file=history_file, listing_change_log_file=listing_log_file)
    rows = read_csv(output)

    los_row = next(row for row in rows if row["test_id"] == "pricelabs_los_pricing_test")
    assert los_row["status"] == "superseded"
    assert "old fallback" not in los_row["reason"]


def test_malformed_listing_change_input_is_skipped_and_logged(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "active_tests.csv"
    write_active_history(history_file)
    write_csv(
        run_dir / "raw" / f"listing_change_input_{RUN_DATE}.csv",
        [
            {
                "change_date": RUN_DATE,
                "change_type": "pricelabs_los_pricing",
                "old_value": "",
                "new_value": "1 night +15%",
                "reason": "",
                "expected_effect": "",
                "review_after_run_date": "2026-07-06",
                "notes": "",
            }
        ],
        active_tests.LISTING_CHANGE_INPUT_COLUMNS,
    )

    output = active_tests.run(RUN_DATE, run_dir=run_dir, history_file=history_file)
    rows = read_csv(output)
    captured = capsys.readouterr().out

    assert len(rows) == 3
    assert "skipped_malformed_input" in captured
    assert f"Source raw/listing_change_input_{RUN_DATE}.csv rows: 1, valid: 0, skipped_malformed: 1" in captured


def test_listing_change_log_fallback_used_only_when_active_history_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    listing_log_file = tmp_path / "data" / "history" / "listing_change_log.csv"
    write_csv(
        listing_log_file,
        [
            {
                "change_date": "2026-05-29",
                "run_date": "2026-06-01",
                "related_issue_id": "airbnb_visibility_up_conversion_down",
                "change_type": "amenity_pool_section_overview_guest_access_photo_order_and_self_checkin",
                "old_value": "",
                "new_value": "old listing test",
                "reason": "",
                "expected_effect": "old effect",
                "status": "active",
                "review_after_run_date": "2026-06-08",
                "notes": "",
            }
        ],
        [
            "change_date",
            "run_date",
            "related_issue_id",
            "change_type",
            "old_value",
            "new_value",
            "reason",
            "expected_effect",
            "status",
            "review_after_run_date",
            "notes",
        ],
    )

    output = active_tests.run(
        RUN_DATE,
        run_dir=run_dir,
        history_file=tmp_path / "data" / "history" / "missing_active_tests.csv",
        listing_change_log_file=listing_log_file,
    )
    rows = read_csv(output)

    assert rows[0]["test_id"] == "amenity_pool_section_overview_guest_access_photo_order_and_self_checkin"


def test_newer_valid_user_declared_row_can_supersede_history_row(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "active_tests.csv"
    write_csv(
        history_file,
        [active_row("competitiveness_booking_friction_test", "pricelabs", "monitoring", change_date="2026-06-15")],
        active_tests.COLUMNS,
    )
    write_csv(
        run_dir / "raw" / f"listing_change_input_{RUN_DATE}.csv",
        [
            active_row(
                "competitiveness_booking_friction_test",
                "pricelabs",
                "active",
                change_date="2026-06-29",
                review_after_run_date="2026-07-21",
                source="user_declared",
            )
        ],
        active_tests.COLUMNS,
    )

    output = active_tests.run(RUN_DATE, run_dir=run_dir, history_file=history_file)
    rows = read_csv(output)

    assert rows[0]["test_id"] == "competitiveness_booking_friction_test"
    assert rows[0]["status"] == "active"
    assert rows[0]["review_after_run_date"] == "2026-07-21"


def test_booking_friction_test_is_not_merged_into_superseded_los_test(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "active_tests.csv"
    los_row = active_row(
        "pricelabs_los_pricing_test",
        "pricelabs",
        "superseded",
        change_date="2026-06-22",
        review_after_run_date="2026-07-14",
    )
    booking_friction_row = active_row(
        "competitiveness_booking_friction_test",
        "pricelabs",
        "active",
        change_date="2026-07-01",
        review_after_run_date="2026-07-21",
        source="user_declared",
    )
    booking_friction_row["duplicate_group_key"] = "booking_friction_competitiveness"
    booking_friction_row["change_area"] = "booking_friction_price_rules"
    booking_friction_row["old_value"] = "LOS pricing 1 night +15%, 2 nights -5%, 3 nights -10%, 4+ nights -15%."
    booking_friction_row["new_value"] = "LOS pricing 1 night +5%, 2 nights 0%, 3 nights -5%, 4+ nights -15%."
    write_csv(history_file, [los_row, booking_friction_row], active_tests.COLUMNS)

    output = active_tests.run(RUN_DATE, run_dir=run_dir, history_file=history_file)
    rows = read_csv(output)

    assert [(row["test_id"], row["status"]) for row in rows] == [
        ("pricelabs_los_pricing_test", "superseded"),
        ("competitiveness_booking_friction_test", "active"),
    ]


def test_settings_snapshot_los_change_merges_into_active_booking_friction_test(tmp_path: Path) -> None:
    run_date = "2026-07-06"
    run_dir = tmp_path / "data" / "runs" / run_date
    history_file = tmp_path / "data" / "history" / "active_tests.csv"
    booking_friction_row = active_row(
        "competitiveness_booking_friction_test",
        "pricelabs",
        "active",
        change_date="2026-07-01",
        review_after_run_date="2026-07-21",
        source="user_declared",
    )
    booking_friction_row["duplicate_group_key"] = "booking_friction_competitiveness"
    booking_friction_row["change_area"] = "booking_friction_price_rules"
    booking_friction_row["new_value"] = (
        "Extra guest fee after 10 guests; LOS pricing 1 night +5%, 2 nights 0%, "
        "3 nights -5%, 4+ nights -15%; pet fee effectively removed."
    )
    booking_friction_row["reason"] = "Booking friction and value perception test."
    write_csv(history_file, [booking_friction_row], active_tests.COLUMNS)
    write_csv(
        run_dir / "settings" / f"pricelabs_settings_changes_{run_date}.csv",
        [
            {
                "listing_id": "650255___717243",
                "field_name": "length_of_stay_based_pricing",
                "changed_flag": "true",
                "previous_value": '{"1_night":"15% premium","2_nights":"5% discount"}',
                "current_value": '{"1_night":"5% premium","2_nights":"0%"}',
            }
        ],
        ["listing_id", "field_name", "changed_flag", "previous_value", "current_value"],
    )

    output = active_tests.run(run_date, run_dir=run_dir, history_file=history_file)
    rows = read_csv(output)

    assert len(rows) == 1
    row = rows[0]
    assert row["test_id"] == "competitiveness_booking_friction_test"
    assert row["status"] == "active"
    assert row["review_after_run_date"] == "2026-07-21"
    assert row["merged_from_test_ids"] == "pricelabs_length_of_stay_based_pricing"
    assert row["supporting_changes"] == "pricelabs_length_of_stay_based_pricing"
    assert "source=settings_snapshot" not in row["notes"]
    assert '{"1_night":"5% premium","2_nights":"0%"}' not in row["notes"]


def test_persisted_settings_snapshot_los_row_merges_into_active_booking_friction_test(tmp_path: Path) -> None:
    run_date = "2026-07-06"
    run_dir = tmp_path / "data" / "runs" / run_date
    history_file = tmp_path / "data" / "history" / "active_tests.csv"
    booking_friction_row = active_row(
        "competitiveness_booking_friction_test",
        "pricelabs",
        "active",
        change_date="2026-07-01",
        review_after_run_date="2026-07-21",
        source="user_declared",
    )
    booking_friction_row["duplicate_group_key"] = "booking_friction_competitiveness"
    booking_friction_row["new_value"] = "Booking friction test with LOS pricing 1 night +5%, 2 nights 0%."
    settings_snapshot_row = active_row(
        "pricelabs_length_of_stay_based_pricing",
        "pricelabs",
        "active",
        change_date="2026-07-06",
        review_after_run_date="",
        source="settings_snapshot",
    )
    settings_snapshot_row["change_area"] = "pricelabs_length_of_stay_based_pricing"
    settings_snapshot_row["new_value"] = '{"1_night":"5% premium","2_nights":"0%"}'
    write_csv(history_file, [booking_friction_row, settings_snapshot_row], active_tests.COLUMNS)

    output = active_tests.run(run_date, run_dir=run_dir, history_file=history_file)
    rows = read_csv(output)

    assert len(rows) == 1
    assert rows[0]["test_id"] == "competitiveness_booking_friction_test"
    assert rows[0]["merged_from_test_ids"] == "pricelabs_length_of_stay_based_pricing"
    assert rows[0]["supporting_changes"] == "pricelabs_length_of_stay_based_pricing"
