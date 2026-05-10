import csv
import sys
import xml.sax.saxutils as xml_escape
from zipfile import ZipFile, ZIP_DEFLATED

from pricelabs.transform.historical_monthly_actuals import normalize_rows, run


def source_row(
    year_month: str,
    bookable: str = "31",
    booked: str = "12",
    paid_occ: str = "38.0%",
    occ: str = "40",
    adr: str = "$391.00",
    revpar: str = "$151.35",
    revenue: str = "$5,114.28",
) -> dict[str, str]:
    return {
        "Year & Month": year_month,
        "Bookable Nights": bookable,
        "Booked Nights": booked,
        "Paid Occupancy %": paid_occ,
        "Occupancy %": occ,
        "Rental ADR": adr,
        "Rental RevPAR": revpar,
        "Total Revenue": revenue,
    }


def write_minimal_xlsx(path, rows: list[list[str]]) -> None:
    shared_strings = []
    shared_index = {}
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            letters = ""
            number = column_index + 1
            while number:
                number, remainder = divmod(number - 1, 26)
                letters = chr(65 + remainder) + letters
            if value not in shared_index:
                shared_index[value] = len(shared_strings)
                shared_strings.append(value)
            cells.append(f'<c r="{letters}{row_index}" t="s"><v>{shared_index[value]}</v></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared_strings)}" uniqueCount="{len(shared_strings)}">'
        + "".join(f"<si><t>{xml_escape.escape(value)}</t></si>" for value in shared_strings)
        + "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as workbook:
        workbook.writestr("xl/sharedStrings.xml", shared_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def test_normalize_kpi_rows() -> None:
    rows = normalize_rows(
        [
            source_row("2026-05 (May)"),
            source_row("Total", revenue="$99,999"),
            source_row("2026-06", paid_occ="1.67", adr="", revenue="342.26"),
        ],
        "2026-05-08",
    )

    assert len(rows) == 2
    assert rows[0] == {
        "run_date": "2026-05-08",
        "stay_month": "2026-05",
        "historical_bookable_nights": "31",
        "historical_booked_nights": "12",
        "historical_paid_occupancy_pct": "38",
        "historical_occupancy_pct": "40",
        "historical_rental_adr": "391",
        "historical_rental_revpar": "151.35",
        "historical_total_revenue": "5114.28",
        "historical_source": "pricelabs_kpis_on_the_books",
    }
    assert rows[1]["stay_month"] == "2026-06"
    assert rows[1]["historical_paid_occupancy_pct"] == "1.67"
    assert rows[1]["historical_rental_adr"] == ""
    assert rows[1]["historical_total_revenue"] == "342.26"


def test_historical_monthly_actuals_cli_writes_csv(tmp_path, monkeypatch) -> None:
    input_file = tmp_path / "kpis_on_the_books.xlsx"
    output_file = tmp_path / "historical_monthly_actuals_2026-05-08.csv"
    header = [
        "Year & Month",
        "Bookable Nights",
        "Booked Nights",
        "Paid Occupancy %",
        "Occupancy %",
        "Rental ADR",
        "Rental RevPAR",
        "Total Revenue",
    ]
    write_minimal_xlsx(input_file, [header, ["2026-05 (May)", "31", "12", "38.0%", "40%", "$391", "$151.35", "$5,114.28"]])

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "historical_monthly_actuals",
            "--run-date",
            "2026-05-08",
            "--input-file",
            str(input_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0

    with output_file.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert len(rows) == 1
    assert rows[0]["stay_month"] == "2026-05"
    assert rows[0]["historical_total_revenue"] == "5114.28"
    assert rows[0]["historical_source"] == "pricelabs_kpis_on_the_books"
