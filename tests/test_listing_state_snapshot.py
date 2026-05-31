import csv
from pathlib import Path

from analysis import listing_state_snapshot


RUN_DATE = "2026-05-25"


def write_snapshot_input(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: "" for column in listing_state_snapshot.SNAPSHOT_INPUT_COLUMNS}
    row.update(
        {
            "snapshot_date": RUN_DATE,
            "snapshot_reason": "Baseline before listing-side review.",
            "related_issue_id": "airbnb_visibility_up_conversion_down",
            "listing_title": "Aloha Poconos",
            "cover_photo_description": "Exterior hero with hot tub.",
            "first_5_photos_summary": "Exterior, living room, kitchen, bedroom, hot tub.",
            "opening_description_text": "Premium family getaway near the lake.",
            "top_amenities_presented": "Hot tub; game room; fire pit",
            "guest_capacity": "10",
            "bedrooms": "4",
            "bathrooms": "3",
            "rating": "4.95",
            "review_count": "86",
            "minimum_stay_visible": "2 nights",
            "main_value_proposition": "Premium family retreat.",
        }
    )
    row.update(
        {
            "full_description_text": "Full listing description captured manually.",
            "booking_widget_notes": "Booking widget shows all-fees price.",
            "fees_visibility_notes": "No cleaning fee visible.",
            "trust_signal_notes": "Guest Favorite and review count visible.",
            "booking_friction_notes": "Minimum stay not confirmed from screenshot.",
        }
    )
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=listing_state_snapshot.SNAPSHOT_INPUT_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def write_old_format_snapshot_input(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: "" for column in listing_state_snapshot.BASE_SNAPSHOT_INPUT_COLUMNS}
    row.update(
        {
            "snapshot_date": RUN_DATE,
            "related_issue_id": "airbnb_visibility_up_conversion_down",
            "listing_title": "Aloha Poconos",
            "opening_description_text": "Old format opening copy.",
        }
    )
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=listing_state_snapshot.BASE_SNAPSHOT_INPUT_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def test_listing_state_snapshot_input_template_has_expected_columns() -> None:
    template = Path("sample_data/listing_state_snapshot_input_template.csv")
    with template.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        columns = next(reader)

    assert columns == listing_state_snapshot.SNAPSHOT_INPUT_COLUMNS


def test_listing_change_log_template_has_expected_columns() -> None:
    template = Path("sample_data/listing_change_log_template.csv")
    with template.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        columns = next(reader)

    assert columns == listing_state_snapshot.CHANGE_LOG_COLUMNS


def test_listing_state_snapshot_generates_markdown_when_input_exists(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    history_file = tmp_path / "data" / "history" / "listing_change_log.csv"
    write_snapshot_input(run_dir / "raw" / f"listing_state_snapshot_input_{RUN_DATE}.csv")

    output = listing_state_snapshot.run(RUN_DATE, run_dir=run_dir, history_file=history_file)
    markdown = output.read_text(encoding="utf-8")

    assert output.exists()
    assert "# Listing State Snapshot - 2026-05-25" in markdown
    assert "Related diagnostic issue: airbnb_visibility_up_conversion_down" in markdown
    assert "Listing title: Aloha Poconos" in markdown
    assert "Cover photo description: Exterior hero with hot tub." in markdown
    assert "Minimum stay visible: 2 nights" in markdown
    assert "## Page Copy And Booking Context" in markdown
    assert "Full description text: Full listing description captured manually." in markdown
    assert "Booking widget notes: Booking widget shows all-fees price." in markdown
    assert "Fees visibility notes: No cleaning fee visible." in markdown
    assert history_file.exists()


def test_listing_state_snapshot_old_format_csv_still_generates(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_old_format_snapshot_input(run_dir / "raw" / f"listing_state_snapshot_input_{RUN_DATE}.csv")

    output = listing_state_snapshot.run(RUN_DATE, run_dir=run_dir)
    markdown = output.read_text(encoding="utf-8")

    assert "Listing title: Aloha Poconos" in markdown
    assert "Opening description text: Old format opening copy." in markdown
    assert "## Page Copy And Booking Context" not in markdown
    assert "Full description text:" not in markdown


def test_listing_state_snapshot_omits_empty_page_context_fields(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_old_format_snapshot_input(run_dir / "raw" / f"listing_state_snapshot_input_{RUN_DATE}.csv")

    output = listing_state_snapshot.run(RUN_DATE, run_dir=run_dir)
    markdown = output.read_text(encoding="utf-8")

    for column in listing_state_snapshot.PAGE_COPY_CONTEXT_COLUMNS:
        assert f"{column.replace('_', ' ').capitalize()}:" not in markdown


def test_listing_state_snapshot_generates_safe_placeholder_when_input_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    output = listing_state_snapshot.run(RUN_DATE, run_dir=run_dir)
    markdown = output.read_text(encoding="utf-8")

    assert "No manual listing snapshot input was provided for this run." in markdown
    assert "Structured listing state unavailable for this run." in markdown
    assert "does not create PriceLabs rule recommendations" in markdown


def test_listing_state_snapshot_lists_available_visual_files(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / f"listing_search_card_{RUN_DATE}.png").write_bytes(b"png")
    (analysis_dir / f"listing_first_5_photos_{RUN_DATE}.png").write_bytes(b"png")

    output = listing_state_snapshot.run(RUN_DATE, run_dir=run_dir)
    markdown = output.read_text(encoding="utf-8")

    assert "listing_search_card_2026-05-25.png" in markdown
    assert "listing_first_5_photos_2026-05-25.png" in markdown
    assert "listing_page_top_2026-05-25.png" not in markdown


def test_listing_state_snapshot_allows_page_top_as_first_five_photos_baseline(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / f"listing_search_card_{RUN_DATE}.png").write_bytes(b"png")
    (analysis_dir / f"listing_page_top_{RUN_DATE}.png").write_bytes(b"png")

    output = listing_state_snapshot.run(RUN_DATE, run_dir=run_dir)
    markdown = output.read_text(encoding="utf-8")

    assert "listing_search_card_2026-05-25.png" in markdown
    assert "listing_page_top_2026-05-25.png" in markdown
    assert "listing_first_5_photos_2026-05-25.png" not in markdown
    assert "If listing_page_top shows the Airbnb hero grid, it can serve as the first-5-photos baseline." in markdown
    assert "Search-card screenshots should use consistent parameters each run" in markdown
    assert "Search: Pocono Mountains, PA" in markdown
