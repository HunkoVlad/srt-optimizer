import sys
from unittest.mock import Mock

import pytest

from pricelabs.transform import email_sender
from pricelabs.transform.email_sender import explicit_send_report, read_send_results, send_if_configured, run


def write_report(path) -> None:
    path.write_text(
        "Subject: Revenue Snapshot\n\n"
        "# Revenue Snapshot\n\n"
        "Body text\n",
        encoding="utf-8",
    )


def write_config(
    path,
    mode: str = "draft",
    smtp_enabled: str = "false",
    recipient: str = "owner@example.com",
    report_format: str = "markdown",
    subject_prefix: str = "",
) -> None:
    path.write_text(
        "[email]\n"
        f'mode = "{mode}"\n'
        f'recipient_email = "{recipient}"\n'
        'cc_email = "cc@example.com"\n'
        f'subject_prefix = "{subject_prefix}"\n'
        "\n"
        "[smtp]\n"
        f"enabled = {smtp_enabled}\n"
        'host = "smtp.gmail.com"\n'
        "port = 587\n"
        'sender_email = "sender@gmail.com"\n'
        'password_env_var = "ALOHA_GMAIL_APP_PASSWORD"\n'
        "use_tls = true\n"
        "\n"
        "[report]\n"
        f'format = "{report_format}"\n',
        encoding="utf-8",
    )


