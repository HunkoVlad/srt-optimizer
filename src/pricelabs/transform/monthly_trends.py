"""Normalize PriceLabs Monthly Trends CSV."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import sys


SOURCE_COLUMNS = (
    "month_year",
    "Revenue",
    "Occupancy",
    "Booked Occupancy",
    "Blocked Occupancy",
    "ADR",
)
OUTPUT_COLUMNS = (
    "run_date",
    "month",
    "monthly_trends_revenue",
    "monthly_trends_occupancy_pct",
    "monthly_trends_booked_occupancy_pct",
    "monthly_trends_blocked_occupancy_pct",
    "monthly_trends_adr",
    "monthly_trends_source",
)
MONTHLY_TRENDS_SOURCE = "pricelabs_monthly_trends"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize PriceLabs Monthly Trends CSV.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument("--input-file", required=True, help="PriceLabs Monthly Trends CSV.")
    parser.add_argument(
        "--output-file",
        help="Normalized output CSV. Defaults to analysis/monthly_trends_normalized_<run-date>.csv.",
    )
    return parser.parse_args()


def require_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Monthly Trends CSV is missing a header row")
    missing = [column for column in SOURCE_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"Monthly Trends CSV is missing required columns: {', '.join(missing)}")


def clean_number(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    cleaned = stripped.replace("$", "").replace(",", "").replace("%", "").strip()
    if not cleaned:
        return ""
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return ""
    rounded = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded)


def parse_month(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return ""
    for fmt in ("%B %Y", "%b %Y", "%Y-%m", "%Y/%m"):
        try:
            parsed = datetime.strptime(stripped, fmt)
            return f"{parsed.year:04d}-{parsed.month:02d}"
        except ValueError:
            continue
    return ""


def normalize_rows(rows: list[dict[str, str]], run_date: str) -> list[dict[str, str]]:
    normalized = []
    for row in rows:
        month = parse_month(row.get("month_year", ""))
        if not month:
            continue
        normalized.append(
            {
                "run_date": run_date,
                "month": month,
                "monthly_trends_revenue": clean_number(row.get("Revenue", "")),
                "monthly_trends_occupancy_pct": clean_number(row.get("Occupancy", "")),
                "monthly_trends_booked_occupancy_pct": clean_number(row.get("Booked Occupancy", "")),
                "monthly_trends_blocked_occupancy_pct": clean_number(row.get("Blocked Occupancy", "")),
                "monthly_trends_adr": clean_number(row.get("ADR", "")),
                "monthly_trends_source": MONTHLY_TRENDS_SOURCE,
            }
        )
    return normalized


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Monthly Trends CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        require_columns(reader.fieldnames)
        return [{key: value or "" for key, value in row.items()} for row in reader]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    output_path = Path(args.output_file or f"analysis/monthly_trends_normalized_{args.run_date}.csv")
    rows = normalize_rows(read_rows(Path(args.input_file)), args.run_date)
    write_rows(output_path, rows)
    print(f"Wrote {output_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
