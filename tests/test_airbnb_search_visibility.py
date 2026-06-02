import csv
from pathlib import Path

from analysis import airbnb_search_visibility


RUN_DATE = "2026-06-01"


def write_input(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=airbnb_search_visibility.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def visibility_row(
    scenario_name: str,
    *,
    found_status: str = "found",
    max_pages_checked: str = "15",
    page_number: str = "4",
    position_on_page: str = "8",
    cover_photo_status: str = "",
) -> dict[str, str]:
    row = {column: "" for column in airbnb_search_visibility.COLUMNS}
    row.update(
        {
            "run_date": RUN_DATE,
            "search_timestamp": "2026-06-01T10:00:00",
            "browser_mode": "manual",
            "logged_in_status": "logged_out",
            "search_location": "Pocono Mountains, PA",
            "date_rule": "flexible_weekend_next_target_month",
            "guest_count": "8",
            "scenario_name": scenario_name,
            "filters_used": "none",
            "found_status": found_status,
            "max_pages_checked": max_pages_checked,
            "page_number": page_number,
            "position_on_page": position_on_page,
            "cover_photo_status": cover_photo_status,
            "visible_title": "Pocono Spa Escape",
        }
    )
    return row


def test_template_exists_with_expected_columns() -> None:
    with Path("sample_data/airbnb_search_visibility_input_template.csv").open("r", newline="", encoding="utf-8") as csv_file:
        columns = next(csv.reader(csv_file))

    assert columns == airbnb_search_visibility.COLUMNS


def test_module_generates_markdown_and_csv_when_input_exists(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_input(
        run_dir / "raw" / f"airbnb_search_visibility_input_{RUN_DATE}.csv",
        [
            visibility_row("broad_no_filters", found_status="not_found", page_number="", position_on_page=""),
            visibility_row("broad_high_intent_filters", page_number="4"),
        ],
    )

    csv_path, md_path = airbnb_search_visibility.run(RUN_DATE, run_dir=run_dir)
    output_rows = read_rows(csv_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert csv_path.exists()
    assert md_path.exists()
    assert "broad_not_found" in output_rows[0]["classifications"]
    assert "high_intent_found" in output_rows[1]["classifications"]
    assert "filtered_visibility_improved" in output_rows[1]["classifications"]
    assert "## High-Intent Filter Visibility" in markdown


def test_missing_input_does_not_fail(tmp_path: Path) -> None:
    csv_path, md_path = airbnb_search_visibility.run(RUN_DATE, run_dir=tmp_path / "run")

    assert csv_path is None
    assert md_path is None


def test_empty_input_does_not_fail(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_input(run_dir / "raw" / f"airbnb_search_visibility_input_{RUN_DATE}.csv", [])

    csv_path, md_path = airbnb_search_visibility.run(RUN_DATE, run_dir=run_dir)

    assert csv_path is None
    assert md_path is None


def test_broad_not_found_classification_works() -> None:
    rows = airbnb_search_visibility.classified_rows(
        [visibility_row("broad_no_filters", found_status="not_found", page_number="", position_on_page="", max_pages_checked="15")]
    )

    assert rows[0]["classifications"] == "broad_not_found"


def test_high_intent_found_and_deep_classifications_work() -> None:
    rows = airbnb_search_visibility.classified_rows(
        [visibility_row("broad_high_intent_filters", found_status="found", page_number="4")]
    )

    assert "high_intent_found" in rows[0]["classifications"]
    assert "high_intent_found_deep" in rows[0]["classifications"]


def test_possible_cover_photo_cache_issue_classification_works() -> None:
    rows = airbnb_search_visibility.classified_rows(
        [visibility_row("broad_high_intent_filters", cover_photo_status="old_cover_after_change")]
    )

    assert "possible_cover_photo_cache_issue" in rows[0]["classifications"]
