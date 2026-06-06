"""Draft-only StayFi guest anniversary email workflow.

This module prepares Gmail-draft data only. It does not send emails and does
not affect PriceLabs recommendation or pricing logic.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
import re
import sys


PROPERTY_NAME = "Aloha Poconos"
DEFAULT_STAYFI_SOURCE_FILE = Path("data") / "source" / "stayfi" / "stayfi_guests_2026.csv"
SUBJECT = "Thinking about another Pocono getaway?"
PROMO_CODE = "ALOHA"
AIRBNB_LISTING_URL = "https://www.airbnb.com/rooms/1313377469848413047"
BOOK_DIRECT_URL = "https://alohapoconos.com"

CANDIDATE_COLUMNS = [
    "email",
    "first_name",
    "last_name",
    "first_sign_in",
    "property",
    "email_status",
    "email_opt_in_consent",
    "guest_rating",
    "eligibility_status",
    "exclusion_reason",
]

DRAFT_COLUMNS = [
    "email",
    "first_name",
    "subject",
    "body",
    "draft_status",
    "gmail_draft_id",
    "created_at",
]

LOG_COLUMNS = [
    "email",
    "first_name",
    "original_first_sign_in",
    "report_week_start",
    "report_week_end",
    "draft_created_at",
    "sent_at",
    "sent_manually",
    "gmail_message_id",
    "gmail_draft_id",
]

SUMMARY_COLUMNS = [
    "run_date",
    "anniversary_audience_window_start",
    "anniversary_audience_window_end",
    "total_stayfi_rows_checked",
    "eligible_guests",
    "drafts_created",
    "drafts_prepared_csv",
    "gmail_drafts_created",
    "excluded_invalid_emails",
    "excluded_no_opt_in",
    "excluded_bad_rating",
    "skipped_duplicates",
    "skipped_duplicates_from_log",
    "rating_missing",
    "detected_columns",
    "date_column_used",
    "email_column_used",
    "rows_in_audience_window",
    "excluded_missing_email",
    "excluded_wrong_property",
    "date_parse_failed",
    "missing_required_columns",
    "stayfi_input_file",
    "source_file_status",
    "draft_mode",
]

DEBUG_COLUMNS = [
    "email_raw",
    "email_parsed",
    "first_name",
    "first_sign_in_raw",
    "first_sign_in_parsed",
    "property",
    "email_status",
    "email_opt_in_consent",
    "guest_rating",
    "eligibility_status",
    "exclusion_reason",
]

FIELD_ALIASES = {
    "email": ("Emails", "Email", "Email Address", "Guest Email", "Contact Email"),
    "full_name": ("Full Name", "Name", "Guest Name"),
    "first_name": ("First Name", "First name", "First", "Guest First Name"),
    "last_name": ("Last Name", "Last name", "Last", "Guest Last Name"),
    "first_sign_in": ("First Sign In", "First Sign-in", "First Sign-In", "First Login", "First Seen", "Sign In Date"),
    "property": ("Property", "Property Name", "Location"),
    "email_status": ("Email Status", "Status"),
    "email_opt_in_consent": ("Email Opt-in Consent", "Email Opt In Consent", "Marketing Consent", "Opt-in", "Opt In"),
    "rating": ("Rating", "Guest Rating", "Review Rating", "Airbnb Rating", "Review Score", "Guest Review Score", "Stars", "Guest Score"),
}

REQUIRED_FIELDS = ("email", "first_sign_in", "property", "email_status", "email_opt_in_consent")

EMAIL_BODY_TEMPLATE = """Hi {first_name},

I hope you've been doing well.

Around this time last year, you visited Aloha Poconos, and I just wanted to say thank you again.

If you're thinking about another Pocono Mountains getaway, you can book again on Airbnb or book directly on our site.

Airbnb listing:
https://www.airbnb.com/rooms/1313377469848413047

Direct booking gives you 15% off with promo code:

ALOHA

Book direct here:
https://alohapoconos.com

