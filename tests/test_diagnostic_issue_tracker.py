import csv
from pathlib import Path

from analysis import diagnostic_issue_tracker


RUN_DATE = "2026-05-25"


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = fieldnames or (list(rows[0]) if rows else ["run_date", "field_name", "changed_flag"])
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def history_rows(
    *,
    impressions_current: str = "3535",
    impressions_previous: str = "489",
    impressions_change: str = "3046",
    search_change: str = "-26.51",
    booking_change: str = "-2.49",
) -> list[dict[str, str]]:
    return [
        {
            "run_date": RUN_DATE,
            "metric_window_start": "2026-05-17",
            "metric_window_end": "2026-05-24",
            "metric_name": "first_page_search_impressions",
            "current_value": impressions_current,
            "previous_week_value": impressions_previous,
            "change_vs_previous_week": impressions_change,
            "last_4_week_avg": "654",
        },
        {
            "run_date": RUN_DATE,
            "metric_window_start": "2026-05-17",
            "metric_window_end": "2026-05-24",
            "metric_name": "search_to_listing_conversion_rate",
            "current_value": "9.48%",
            "previous_week_value": "35.99",
            "change_vs_previous_week": search_change,
            "last_4_week_avg": "40.91",
        },
        {
            "run_date": RUN_DATE,
            "metric_window_start": "2026-05-17",
            "metric_window_end": "2026-05-24",
            "metric_name": "listing_to_booking_conversion_rate",
            "current_value": "1.49%",
            "previous_week_value": "3.98",
            "change_vs_previous_week": booking_change,
            "last_4_week_avg": "2.36",
        },
    ]


def run_tracker(
    tmp_path: Path,
    *,
    airbnb_rows: list[dict[str, str]] | None = None,
    settings_rows: list[dict[str, str]] | None = None,
    existing_history_rows: list[dict[str, str]] | None = None,
) -> tuple[Path, Path, list[dict[str, str]]]:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "diagnostic_issue_tracker.csv"
    if airbnb_rows is not None:
        write_csv(run_dir / "analysis" / f"airbnb_weekly_history_comparison_{RUN_DATE}.csv", airbnb_rows)
    if settings_rows is not None:
        write_csv(run_dir / "settings" / f"pricelabs_settings_changes_{RUN_DATE}.csv", settings_rows)
    if existing_history_rows is not None:
        write_csv(history_file, existing_history_rows, diagnostic_issue_tracker.COLUMNS)

    output = diagnostic_issue_tracker.run(RUN_DATE, run_dir=run_dir, history_file=history_file)
    return output, history_file, read_rows(output)


def test_creates_issue_when_visibility_up_more_than_3x_and_conversion_weakens(tmp_path: Path) -> None:
    output, history_file, rows = run_tracker(tmp_path, airbnb_rows=history_rows(), settings_rows=[])

    assert output.exists()
    assert history_file.exists()
    assert len(rows) == 1
    row = rows[0]
    assert row["issue_id"] == "airbnb_visibility_up_conversion_down"
    assert row["status"] == "open"
    assert row["severity"] == "high"
    assert row["source_type"] == "airbnb_diagnostic"
    assert row["signal_type"] == "visibility_up_conversion_down"
    assert row["current_value"] == "3535"
    assert row["previous_value"] == "489"
    assert "First-page search impressions increased sharply: 3535 vs 489" in row["evidence_summary"]
    assert "Conversion weakened / remained weak" in row["evidence_summary"]
    assert "PriceLabs rules did not materially change" in row["evidence_summary"]
    assert row["suspected_cause"] == "listing competitiveness / value perception / booking friction"
    assert row["recommended_investigation"] == "Review listing against competitors before changing PriceLabs rules."
    assert row["blocked_recommendation_reason"] == "Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation."


def test_does_not_create_issue_when_visibility_does_not_increase_sharply(tmp_path: Path) -> None:
    _output, history_file, rows = run_tracker(
        tmp_path,
        airbnb_rows=history_rows(impressions_current="900", impressions_previous="489", impressions_change="411"),
        settings_rows=[],
    )

    assert rows == []
    assert history_file.exists()
    assert read_rows(history_file) == []


