import base64
import csv
from pathlib import Path

from marketing import stayfi_anniversary_email as stayfi
from marketing import stayfi_gmail_drafts as gmail_drafts


RUN_DATE = "2026-07-07"


class FakeCreateCall:
    def __init__(self, draft_id: str | None = None, error: Exception | None = None) -> None:
        self.draft_id = draft_id
        self.error = error

    def execute(self) -> dict[str, str]:
        if self.error:
            raise self.error
        return {"id": self.draft_id or ""}


class FakeDrafts:
    def __init__(self, service) -> None:
        self.service = service

    def create(self, userId: str, body: dict) -> FakeCreateCall:
        self.service.created_bodies.append({"userId": userId, "body": body})
        if self.service.errors:
            return FakeCreateCall(error=self.service.errors.pop(0))
        draft_id = self.service.ids.pop(0) if self.service.ids else "draft-default"
        return FakeCreateCall(draft_id=draft_id)


class FakeUsers:
    def __init__(self, service) -> None:
        self.service = service

    def drafts(self) -> FakeDrafts:
        return FakeDrafts(self.service)


class FakeGmailService:
    def __init__(self, ids: list[str] | None = None, errors: list[Exception] | None = None) -> None:
        self.ids = ids or []
        self.errors = errors or []
        self.created_bodies: list[dict] = []

    def users(self) -> FakeUsers:
        return FakeUsers(self)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def create_input_files(run_dir: Path, log_file: Path) -> None:
    candidate = {
        "email": "guest@example.com",
        "first_name": "Ana",
        "last_name": "Guest",
        "first_sign_in": "2025-07-11",
        "property": "Aloha Poconos",
        "email_status": "Valid",
        "email_opt_in_consent": "Yes",
        "guest_rating": "5",
        "eligibility_status": "eligible",
        "exclusion_reason": "",
    }
    draft = {
        "email": "guest@example.com",
        "first_name": "Ana",
        "subject": "Thinking about another Pocono getaway?",
        "body": "Hi Ana,\n\nCome back soon.",
        "draft_status": "draft_prepared_manual_gmail_creation",
        "gmail_draft_id": "",
        "created_at": "2026-07-07T00:00:00+00:00",
    }
    summary = {
        column: ""
        for column in [*stayfi.SUMMARY_COLUMNS, "gmail_draft_failures"]
    }
    summary.update(
        {
            "run_date": RUN_DATE,
            "anniversary_audience_window_start": "2025-07-07",
            "anniversary_audience_window_end": "2025-07-13",
            "drafts_prepared_csv": "1",
            "gmail_drafts_created": "0",
            "gmail_draft_failures": "0",
            "skipped_duplicates_from_log": "0",
        }
    )
    write_csv(stayfi.candidate_path(RUN_DATE, run_dir), [candidate], stayfi.CANDIDATE_COLUMNS)
    write_csv(stayfi.draft_path(RUN_DATE, run_dir), [draft], stayfi.DRAFT_COLUMNS)
    write_csv(stayfi.summary_path(RUN_DATE, run_dir), [summary], [*stayfi.SUMMARY_COLUMNS, "gmail_draft_failures"])
    stayfi.ensure_log_exists(log_file)


def test_create_gmail_draft_uses_drafts_create_not_send() -> None:
    service = FakeGmailService(ids=["draft-1"])

    draft_id = gmail_drafts.create_gmail_draft(
        service,
        to_email="guest@example.com",
        subject="Hello",
        body="Body",
        sender_email="owner@example.com",
    )

    assert draft_id == "draft-1"
    assert len(service.created_bodies) == 1
    body = service.created_bodies[0]["body"]
    assert "raw" in body["message"]
    decoded = base64.urlsafe_b64decode(body["message"]["raw"]).decode("utf-8")
    assert "To: guest@example.com" in decoded
    assert "Subject: Hello" in decoded
    assert not hasattr(service.users(), "send")


