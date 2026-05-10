"""Create a local .eml draft file from the email-ready markdown report."""

from __future__ import annotations

import argparse
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
import sys
import tomllib


PLACEHOLDER_RECIPIENT = "your-email@example.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a local .eml email draft file.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--report-file",
        help="Email-ready markdown report. Defaults to analysis/email_revenue_report_<run-date>.md.",
    )
    parser.add_argument(
        "--config-file",
        default="config/email.toml",
        help="Optional local email config TOML. Defaults to config/email.toml.",
    )
    parser.add_argument(
        "--output-file",
        help="Draft .eml output. Defaults to analysis/email_revenue_report_<run-date>.eml.",
    )
    return parser.parse_args()


def read_report(path: Path) -> tuple[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Email revenue report does not exist: {path}")

    lines = path.read_text(encoding="utf-8-sig").splitlines()
    subject_index = next(
        (index for index, line in enumerate(lines) if line.startswith("Subject:")),
        None,
    )
    if subject_index is None:
        raise ValueError("Email revenue report is missing a Subject: line")

    subject = lines[subject_index].removeprefix("Subject:").strip()
    body_lines = lines[:subject_index] + lines[subject_index + 1 :]
    while body_lines and not body_lines[0].strip():
        body_lines.pop(0)
    body = "\n".join(body_lines).strip() + "\n"
    return subject, body


def read_recipient(path: Path) -> str:
    if not path.exists():
        return PLACEHOLDER_RECIPIENT

    with path.open("rb") as config_file:
        config = tomllib.load(config_file)
    recipient = str(config.get("email", {}).get("recipient_email", "")).strip()
    return recipient or PLACEHOLDER_RECIPIENT


def build_message(subject: str, body: str, recipient: str) -> EmailMessage:
    message = EmailMessage(policy=SMTP)
    message["To"] = recipient
    message["Subject"] = subject
    message["MIME-Version"] = "1.0"
    message.set_content(body, subtype="plain", charset="utf-8", cte="8bit")
    return message


def write_draft(path: Path, message: EmailMessage) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(message.as_bytes(policy=SMTP))


def run() -> int:
    args = parse_args()
    report_path = Path(args.report_file or f"analysis/email_revenue_report_{args.run_date}.md")
    config_path = Path(args.config_file)
    output_path = Path(args.output_file or f"analysis/email_revenue_report_{args.run_date}.eml")

    subject, body = read_report(report_path)
    recipient = read_recipient(config_path)
    message = build_message(subject, body, recipient)
    write_draft(output_path, message)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
