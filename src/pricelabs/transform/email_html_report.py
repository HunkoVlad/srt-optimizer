"""Render the email-ready markdown report as simple standalone HTML."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re
import sys

from pricelabs.transform.email_draft_file import read_report


TABLE_SEPARATOR_PATTERN = re.compile(r"^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML email revenue report.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--report-file",
        help="Email-ready markdown report. Defaults to analysis/email_revenue_report_<run-date>.md.",
    )
    parser.add_argument(
        "--output-file",
        help="HTML output file. Defaults to analysis/email_revenue_report_<run-date>.html.",
    )
    return parser.parse_args()


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    return bool(TABLE_SEPARATOR_PATTERN.match(line.strip()))


def cell_is_numeric(value: str) -> bool:
    if re.match(r"^\d{4}-\d{2}$", value):
        return False
    if value == "-":
        return True
    compact = value.replace("$", "").replace(",", "").replace("%", "").replace("-", "").strip()
    return bool(compact) and compact.replace(".", "", 1).isdigit()


def render_table(lines: list[str], start_index: int) -> tuple[str, int]:
    headers = split_table_row(lines[start_index])
    index = start_index + 2
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].strip().startswith("|"):
        rows.append(split_table_row(lines[index]))
        index += 1

    html_lines = ["<table>", "<thead>", "<tr>"]
    html_lines.extend(f"<th>{escape(header)}</th>" for header in headers)
    html_lines.extend(["</tr>", "</thead>", "<tbody>"])
    for row in rows:
        html_lines.append("<tr>")
        for cell in row:
            class_attr = ' class="num"' if cell_is_numeric(cell) else ""
            html_lines.append(f"<td{class_attr}>{escape(cell)}</td>")
        html_lines.append("</tr>")
    html_lines.extend(["</tbody>", "</table>"])
    return "\n".join(html_lines), index


def markdown_body_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    html_lines: list[str] = []
    in_list = False
    index = 0

    while index < len(lines):
        line = lines[index].rstrip()
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            index += 1
            continue

        if stripped.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            table_html, index = render_table(lines, index)
            html_lines.append(table_html)
            continue

        if stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{escape(stripped[2:].strip())}</li>")
            index += 1
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False

        heading_level = len(stripped) - len(stripped.lstrip("#"))
        if 1 <= heading_level <= 3 and stripped[heading_level:].startswith(" "):
            text = stripped[heading_level:].strip()
            html_lines.append(f"<h{heading_level}>{escape(text)}</h{heading_level}>")
        else:
            html_lines.append(f"<p>{escape(stripped)}</p>")
        index += 1

    if in_list:
        html_lines.append("</ul>")
    return "\n".join(html_lines)


def build_html(subject: str, body: str) -> str:
    body_html = markdown_body_to_html(body)
    title = escape(subject)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
body {{ margin: 0; padding: 24px; background: #f6f7f9; color: #1f2933; font-family: Arial, Helvetica, sans-serif; line-height: 1.45; }}
.report {{ max-width: 900px; margin: 0 auto; background: #ffffff; padding: 28px; border: 1px solid #d9dee7; }}
h1 {{ margin: 0 0 20px; font-size: 24px; }}
h2 {{ margin: 28px 0 12px; font-size: 18px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }}
h3 {{ margin: 18px 0 8px; font-size: 15px; }}
p {{ margin: 10px 0; }}
ul {{ margin: 8px 0 16px 22px; padding: 0; }}
li {{ margin: 5px 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0 22px; font-size: 13px; }}
th, td {{ border: 1px solid #d9dee7; padding: 7px 8px; vertical-align: top; }}
th {{ background: #f0f3f7; text-align: left; font-weight: 700; }}
td.num {{ text-align: right; white-space: nowrap; }}
</style>
</head>
<body>
<div class="report">
{body_html}
</div>
</body>
</html>
"""


def write_html(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run() -> int:
    args = parse_args()
    report_path = Path(args.report_file or f"analysis/email_revenue_report_{args.run_date}.md")
    output_path = Path(args.output_file or f"analysis/email_revenue_report_{args.run_date}.html")
    subject, body = read_report(report_path)
    write_html(output_path, build_html(subject, body))
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
