import csv
from pathlib import Path

from analysis import listing_competitor_review


RUN_DATE = "2026-05-25"
TEMPLATE_PATH = Path("sample_data") / "pricelabs_competitor_list_template.csv"


def write_issue_tracker(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "issue_id",
        "issue_title",
        "first_seen_run_date",
        "last_seen_run_date",
        "status",
        "severity",
        "source_type",
        "signal_type",
        "current_value",
        "previous_value",
        "wow_change",
        "four_week_average",
        "weeks_open",
        "evidence_summary",
        "suspected_cause",
        "recommended_investigation",
        "blocked_recommendation_reason",
        "resolution_rule",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_competitor_list(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "competitor_name",
        "airbnb_url",
        "bedrooms",
        "rating",
        "review_count",
        "cleaning_fee",
        "airbnb_service_fee_type",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_competitor_calendar(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "run_date",
        "stay_date",
        "competitor_name",
        "competitor_listing_id",
        "airbnb_url",
        "is_subject_listing",
        "competitor_price",
        "competitor_available",
        "competitor_min_stay",
        "source_file",
    ]
    rows = [
        [RUN_DATE, "2026-05-27", "Comp A", "111", "https://www.airbnb.com/rooms/111", "false", "200", "1", "2", "source.csv"],
        [RUN_DATE, "2026-05-28", "Comp A", "111", "https://www.airbnb.com/rooms/111", "false", "220", "1", "2", "source.csv"],
        [RUN_DATE, "2026-05-27", "Comp B", "222", "https://www.airbnb.com/rooms/222", "false", "300", "1", "3", "source.csv"],
        [RUN_DATE, "2026-05-28", "Comp B", "222", "https://www.airbnb.com/rooms/222", "false", "320", "0", "3", "source.csv"],
        [RUN_DATE, "2026-05-27", "Your Listing - Aloha Poconos", "", "", "true", "400", "1", "4", "source.csv"],
        [RUN_DATE, "2026-05-28", "Your Listing - Aloha Poconos", "", "", "true", "420", "1", "4", "source.csv"],
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(columns)
        writer.writerows(rows)


def active_visibility_issue() -> dict[str, str]:
    return {
        "issue_id": "airbnb_visibility_up_conversion_down",
        "issue_title": "Airbnb visibility up, conversion down",
        "first_seen_run_date": RUN_DATE,
        "last_seen_run_date": RUN_DATE,
        "status": "open",
        "severity": "high",
        "source_type": "airbnb_diagnostic",
        "signal_type": "visibility_up_conversion_down",
        "current_value": "3535",
        "previous_value": "489",
        "wow_change": "3046",
        "four_week_average": "654",
        "weeks_open": "1",
        "evidence_summary": (
            "First-page search impressions increased sharply: 3535 vs 489. "
            "Conversion weakened / remained weak."
        ),
        "suspected_cause": "listing competitiveness / value perception / booking friction",
        "recommended_investigation": "Review listing against competitors before changing PriceLabs rules.",
        "blocked_recommendation_reason": "Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation.",
        "resolution_rule": "Keep open until conversion improves for 2 consecutive runs.",
        "notes": "Diagnostic issue only; no recommendation action is created.",
    }


def run_review(
    tmp_path: Path,
    issue_rows: list[dict[str, str]] | None = None,
    competitor_rows: list[dict[str, str]] | None = None,
    with_competitor_calendar: bool = False,
) -> tuple[Path, Path, list[dict[str, str]], str]:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    issue_file = run_dir / "analysis" / f"diagnostic_issue_tracker_{RUN_DATE}.csv"
    if issue_rows is not None:
        write_issue_tracker(issue_file, issue_rows)
    if competitor_rows is not None:
        write_competitor_list(run_dir / "raw" / f"pricelabs_competitor_list_{RUN_DATE}.csv", competitor_rows)
    if with_competitor_calendar:
        write_competitor_calendar(run_dir / "analysis" / f"pricelabs_competitor_calendar_{RUN_DATE}.csv")

    markdown_path, csv_path = listing_competitor_review.run(RUN_DATE, run_dir=run_dir)
    return markdown_path, csv_path, read_rows(csv_path), markdown_path.read_text(encoding="utf-8")


def test_pricelabs_competitor_list_template_exists_with_expected_columns() -> None:
    with TEMPLATE_PATH.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = reader.fieldnames or []

    assert columns[:8] == [
        "competitor_name",
        "airbnb_url",
        "bedrooms",
        "rating",
        "review_count",
        "cleaning_fee",
        "airbnb_service_fee_type",
        "notes",
    ]
    assert {"sample_date", "competitor_price", "competitor_min_stay", "visible_total_price_notes"}.issubset(columns)


def test_generates_markdown_and_csv_for_active_visibility_issue(tmp_path: Path) -> None:
    markdown_path, csv_path, rows, markdown = run_review(tmp_path, [active_visibility_issue()])

    assert markdown_path.exists()
    assert csv_path.exists()
    assert "# Listing Competitor Review - 2026-05-25" in markdown
    assert "Airbnb visibility increased sharply, but conversion weakened or remained weak" in markdown
    assert "Review listing against competitors before changing PriceLabs rules." in markdown
    assert len(rows) == len(listing_competitor_review.RUBRIC_ROWS)


def test_csv_contains_expected_rubric_areas(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, _markdown = run_review(tmp_path, [active_visibility_issue()])

    areas = {row["review_area"] for row in rows}

    assert {
        "search_card_appeal",
        "cover_photo_first_five_photos",
        "title_description_opening",
        "amenities_presentation",
        "guest_fit_sleeping_capacity",
        "trust_review_signals",
        "booking_friction_risks",
        "competitor_comparison",
    }.issubset(areas)


def test_report_includes_guardrails_and_does_not_create_price_rule_change(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, markdown = run_review(tmp_path, [active_visibility_issue()])

    assert "This review should focus on listing presentation" in markdown
    assert "Airbnb diagnostics can identify conversion friction, but they cannot create PriceLabs rule recommendations" in markdown
    assert "Do not use this listing review to create automatic PriceLabs rule changes." in markdown
    assert all(row["price_rule_change_allowed"] == "false" for row in rows)


def test_no_competitor_findings_are_invented(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, markdown = run_review(tmp_path, [active_visibility_issue()])
    combined_text = markdown + "\n" + "\n".join(str(row) for row in rows)

    assert "No competitor findings are inferred in V1" in combined_text
    assert "unless actual competitor data is provided" in combined_text
    assert "competitor is better" not in combined_text.lower()
    assert "competitors are cheaper" not in combined_text.lower()


def test_review_includes_pricelabs_competitor_set_when_input_exists(tmp_path: Path) -> None:
    competitor_rows = [
        {
            "competitor_name": "Lakeview Chalet",
            "airbnb_url": "https://www.airbnb.com/rooms/111",
            "bedrooms": "3",
            "rating": "4.96",
            "review_count": "84",
            "cleaning_fee": "0",
            "airbnb_service_fee_type": "split",
            "notes": "Selected in PriceLabs Competitor Calendar.",
        },
        {
            "competitor_name": "Forest Spa Cabin",
            "airbnb_url": "https://www.airbnb.com/rooms/222",
            "bedrooms": "4",
            "rating": "4.91",
            "review_count": "126",
            "cleaning_fee": "125",
            "airbnb_service_fee_type": "guest",
            "notes": "Manual review reference.",
        },
    ]

    _markdown_path, _csv_path, rows, markdown = run_review(tmp_path, [active_visibility_issue()], competitor_rows)

    assert "## Competitor Set" in markdown
    assert "manually selected PriceLabs Competitor Calendar set" in markdown
    assert "Lakeview Chalet" in markdown
    assert "https://www.airbnb.com/rooms/111" in markdown
    assert "Forest Spa Cabin" in markdown
    assert "https://www.airbnb.com/rooms/222" in markdown
    assert "Use this competitor set when working through the review rubric." in markdown
    assert {row["price_rule_change_allowed"] for row in rows} == {"false"}


def test_review_works_when_pricelabs_competitor_list_is_missing(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, markdown = run_review(tmp_path, [active_visibility_issue()])

    assert rows
    assert "## Competitor Set" in markdown
    assert "No PriceLabs competitor list was provided for this run." in markdown


def test_competitor_urls_are_reference_context_not_findings(tmp_path: Path) -> None:
    competitor_rows = [
        {
            "competitor_name": "Reference Cabin",
            "airbnb_url": "https://www.airbnb.com/rooms/333",
            "bedrooms": "3",
            "rating": "4.90",
            "review_count": "50",
            "cleaning_fee": "0",
            "airbnb_service_fee_type": "split",
            "notes": "Reference only.",
        }
    ]

    _markdown_path, _csv_path, rows, markdown = run_review(tmp_path, [active_visibility_issue()], competitor_rows)
    combined_text = markdown + "\n" + "\n".join(str(row) for row in rows)

    assert "https://www.airbnb.com/rooms/333" in markdown
    assert "not scraped findings" in markdown
    assert "Do not infer strengths or weaknesses unless manual observations are added." in markdown
    assert "Reference Cabin is stronger" not in combined_text
    assert "Reference Cabin is weaker" not in combined_text


def test_listing_review_includes_competitor_calendar_context_when_file_exists(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, markdown = run_review(
        tmp_path,
        [active_visibility_issue()],
        with_competitor_calendar=True,
    )

    assert "## PriceLabs Competitor Calendar Context" in markdown
    assert "90-day window: 2026-05-27 to 2026-05-28." in markdown
    assert "Selected competitors: 2." in markdown
    assert "Competitor median average price over available dates: 255." in markdown
    assert "Competitor median min stay: 2.5." in markdown
    assert "Competitor median available date count: 1.5." in markdown
    assert "Subject listing metrics are intentionally excluded here because PriceLabs core outputs are the source of truth" in markdown
    assert "This is diagnostic context from selected PriceLabs competitors only." in markdown
    assert "Subject listing average price over available dates" not in markdown
    assert "Subject listing average min stay" not in markdown
    assert "Subject listing available date count" not in markdown
    context_row = next(row for row in rows if row["review_area"] == "competitor_calendar_context")
    assert context_row["price_rule_change_allowed"] == "false"
    assert "Review competitor price/min-stay/availability context" in context_row["suggested_investigation"]


def test_listing_review_works_when_competitor_calendar_missing(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, markdown = run_review(tmp_path, [active_visibility_issue()])

    assert "## PriceLabs Competitor Calendar Context" in markdown
    assert "No normalized PriceLabs competitor calendar context was available for this run." in markdown
    assert "competitor_calendar_context" not in {row["review_area"] for row in rows}


def test_competitor_calendar_context_does_not_invent_findings_or_rule_changes(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, markdown = run_review(
        tmp_path,
        [active_visibility_issue()],
        with_competitor_calendar=True,
    )
    combined_text = markdown + "\n" + "\n".join(str(row) for row in rows)

    assert "does not create price-rule recommendations" in combined_text
    assert "Subject listing metrics are intentionally excluded" in combined_text
    assert "lower price" not in combined_text.lower()
    assert "raise price" not in combined_text.lower()
    assert "competitor listing is better" not in combined_text.lower()
    assert {row["price_rule_change_allowed"] for row in rows} == {"false"}


def test_missing_diagnostic_issue_tracker_does_not_crash(tmp_path: Path) -> None:
    markdown_path, csv_path, rows, markdown = run_review(tmp_path)

    assert markdown_path.exists()
    assert csv_path.exists()
    assert rows == []
    assert "No active listing competitor review issue was found for this run." in markdown


def test_no_active_issue_produces_safe_no_review_output(tmp_path: Path) -> None:
    resolved = active_visibility_issue()
    resolved["status"] = "resolved"

    _markdown_path, _csv_path, rows, markdown = run_review(tmp_path, [resolved])

    assert rows == []
    assert "No active listing competitor review issue was found for this run." in markdown
    assert "No listing-side or PriceLabs rule recommendation is created by this report." in markdown


def test_price_rule_change_allowed_false_for_all_v1_rows(tmp_path: Path) -> None:
    _markdown_path, _csv_path, rows, _markdown = run_review(tmp_path, [active_visibility_issue()])

    assert rows
    assert {row["price_rule_change_allowed"] for row in rows} == {"false"}
