"""Send StayFi anniversary emails through Gmail.

This is an explicit, separate step. It sends real Gmail messages only when
the operator runs the send command. It is not part of the weekly pipeline.
"""

from __future__ import annotations

import argparse
import base64
import csv
from datetime import UTC, datetime
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
import sys

from marketing import stayfi_anniversary_email as stayfi


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"

RESULT_COLUMNS = [
    "email",
    "subject",
    "gmail_message_id",
    "send_status",
    "error_message",
    "sent_at",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send StayFi anniversary emails through Gmail.")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--run-dir", help="Defaults to data/runs/<run-date>.")
    parser.add_argument("--draft-file", help="Defaults to analysis/stayfi_anniversary_email_drafts_<run-date>.csv.")
    parser.add_argument("--history-log-file", help="Defaults to data/history/stayfi_anniversary_email_log.csv.")
    parser.add_argument("--credentials-file", default="config/gmail_oauth_client.json")
    parser.add_argument("--token-file", default=".local/gmail_token.json")
    parser.add_argument("--sender-email", default="")
    parser.add_argument("--dry-run", action="store_true", help="Validate send inputs and OAuth setup without sending emails.")
    return parser.parse_args(argv)


def run_dir_for(run_date: str, provided: Path | None = None) -> Path:
    return provided or Path("data") / "runs" / run_date


def draft_file_for(run_date: str, run_dir: Path, provided: Path | None = None) -> Path:
    return provided or stayfi.draft_path(run_date, run_dir)


def candidates_file_for(run_date: str, run_dir: Path) -> Path:
    return stayfi.candidate_path(run_date, run_dir)


def summary_file_for(run_date: str, run_dir: Path) -> Path:
    return stayfi.summary_path(run_date, run_dir)


def results_file_for(run_date: str, run_dir: Path) -> Path:
    return stayfi.analysis_dir(run_dir) / f"stayfi_anniversary_email_send_results_{run_date}.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in columns} for row in rows])


def build_raw_message(*, to_email: str, subject: str, body: str, sender_email: str = "") -> str:
    message = EmailMessage(policy=SMTP)
    if sender_email:
        message["From"] = sender_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body, subtype="plain", charset="utf-8", cte="8bit")
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def send_gmail_message(service, *, to_email: str, subject: str, body: str, sender_email: str = "") -> str:
    raw = build_raw_message(to_email=to_email, subject=subject, body=body, sender_email=sender_email)
    response = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return str(response.get("id", "")).strip()


def build_gmail_service(credentials_file: Path, token_file: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Gmail email sending requires google-api-python-client, google-auth, and google-auth-oauthlib."
        ) from exc

    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), [GMAIL_SEND_SCOPE])
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not credentials_file.exists():
                raise FileNotFoundError(f"Missing Gmail OAuth client credentials: {credentials_file}")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), [GMAIL_SEND_SCOPE])
            credentials = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(credentials.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=credentials)


def valid_send_input(row: dict[str, str]) -> tuple[bool, str]:
    if not stayfi.email_is_valid(row.get("email", "")):
        return False, "invalid_email"
    if not row.get("subject", "").strip():
        return False, "missing_subject"
    if not row.get("body", "").strip():
        return False, "missing_body"
    return True, ""


def result_row(
    email: str,
    subject: str,
    send_status: str,
    *,
    gmail_message_id: str = "",
    error_message: str = "",
    sent_at: str = "",
) -> dict[str, str]:
    return {
        "email": email,
        "subject": subject,
        "gmail_message_id": gmail_message_id,
        "send_status": send_status,
        "error_message": error_message,
        "sent_at": sent_at,
    }


def sent_logged_emails(path: Path) -> set[str]:
    logged: set[str] = set()
    for row in read_csv(path):
        email = row.get("email", "").strip().lower()
        if not email:
            continue
        sent_manually = row.get("sent_manually", "").strip().lower() == "true"
        sent_at = row.get("sent_at", "").strip()
        gmail_message_id = row.get("gmail_message_id", "").strip()
        if sent_manually or sent_at or gmail_message_id:
            logged.add(email)
    return logged


