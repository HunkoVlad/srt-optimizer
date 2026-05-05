"""Manual enrichment of standardized future pricing with Price Occ benchmarks."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


OPERATIONAL_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_date",
    "nightly_price",
    "min_stay",
    "status",
    "analysis_status",
    "status_confidence",
    "status_reason",
)
PRICE_OCC_REQUIRED_COLUMNS = ("Date", "Market Occupancy", "Market 50th Percentile Price")
ENRICHED_COLUMNS = (
    "run_date",
    "listing_id",
    "stay_date",
    "nightly_price",
    "min_stay",
    "status",
    "analysis_status",
    "status_confidence",
    "status_reason",
    "market_occupancy",
    "market_50th_price",
    "market_25th_price",
    "market_75th_price",
    "market_90th_price",
    "median_booked_price",
    "last_seen_price",
    "final_price",
    "holiday_event",
)

PRICE_OCC_FIELD_MAP = {
    "Market Occupancy": "market_occupancy",
    "Market 50th Percentile Price": "market_50th_price",
    "Market 25th Percentile Price": "market_25th_price",
    "Market 75th Percentile Price": "market_75th_price",
    "Market 90th Percentile Price": "market_90th_price",
    "Median Booked Price": "median_booked_price",
    "Last Seen Price": "last_seen_price",
    "Final Price": "final_price",
    "Holiday/Event": "holiday_event",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich V1 future pricing with Price Occ benchmarks.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--standardized-file",
        help="Standardized future pricing CSV. Defaults to standardized/future_daily_pricing_<run-date>.csv.",
    )
    parser.add_argument(
        "--price-occ-file",
        default="sample_data/Price Occ for 650255___717243.csv",
        help="Price Occ benchmark CSV.",
    )
    parser.add_argument(
        "--output-file",
        help="Enriched output CSV. Defaults to analysis/future_daily_pricing_enriched_<run-date>.csv.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None, required_columns: tuple[str, ...], label: str) -> None:
    if fieldnames is None:
        raise ValueError(f"{label} CSV is missing a header row")
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        raise ValueError(f"{label} CSV is missing required columns: {', '.join(missing)}")


def read_csv_rows(path: Path, required_columns: tuple[str, ...], label: str) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"{label} CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames, required_columns, label)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def build_price_occ_by_date(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_date: dict[str, dict[str, str]] = {}
    for row in rows:
        stay_date = row["Date"].strip()
        if stay_date in by_date:
            raise ValueError(f"Duplicate Price Occ Date found: {stay_date}")
        by_date[stay_date] = {
            target: row.get(source, "").strip()
            for source, target in PRICE_OCC_FIELD_MAP.items()
        }
    return by_date


def enrich_rows(
    operational_rows: list[dict[str, str]],
    price_occ_by_date: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    enriched_rows = []
    for row in operational_rows:
        enriched_row = {column: row[column].strip() for column in OPERATIONAL_COLUMNS}
        enrichment = price_occ_by_date.get(row["stay_date"].strip(), {})
        for column in ENRICHED_COLUMNS:
            enriched_row.setdefault(column, enrichment.get(column, ""))
        enriched_rows.append(enriched_row)
    return enriched_rows


def write_enriched_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=ENRICHED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    standardized_path = Path(args.standardized_file or f"standardized/future_daily_pricing_{args.run_date}.csv")
    price_occ_path = Path(args.price_occ_file)
    output_path = Path(args.output_file or f"analysis/future_daily_pricing_enriched_{args.run_date}.csv")

    operational_rows = read_csv_rows(standardized_path, OPERATIONAL_COLUMNS, "Standardized")
    price_occ_rows = read_csv_rows(price_occ_path, PRICE_OCC_REQUIRED_COLUMNS, "Price Occ")
    price_occ_by_date = build_price_occ_by_date(price_occ_rows)
    enriched_rows = enrich_rows(operational_rows, price_occ_by_date)

    if len(enriched_rows) != len(operational_rows):
        raise ValueError("Enriched output row count does not match standardized input row count")

    write_enriched_rows(output_path, enriched_rows)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
