import base64
import csv
from pathlib import Path

from marketing import stayfi_anniversary_email as stayfi
from marketing import stayfi_gmail_send as gmail_send


RUN_DATE = "2026-07-07"


class FakeSendCall:
    def __init__(self, message_id: str | None = None, error: Exception | None = None) -> None:
        self.message_id = message_id
        self.error = error

    def execute(self) -> dict[str, str]:
        if self.error:
            raise self.error
        return {"id": self.message_id or ""}


class FakeMessages:
    def __init__(self, service) -> None:
        self.service = service

    def send(self, userId: str, body: dict) -> FakeSendCall:
        self.service.sent_bodies.append({"userId": userId, "body": body})
        if self.service.errors:
            return FakeSendCall(error=self.service.errors.pop(0))
        message_id = self.service.ids.pop(0) if self.service.ids else "message-default"
        return FakeSendCall(message_id=message_id)


class FakeUsers:
    def __init__(self, service) -> None:
        self.service = service

    def messages(self) -> FakeMessages:
        return FakeMessages(self.service)


class FakeGmailService:
    def __init__(self, ids: list[str] | None = None, errors: list[Exception] | None = None) -> None:
        self.ids = ids or []
        self.errors = errors or []
        self.sent_bodies: list[dict] = []

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
    summary = {column: "" for column in [*stayfi.SUMMARY_COLUMNS, "gmail_draft_failures"]}
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


def test_send_gmail_message_uses_messages_send() -> None:
    service = FakeGmailService(ids=["msg-1"])

    message_id = gmail_send.send_gmail_message(
        service,
        to_email="guest@example.com",
        subject="Hello",
        body="Body",
        sender_email="owner@example.com",
    )

    assert message_id == "msg-1"
    assert len(service.sent_bodies) == 1
    body = service.sent_bodies[0]["body"]
    assert "raw" in body
    decoded = base64.urlsafe_b64decode(body["raw"]).decode("utf-8")
    assert "To: guest@example.com" in decoded
    assert "Subject: Hello" in decoded


def test_successful_send_updates_results_summary_and_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    service = FakeGmailService(ids=["msg-123"])

    results_path = gmail_send.send_emails_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    summary = read_csv(stayfi.summary_path(RUN_DATE, run_dir))[0]
    log_rows = read_csv(log_file)
    assert results[0]["send_status"] == "sent"
    assert results[0]["gmail_message_id"] == "msg-123"
    assert summary["emails_sent"] == "1"
    assert summary["send_failures"] == "0"
    assert log_rows[0]["email"] == "guest@example.com"
    assert log_rows[0]["sent_manually"] == "false"
    assert log_rows[0]["gmail_message_id"] == "msg-123"
    assert log_rows[0]["gmail_draft_id"] == ""
    assert log_rows[0]["sent_at"]


def test_failed_send_does_not_update_permanent_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    service = FakeGmailService(errors=[RuntimeError("api failed")])

    results_path = gmail_send.send_emails_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    summary = read_csv(stayfi.summary_path(RUN_DATE, run_dir))[0]
    assert results[0]["send_status"] == "failed"
    assert "api failed" in results[0]["error_message"]
    assert read_csv(log_file) == []
    assert summary["emails_sent"] == "0"
    assert summary["send_failures"] == "1"


def test_oauth_invalid_grant_is_recognized_and_has_recovery_message() -> None:
    error = RuntimeError("invalid_grant: Token has been expired or revoked.")

    assert gmail_send.is_oauth_token_error(error)
    assert "Gmail OAuth token is expired or revoked." in gmail_send.OAUTH_RECOVERY_MESSAGE
    assert "move the Google OAuth app from Testing to In production" in gmail_send.OAUTH_RECOVERY_MESSAGE
    assert gmail_send.OAUTH_ERROR_EXIT_CODE == 3


def test_oauth_failure_does_not_update_permanent_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    service = FakeGmailService(errors=[RuntimeError("invalid_grant: Token has been expired or revoked.")])

    try:
        gmail_send.send_emails_from_csv(
            RUN_DATE,
            run_dir=run_dir,
            draft_file=stayfi.draft_path(RUN_DATE, run_dir),
            log_file=log_file,
            service=service,
        )
    except gmail_send.GmailOAuthError as exc:
        assert str(exc) == gmail_send.OAUTH_RECOVERY_MESSAGE
    else:
        raise AssertionError("Expected GmailOAuthError")

    assert read_csv(log_file) == []


