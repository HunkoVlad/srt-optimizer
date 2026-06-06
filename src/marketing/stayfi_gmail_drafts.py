"""Create real Gmail drafts from StayFi anniversary draft-ready CSV records.

This is an explicit, separate step. It creates Gmail drafts only and never
sends messages.
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


GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"

RESULT_COLUMNS = [
    "email",
    "subject",
    "gmail_draft_id",
    "draft_status",
    "error_message",
    "created_at",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create Gmail drafts from StayFi anniversary draft-ready CSV.")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--run-dir", help="Defaults to data/runs/<run-date>.")
    parser.add_argument("--draft-file", help="Defaults to analysis/stayfi_anniversary_email_drafts_<run-date>.csv.")
    parser.add_argument("--history-log-file", help="Defaults to data/history/stayfi_anniversary_email_log.csv.")
    parser.add_argument("--credentials-file", default="config/gmail_oauth_client.json")
    parser.add_argument("--token-file", default=".local/gmail_token.json")
    parser.add_argument("--sender-email", default="")
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
    return stayfi.analysis_dir(run_dir) / f"stayfi_anniversary_gmail_draft_results_{run_date}.csv"


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


def create_gmail_draft(service, *, to_email: str, subject: str, body: str, sender_email: str = "") -> str:
    raw = build_raw_message(to_email=to_email, subject=subject, body=body, sender_email=sender_email)
    response = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return str(response.get("id", "")).strip()


def build_gmail_service(credentials_file: Path, token_file: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Gmail draft creation requires google-api-python-client, google-auth, and google-auth-oauthlib."
        ) from exc

    credentials = None
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), [GMAIL_COMPOSE_SCOPE])
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not credentials_file.exists():
                raise FileNotFoundError(f"Missing Gmail OAuth client credentials: {credentials_file}")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), [GMAIL_COMPOSE_SCOPE])
            credentials = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(credentials.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=credentials)


def candidate_by_email(candidates: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("email", "").strip().lower(): row for row in candidates if row.get("email", "").strip()}


def valid_draft_input(row: dict[str, str]) -> tuple[bool, str]:
    if not stayfi.email_is_valid(row.get("email", "")):
        return False, "invalid_email"
    if not row.get("subject", "").strip():
        return False, "missing_subject"
    if not row.get("body", "").strip():
        return False, "missing_body"
    return True, ""


def result_row(email: str, subject: str, draft_status: str, *, gmail_draft_id: str = "", error_message: str = "", created_at: str = "") -> dict[str, str]:
    return {
        "email": email,
        "subject": subject,
        "gmail_draft_id": gmail_draft_id,
        "draft_status": draft_status,
        "error_message": error_message,
        "created_at": created_at,
    }


def log_successful_drafts(
    *,
    log_file: Path,
    successful_drafts: list[dict[str, str]],
    candidates: list[dict[str, str]],
    run_date: str,
) -> None:
    if not successful_drafts:
        stayfi.ensure_log_exists(log_file)
        return
    window = stayfi.weekly_window(run_date)
    stayfi.append_log(log_file, successful_drafts, candidates, window)


def update_summary(run_date: str, run_dir: Path, results: list[dict[str, str]]) -> None:
    summary_path = summary_file_for(run_date, run_dir)
    rows = read_csv(summary_path)
    if not rows:
        return
    row = rows[0]
    gmail_created = sum(1 for result in results if result.get("draft_status") == "gmail_draft_created")
    failures = sum(1 for result in results if result.get("draft_status") == "failed")
    skipped = sum(1 for result in results if result.get("draft_status") == "skipped_duplicate_logged")
    row["drafts_created"] = str(gmail_created)
    row["gmail_drafts_created"] = str(gmail_created)
    row["gmail_draft_failures"] = str(failures)
    row["skipped_duplicates"] = str(skipped)
    row["skipped_duplicates_from_log"] = str(skipped)
    columns = list(dict.fromkeys([*stayfi.SUMMARY_COLUMNS, "gmail_draft_failures"]))
    write_csv(summary_path, [row], columns)


def create_drafts_from_csv(
    run_date: str,
    *,
    run_dir: Path,
    draft_file: Path,
    log_file: Path,
    service,
    sender_email: str = "",
) -> Path:
    draft_rows = read_csv(draft_file)
    candidates = read_csv(candidates_file_for(run_date, run_dir))
    logged = stayfi.logged_emails(log_file)
    results: list[dict[str, str]] = []
    successful_for_log: list[dict[str, str]] = []

    for draft in draft_rows:
        email = draft.get("email", "").strip()
        subject = draft.get("subject", "").strip()
        valid, reason = valid_draft_input(draft)
        if not valid:
            results.append(result_row(email, subject, "failed", error_message=reason))
            continue
        if email.lower() in logged:
            results.append(result_row(email, subject, "skipped_duplicate_logged", error_message="already_logged"))
            continue
        try:
            gmail_draft_id = create_gmail_draft(
                service,
                to_email=email,
                subject=subject,
                body=draft.get("body", ""),
                sender_email=sender_email,
            )
            if not gmail_draft_id:
                raise RuntimeError("Gmail draft response did not include an id.")
            created_at = datetime.now(UTC).isoformat()
            results.append(
                result_row(
                    email,
                    subject,
                    "gmail_draft_created",
                    gmail_draft_id=gmail_draft_id,
                    created_at=created_at,
                )
            )
            successful_for_log.append(
                {
                    **draft,
                    "gmail_draft_id": gmail_draft_id,
                    "created_at": created_at,
                }
            )
            logged.add(email.lower())
        except Exception as exc:
            results.append(result_row(email, subject, "failed", error_message=str(exc)))

    log_successful_drafts(
        log_file=log_file,
        successful_drafts=successful_for_log,
        candidates=candidates,
        run_date=run_date,
    )
    update_summary(run_date, run_dir, results)
    output_path = results_file_for(run_date, run_dir)
    write_csv(output_path, results, RESULT_COLUMNS)
    return output_path


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = run_dir_for(args.run_date, Path(args.run_dir) if args.run_dir else None)
    service = build_gmail_service(Path(args.credentials_file), Path(args.token_file))
    output_path = create_drafts_from_csv(
        args.run_date,
        run_dir=run_dir,
        draft_file=draft_file_for(args.run_date, run_dir, Path(args.draft_file) if args.draft_file else None),
        log_file=stayfi.history_log_path(Path(args.history_log_file) if args.history_log_file else None),
        service=service,
        sender_email=args.sender_email,
    )
    print(f"Wrote {output_path}")
    print("Gmail drafts created only; no emails were sent.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
