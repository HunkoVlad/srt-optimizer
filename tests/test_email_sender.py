import sys
from unittest.mock import Mock

import pytest

from pricelabs.transform import email_sender
from pricelabs.transform.email_sender import send_if_configured, run


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
) -> None:
    path.write_text(
        "[email]\n"
        f'mode = "{mode}"\n'
        f'recipient_email = "{recipient}"\n'
        'cc_email = "cc@example.com"\n'
        "\n"
        "[smtp]\n"
        f"enabled = {smtp_enabled}\n"
        'host = "smtp.gmail.com"\n'
        "port = 587\n"
        'sender_email = "sender@gmail.com"\n'
        'password_env_var = "ALOHA_GMAIL_APP_PASSWORD"\n'
        "use_tls = true\n",
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