def test_carries_open_issue_forward_from_history(tmp_path: Path) -> None:
    existing = {
        "issue_id": "airbnb_visibility_up_conversion_down",
        "issue_title": "Airbnb visibility up, conversion down",
        "first_seen_run_date": "2026-05-18",
        "last_seen_run_date": "2026-05-18",
        "status": "open",
        "severity": "high",
        "source_type": "airbnb_diagnostic",
        "signal_type": "visibility_up_conversion_down",
        "current_value": "1200",
        "previous_value": "300",
        "wow_change": "900",
        "four_week_average": "400",
        "weeks_open": "1",
        "evidence_summary": "Prior issue.",
        "suspected_cause": "listing competitiveness / value perception / booking friction",
        "recommended_investigation": "Review listing against competitors before changing PriceLabs rules.",
        "blocked_recommendation_reason": "Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation.",
        "resolution_rule": "Keep open until conversion improves for 2 consecutive runs; V1 does not auto-resolve.",
        "notes": "Prior note.",
    }

    _output, _history_file, rows = run_tracker(
        tmp_path,
        airbnb_rows=history_rows(impressions_current="900", impressions_previous="489", impressions_change="411"),
        settings_rows=[],
        existing_history_rows=[existing],
    )

    assert len(rows) == 1
    assert rows[0]["status"] == "monitoring"
    assert rows[0]["first_seen_run_date"] == "2026-05-18"
    assert rows[0]["last_seen_run_date"] == RUN_DATE
    assert rows[0]["weeks_open"] == "2"
    assert "Carried forward" in rows[0]["notes"]


def test_rerunning_same_run_date_does_not_increment_weeks_open(tmp_path: Path) -> None:
    output, history_file, rows = run_tracker(tmp_path, airbnb_rows=history_rows(), settings_rows=[])
    assert rows[0]["weeks_open"] == "1"

    output = diagnostic_issue_tracker.run(RUN_DATE, run_dir=tmp_path / "data" / "runs" / RUN_DATE, history_file=history_file)
    rerun_rows = read_rows(output)
    history = read_rows(history_file)

    assert rerun_rows[0]["weeks_open"] == "1"
    assert len([row for row in history if row["issue_id"] == "airbnb_visibility_up_conversion_down"]) == 1


def test_missing_airbnb_files_does_not_crash_and_creates_empty_outputs(tmp_path: Path) -> None:
    output, history_file, rows = run_tracker(tmp_path)

    assert output.exists()
    assert history_file.exists()
    assert rows == []
    assert read_rows(history_file) == []


def test_meaningful_pricelabs_rule_change_blocks_new_airbnb_issue(tmp_path: Path) -> None:
    _output, _history_file, rows = run_tracker(
        tmp_path,
        airbnb_rows=history_rows(),
        settings_rows=[
            {
                "run_date": RUN_DATE,
                "field_name": "minimum_stay_rules",
                "changed_flag": "true",
            }
        ],
    )

    assert rows == []


def test_non_mapped_settings_change_does_not_block_2026_05_25_style_issue(tmp_path: Path) -> None:
    _output, _history_file, rows = run_tracker(
        tmp_path,
        airbnb_rows=history_rows(),
        settings_rows=[
            {
                "run_date": RUN_DATE,
                "field_name": "occupancy_based_adjustments_snapshot",
                "changed_flag": "true",
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["issue_id"] == "airbnb_visibility_up_conversion_down"


def test_issue_tracker_output_does_not_create_recommendation_actions(tmp_path: Path) -> None:
    _output, _history_file, rows = run_tracker(tmp_path, airbnb_rows=history_rows(), settings_rows=[])
    text = "\n".join(str(value) for row in rows for value in row.values()).lower()

    assert "blocked_recommendation_reason" not in text
    assert "cannot create pricelabs rule recommendation" in text
    assert "change pricelabs rule" not in text
    assert "lower price" not in text
    assert "raise price" not in text