def test_dry_run_validates_rows_without_sending_or_updating_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    service = FakeGmailService(ids=["message-should-not-send"])

    results_path = gmail_send.send_emails_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
        dry_run=True,
    )

    results = read_csv(results_path)
    summary = read_csv(stayfi.summary_path(RUN_DATE, run_dir))[0]
    assert results[0]["send_status"] == "dry_run_would_send"
    assert results[0]["gmail_message_id"] == ""
    assert service.sent_bodies == []
    assert read_csv(log_file) == []
    assert summary["dry_run_would_send"] == "1"
    assert summary["emails_sent"] == "0"
    assert summary["send_failures"] == "0"


def test_logged_message_id_skips_duplicate_without_sending(tmp_path: Path) -> None:
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
                "sent_at": "2026-07-07T00:00:00+00:00",
                "sent_manually": "false",
                "gmail_message_id": "existing-message",
                "gmail_draft_id": "",
            }
        ],
        stayfi.LOG_COLUMNS,
    )
    service = FakeGmailService(ids=["message-should-not-send"])

    results_path = gmail_send.send_emails_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    summary = read_csv(stayfi.summary_path(RUN_DATE, run_dir))[0]
    assert results[0]["send_status"] == "skipped_duplicate_logged"
    assert service.sent_bodies == []
    assert summary["send_skipped_duplicates_from_log"] == "1"


def test_invalid_send_input_fails_without_gmail_call_or_log(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    log_file = tmp_path / "data" / "history" / "stayfi_anniversary_email_log.csv"
    create_input_files(run_dir, log_file)
    drafts = read_csv(stayfi.draft_path(RUN_DATE, run_dir))
    drafts[0]["email"] = "bad"
    write_csv(stayfi.draft_path(RUN_DATE, run_dir), drafts, stayfi.DRAFT_COLUMNS)
    service = FakeGmailService(ids=["message-should-not-send"])

    results_path = gmail_send.send_emails_from_csv(
        RUN_DATE,
        run_dir=run_dir,
        draft_file=stayfi.draft_path(RUN_DATE, run_dir),
        log_file=log_file,
        service=service,
    )

    results = read_csv(results_path)
    assert results[0]["send_status"] == "failed"
    assert results[0]["error_message"] == "invalid_email"
    assert service.sent_bodies == []
    assert read_csv(log_file) == []


def test_gmail_send_is_explicit_and_not_in_weekly_pipeline() -> None:
    project_root = Path(__file__).resolve().parents[1]
    module_text = (project_root / "src" / "marketing" / "stayfi_gmail_send.py").read_text(encoding="utf-8")
    wrapper_text = (project_root / "scripts" / "send_stayfi_anniversary_emails.ps1").read_text(encoding="utf-8")
    weekly_pipeline_text = (project_root / "run_weekly_pipeline.ps1").read_text(encoding="utf-8")

    assert ".messages().send(" in module_text
    assert "marketing.stayfi_gmail_send" in wrapper_text
    assert "[switch]$DryRun" in wrapper_text
    assert "[switch]$ResetOAuthToken" in wrapper_text
    assert "--dry-run" in wrapper_text
    assert "--validate-oauth-only" in wrapper_text
    assert "gmail_token_backup_$timestamp.json" in wrapper_text
    assert "No emails will be sent." in wrapper_text
    assert "pip install google-api-python-client google-auth google-auth-oauthlib" in wrapper_text
    assert "marketing.stayfi_gmail_send" not in weekly_pipeline_text


def test_gmail_oauth_status_script_is_validation_only() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script_text = (project_root / "scripts" / "check_gmail_oauth_status.ps1").read_text(encoding="utf-8")

    assert "config\\gmail_oauth_client.json" in script_text
    assert ".local\\gmail_token.json" in script_text
    assert "--validate-oauth-only" in script_text
    assert "this check never sends email" in script_text
    assert "pip install google-api-python-client google-auth google-auth-oauthlib" in script_text
    assert "Gmail OAuth token is expired or revoked." in script_text
    assert "messages.send" not in script_text