Warmly,
Volodymyr
Aloha Poconos
"""


@dataclass(frozen=True)
class WeeklyWindow:
    report_week_start: date
    report_week_end: date
    audience_start: date
    audience_end: date


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare draft-only StayFi anniversary emails.")
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument(
        "--stayfi-file",
        help="StayFi CSV export override. Defaults to data/source/stayfi/stayfi_guests_2026.csv.",
    )
    parser.add_argument("--run-dir", help="Defaults to data/runs/<run-date>.")
    parser.add_argument("--history-log-file", help="Defaults to data/history/stayfi_anniversary_email_log.csv.")
    return parser.parse_args(argv)


def parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    candidates = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M %p",
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
        "%Y-%m-%dT%H:%M:%S",
    ]
    cleaned = text.replace("Z", "").split("+", 1)[0]
    for fmt in candidates:
        try:
            return datetime.strptime(cleaned[: len(datetime.now().strftime(fmt))], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        return None


def shift_back_one_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


def weekly_window(run_date: str) -> WeeklyWindow:
    start = date.fromisoformat(run_date)
    end = start + timedelta(days=6)
    return WeeklyWindow(
        report_week_start=start,
        report_week_end=end,
        audience_start=shift_back_one_year(start),
        audience_end=shift_back_one_year(end),
    )


def run_dir_for(run_date: str, provided: Path | None = None) -> Path:
    return provided or Path("data") / "runs" / run_date


def analysis_dir(run_dir: Path) -> Path:
    return run_dir / "analysis"


def history_log_path(provided: Path | None = None) -> Path:
    return provided or Path("data") / "history" / "stayfi_anniversary_email_log.csv"


def candidate_path(run_date: str, run_dir: Path) -> Path:
    return analysis_dir(run_dir) / f"stayfi_anniversary_email_candidates_{run_date}.csv"


def draft_path(run_date: str, run_dir: Path) -> Path:
    return analysis_dir(run_dir) / f"stayfi_anniversary_email_drafts_{run_date}.csv"


def summary_path(run_date: str, run_dir: Path) -> Path:
    return analysis_dir(run_dir) / f"stayfi_anniversary_email_summary_{run_date}.csv"


def debug_path(run_date: str, run_dir: Path) -> Path:
    return analysis_dir(run_dir) / f"stayfi_anniversary_email_debug_{run_date}.csv"


def default_stayfi_input() -> Path:
    return DEFAULT_STAYFI_SOURCE_FILE


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")


def row_value(row: dict[str, str], aliases: tuple[str, ...]) -> str:
    normalized = {normalize_header(key): value or "" for key, value in row.items()}
    for alias in aliases:
        value = normalized.get(normalize_header(alias), "")
        if value:
            return value.strip()
    return ""


def resolve_headers(headers: list[str]) -> dict[str, str]:
    normalized_to_original = {normalize_header(header): header for header in headers}
    resolved: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            original = normalized_to_original.get(normalize_header(alias), "")
            if original:
                resolved[field] = original
                break
        else:
            resolved[field] = ""
    return resolved


def missing_required_columns(resolved_headers: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not resolved_headers.get(field)]


def resolved_row_value(row: dict[str, str], resolved_headers: dict[str, str], field: str) -> str:
    header = resolved_headers.get(field, "")
    return (row.get(header, "") or "").strip() if header else ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def read_csv_rows_and_headers(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return [{key: value or "" for key, value in row.items()} for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in columns} for row in rows])


def ensure_log_exists(path: Path) -> None:
    if path.exists():
        return
    write_csv(path, [], LOG_COLUMNS)


def email_is_valid(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (email or "").strip()))


def first_valid_email(value: str) -> str:
    for match in re.finditer(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+", value or ""):
        candidate = match.group(0).strip().strip(".,;")
        if email_is_valid(candidate):
            return candidate
    return ""


def split_full_name(value: str) -> tuple[str, str]:
    parts = [part for part in (value or "").strip().split() if part]
    if not parts:
        return "", ""
    return parts[0], " ".join(parts[1:])


def yes_value(value: str) -> bool:
    return (value or "").strip().lower() in {"yes", "y", "true", "1", "opted in", "opt-in", "opt in"}


def property_matches(value: str) -> bool:
    return (value or "").strip().lower() == PROPERTY_NAME.lower()


def rating_value(row: dict[str, str]) -> str:
    return row_value(row, FIELD_ALIASES["rating"])


def rating_exclusion(rating: str) -> tuple[bool, str]:
    if not rating:
        return False, "rating_missing"
    match = re.search(r"\d+(?:\.\d+)?", rating)
    if not match:
        return False, "rating_missing"
    value = float(match.group(0))
    if value in {1, 2, 3} or value < 4:
        return True, "bad_rating"
    return False, ""


def logged_emails(path: Path) -> set[str]:
    logged: set[str] = set()
    for row in read_csv_rows(path):
        email = row.get("email", "").strip().lower()
        if not email:
            continue
        sent_manually = row.get("sent_manually", "").strip().lower() == "true"
        sent_at = row.get("sent_at", "").strip()
        gmail_message_id = row.get("gmail_message_id", "").strip()
        gmail_draft_id = row.get("gmail_draft_id", "").strip()
        if sent_manually or sent_at or gmail_message_id or gmail_draft_id:
            logged.add(email)
    return logged


def extract_guest_row(row: dict[str, str], resolved_headers: dict[str, str] | None = None) -> dict[str, str]:
    if resolved_headers:
        full_name = resolved_row_value(row, resolved_headers, "full_name")
        parsed_first_name, parsed_last_name = split_full_name(full_name)
        first_name = resolved_row_value(row, resolved_headers, "first_name") or parsed_first_name
        last_name = resolved_row_value(row, resolved_headers, "last_name") or parsed_last_name
        email_raw = resolved_row_value(row, resolved_headers, "email")
        return {
            "email": first_valid_email(email_raw),
            "email_raw": email_raw,
            "first_name": first_name,
            "last_name": last_name,
            "first_sign_in": resolved_row_value(row, resolved_headers, "first_sign_in"),
            "property": resolved_row_value(row, resolved_headers, "property"),
            "email_status": resolved_row_value(row, resolved_headers, "email_status"),
            "email_opt_in_consent": resolved_row_value(row, resolved_headers, "email_opt_in_consent"),
            "guest_rating": resolved_row_value(row, resolved_headers, "rating"),
        }
    full_name = row_value(row, FIELD_ALIASES["full_name"])
    parsed_first_name, parsed_last_name = split_full_name(full_name)
    email_raw = row_value(row, FIELD_ALIASES["email"]).strip()
    return {
        "email": first_valid_email(email_raw),
        "email_raw": email_raw,
        "first_name": row_value(row, FIELD_ALIASES["first_name"]) or parsed_first_name,
        "last_name": row_value(row, FIELD_ALIASES["last_name"]) or parsed_last_name,
        "first_sign_in": row_value(row, FIELD_ALIASES["first_sign_in"]),
        "property": row_value(row, FIELD_ALIASES["property"]),
        "email_status": row_value(row, FIELD_ALIASES["email_status"]),
        "email_opt_in_consent": row_value(row, FIELD_ALIASES["email_opt_in_consent"]),
        "guest_rating": rating_value(row),
    }


def evaluate_guest(
    row: dict[str, str],
    *,
    window: WeeklyWindow,
    duplicate_emails: set[str],
    resolved_headers: dict[str, str] | None = None,
) -> dict[str, str] | None:
    guest = extract_guest_row(row, resolved_headers)
    sign_in_date = parse_date(guest["first_sign_in"])
    if sign_in_date is None or not (window.audience_start <= sign_in_date <= window.audience_end):
        return None

    exclusion_reasons: list[str] = []
    email_key = guest["email"].strip().lower()
    if not property_matches(guest["property"]):
        exclusion_reasons.append("property_mismatch")
    if not guest["email"].strip():
        exclusion_reasons.append("missing_email")
    elif not email_is_valid(guest["email"]):
        exclusion_reasons.append("invalid_email")
    if guest["email_status"].strip().lower() != "valid":
        exclusion_reasons.append("invalid_email_status")
    if not yes_value(guest["email_opt_in_consent"]):
        exclusion_reasons.append("no_opt_in")
    bad_rating, rating_reason = rating_exclusion(guest["guest_rating"])
    if bad_rating:
        exclusion_reasons.append("bad_rating")
    if email_key in duplicate_emails:
        exclusion_reasons.append("duplicate_already_logged")

    guest["eligibility_status"] = "eligible" if not exclusion_reasons else "excluded"
    if not guest["guest_rating"] and "bad_rating" not in exclusion_reasons:
        guest["exclusion_reason"] = "rating_missing" if not exclusion_reasons else ";".join([*exclusion_reasons, "rating_missing"])
    else:
        guest["exclusion_reason"] = ";".join(exclusion_reasons)
    return guest


def debug_guest_row(
    row: dict[str, str],
    *,
    window: WeeklyWindow,
    duplicate_emails: set[str],
    resolved_headers: dict[str, str],
) -> dict[str, str]:
    guest = extract_guest_row(row, resolved_headers)
    sign_in_date = parse_date(guest["first_sign_in"])
    candidate = evaluate_guest(
        row,
        window=window,
        duplicate_emails=duplicate_emails,
        resolved_headers=resolved_headers,
    )
    exclusion_reason = candidate.get("exclusion_reason", "") if candidate else ""
    eligibility_status = candidate.get("eligibility_status", "excluded") if candidate else "excluded"
    if sign_in_date is None:
        exclusion_reason = "date_parse_failed"
    elif not (window.audience_start <= sign_in_date <= window.audience_end):
        exclusion_reason = "outside_audience_window"
    return {
        "email_raw": guest.get("email_raw", resolved_row_value(row, resolved_headers, "email")),
        "email_parsed": guest["email"].strip().lower(),
        "first_name": guest["first_name"],
        "first_sign_in_raw": guest["first_sign_in"],
        "first_sign_in_parsed": sign_in_date.isoformat() if sign_in_date else "",
        "property": guest["property"],
        "email_status": guest["email_status"],
        "email_opt_in_consent": guest["email_opt_in_consent"],
        "guest_rating": guest["guest_rating"],
        "eligibility_status": eligibility_status,
        "exclusion_reason": exclusion_reason,
    }


def dedupe_by_email_most_recent(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_email: dict[str, dict[str, str]] = {}
    for row in rows:
        email = row.get("email", "").strip().lower()
        if not email:
            by_email[f"missing:{len(by_email)}"] = row
            continue
        current = by_email.get(email)
        if current is None:
            by_email[email] = row
            continue
        current_date = parse_date(current.get("first_sign_in", "")) or date.min
        row_date = parse_date(row.get("first_sign_in", "")) or date.min
        if row_date >= current_date:
            by_email[email] = row
    return list(by_email.values())


def email_body(first_name: str) -> str:
    return EMAIL_BODY_TEMPLATE.format(first_name=(first_name or "there").strip() or "there")


def draft_rows(candidates: list[dict[str, str]], created_at: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        if candidate.get("eligibility_status") != "eligible":
            continue
        rows.append(
            {
                "email": candidate["email"],
                "first_name": candidate["first_name"],
                "subject": SUBJECT,
                "body": email_body(candidate["first_name"]),
                "draft_status": "draft_prepared_manual_gmail_creation",
                "gmail_draft_id": "",
                "created_at": created_at,
            }
        )
    return rows


def append_log(path: Path, drafts: list[dict[str, str]], candidates: list[dict[str, str]], window: WeeklyWindow) -> None:
    ensure_log_exists(path)
    candidate_by_email = {row["email"].strip().lower(): row for row in candidates}
    existing = read_csv_rows(path)
    existing_emails = {row.get("email", "").strip().lower() for row in existing}
    new_rows: list[dict[str, str]] = []
    for draft in drafts:
        if not draft.get("gmail_draft_id", "").strip():
            continue
        email_key = draft["email"].strip().lower()
        if email_key in existing_emails:
            continue
        candidate = candidate_by_email.get(email_key, {})
        new_rows.append(
            {
                "email": draft["email"],
                "first_name": draft["first_name"],
                "original_first_sign_in": candidate.get("first_sign_in", ""),
                "report_week_start": window.report_week_start.isoformat(),
                "report_week_end": window.report_week_end.isoformat(),
                "draft_created_at": draft["created_at"],
                "sent_at": "",
                "sent_manually": "false",
                "gmail_message_id": "",
                "gmail_draft_id": draft.get("gmail_draft_id", ""),
            }
        )
    write_csv(path, [*existing, *new_rows], LOG_COLUMNS)


def summary_row(
    *,
    run_date: str,
    window: WeeklyWindow,
    stayfi_rows_checked: int,
    candidates: list[dict[str, str]],
    drafts: list[dict[str, str]],
    debug_rows: list[dict[str, str]],
    stayfi_input_file: Path | None,
    source_file_status: str,
    detected_columns: list[str],
    resolved_headers: dict[str, str],
    missing_columns: list[str],
) -> dict[str, str]:
    def count_reason(reason: str) -> int:
        return sum(1 for row in candidates if reason in row.get("exclusion_reason", "").split(";"))

    def count_debug_reason(reason: str) -> int:
        return sum(1 for row in debug_rows if reason in row.get("exclusion_reason", "").split(";"))

    return {
        "run_date": run_date,
        "anniversary_audience_window_start": window.audience_start.isoformat(),
        "anniversary_audience_window_end": window.audience_end.isoformat(),
        "total_stayfi_rows_checked": str(stayfi_rows_checked),
        "eligible_guests": str(sum(1 for row in candidates if row.get("eligibility_status") == "eligible")),
        "drafts_created": str(sum(1 for row in drafts if row.get("gmail_draft_id", "").strip())),
        "drafts_prepared_csv": str(len(drafts)),
        "gmail_drafts_created": str(sum(1 for row in drafts if row.get("gmail_draft_id", "").strip())),
        "excluded_invalid_emails": str(count_reason("invalid_email") + count_reason("invalid_email_status")),
        "excluded_no_opt_in": str(count_reason("no_opt_in")),
        "excluded_bad_rating": str(count_reason("bad_rating")),
        "skipped_duplicates": str(count_reason("duplicate_already_logged")),
        "skipped_duplicates_from_log": str(count_reason("duplicate_already_logged")),
        "rating_missing": str(count_reason("rating_missing")),
        "detected_columns": " | ".join(detected_columns),
        "date_column_used": resolved_headers.get("first_sign_in", ""),
        "email_column_used": resolved_headers.get("email", ""),
        "rows_in_audience_window": str(
            sum(
                1
                for row in debug_rows
                if row.get("first_sign_in_parsed")
                and row.get("exclusion_reason") != "outside_audience_window"
                and "date_parse_failed" not in row.get("exclusion_reason", "")
            )
        ),
        "excluded_missing_email": str(count_reason("missing_email")),
        "excluded_wrong_property": str(count_reason("property_mismatch")),
        "date_parse_failed": str(count_debug_reason("date_parse_failed")),
        "missing_required_columns": " | ".join(missing_columns),
        "stayfi_input_file": str(stayfi_input_file or ""),
        "source_file_status": source_file_status,
        "draft_mode": "manual_gmail_draft_prepared_only",
    }


def run_workflow(
    run_date: str,
    *,
    run_dir: Path,
    stayfi_file: Path | None,
    log_file: Path,
) -> tuple[Path, Path, Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir(run_dir).mkdir(parents=True, exist_ok=True)
    ensure_log_exists(log_file)
    window = weekly_window(run_date)
    resolved_input = stayfi_file or default_stayfi_input()
    source_file_status = "available" if resolved_input.exists() else "missing"
    raw_rows, detected_columns = read_csv_rows_and_headers(resolved_input) if resolved_input.exists() else ([], [])
    resolved_headers = resolve_headers(detected_columns)
    missing_columns = missing_required_columns(resolved_headers)
    if source_file_status == "available" and missing_columns:
        source_file_status = "available_but_missing_columns"
    duplicate_emails = logged_emails(log_file)
    debug_rows = [
        debug_guest_row(row, window=window, duplicate_emails=duplicate_emails, resolved_headers=resolved_headers)
        for row in raw_rows
    ]
    evaluated = [
        candidate
        for row in raw_rows
        if (candidate := evaluate_guest(row, window=window, duplicate_emails=duplicate_emails, resolved_headers=resolved_headers)) is not None
    ]
    candidates = dedupe_by_email_most_recent(evaluated)
    created_at = datetime.now(UTC).isoformat()
    drafts = draft_rows(candidates, created_at)
    append_log(log_file, drafts, candidates, window)
    summary = summary_row(
        run_date=run_date,
        window=window,
        stayfi_rows_checked=len(raw_rows),
        candidates=candidates,
        drafts=drafts,
        debug_rows=debug_rows,
        stayfi_input_file=resolved_input,
        source_file_status=source_file_status,
        detected_columns=detected_columns,
        resolved_headers=resolved_headers,
        missing_columns=missing_columns,
    )

    candidates_path = candidate_path(run_date, run_dir)
    drafts_path = draft_path(run_date, run_dir)
    summary_output_path = summary_path(run_date, run_dir)
    debug_output_path = debug_path(run_date, run_dir)
    write_csv(candidates_path, candidates, CANDIDATE_COLUMNS)
    write_csv(drafts_path, drafts, DRAFT_COLUMNS)
    write_csv(summary_output_path, [summary], SUMMARY_COLUMNS)
    write_csv(debug_output_path, debug_rows, DEBUG_COLUMNS)
    return candidates_path, drafts_path, summary_output_path, log_file


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = run_dir_for(args.run_date, Path(args.run_dir) if args.run_dir else None)
    log_file = history_log_path(Path(args.history_log_file) if args.history_log_file else None)
    candidates_path, drafts_path, summary_output_path, log_file = run_workflow(
        args.run_date,
        run_dir=run_dir,
        stayfi_file=Path(args.stayfi_file) if args.stayfi_file else None,
        log_file=log_file,
    )
    print(f"Wrote {candidates_path}")
    print(f"Wrote {drafts_path}")
    print(f"Wrote {summary_output_path}")
    print(f"Wrote {debug_path(args.run_date, run_dir)}")
    print(f"Updated {log_file}")
    print("StayFi anniversary emails are draft-only; no emails were sent automatically.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
