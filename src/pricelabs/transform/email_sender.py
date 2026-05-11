"""Optional SMTP sender for the generated email revenue report."""

from __future__ import annotations

import argparse
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
    report_path = Path(args.report_file or f"analysis/email_revenue_report_{args.run_date}.md")
    html_path = Path(args.html_file or f"analysis/email_revenue_report_{args.run_date}.html")
    config_path = Path(args.config_file)
    print(send_if_configured(report_path, config_path, html_path))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
