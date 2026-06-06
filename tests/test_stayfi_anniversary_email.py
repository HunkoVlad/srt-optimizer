import csv
from pathlib import Path

from marketing import stayfi_anniversary_email as stayfi


RUN_DATE = "2026-06-01"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_stayfi(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "Email",
        "First Name",
        "Last Name",
        "First Sign In",
        "Property",
        "Email Status",
        "Email Opt-in Consent",
        "Guest Rating",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def stayfi_row(
    email: str = "guest@example.com",
    first_name: str = "Ana",
    first_sign_in: str = "2025-06-03",
    property_name: str = "Aloha Poconos",
    email_status: str = "Valid",
    opt_in: str = "Yes",
    rating: str = "5",
) -> dict[str, str]:
    return {
        "Email": email,
        "First Name": first_name,
        "Last Name": "Guest",
        "First Sign In": first_sign_in,
        "Property": property_name,
        "Email Status": email_status,
        "Email Opt-in Consent": opt_in,
        "Guest Rating": rating,
    }


def test_weekly_window_shifts_report_week_back_one_year() -> None:
    window = stayfi.weekly_window("2026-06-01")

    assert window.report_week_start.isoformat() == "2026-06-01"
    assert window.report_week_end.isoformat() == "2026-06-07"
    assert window.audience_start.isoformat() == "2025-06-01"
    assert window.audience_end.isoformat() == "2025-06-07"


def test_default_stayfi_input_uses_source_folder() -> None:
    assert stayfi.default_stayfi_input() == Path("data") / "source" / "stayfi" / "stayfi_guests_2026.csv"


def test_workflow_creates_candidate_draft_and_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    stayfi_file = run_dir / "raw" / "StayFi Guests.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    write_stayfi(stayfi_file, [stayfi_row()])

    candidates_path, drafts_path, summary_path, log_path = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    candidates = read_csv(candidates_path)
    drafts = read_csv(drafts_path)
    summary = read_csv(summary_path)[0]
    debug_rows = read_csv(stayfi.debug_path(RUN_DATE, run_dir))
    assert candidates[0]["eligibility_status"] == "eligible"
    assert drafts[0]["email"] == "guest@example.com"
    assert drafts[0]["subject"] == "Thinking about another Pocono getaway?"
    assert "Airbnb listing:\nhttps://www.airbnb.com/rooms/1313377469848413047" in drafts[0]["body"]
    assert "Book direct here:\nhttps://alohapoconos.com" in drafts[0]["body"]
    assert "ALOHA" in drafts[0]["body"]
    assert drafts[0]["draft_status"] == "draft_prepared_manual_gmail_creation"
    assert summary["eligible_guests"] == "1"
    assert summary["drafts_created"] == "0"
    assert summary["drafts_prepared_csv"] == "1"
    assert summary["gmail_drafts_created"] == "0"
    assert summary["source_file_status"] == "available"
    assert summary["detected_columns"]
    assert summary["date_column_used"] == "First Sign In"
    assert summary["email_column_used"] == "Email"
    assert summary["rows_in_audience_window"] == "1"
    assert debug_rows[0]["email_parsed"] == "guest@example.com"
    assert debug_rows[0]["first_sign_in_parsed"] == "2025-06-03"
    assert read_csv(log_path) == []


def test_missing_default_source_creates_empty_outputs_without_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"

    candidates_path, drafts_path, summary_path, log_path = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=None,
        log_file=log_file,
    )

    summary = read_csv(summary_path)[0]
    assert read_csv(candidates_path) == []
    assert read_csv(drafts_path) == []
    assert log_path.exists()
    assert summary["total_stayfi_rows_checked"] == "0"
    assert summary["eligible_guests"] == "0"
    assert summary["drafts_created"] == "0"
    assert summary["drafts_prepared_csv"] == "0"
    assert summary["gmail_drafts_created"] == "0"
    assert summary["source_file_status"] == "missing"
    assert summary["stayfi_input_file"] == str(Path("data") / "source" / "stayfi" / "stayfi_guests_2026.csv")
    assert read_csv(stayfi.debug_path(RUN_DATE, run_dir)) == []


