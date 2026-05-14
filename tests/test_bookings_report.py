import csv
import sys
import xml.sax.saxutils as xml_escape
from zipfile import ZipFile, ZIP_DEFLATED

from pricelabs.transform.bookings_report import aggregate_monthly, normalize_rows, run


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


def source_row(
    status: str = "Booked",
    check_in: str = "2026-05-10",
    nights: str = "3",
    revenue: str = "$1,200",
    booking_source: str = "Airbnb",
) -> dict[str, str]:
    return {
        "Listing Name": "Aloha Poconos.",
        "Check-in Date": check_in,
        "Check-out Date": "2026-05-13",
        "Booked Date": "2026-04-20",
        "Average Daily Rate": "$400",
        "Rental Revenue": revenue,
        "Total Revenue": "$1,350",
        "Booking Source": booking_source,
        "Booking Status": status,
        "Length of Stay (Days)": nights,
        "Booking Window (Days)": "20",
        "Reservation ID": "R1",
        "Listing ID": "650255___717243",
    }


def test_bookings_report_normalization_and_aggregation() -> None:
    rows = normalize_rows(
        [
            source_row(),
            source_row(check_in="2026-05-18", nights="2", revenue="$900"),
            source_row(status="Cancelled", check_in="2026-05-20", nights="5", revenue="$9999"),
        ],
        "2026-05-08",
    )
    metrics = aggregate_monthly(rows)

    assert len(rows) == 2
    assert rows[0]["stay_month"] == "2026-05"
    assert rows[0]["average_daily_rate"] == "400"
    assert rows[0]["rental_revenue"] == "1200"
    assert metrics == [
        {
            "run_date": "2026-05-08",
            "month": "2026-05",
            "bookings_report_bookings": "2",
            "bookings_report_cleanings_proxy": "2",
            "bookings_report_booked_nights": "5",
            "bookings_report_avg_los": "2.50",
            "bookings_report_rental_revenue": "2100",
            "bookings_report_total_revenue": "2700",
            "bookings_report_adr": "420",
            "bookings_report_avg_booking_window": "20",
            "airbnb_stays": "2",
            "vrbo_stays": "0",
            "direct_stays": "0",
            "other_unknown_stays": "0",
            "main_booking_source": "airbnb",
            "booking_source_mix_summary": "Airbnb 2",
        }
    ]


def test_booking_source_mix_counts_and_main_source() -> None:
    rows = normalize_rows(
        [
            source_row(booking_source="Airbnb"),
            source_row(booking_source="Airbnb"),
            source_row(booking_source="VRBO"),
            source_row(booking_source="Lodgify Direct"),
            source_row(booking_source=""),
        ],
        "2026-05-08",
    )

    metrics = aggregate_monthly(rows)

    assert metrics[0]["airbnb_stays"] == "2"
    assert metrics[0]["vrbo_stays"] == "1"
    assert metrics[0]["direct_stays"] == "1"
    assert metrics[0]["other_unknown_stays"] == "1"
    assert metrics[0]["main_booking_source"] == "airbnb"
    assert metrics[0]["booking_source_mix_summary"] == "Airbnb 2, Vrbo 1, Direct 1, Other/Unknown 1"


def test_bookings_report_cli_writes_outputs(tmp_path, monkeypatch) -> None:
    input_file = tmp_path / "bookings_report.xlsx"
    normalized_file = tmp_path / "bookings_report_normalized_2026-05-08.csv"
    metrics_file = tmp_path / "monthly_booking_metrics_2026-05-08.csv"
    header = [
        "Listing Name",
        "Check-in Date",
        "Check-out Date",
        "Booked Date",
        "Average Daily Rate",
        "Rental Revenue",
        "Total Revenue",
        "Booking Source",
        "Booking Status",
        "Length of Stay (Days)",
        "Booking Window (Days)",
        "Reservation ID",
        "Listing ID",
    ]
    write_minimal_xlsx(
        input_file,
        [
            header,
            [
                "Aloha Poconos.",
                "2026-06-01",
                "2026-06-03",
                "2026-05-01",
                "$500",
                "$1,000",
                "$1,100",
                "Airbnb",
                "Booked",
                "2",
                "31",
                "R2",
                "650255___717243",
            ],
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "bookings_report",
            "--run-date",
            "2026-05-08",
            "--input-file",
            str(input_file),
            "--normalized-output-file",
            str(normalized_file),
            "--metrics-output-file",
            str(metrics_file),
        ],
    )

    assert run() == 0

    with normalized_file.open("r", newline="", encoding="utf-8") as csv_file:
        normalized = list(csv.DictReader(csv_file))
    with metrics_file.open("r", newline="", encoding="utf-8") as csv_file:
        metrics = list(csv.DictReader(csv_file))

    assert normalized[0]["stay_month"] == "2026-06"
    assert metrics[0]["bookings_report_booked_nights"] == "2"
    assert metrics[0]["bookings_report_adr"] == "500"
    assert metrics[0]["airbnb_stays"] == "1"