def append_sent_log(
    *,
    log_file: Path,
    sent_rows: list[dict[str, str]],
    candidates: list[dict[str, str]],
    run_date: str,
) -> None:
    stayfi.ensure_log_exists(log_file)
    if not sent_rows:
        return
    window = stayfi.weekly_window(run_date)
    candidate_by_email = {row.get("email", "").strip().lower(): row for row in candidates}
    existing = read_csv(log_file)
    existing_sent = sent_logged_emails(log_file)
    new_rows: list[dict[str, str]] = []
    for sent in sent_rows:
        email_key = sent.get("email", "").strip().lower()
        if not email_key or email_key in existing_sent:
            continue
        candidate = candidate_by_email.get(email_key, {})
        new_rows.append(
            {
                "email": sent.get("email", ""),
                "first_name": sent.get("first_name", ""),
                "original_first_sign_in": candidate.get("first_sign_in", ""),
                "report_week_start": window.report_week_start.isoformat(),
                "report_week_end": window.report_week_end.isoformat(),
                "draft_created_at": "",
                "sent_at": sent.get("sent_at", ""),
                "sent_manually": "false",
                "gmail_message_id": sent.get("gmail_message_id", ""),
                "gmail_draft_id": "",
            }
        )
        existing_sent.add(email_key)
    write_csv(log_file, [*existing, *new_rows], stayfi.LOG_COLUMNS)


def update_summary(run_date: str, run_dir: Path, results: list[dict[str, str]]) -> None:
    summary_path = summary_file_for(run_date, run_dir)
    rows = read_csv(summary_path)
    if not rows:
        return
    row = rows[0]
    sent = sum(1 for result in results if result.get("send_status") == "sent")
    dry_run_would_send = sum(1 for result in results if result.get("send_status") == "dry_run_would_send")
    failures = sum(1 for result in results if result.get("send_status") == "failed")
    skipped = sum(1 for result in results if result.get("send_status") == "skipped_duplicate_logged")
    row["dry_run_would_send"] = str(dry_run_would_send)
    row["emails_sent"] = str(sent)
    row["send_failures"] = str(failures)
    row["send_skipped_duplicates_from_log"] = str(skipped)
    columns = list(
        dict.fromkeys(
            [
                *stayfi.SUMMARY_COLUMNS,
                "gmail_draft_failures",
                "dry_run_would_send",
                "emails_sent",
                "send_failures",
                "send_skipped_duplicates_from_log",
            ]
        )
    )
    write_csv(summary_path, [row], columns)


def send_emails_from_csv(
    run_date: str,
    *,
    run_dir: Path,
    draft_file: Path,
    log_file: Path,
    service,
    sender_email: str = "",
    dry_run: bool = False,
) -> Path:
    draft_rows = read_csv(draft_file)
    candidates = read_csv(candidates_file_for(run_date, run_dir))
    logged = sent_logged_emails(log_file)
    results: list[dict[str, str]] = []
    successful_for_log: list[dict[str, str]] = []

    for draft in draft_rows:
        email = draft.get("email", "").strip()
        subject = draft.get("subject", "").strip()
        valid, reason = valid_send_input(draft)
        if not valid:
            results.append(result_row(email, subject, "failed", error_message=reason))
            continue
        if email.lower() in logged:
            results.append(result_row(email, subject, "skipped_duplicate_logged", error_message="already_logged"))
            continue
        if dry_run:
            results.append(result_row(email, subject, "dry_run_would_send"))
            logged.add(email.lower())
            continue
        try:
            gmail_message_id = send_gmail_message(
                service,
                to_email=email,
                subject=subject,
                body=draft.get("body", ""),
                sender_email=sender_email,
            )
            if not gmail_message_id:
                raise RuntimeError("Gmail send response did not include an id.")
            sent_at = datetime.now(UTC).isoformat()
            results.append(
                result_row(
                    email,
                    subject,
                    "sent",
                    gmail_message_id=gmail_message_id,
                    sent_at=sent_at,
                )
            )
            successful_for_log.append(
                {
                    **draft,
                    "gmail_message_id": gmail_message_id,
                    "sent_at": sent_at,
                }
            )
            logged.add(email.lower())
        except Exception as exc:
            results.append(result_row(email, subject, "failed", error_message=str(exc)))

    if not dry_run:
        append_sent_log(log_file=log_file, sent_rows=successful_for_log, candidates=candidates, run_date=run_date)
    update_summary(run_date, run_dir, results)
    output_path = results_file_for(run_date, run_dir)
    write_csv(output_path, results, RESULT_COLUMNS)
    return output_path


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = run_dir_for(args.run_date, Path(args.run_dir) if args.run_dir else None)
    service = build_gmail_service(Path(args.credentials_file), Path(args.token_file))
    output_path = send_emails_from_csv(
        args.run_date,
        run_dir=run_dir,
        draft_file=draft_file_for(args.run_date, run_dir, Path(args.draft_file) if args.draft_file else None),
        log_file=stayfi.history_log_path(Path(args.history_log_file) if args.history_log_file else None),
        service=service,
        sender_email=args.sender_email,
        dry_run=args.dry_run,
    )
    print(f"Wrote {output_path}")
    if args.dry_run:
        print("Dry run complete. No Gmail messages were sent and the permanent log was not updated.")
    else:
        print("StayFi anniversary emails were sent through Gmail by explicit command.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
