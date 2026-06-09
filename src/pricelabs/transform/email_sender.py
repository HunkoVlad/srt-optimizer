"""Optional SMTP sender for the generated email revenue report."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from email.message import EmailMessage
from email.policy import SMTP
import os
from pathlib import Path
import smtplib
import sys
import tomllib

from pricelabs.transform.email_draft_file import PLACEHOLDER_RECIPIENT, read_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send the email revenue report when explicitly configured.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--report-file",
        help="Email-ready markdown report. Defaults to analysis/email_revenue_report_<run-date>.md.",
    )
    parser.add_argument(
        "--html-file",
        help="Optional HTML email report. Defaults to analysis/email_revenue_report_<run-date>.html.",
    )
    parser.add_argument(
        "--config-file",
        default="config/email.toml",
        help="Local email config TOML. Defaults to config/email.toml.",
    )
    parser.add_argument(
        "--result-file",
        help="Optional send result CSV path. Defaults to analysis/email_revenue_report_send_result_<run-date>.csv.",
    )
    parser.add_argument(
        "--explicit-send",
        action="store_true",
        help="Explicitly send the weekly report regardless of email.mode draft setting.",
    )
    return parser.parse_args()


def read_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def bool_value(value: object) -> bool:
    return bool(value) if isinstance(value, bool) else str(value).strip().lower() == "true"


def build_message(
    subject: str,
    body: str,
    sender: str,
    recipient: str,
    cc_email: str = "",
    html_body: str = "",
) -> EmailMessage:
    message = EmailMessage(policy=SMTP)
    message["From"] = sender
    message["To"] = recipient
    if cc_email:
        message["Cc"] = cc_email
    message["Subject"] = subject
    message["MIME-Version"] = "1.0"
    message.set_content(body, subtype="plain", charset="utf-8", cte="8bit")
    if html_body:
        message.add_alternative(html_body, subtype="html", charset="utf-8", cte="8bit")
    return message


SEND_RESULT_COLUMNS = [
    "run_date",
    "recipient",
    "sender",
    "report_path_used",
    "send_status",
    "error_message",
    "sent_at",
]


def write_send_result(path: Path, row: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
            existing_rows = [{key: value or "" for key, value in entry.items()} for entry in csv.DictReader(csv_file)]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=SEND_RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: entry.get(column, "") for column in SEND_RESULT_COLUMNS} for entry in [*existing_rows, row]])


def read_send_results(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def send_message(
    message: EmailMessage,
    host: str,
    port: int,
    sender: str,
    password: str,
    use_tls: bool,
) -> None:
    with smtplib.SMTP(host, port) as smtp:
        if use_tls:
            smtp.starttls()
        smtp.login(sender, password)
        smtp.send_message(message)


def default_report_path(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "analysis" / f"email_revenue_report_{run_date}.md"


def default_html_path(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "analysis" / f"email_revenue_report_{run_date}.html"


def default_result_path(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "analysis" / f"email_revenue_report_send_result_{run_date}.csv"


def report_path_for_send(report_path: Path, html_path: Path, report_format: str) -> Path:
    if report_format == "markdown":
        return report_path
    if html_path.exists():
        return html_path
    return report_path


def subject_with_prefix(subject: str, subject_prefix: str) -> str:
    prefix = subject_prefix.strip()
    return f"{prefix} {subject}".strip() if prefix else subject


def result_row(
    *,
    run_date: str,
    recipient: str,
    sender: str,
    report_path_used: Path,
    send_status: str,
    error_message: str = "",
    sent_at: str = "",
) -> dict[str, str]:
    return {
        "run_date": run_date,
        "recipient": recipient,
        "sender": sender,
        "report_path_used": str(report_path_used),
        "send_status": send_status,
        "error_message": error_message,
        "sent_at": sent_at,
    }


def explicit_send_report(
    *,
    run_date: str,
    report_path: Path,
    html_path: Path,
    config_path: Path,
    result_path: Path,
) -> str:
    config = read_config(config_path)
    email_config = config.get("email", {})
    smtp_config = config.get("smtp", {})
    report_config = config.get("report", {})
    report_format = str(report_config.get("format", "html")).strip().lower()

    recipient = str(email_config.get("recipient_email", "")).strip()
    subject_prefix = str(email_config.get("subject_prefix", "")).strip()
    cc_email = str(email_config.get("cc_email", "")).strip()
    sender = str(smtp_config.get("sender_email", "")).strip()
    selected_report_path = report_path_for_send(report_path, html_path, report_format)

    if any(row.get("send_status") == "sent" for row in read_send_results(result_path)):
        write_send_result(
            result_path,
            result_row(
                run_date=run_date,
                recipient=recipient,
                sender=sender,
                report_path_used=selected_report_path,
                send_status="skipped",
                error_message="already_sent_for_run",
            ),
        )
        return "Weekly report email send skipped: already sent for this run."

    try:
        if not config:
            raise FileNotFoundError(f"Email config does not exist: {config_path}")
        if not recipient:
            raise ValueError("recipient_email is required in config/email.toml.")
        if not sender:
            raise ValueError("smtp.sender_email is required in config/email.toml.")
        password_env_var = str(smtp_config.get("password_env_var", "")).strip()
        if not password_env_var:
            raise ValueError("smtp.password_env_var is required in config/email.toml.")
        password = os.environ.get(password_env_var)
        if not password:
            raise RuntimeError(f"SMTP password environment variable is missing: {password_env_var}")
        if not selected_report_path.exists():
            raise FileNotFoundError(f"Email report does not exist: {selected_report_path}")

        subject, markdown_body = read_report(report_path)
        html_body = ""
        if selected_report_path.suffix.lower() == ".html":
            html_body = selected_report_path.read_text(encoding="utf-8-sig")
        message = build_message(
            subject_with_prefix(subject, subject_prefix),
            markdown_body,
            sender,
            recipient,
            cc_email,
            html_body,
        )
        send_message(
            message,
            str(smtp_config.get("host", "smtp.gmail.com")).strip() or "smtp.gmail.com",
            int(smtp_config.get("port", 587)),
            sender,
            password,
            bool_value(smtp_config.get("use_tls", True)),
        )
        write_send_result(
            result_path,
            result_row(
                run_date=run_date,
                recipient=recipient,
                sender=sender,
                report_path_used=selected_report_path,
                send_status="sent",
                sent_at=datetime.now(UTC).isoformat(),
            ),
        )
        return f"Weekly report email sent to {recipient}."
    except Exception as exc:
        write_send_result(
            result_path,
            result_row(
                run_date=run_date,
                recipient=recipient,
                sender=sender,
                report_path_used=selected_report_path,
                send_status="failed",
                error_message=str(exc),
            ),
        )
        raise


def send_if_configured(report_path: Path, config_path: Path, html_path: Path | None = None) -> str:
    config = read_config(config_path)
    if not config:
        return "Email mode: draft — send skipped."

    email_config = config.get("email", {})
    smtp_config = config.get("smtp", {})
    report_config = config.get("report", {})
    mode = str(email_config.get("mode", "draft")).strip().lower()
    smtp_enabled = bool_value(smtp_config.get("enabled", False))
    report_format = str(report_config.get("format", "markdown")).strip().lower()

    if mode != "send":
        return "Email mode: draft — send skipped."
    if not smtp_enabled:
        return "Email mode: send but SMTP disabled — send skipped."

    sender = str(smtp_config.get("sender_email", "")).strip()
    if not sender:
        raise ValueError("SMTP sender_email is required when email mode is send.")

    recipient = str(email_config.get("recipient_email", "")).strip() or PLACEHOLDER_RECIPIENT
    cc_email = str(email_config.get("cc_email", "")).strip()
    password_env_var = str(smtp_config.get("password_env_var", "")).strip()
    if not password_env_var:
        raise ValueError("SMTP password_env_var is required when email mode is send.")

    password = os.environ.get(password_env_var)
    if not password:
        raise RuntimeError(f"SMTP password environment variable is missing: {password_env_var}")

    subject, body = read_report(report_path)
    html_body = ""
    if report_format == "html":
        resolved_html_path = html_path or report_path.with_suffix(".html")
        if not resolved_html_path.exists():
            raise FileNotFoundError(f"HTML email report does not exist: {resolved_html_path}")
        html_body = resolved_html_path.read_text(encoding="utf-8-sig")
    message = build_message(subject, body, sender, recipient, cc_email, html_body)
    send_message(
        message,
        str(smtp_config.get("host", "smtp.gmail.com")).strip() or "smtp.gmail.com",
        int(smtp_config.get("port", 587)),
        sender,
        password,
        bool_value(smtp_config.get("use_tls", True)),
    )
    return f"Email sent to {recipient}."


def run() -> int:
    args = parse_args()
    report_path = Path(args.report_file) if args.report_file else default_report_path(args.run_date)
    html_path = Path(args.html_file) if args.html_file else default_html_path(args.run_date)
    config_path = Path(args.config_file)
    if args.explicit_send:
        result_path = Path(args.result_file) if args.result_file else default_result_path(args.run_date)
        print(explicit_send_report(run_date=args.run_date, report_path=report_path, html_path=html_path, config_path=config_path, result_path=result_path))
    else:
        print(send_if_configured(report_path, config_path, html_path))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