def test_alternate_stayfi_headers_are_supported(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / "2026-07-07"
    stayfi_file = tmp_path / "data" / "source" / "stayfi" / "stayfi_guests_2026.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    rows = [
        {
            "Contact Email": "july@example.com",
            "First": "July",
            "Last": "Guest",
            "First Seen": "2025-07-10",
            "Location": "Aloha Poconos",
            "Status": "Valid",
            "Opt-in": "Yes",
            "Airbnb Rating": "4",
        }
    ]
    stayfi.write_csv(stayfi_file, rows, list(rows[0].keys()))

    candidates_path, drafts_path, summary_path, _ = stayfi.run_workflow(
        "2026-07-07",
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    candidates = read_csv(candidates_path)
    drafts = read_csv(drafts_path)
    summary = read_csv(summary_path)[0]
    debug_rows = read_csv(stayfi.debug_path("2026-07-07", run_dir))
    assert candidates[0]["eligibility_status"] == "eligible"
    assert drafts[0]["email"] == "july@example.com"
    assert summary["date_column_used"] == "First Seen"
    assert summary["email_column_used"] == "Contact Email"
    assert summary["rows_in_audience_window"] == "1"
    assert debug_rows[0]["first_sign_in_parsed"] == "2025-07-10"


def test_real_stayfi_export_headers_use_emails_and_full_name(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / "2026-07-07"
    stayfi_file = tmp_path / "data" / "source" / "stayfi" / "stayfi_guests_2026.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    rows = [
        {
            "Full Name": "Real Guest",
            "Emails": "backup@example.com; real@example.com",
            "Phone numbers": "",
            "18+": "Yes",
            "Email Status": "Valid",
            "Property": "Aloha Poconos",
            "Property Group": "",
            "First Sign In": "Jul 11, 2025",
            "Email Opt-in Consent": "Yes",
            "Source": "",
            "Rating": "5",
            "Next Booking Arrival": "",
            "Next Booking Departure": "",
            "Next Booking Property": "",
            "Next Booking Source": "",
            "Last Booking Arrival": "",
            "Last Booking Departure": "",
            "Last Booking Property": "",
            "Last Booking Source": "",
        }
    ]
    stayfi.write_csv(stayfi_file, rows, list(rows[0].keys()))

    candidates_path, drafts_path, summary_path, _ = stayfi.run_workflow(
        "2026-07-07",
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    candidate = read_csv(candidates_path)[0]
    draft = read_csv(drafts_path)[0]
    summary = read_csv(summary_path)[0]
    debug_row = read_csv(stayfi.debug_path("2026-07-07", run_dir))[0]
    assert candidate["email"] == "backup@example.com"
    assert candidate["first_name"] == "Real"
    assert candidate["last_name"] == "Guest"
    assert draft["body"].startswith("Hi Real,")
    assert summary["source_file_status"] == "available"
    assert summary["total_stayfi_rows_checked"] == "1"
    assert summary["rows_in_audience_window"] == "1"
    assert summary["eligible_guests"] == "1"
    assert summary["email_column_used"] == "Emails"
    assert debug_row["first_sign_in_parsed"] == "2025-07-11"


def test_available_source_with_missing_required_columns_writes_warning_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    stayfi_file = tmp_path / "data" / "source" / "stayfi" / "stayfi_guests_2026.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    rows = [{"Email": "guest@example.com", "First Name": "Ana"}]
    stayfi.write_csv(stayfi_file, rows, list(rows[0].keys()))

    _, drafts_path, summary_path, _ = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    summary = read_csv(summary_path)[0]
    assert read_csv(drafts_path) == []
    assert summary["source_file_status"] == "available_but_missing_columns"
    assert "first_sign_in" in summary["missing_required_columns"]
    assert "property" in summary["missing_required_columns"]
    assert "detected_columns" in summary


def test_invalid_email_no_opt_in_bad_rating_and_duplicates_are_excluded(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    stayfi_file = run_dir / "raw" / "stayfi_export.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    stayfi.write_csv(
        log_file,
        [
            {
                "email": "duplicate@example.com",
                "first_name": "Dup",
                "original_first_sign_in": "2025-06-02",
                "report_week_start": "2025-06-09",
                "report_week_end": "2025-06-15",
                "draft_created_at": "2025-06-09T00:00:00+00:00",
                "sent_manually": "false",
                "gmail_draft_id": "draft-123",
            }
        ],
        stayfi.LOG_COLUMNS,
    )
    write_stayfi(
        stayfi_file,
        [
            stayfi_row(email="bad", rating="5"),
            stayfi_row(email="noopt@example.com", opt_in="No", rating="5"),
            stayfi_row(email="badreview@example.com", rating="3"),
            stayfi_row(email="duplicate@example.com", rating="5"),
        ],
    )

    candidates_path, drafts_path, summary_path, _ = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    candidates = read_csv(candidates_path)
    summary = read_csv(summary_path)[0]
    assert read_csv(drafts_path) == []
    assert {row["eligibility_status"] for row in candidates} == {"excluded"}
    assert summary["excluded_invalid_emails"] == "0"
    assert summary["excluded_missing_email"] == "1"
    assert summary["excluded_no_opt_in"] == "1"
    assert summary["excluded_bad_rating"] == "1"
    assert summary["skipped_duplicates"] == "1"
    assert summary["skipped_duplicates_from_log"] == "1"


def test_blank_gmail_draft_id_log_rows_do_not_block_future_preparation(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    stayfi_file = run_dir / "raw" / "stayfi_export.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    stayfi.write_csv(
        log_file,
        [
            {
                "email": "guest@example.com",
                "first_name": "Ana",
                "original_first_sign_in": "2025-06-03",
                "report_week_start": "2026-06-01",
                "report_week_end": "2026-06-07",
                "draft_created_at": "2026-06-01T00:00:00+00:00",
                "sent_manually": "false",
                "gmail_draft_id": "",
            }
        ],
        stayfi.LOG_COLUMNS,
    )
    write_stayfi(stayfi_file, [stayfi_row()])

    candidates_path, drafts_path, summary_path, _ = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    candidate = read_csv(candidates_path)[0]
    summary = read_csv(summary_path)[0]
    assert candidate["eligibility_status"] == "eligible"
    assert read_csv(drafts_path)[0]["email"] == "guest@example.com"
    assert summary["skipped_duplicates_from_log"] == "0"
    assert summary["drafts_prepared_csv"] == "1"
    assert summary["gmail_drafts_created"] == "0"


def test_missing_email_and_date_parse_failed_are_counted_in_debug_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    stayfi_file = run_dir / "raw" / "stayfi.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    write_stayfi(
        stayfi_file,
        [
            stayfi_row(email="", rating="5"),
            stayfi_row(email="bad-date@example.com", first_sign_in="not a date", rating="5"),
            stayfi_row(email="wrong@example.com", property_name="Other Property", rating="5"),
        ],
    )

    candidates_path, drafts_path, summary_path, _ = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    summary = read_csv(summary_path)[0]
    debug_rows = read_csv(stayfi.debug_path(RUN_DATE, run_dir))
    assert read_csv(drafts_path) == []
    assert len(read_csv(candidates_path)) == 2
    assert summary["excluded_missing_email"] == "1"
    assert summary["excluded_wrong_property"] == "1"
    assert summary["date_parse_failed"] == "1"
    assert any(row["exclusion_reason"] == "date_parse_failed" for row in debug_rows)


def test_missing_rating_is_logged_but_does_not_exclude(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    stayfi_file = run_dir / "raw" / "stayfi.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    write_stayfi(stayfi_file, [stayfi_row(rating="")])

    candidates_path, drafts_path, summary_path, _ = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    candidate = read_csv(candidates_path)[0]
    summary = read_csv(summary_path)[0]
    assert candidate["eligibility_status"] == "eligible"
    assert candidate["exclusion_reason"] == "rating_missing"
    assert read_csv(drafts_path)[0]["email"] == "guest@example.com"
    assert summary["rating_missing"] == "1"


def test_duplicate_emails_keep_most_recent_matching_record(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    stayfi_file = run_dir / "raw" / "stayfi.csv"
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    write_stayfi(
        stayfi_file,
        [
            stayfi_row(email="same@example.com", first_name="Old", first_sign_in="2025-06-01"),
            stayfi_row(email="same@example.com", first_name="New", first_sign_in="2025-06-07"),
        ],
    )

    candidates_path, _, _, _ = stayfi.run_workflow(
        RUN_DATE,
        run_dir=run_dir,
        stayfi_file=stayfi_file,
        log_file=log_file,
    )

    candidates = read_csv(candidates_path)
    assert len(candidates) == 1
    assert candidates[0]["first_name"] == "New"
