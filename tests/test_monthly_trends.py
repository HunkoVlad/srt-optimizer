import csv
import sys

from pricelabs.transform.monthly_trends import normalize_rows, run


def test_monthly_trends_normalization() -> None:
    rows = normalize_rows(
        [
            {
                "month_year": "May 2026",
                "Revenue": "$10,259.25",
                "Occupancy": "45%",
                "Booked Occupancy": "35.5%",
                "Blocked Occupancy": "2",
                "ADR": "$425.10",
            },
            {
                "month_year": "Total",
                "Revenue": "$99,999",
                "Occupancy": "",
                "Booked Occupancy": "",
                "Blocked Occupancy": "",
                "ADR": "",
            },
        ],
        "2026-05-08",
    )

    assert rows == [
        {
            "run_date": "2026-05-08",
            "month": "2026-05",
            "monthly_trends_revenue": "10259.25",
            "monthly_trends_occupancy_pct": "45",
            "monthly_trends_booked_occupancy_pct": "35.50",
            "monthly_trends_blocked_occupancy_pct": "2",
            "monthly_trends_adr": "425.10",
            "monthly_trends_source": "pricelabs_monthly_trends",
        }
    ]


def test_monthly_trends_cli_writes_csv(tmp_path, monkeypatch) -> None:
    input_file = tmp_path / "monthly_trends.csv"
    output_file = tmp_path / "monthly_trends_normalized_2026-05-08.csv"

    with input_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("month_year", "Revenue", "Occupancy", "Booked Occupancy", "Blocked Occupancy", "ADR"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "month_year": "June 2026",
                "Revenue": "$1,234.00",
                "Occupancy": "12.3%",
                "Booked Occupancy": "10%",
                "Blocked Occupancy": "1%",
                "ADR": "$411",
            }
        )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "monthly_trends",
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

    assert rows[0]["month"] == "2026-06"
    assert rows[0]["monthly_trends_revenue"] == "1234"
