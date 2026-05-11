import sys

from pricelabs.transform.email_html_report import build_html, run


def sample_body() -> str:
    return (
        "# Aloha Poconos Weekly Revenue Snapshot - 2026-05-08\n\n"
        "## Executive Snapshot\n\n"
        "- Current month 2026-05 is conversion_risk.\n\n"
        "## What Needs Attention\n\n"
        "- 2026-05 needs review.\n\n"
        "## Recommendation Review\n\n"
        "- Review near-term conversion behavior.\n\n"
        "## Key Monthly Snapshot\n\n"
        "| Month | Data | Revenue Captured |\n"
        "| --- | --- | ---: |\n"
        "| 2026-05 | available | $2,834 |\n\n"
        "## Data Notes\n\n"
        "- Market benchmark is context only.\n"
    )


def test_build_html_renders_sections_and_table() -> None:
    html = build_html("Revenue Snapshot", sample_body())

    assert "<h1>Aloha Poconos Weekly Revenue Snapshot - 2026-05-08</h1>" in html
    assert "<h2>Executive Snapshot</h2>" in html
    assert "<h2>What Needs Attention</h2>" in html
    assert "<h2>Recommendation Review</h2>" in html
    assert "<h2>Key Monthly Snapshot</h2>" in html
    assert "<h2>Data Notes</h2>" in html
    assert "<table>" in html
    assert "<th>Month</th>" in html
    assert "<td>2026-05</td>" in html
    assert '<td class="num">$2,834</td>' in html
    assert "<script" not in html.lower()
    assert "http://" not in html.lower()
    assert "https://" not in html.lower()


def test_email_html_report_cli_writes_file(tmp_path, monkeypatch) -> None:
    report_file = tmp_path / "email_revenue_report_2026-05-08.md"
    output_file = tmp_path / "email_revenue_report_2026-05-08.html"
    report_file.write_text(
        "Subject: Revenue Snapshot\n\n" + sample_body(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_html_report",
            "--run-date",
            "2026-05-08",
            "--report-file",
            str(report_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0
    assert output_file.exists()
    assert "<html>" in output_file.read_text(encoding="utf-8")
