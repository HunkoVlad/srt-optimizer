"""Normalize PriceLabs KPIs On The Books to monthly historical actuals."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile


SOURCE_COLUMNS = (
    "Year & Month",
    "Bookable Nights",
    "Booked Nights",
    "Paid Occupancy %",
    "Occupancy %",
    "Rental ADR",
    "Rental RevPAR",
    "Total Revenue",
)
OUTPUT_COLUMNS = (
    "run_date",
    "stay_month",
    "historical_bookable_nights",
    "historical_booked_nights",
    "historical_paid_occupancy_pct",
    "historical_occupancy_pct",
    "historical_rental_adr",
    "historical_rental_revpar",
    "historical_total_revenue",
    "historical_source",
)
FIELD_MAP = {
    "Bookable Nights": "historical_bookable_nights",
    "Booked Nights": "historical_booked_nights",
    "Paid Occupancy %": "historical_paid_occupancy_pct",
    "Occupancy %": "historical_occupancy_pct",
    "Rental ADR": "historical_rental_adr",
    "Rental RevPAR": "historical_rental_revpar",
    "Total Revenue": "historical_total_revenue",
}
HISTORICAL_SOURCE = "pricelabs_kpis_on_the_books"
XML_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize PriceLabs KPI historical monthly actuals.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--input-file",
        default="data/runs/<run_date>/raw/kpis_on_the_books.xlsx",
        help="PriceLabs KPIs On The Books XLSX.",
    )
    parser.add_argument(
        "--output-file",
        help="Historical actuals CSV. Defaults to analysis/historical_monthly_actuals_<run-date>.csv.",
    )
    return parser.parse_args()


def column_index(cell_reference: str) -> int:
    letters = "".join(char for char in cell_reference if char.isalpha())
    index = 0
    for char in letters:
        index = index * 26 + (ord(char.upper()) - ord("A") + 1)
    return index - 1


def read_shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    shared_strings = []
    for item in root.findall("a:si", XML_NS):
        shared_strings.append("".join(text.text or "" for text in item.findall(".//a:t", XML_NS)))
    return shared_strings


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//a:t", XML_NS)).strip()

    value_node = cell.find("a:v", XML_NS)
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text.strip()
    if cell_type == "s" and value:
        return shared_strings[int(value)].strip()
    return value


def read_xlsx_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        raise FileNotFoundError(f"KPI workbook does not exist: {path}")
    with ZipFile(path) as workbook:
        shared_strings = read_shared_strings(workbook)
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row in sheet.findall(".//a:sheetData/a:row", XML_NS):
            values_by_index: dict[int, str] = {}
            for cell in row.findall("a:c", XML_NS):
                values_by_index[column_index(cell.attrib["r"])] = cell_value(cell, shared_strings)
            if values_by_index:
                last_index = max(values_by_index)
                rows.append([values_by_index.get(index, "") for index in range(last_index + 1)])
        return rows


def rows_to_dicts(rows: list[list[str]]) -> list[dict[str, str]]:
    if not rows:
        raise ValueError("KPI workbook is empty")
    header = [value.strip() for value in rows[0]]
    missing = [column for column in SOURCE_COLUMNS if column not in header]
    if missing:
        raise ValueError(f"KPI workbook is missing required columns: {', '.join(missing)}")
    output = []
    for row in rows[1:]:
        output.append({column: row[index].strip() if index < len(row) else "" for index, column in enumerate(header)})
    return output


def parse_stay_month(value: str) -> str:
    match = re.search(r"(\d{4})[-/](\d{1,2})", value.strip())
    if not match:
        return ""
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"


def clean_number(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    cleaned = stripped.replace("$", "").replace(",", "").replace("%", "").strip()
    if not cleaned:
        return ""
    try:
        decimal_value = Decimal(cleaned)
    except InvalidOperation:
        return ""
    rounded = decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded)


def normalize_rows(rows: list[dict[str, str]], run_date: str) -> list[dict[str, str]]:
    normalized_rows = []
    for row in rows:
        stay_month = parse_stay_month(row.get("Year & Month", ""))
        if not stay_month:
            continue
        normalized_row = {
            "run_date": run_date,
            "stay_month": stay_month,
            "historical_source": HISTORICAL_SOURCE,
        }
        for source, target in FIELD_MAP.items():
            normalized_row[target] = clean_number(row.get(source, ""))
        normalized_rows.append({column: normalized_row.get(column, "") for column in OUTPUT_COLUMNS})
    return normalized_rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def normalize_workbook(input_path: Path, output_path: Path, run_date: str) -> int:
    source_rows = rows_to_dicts(read_xlsx_rows(input_path))
    normalized_rows = normalize_rows(source_rows, run_date)
    write_rows(output_path, normalized_rows)
    return len(normalized_rows)


def run() -> int:
    args = parse_args()
    input_path = Path(args.input_file.replace("<run_date>", args.run_date))
    output_path = Path(args.output_file or f"analysis/historical_monthly_actuals_{args.run_date}.csv")

    row_count = normalize_workbook(input_path, output_path, args.run_date)
    print(f"Wrote {output_path} ({row_count} rows)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
