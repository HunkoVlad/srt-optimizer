"""Normalize PriceLabs Competitor Calendar exports."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import sys


LIST_COLUMNS = [
    "competitor_name",
    "airbnb_url",
    "bedrooms",
    "rating",
    "review_count",
    "cleaning_fee",
    "airbnb_service_fee_type",
    "notes",
    "sample_date",
    "competitor_price",
    "competitor_min_stay",
    "visible_total_price_notes",
    "competitor_listing_id",
    "source_file",
    "is_subject_listing",
]

CALENDAR_COLUMNS = [
    "run_date",
    "stay_date",
    "competitor_name",
    "competitor_listing_id",
    "airbnb_url",
    "is_subject_listing",
    "competitor_price",
    "competitor_available",
    "competitor_min_stay",
    "source_file",
]

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LISTING_RE = re.compile(r"^(?P<name>.+?) \((?P<listing_id>\d+)\)$")
NOTES = "Imported from PriceLabs Competitor Calendar export. Daily prices, availability, and min stay are available in source calendar."
DEFAULT_HORIZON_DAYS = 90


@dataclass(frozen=True)
class ListingTriplet:
    name: str
    listing_id: str
    price_column: str
    available_column: str
    min_stay_column: str
    is_subject_listing: bool

    @property
    def airbnb_url(self) -> str:
        if not self.listing_id:
            return ""
        return f"https://www.airbnb.com/rooms/{self.listing_id}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize PriceLabs Competitor Calendar export.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--input-file",
        help="PriceLabs Competitor Calendar CSV. Defaults to data/runs/<run-date>/raw/Competitor Calendar.csv.",
    )
    parser.add_argument(
        "--competitor-list-output",
        help="Competitor list output CSV. Defaults to raw/pricelabs_competitor_list_<run-date>.csv.",
    )
    parser.add_argument(
        "--calendar-output",
        help="Normalized calendar output CSV. Defaults to analysis/pricelabs_competitor_calendar_<run-date>.csv.",
    )
    return parser.parse_args()


def parse_stay_date(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def mangle_fieldnames(fieldnames: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    mangled: list[str] = []
    for index, fieldname in enumerate(fieldnames):
        name = fieldname.strip() if fieldname else ""
        if index == 0 and not name:
            name = "Unnamed: 0"
        if name not in counts:
            counts[name] = 0
            mangled.append(name)
            continue
        counts[name] += 1
        mangled.append(f"{name}.{counts[name]}")
    return mangled


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"PriceLabs Competitor Calendar CSV does not exist: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.reader(csv_file)
        try:
            raw_fieldnames = next(reader)
        except StopIteration as exc:
            raise ValueError("PriceLabs Competitor Calendar CSV is missing a header row")
        fieldnames = mangle_fieldnames(raw_fieldnames)
        rows = []
        for values in reader:
            padded_values = values + [""] * max(0, len(fieldnames) - len(values))
            rows.append({key: value or "" for key, value in zip(fieldnames, padded_values, strict=False)})
        return fieldnames, rows


def is_date_row(row: dict[str, str]) -> bool:
    return bool(DATE_RE.match((row.get("Unnamed: 0", "") or "").strip()))


def extract_listing_name_and_id(column_name: str) -> tuple[str, str]:
    match = LISTING_RE.match(column_name.strip())
    if not match:
        return column_name.strip().rstrip("."), ""
    return match.group("name").strip(), match.group("listing_id").strip()


def detect_listing_triplets(fieldnames: list[str]) -> list[ListingTriplet]:
    triplets: list[ListingTriplet] = []
    columns = set(fieldnames)
    for column in fieldnames:
        if column == "Unnamed: 0" or re.search(r"\.\d+$", column):
            continue
        available_column = f"{column}.1"
        min_stay_column = f"{column}.2"
        if available_column not in columns or min_stay_column not in columns:
            continue
        name, listing_id = extract_listing_name_and_id(column)
        triplets.append(
            ListingTriplet(
                name=name,
                listing_id=listing_id,
                price_column=column,
                available_column=available_column,
                min_stay_column=min_stay_column,
                is_subject_listing=name.lower().startswith("your listing - aloha poconos"),
            )
        )
    return triplets


def date_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if is_date_row(row)]


def horizon_date_rows(rows: list[dict[str, str]], horizon_days: int = DEFAULT_HORIZON_DAYS) -> list[dict[str, str]]:
    dated_rows = date_rows(rows)
    parsed_dates = [parse_stay_date(row.get("Unnamed: 0", "")) for row in dated_rows]
    valid_dates = [value for value in parsed_dates if value is not None]
    if not valid_dates:
        return []
    start_date = min(valid_dates)
    end_date = start_date + timedelta(days=horizon_days)
    return [
        row
        for row in dated_rows
        if (parsed := parse_stay_date(row.get("Unnamed: 0", ""))) is not None
        and start_date <= parsed <= end_date
    ]


def sample_row_for_listing(rows: list[dict[str, str]], triplet: ListingTriplet) -> dict[str, str] | None:
    dated_rows = date_rows(rows)
    for row in dated_rows:
        if row.get(triplet.available_column, "").strip() == "1":
            return row
    return dated_rows[0] if dated_rows else None


def build_competitor_list_rows(
    run_date: str,
    source_file: Path,
    rows: list[dict[str, str]],
    triplets: list[ListingTriplet],
) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []
    for triplet in triplets:
        sample = sample_row_for_listing(rows, triplet)
        output_rows.append(
            {
                "competitor_name": triplet.name,
                "airbnb_url": triplet.airbnb_url,
                "bedrooms": "",
                "rating": "",
                "review_count": "",
                "cleaning_fee": "",
                "airbnb_service_fee_type": "",
                "notes": NOTES,
                "sample_date": sample.get("Unnamed: 0", "") if sample else "",
                "competitor_price": sample.get(triplet.price_column, "") if sample else "",
                "competitor_min_stay": sample.get(triplet.min_stay_column, "") if sample else "",
                "visible_total_price_notes": "",
                "competitor_listing_id": triplet.listing_id,
                "source_file": str(source_file),
                "is_subject_listing": "true" if triplet.is_subject_listing else "false",
            }
        )
    return output_rows


def build_calendar_rows(
    run_date: str,
    source_file: Path,
    rows: list[dict[str, str]],
    triplets: list[ListingTriplet],
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> list[dict[str, str]]:
    output_rows: list[dict[str, str]] = []
    for row in horizon_date_rows(rows, horizon_days):
        stay_date = row.get("Unnamed: 0", "")
        for triplet in triplets:
            output_rows.append(
                {
                    "run_date": run_date,
                    "stay_date": stay_date,
                    "competitor_name": triplet.name,
                    "competitor_listing_id": triplet.listing_id,
                    "airbnb_url": triplet.airbnb_url,
                    "is_subject_listing": "true" if triplet.is_subject_listing else "false",
                    "competitor_price": row.get(triplet.price_column, ""),
                    "competitor_available": row.get(triplet.available_column, ""),
                    "competitor_min_stay": row.get(triplet.min_stay_column, ""),
                    "source_file": str(source_file),
                }
            )
    return output_rows


def write_rows(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in columns} for row in rows])


def default_input_path(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "raw" / "Competitor Calendar.csv"


def preferred_staging_input_path(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "downloads_staging" / "pricelabs" / "Competitor Calendar.csv"


def default_competitor_list_output(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "raw" / f"pricelabs_competitor_list_{run_date}.csv"


def default_calendar_output(run_date: str) -> Path:
    return Path("data") / "runs" / run_date / "analysis" / f"pricelabs_competitor_calendar_{run_date}.csv"


def transform(
    run_date: str,
    *,
    input_file: Path,
    competitor_list_output: Path,
    calendar_output: Path,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> tuple[Path, Path, int, int]:
    fieldnames, rows = read_rows(input_file)
    triplets = detect_listing_triplets(fieldnames)
    if not triplets:
        raise ValueError("No listing price/available/min_stay triplets found in Competitor Calendar CSV")
    competitor_rows = build_competitor_list_rows(run_date, input_file, rows, triplets)
    calendar_rows = build_calendar_rows(run_date, input_file, rows, triplets, horizon_days)
    write_rows(competitor_list_output, LIST_COLUMNS, competitor_rows)
    write_rows(calendar_output, CALENDAR_COLUMNS, calendar_rows)
    return competitor_list_output, calendar_output, len(competitor_rows), len(calendar_rows)


def resolve_default_input(run_date: str) -> tuple[Path | None, str]:
    staging = preferred_staging_input_path(run_date)
    if staging.exists():
        return staging, "staging"
    fallback = default_input_path(run_date)
    if fallback.exists():
        return fallback, "raw_fallback"
    return None, "missing"


def transform_for_run_date(
    run_date: str,
    *,
    input_file: Path | None = None,
    competitor_list_output: Path | None = None,
    calendar_output: Path | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> tuple[Path | None, Path | None, int, int, str, str]:
    explicit_input = input_file is not None
    if input_file is None:
        resolved_input, source_status = resolve_default_input(run_date)
        if resolved_input is None:
            return None, None, 0, 0, source_status, "not_applicable"
    else:
        resolved_input = input_file
        source_status = "explicit"

    resolved_list_output = competitor_list_output or default_competitor_list_output(run_date)
    resolved_calendar_output = calendar_output or default_calendar_output(run_date)
    list_path, calendar_path, list_count, calendar_count = transform(
        run_date,
        input_file=resolved_input,
        competitor_list_output=resolved_list_output,
        calendar_output=resolved_calendar_output,
        horizon_days=horizon_days,
    )
    cleanup_status = "not_applicable"
    if source_status == "staging" and not explicit_input:
        resolved_input.unlink()
        cleanup_status = "deleted_staging_input"
    return list_path, calendar_path, list_count, calendar_count, source_status, cleanup_status


def run() -> int:
    args = parse_args()
    list_path, calendar_path, list_count, calendar_count, source_status, cleanup_status = transform_for_run_date(
        args.run_date,
        input_file=Path(args.input_file) if args.input_file else None,
        competitor_list_output=Path(args.competitor_list_output) if args.competitor_list_output else None,
        calendar_output=Path(args.calendar_output) if args.calendar_output else None,
    )
    print(f"source_file_used: {source_status}")
    print(f"output_horizon_days: {DEFAULT_HORIZON_DAYS}")
    print(f"input_cleanup_status: {cleanup_status}")
    if list_path is None or calendar_path is None:
        print("Skipping competitor calendar transform: no staging or raw fallback input found.")
        return 0
    print(f"Wrote {list_path} ({list_count} rows)")
    print(f"Wrote {calendar_path} ({calendar_count} rows)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