def test_missing_config_does_not_send(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    write_report(report)
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    status = send_if_configured(report, tmp_path / "missing.toml")

    assert status == "Email mode: draft — send skipped."
    send_mock.assert_not_called()


def test_draft_mode_does_not_send(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    config = tmp_path / "email.toml"
    write_report(report)
    write_config(config, mode="draft", smtp_enabled="true")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    status = send_if_configured(report, config)

    assert status == "Email mode: draft — send skipped."
    send_mock.assert_not_called()


def test_send_mode_requires_smtp_enabled(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    config = tmp_path / "email.toml"
    write_report(report)
    write_config(config, mode="send", smtp_enabled="false")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    status = send_if_configured(report, config)

    assert status == "Email mode: send but SMTP disabled — send skipped."
    send_mock.assert_not_called()


def test_send_mode_requires_password_env_var(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    config = tmp_path / "email.toml"
    write_report(report)
    write_config(config, mode="send", smtp_enabled="true")
    monkeypatch.delenv("ALOHA_GMAIL_APP_PASSWORD", raising=False)
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    with pytest.raises(RuntimeError, match="ALOHA_GMAIL_APP_PASSWORD"):
        send_if_configured(report, config)

    send_mock.assert_not_called()


def test_send_mode_uses_configured_sender_recipient_and_report_body(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    config = tmp_path / "email.toml"
    write_report(report)
    write_config(config, mode="send", smtp_enabled="true")
    monkeypatch.setenv("ALOHA_GMAIL_APP_PASSWORD", "secret-password")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    status = send_if_configured(report, config)

    assert status == "Email sent to owner@example.com."
    send_mock.assert_called_once()
    message, host, port, sender, password, use_tls = send_mock.call_args.args
    assert host == "smtp.gmail.com"
    assert port == 587
    assert sender == "sender@gmail.com"
    assert password == "secret-password"
    assert use_tls is True
    assert message["From"] == "sender@gmail.com"
    assert message["To"] == "owner@example.com"
    assert message["Cc"] == "cc@example.com"
    assert message["Subject"] == "Revenue Snapshot"
    assert "Subject:" not in message.get_content()
    assert "# Revenue Snapshot" in message.get_content()
    assert "Body text" in message.get_content()
    assert message.get_content_type() == "text/plain"


def test_send_mode_uses_html_body_when_configured(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    html_report = tmp_path / "email_revenue_report_2026-05-08.html"
    config = tmp_path / "email.toml"
    write_report(report)
    html_report.write_text("<html><body><h1>Revenue Snapshot</h1></body></html>", encoding="utf-8")
    write_config(config, mode="send", smtp_enabled="true", report_format="html")
    monkeypatch.setenv("ALOHA_GMAIL_APP_PASSWORD", "secret-password")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    status = send_if_configured(report, config, html_report)

    assert status == "Email sent to owner@example.com."
    message = send_mock.call_args.args[0]
    assert message.is_multipart()
    assert message.get_body(preferencelist=("html",)).get_content_type() == "text/html"
    assert "<h1>Revenue Snapshot</h1>" in message.get_body(preferencelist=("html",)).get_content()
    assert "# Revenue Snapshot" in message.get_body(preferencelist=("plain",)).get_content()


def test_cli_reports_draft_skip_without_sending(tmp_path, monkeypatch, capsys) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    config = tmp_path / "email.toml"
    write_report(report)
    write_config(config, mode="draft", smtp_enabled="true")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_sender",
            "--run-date",
            "2026-05-08",
            "--report-file",
            str(report),
            "--config-file",
            str(config),
        ],
    )

    assert run() == 0

    assert "Email mode: draft — send skipped." in capsys.readouterr().out
    send_mock.assert_not_called()
def test_explicit_send_sends_html_report_even_when_config_mode_is_draft(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-06-08.md"
    html_report = tmp_path / "email_revenue_report_2026-06-08.html"
    config = tmp_path / "email.toml"
    result_csv = tmp_path / "email_revenue_report_send_result_2026-06-08.csv"
    write_report(report)
    html_report.write_text("<html><body><h1>Revenue Snapshot</h1></body></html>", encoding="utf-8")
    write_config(config, mode="draft", smtp_enabled="false", report_format="html", subject_prefix="[Aloha]")
    monkeypatch.setenv("ALOHA_GMAIL_APP_PASSWORD", "secret-password")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    status = explicit_send_report(
        run_date="2026-06-08",
        report_path=report,
        html_path=html_report,
        config_path=config,
        result_path=result_csv,
    )

    assert status == "Weekly report email sent to owner@example.com."
    message, host, port, sender, password, use_tls = send_mock.call_args.args
    assert host == "smtp.gmail.com"
    assert port == 587
    assert sender == "sender@gmail.com"
    assert password == "secret-password"
    assert use_tls is True
    assert message["To"] == "owner@example.com"
    assert message["From"] == "sender@gmail.com"
    assert message["Subject"] == "[Aloha] Revenue Snapshot"
    assert message.get_body(preferencelist=("html",)).get_content_type() == "text/html"
    rows = read_send_results(result_csv)
    assert rows[0]["send_status"] == "sent"
    assert rows[0]["recipient"] == "owner@example.com"
    assert rows[0]["sender"] == "sender@gmail.com"
    assert rows[0]["report_path_used"] == str(html_report)
    assert rows[0]["sent_at"]
    assert "secret-password" not in result_csv.read_text(encoding="utf-8")


def test_explicit_send_falls_back_to_markdown_when_html_missing(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-06-08.md"
    html_report = tmp_path / "missing.html"
    config = tmp_path / "email.toml"
    result_csv = tmp_path / "email_revenue_report_send_result_2026-06-08.csv"
    write_report(report)
    write_config(config, mode="draft", smtp_enabled="false", report_format="html")
    monkeypatch.setenv("ALOHA_GMAIL_APP_PASSWORD", "secret-password")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    explicit_send_report(
        run_date="2026-06-08",
        report_path=report,
        html_path=html_report,
        config_path=config,
        result_path=result_csv,
    )

    message = send_mock.call_args.args[0]
    assert message.get_content_type() == "text/plain"
    assert read_send_results(result_csv)[0]["report_path_used"] == str(report)


def test_explicit_send_missing_password_writes_failed_result_without_secret(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-06-08.md"
    html_report = tmp_path / "email_revenue_report_2026-06-08.html"
    config = tmp_path / "email.toml"
    result_csv = tmp_path / "email_revenue_report_send_result_2026-06-08.csv"
    write_report(report)
    html_report.write_text("<html></html>", encoding="utf-8")
    write_config(config, mode="draft", smtp_enabled="false", report_format="html")
    monkeypatch.delenv("ALOHA_GMAIL_APP_PASSWORD", raising=False)
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    with pytest.raises(RuntimeError, match="ALOHA_GMAIL_APP_PASSWORD"):
        explicit_send_report(
            run_date="2026-06-08",
            report_path=report,
            html_path=html_report,
            config_path=config,
            result_path=result_csv,
        )

    send_mock.assert_not_called()
    rows = read_send_results(result_csv)
    assert rows[0]["send_status"] == "failed"
    assert "ALOHA_GMAIL_APP_PASSWORD" in rows[0]["error_message"]
    assert "secret" not in result_csv.read_text(encoding="utf-8").lower()


def test_explicit_send_skips_if_already_sent(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-06-08.md"
    html_report = tmp_path / "email_revenue_report_2026-06-08.html"
    config = tmp_path / "email.toml"
    result_csv = tmp_path / "email_revenue_report_send_result_2026-06-08.csv"
    write_report(report)
    html_report.write_text("<html></html>", encoding="utf-8")
    write_config(config, mode="draft", smtp_enabled="false", report_format="html")
    monkeypatch.setenv("ALOHA_GMAIL_APP_PASSWORD", "secret-password")
    send_mock = Mock()
    monkeypatch.setattr(email_sender, "send_message", send_mock)

    explicit_send_report(
        run_date="2026-06-08",
        report_path=report,
        html_path=html_report,
        config_path=config,
        result_path=result_csv,
    )
    second_status = explicit_send_report(
        run_date="2026-06-08",
        report_path=report,
        html_path=html_report,
        config_path=config,
        result_path=result_csv,
    )

    assert second_status == "Weekly report email send skipped: already sent for this run."
    assert send_mock.call_count == 1
    rows = read_send_results(result_csv)
    assert [row["send_status"] for row in rows] == ["sent", "skipped"]