def test_successful_gmail_draft_updates_results_summary_and_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    service = FakeGmailService(ids=["draft-123"])

    results_path = gmail_drafts.create_drafts_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    summary = read_csv(stayfi.summary_path(RUN_DATE, run_dir))[0]
    log_rows = read_csv(log_file)
    assert results[0]["draft_status"] == "gmail_draft_created"
    assert results[0]["gmail_draft_id"] == "draft-123"
    assert summary["gmail_drafts_created"] == "1"
    assert summary["drafts_created"] == "1"
    assert summary["gmail_draft_failures"] == "0"
    assert log_rows[0]["email"] == "guest@example.com"
    assert log_rows[0]["gmail_draft_id"] == "draft-123"
    assert log_rows[0]["sent_manually"] == "false"


def test_failed_gmail_draft_does_not_update_permanent_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    service = FakeGmailService(errors=[RuntimeError("api failed")])

    results_path = gmail_drafts.create_drafts_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    summary = read_csv(stayfi.summary_path(RUN_DATE, run_dir))[0]
    assert results[0]["draft_status"] == "failed"
    assert "api failed" in results[0]["error_message"]
    assert read_csv(log_file) == []
    assert summary["gmail_drafts_created"] == "0"
    assert summary["gmail_draft_failures"] == "1"


def test_logged_gmail_draft_id_skips_duplicate_without_creating_draft(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    write_csv(
        log_file,
        [
            {
                "email": "guest@example.com",
                "first_name": "Ana",
                "original_first_sign_in": "2025-07-11",
                "report_week_start": "2026-07-07",
                "report_week_end": "2026-07-13",
                "draft_created_at": "2026-07-07T00:00:00+00:00",
                "sent_manually": "false",
                "gmail_draft_id": "existing-draft",
            }
        ],
        stayfi.LOG_COLUMNS,
    )
    service = FakeGmailService(ids=["draft-should-not-create"])

    results_path = gmail_drafts.create_drafts_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    summary = read_csv(stayfi.summary_path(RUN_DATE, run_dir))[0]
    assert results[0]["draft_status"] == "skipped_duplicate_logged"
    assert service.created_bodies == []
    assert summary["skipped_duplicates_from_log"] == "1"
    assert summary["gmail_drafts_created"] == "0"


def test_sent_manually_log_row_skips_duplicate_without_creating_draft(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    write_csv(
        log_file,
        [
            {
                "email": "guest@example.com",
                "first_name": "Ana",
                "original_first_sign_in": "2025-07-11",
                "report_week_start": "2026-07-07",
                "report_week_end": "2026-07-13",
                "draft_created_at": "",
                "sent_manually": "true",
                "gmail_draft_id": "",
            }
        ],
        stayfi.LOG_COLUMNS,
    )
    service = FakeGmailService(ids=["draft-should-not-create"])

    results_path = gmail_drafts.create_drafts_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    assert results[0]["draft_status"] == "skipped_duplicate_logged"
    assert service.created_bodies == []


def test_invalid_draft_input_fails_without_gmail_call_or_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    drafts = read_csv(stayfi.draft_path(RUN_DATE, run_dir))
    drafts[0]["email"] = "bad"
    write_csv(stayfi.draft_path(RUN_DATE, run_dir), drafts, stayfi.DRAFT_COLUMNS)
    service = FakeGmailService(ids=["draft-should-not-create"])

    results_path = gmail_drafts.create_drafts_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    assert results[0]["draft_status"] == "failed"
    assert results[0]["error_message"] == "invalid_email"
    assert service.created_bodies == []
    assert read_csv(log_file) == []


def test_gmail_draft_creation_is_explicit_and_never_uses_send() -> None:
    project_root = Path(__file__).resolve().parents[1]
    module_text = (project_root / "src" / "marketing" / "stayfi_gmail_drafts.py").read_text(encoding="utf-8")
    wrapper_text = (project_root / "scripts" / "create_stayfi_gmail_drafts.ps1").read_text(encoding="utf-8")
    weekly_pipeline_text = (project_root / "run_weekly_pipeline.ps1").read_text(encoding="utf-8")
    pyproject_text = (project_root / "pyproject.toml").read_text(encoding="utf-8")

    assert ".send(" not in module_text
    assert "marketing.stayfi_gmail_drafts" in wrapper_text
    assert "pip install google-api-python-client google-auth google-auth-oauthlib" in wrapper_text
    assert "marketing.stayfi_gmail_drafts" not in weekly_pipeline_text
    assert '"google-api-python-client"' in pyproject_text
    assert '"google-auth"' in pyproject_text
    assert '"google-auth-oauthlib"' in pyproject_text
