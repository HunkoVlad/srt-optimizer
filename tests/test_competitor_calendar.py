import csv
from pathlib import Path

from pricelabs.transform import competitor_calendar


RUN_DATE = "2026-05-25"


def write_calendar(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def sample_calendar_rows() -> list[list[str]]:
    return [
        [
            "Unnamed: 0",
            "Lake retreat - hot tub (31588567)",
            "Lake retreat - hot tub (31588567).1",
            "Lake retreat - hot tub (31588567).2",
            "Your Listing - Aloha Poconos.",
            "Your Listing - Aloha Poconos..1",
            "Your Listing - Aloha Poconos..2",
        ],
        ["", "prices", "available", "min_stay", "prices", "available", "min_stay"],
        ["Date", "", "", "", "", "", ""],
        ["2026-05-27", "447", "1", "1", "313", "0", "1"],
        ["2026-05-28", "", "1", "", "394", "0", ""],
        ["2026-05-29", "489", "", "2", "532", "1", "1"],
    ]


def long_calendar_rows(day_count: int = 95) -> list[list[str]]:
    rows = sample_calendar_rows()[:3]
    from datetime import date, timedelta

    start = date(2026, 5, 27)
    for offset in range(day_count):
        stay_date = start + timedelta(days=offset)
        rows.append([stay_date.isoformat(), str(100 + offset), "1", "2", str(300 + offset), "1", "1"])
    return rows


def run_transform(tmp_path: Path, rows: list[list[str]] | None = None) -> tuple[Path, Path, list[dict[str, str]], list[dict[str, str]]]:
    input_file = tmp_path / "data" / "runs" / RUN_DATE / "raw" / "Competitor Calendar.csv"
    list_output = tmp_path / "data" / "runs" / RUN_DATE / "raw" / f"pricelabs_competitor_list_{RUN_DATE}.csv"
    calendar_output = tmp_path / "data" / "runs" / RUN_DATE / "analysis" / f"pricelabs_competitor_calendar_{RUN_DATE}.csv"
    write_calendar(input_file, rows or sample_calendar_rows())

    competitor_calendar.transform(
        RUN_DATE,
        input_file=input_file,
        competitor_list_output=list_output,
        calendar_output=calendar_output,
    )
    return list_output, calendar_output, read_rows(list_output), read_rows(calendar_output)


def test_detects_listing_triplets_from_wide_calendar_export(tmp_path: Path) -> None:
    input_file = tmp_path / "Competitor Calendar.csv"
    write_calendar(input_file, sample_calendar_rows())
    fieldnames, _rows = competitor_calendar.read_rows(input_file)

    triplets = competitor_calendar.detect_listing_triplets(fieldnames)

    assert len(triplets) == 2
    assert triplets[0].price_column == "Lake retreat - hot tub (31588567)"
    assert triplets[0].available_column == "Lake retreat - hot tub (31588567).1"
    assert triplets[0].min_stay_column == "Lake retreat - hot tub (31588567).2"


def test_mangles_duplicate_export_headers_like_pandas() -> None:
    fieldnames = competitor_calendar.mangle_fieldnames(
        [
            "",
            "Lake retreat - hot tub (31588567)",
            "Lake retreat - hot tub (31588567)",
            "Lake retreat - hot tub (31588567)",
        ]
    )

    assert fieldnames == [
        "Unnamed: 0",
        "Lake retreat - hot tub (31588567)",
        "Lake retreat - hot tub (31588567).1",
        "Lake retreat - hot tub (31588567).2",
    ]


def test_extracts_competitor_name_and_listing_id_from_headers() -> None:
    name, listing_id = competitor_calendar.extract_listing_name_and_id("Lake retreat - hot tub (31588567)")
    subject_name, subject_id = competitor_calendar.extract_listing_name_and_id("Your Listing - Aloha Poconos.")

    assert name == "Lake retreat - hot tub"
    assert listing_id == "31588567"
    assert subject_name == "Your Listing - Aloha Poconos"
    assert subject_id == ""


def test_builds_airbnb_url_from_listing_id(tmp_path: Path) -> None:
    _list_output, _calendar_output, list_rows, calendar_rows = run_transform(tmp_path)

    assert list_rows[0]["airbnb_url"] == "https://www.airbnb.com/rooms/31588567"
    assert calendar_rows[0]["airbnb_url"] == "https://www.airbnb.com/rooms/31588567"
    assert list_rows[1]["airbnb_url"] == ""


def test_creates_one_row_per_listing_competitor_list(tmp_path: Path) -> None:
    list_output, _calendar_output, list_rows, _calendar_rows = run_transform(tmp_path)

    assert list_output.exists()
    assert len(list_rows) == 2
    assert list_rows[0]["competitor_name"] == "Lake retreat - hot tub"
    assert list_rows[0]["competitor_listing_id"] == "31588567"
    assert list_rows[0]["sample_date"] == "2026-05-27"
    assert list_rows[0]["competitor_price"] == "447"
    assert list_rows[0]["competitor_min_stay"] == "1"


def test_creates_one_row_per_listing_per_date_normalized_calendar(tmp_path: Path) -> None:
    _list_output, calendar_output, _list_rows, calendar_rows = run_transform(tmp_path)

    assert calendar_output.exists()
    assert len(calendar_rows) == 6
    assert calendar_rows[0] == {
        "run_date": RUN_DATE,
        "stay_date": "2026-05-27",
        "competitor_name": "Lake retreat - hot tub",
        "competitor_listing_id": "31588567",
        "airbnb_url": "https://www.airbnb.com/rooms/31588567",
        "is_subject_listing": "false",
        "competitor_price": "447",
        "competitor_available": "1",
        "competitor_min_stay": "1",
        "source_file": str(tmp_path / "data" / "runs" / RUN_DATE / "raw" / "Competitor Calendar.csv"),
    }


def test_prefers_staging_file_over_raw_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    staging = Path("data") / "runs" / RUN_DATE / "downloads_staging" / "pricelabs" / "Competitor Calendar.csv"
    raw = Path("data") / "runs" / RUN_DATE / "raw" / "Competitor Calendar.csv"
    staging_rows = sample_calendar_rows()
    raw_rows = sample_calendar_rows()
    raw_rows[0][1] = "Raw fallback listing (999999)"
    raw_rows[0][2] = "Raw fallback listing (999999).1"
    raw_rows[0][3] = "Raw fallback listing (999999).2"
    write_calendar(staging, staging_rows)
    write_calendar(raw, raw_rows)

    _list_path, _calendar_path, _list_count, _calendar_count, source_status, cleanup_status = (
        competitor_calendar.transform_for_run_date(RUN_DATE)
    )
    list_rows = read_rows(Path("data") / "runs" / RUN_DATE / "raw" / f"pricelabs_competitor_list_{RUN_DATE}.csv")

    assert source_status == "staging"
    assert cleanup_status == "deleted_staging_input"
    assert list_rows[0]["competitor_name"] == "Lake retreat - hot tub"


def test_raw_fallback_still_works_when_staging_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    raw = Path("data") / "runs" / RUN_DATE / "raw" / "Competitor Calendar.csv"
    write_calendar(raw, sample_calendar_rows())

    _list_path, _calendar_path, list_count, calendar_count, source_status, cleanup_status = (
        competitor_calendar.transform_for_run_date(RUN_DATE)
    )

    assert source_status == "raw_fallback"
    assert cleanup_status == "not_applicable"
    assert list_count == 2
    assert calendar_count == 6
    assert raw.exists()


def test_missing_competitor_calendar_is_optional(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    list_path, calendar_path, list_count, calendar_count, source_status, cleanup_status = (
        competitor_calendar.transform_for_run_date(RUN_DATE)
    )

    assert list_path is None
    assert calendar_path is None
    assert list_count == 0
    assert calendar_count == 0
    assert source_status == "missing"
    assert cleanup_status == "not_applicable"


def test_normalized_calendar_output_is_limited_to_90_day_horizon(tmp_path: Path) -> None:
    _list_output, _calendar_output, _list_rows, calendar_rows = run_transform(tmp_path, long_calendar_rows())

    assert len(calendar_rows) == 182
    assert calendar_rows[0]["stay_date"] == "2026-05-27"
    assert calendar_rows[-1]["stay_date"] == "2026-08-25"


def test_staged_competitor_calendar_is_deleted_after_successful_transform(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    staging = Path("data") / "runs" / RUN_DATE / "downloads_staging" / "pricelabs" / "Competitor Calendar.csv"
    write_calendar(staging, sample_calendar_rows())

    _list_path, _calendar_path, _list_count, _calendar_count, source_status, cleanup_status = (
        competitor_calendar.transform_for_run_date(RUN_DATE)
    )

    assert source_status == "staging"
    assert cleanup_status == "deleted_staging_input"
    assert not staging.exists()
    assert (Path("data") / "runs" / RUN_DATE / "raw" / f"pricelabs_competitor_list_{RUN_DATE}.csv").exists()
    assert (Path("data") / "runs" / RUN_DATE / "analysis" / f"pricelabs_competitor_calendar_{RUN_DATE}.csv").exists()


def test_staged_competitor_calendar_is_kept_after_transform_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    staging = Path("data") / "runs" / RUN_DATE / "downloads_staging" / "pricelabs" / "Competitor Calendar.csv"
    write_calendar(staging, [["Unnamed: 0", "not_a_triplet"], ["2026-05-27", "123"]])

    try:
        competitor_calendar.transform_for_run_date(RUN_DATE)
    except ValueError:
        pass

    assert staging.exists()


def test_marks_your_listing_as_subject_listing(tmp_path: Path) -> None:
    _list_output, _calendar_output, list_rows, calendar_rows = run_transform(tmp_path)

    subject = next(row for row in list_rows if row["competitor_name"] == "Your Listing - Aloha Poconos")
    subject_calendar = next(row for row in calendar_rows if row["competitor_name"] == "Your Listing - Aloha Poconos")

    assert subject["is_subject_listing"] == "true"
    assert subject_calendar["is_subject_listing"] == "true"
    assert subject["sample_date"] == "2026-05-29"
    assert subject["competitor_price"] == "532"


def test_handles_missing_prices_min_stay_and_availability_without_crashing(tmp_path: Path) -> None:
    _list_output, _calendar_output, list_rows, calendar_rows = run_transform(tmp_path)

    missing_calendar = next(
        row
        for row in calendar_rows
        if row["stay_date"] == "2026-05-28" and row["competitor_name"] == "Lake retreat - hot tub"
    )

    assert missing_calendar["competitor_price"] == ""
    assert missing_calendar["competitor_min_stay"] == ""
    assert list_rows[0]["sample_date"] == "2026-05-27"


def test_does_not_invent_rating_review_count_or_cleaning_fee(tmp_path: Path) -> None:
    _list_output, _calendar_output, list_rows, _calendar_rows = run_transform(tmp_path)

    for row in list_rows:
        assert row["bedrooms"] == ""
        assert row["rating"] == ""
        assert row["review_count"] == ""
        assert row["cleaning_fee"] == ""
        assert row["airbnb_service_fee_type"] == ""


def test_output_is_diagnostic_and_does_not_include_recommendation_fields(tmp_path: Path) -> None:
    _list_output, _calendar_output, list_rows, calendar_rows = run_transform(tmp_path)
    combined_columns = set(list_rows[0]) | set(calendar_rows[0])

    assert "recommendation" not in " ".join(combined_columns).lower()
    assert "rule_change" not in " ".join(combined_columns).lower()
