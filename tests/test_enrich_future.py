from decimal import Decimal
import csv
import sys

from pricelabs.transform.enrich_future import enrich_rows, run


STEP_1_COLUMNS = (
    "upcoming_adr",
    "booked_revenue_proxy",
    "open_revenue_ask",
    "previous_status",
    "previous_upcoming_adr",
    "booked_stay_start_proxy",
    "booked_stay_id_proxy",
)


def operational_row(stay_date: str, status: str, nightly_price: str) -> dict[str, str]:
    return {
        "run_date": "2026-05-01",
        "listing_id": "650255___717243",
        "stay_date": stay_date,
        "nightly_price": nightly_price,
        "min_stay": "1",
        "status": status,
        "upcoming_adr": "",
        "analysis_status": status if status in {"available", "booked", "blocked"} else "booked",
        "status_confidence": "high",
        "status_reason": f"explicit_{status}",
    }


def money_sum(rows: list[dict[str, str]], column: str) -> Decimal:
    return sum(Decimal(row[column] or "0") for row in rows)


def test_revenue_and_booked_stay_proxies() -> None:
    operational_rows = [
        operational_row("2026-05-10", "booked", "350"),
        operational_row("2026-05-11", "booked", "350"),
        operational_row("2026-05-12", "booked", "500"),
        operational_row("2026-05-13", "available", "475"),
        operational_row("2026-05-14", "blocked", "600"),
        operational_row("2026-05-15", "unavailable", "700"),
    ]
    operational_rows[0]["upcoming_adr"] = "350"
    operational_rows[1]["upcoming_adr"] = "350.004"
    operational_rows[2]["upcoming_adr"] = "500"

    rows = enrich_rows(operational_rows, {})

    assert money_sum(rows, "booked_revenue_proxy") == Decimal("1200")
    assert money_sum(rows, "open_revenue_ask") == Decimal("475")
    assert sum(int(row["booked_stay_start_proxy"]) for row in rows) == 2
    assert [row["booked_stay_id_proxy"] for row in rows if row["status"] == "booked"] == ["1", "1", "2"]
    assert [row["booked_stay_id_proxy"] for row in rows if row["status"] != "booked"] == ["", "", ""]


def test_blocked_and_unavailable_do_not_contribute_revenue_proxy() -> None:
    rows = enrich_rows(
        [
            operational_row("2026-05-10", "blocked", "400"),
            operational_row("2026-05-11", "unavailable", "500"),
        ],
        {},
    )

    assert all(row["booked_revenue_proxy"] == "0" for row in rows)
    assert all(row["open_revenue_ask"] == "0" for row in rows)
    assert all(row["booked_stay_id_proxy"] == "" for row in rows)


def test_enrichment_cli_writes_step_1_columns(tmp_path, monkeypatch) -> None:
    standardized_file = tmp_path / "future_daily_pricing_2026-05-10.csv"
    price_occ_file = tmp_path / "price_occ.csv"
    output_file = tmp_path / "future_daily_pricing_enriched_2026-05-10.csv"

    with standardized_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=(
                "run_date",
                "listing_id",
                "stay_date",
                "nightly_price",
                "min_stay",
                "status",
                "upcoming_adr",
                "analysis_status",
                "status_confidence",
                "status_reason",
            ),
        )
        writer.writeheader()
        writer.writerow(
            {
                "run_date": "2026-05-10",
                "listing_id": "650255___717243",
                "stay_date": "2026-05-10",
                "nightly_price": "350",
                "min_stay": "1",
                "status": "booked",
                "upcoming_adr": "350",
                "analysis_status": "booked",
                "status_confidence": "high",
                "status_reason": "explicit_booked",
            }
        )

    with price_occ_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("Date", "Market Occupancy", "Market 50th Percentile Price", "Upcoming ADR"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "Date": "2026-05-10",
                "Market Occupancy": "10",
                "Market 50th Percentile Price": "300",
                "Upcoming ADR": "999",
            }
        )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "enrich_future",
            "--run-date",
            "2026-05-10",
            "--standardized-file",
            str(standardized_file),
            "--price-occ-file",
            str(price_occ_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0

    with output_file.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        assert reader.fieldnames is not None
        for column in STEP_1_COLUMNS:
            assert column in reader.fieldnames
        row = next(reader)

    assert row["upcoming_adr"] == "350"
    assert row["booked_revenue_proxy"] == "350"
    assert row["booked_stay_start_proxy"] == "1"
