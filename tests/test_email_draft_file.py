import sys

from pricelabs.transform.email_draft_file import PLACEHOLDER_RECIPIENT, read_report, run


def test_read_report_extracts_subject_and_excludes_subject_line(tmp_path) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    report.write_text(
        "Subject: Aloha Poconos Weekly Revenue Snapshot - 2026-05-08\n\n"
        "# Aloha Poconos Weekly Revenue Snapshot\n\n"
        "Body line\n",
        encoding="utf-8",
    )

    subject, body = read_report(report)

    assert subject == "Aloha Poconos Weekly Revenue Snapshot - 2026-05-08"
    assert "Subject:" not in body
    assert "# Aloha Poconos Weekly Revenue Snapshot" in body
    assert "Body line" in body


def test_email_draft_file_cli_uses_placeholder_when_config_missing(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    output = tmp_path / "email_revenue_report_2026-05-08.eml"
    missing_config = tmp_path / "email.toml"
    report.write_text(
        "Subject: Aloha Poconos Weekly Revenue Snapshot - 2026-05-08\n\n"
        "# Report\n\n"
        "Markdown body\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_draft_file",
            "--run-date",
            "2026-05-08",
            "--report-file",
            str(report),
            "--config-file",
            str(missing_config),
            "--output-file",
            str(output),
        ],
    )

    assert run() == 0
    content = output.read_text(encoding="utf-8")

    assert output.exists()
    assert f"To: {PLACEHOLDER_RECIPIENT}" in content
    assert "Subject: Aloha Poconos Weekly Revenue Snapshot - 2026-05-08" in content
    assert "MIME-Version: 1.0" in content
    assert 'Content-Type: text/plain; charset="utf-8"' in content
    assert "Content-Transfer-Encoding: 8bit" in content
    assert "Subject:" not in content.split("\n\n", 1)[1]
    assert "# Report" in content
    assert "Markdown body" in content


def test_email_draft_file_cli_uses_configured_recipient(tmp_path, monkeypatch) -> None:
    report = tmp_path / "email_revenue_report_2026-05-08.md"
    config = tmp_path / "email.toml"
    output = tmp_path / "email_revenue_report_2026-05-08.eml"
    report.write_text(
        "Subject: Revenue Snapshot\n\n"
        "# Report\n",
        encoding="utf-8",
    )
    config.write_text(
        "[email]\n"
        'mode = "draft"\n'
        'recipient_email = "owner@example.com"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_draft_file",
            "--run-date",
            "2026-05-08",
            "--report-file",
            str(report),
            "--config-file",
            str(config),
            "--output-file",
            str(output),
        ],
    )

    assert run() == 0
    content = output.read_text(encoding="utf-8")

    assert "To: owner@example.com" in content
    assert "Subject: Revenue Snapshot" in content
    assert "smtp" not in content.lower()
    assert "gmail api" not in content.lower()
