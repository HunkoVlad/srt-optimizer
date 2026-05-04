"""Minimal validation for the PriceLabs V1 transform."""

from __future__ import annotations

from pathlib import Path

from pricelabs.transform.mapping import OUTPUT_COLUMNS, REQUIRED_SOURCE_COLUMNS


ALLOWED_STATUSES = {"available", "booked", "blocked", "unavailable"}


def require_input_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")


def require_source_columns(fieldnames: list[str] | None) -> None:
    if fieldnames is None:
        raise ValueError("Input CSV is missing a header row")
    missing = [column for column in REQUIRED_SOURCE_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"Input CSV is missing required columns: {', '.join(missing)}")


def validate_standardized_rows(rows: list[dict[str, str]]) -> None:
    seen_keys: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows, start=2):
        missing = [column for column in OUTPUT_COLUMNS if column not in row]
        if missing:
            raise ValueError(f"Output row {index} is missing columns: {', '.join(missing)}")

        status = row["status"]
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Output row {index} has invalid status: {status!r}")

        primary_key = (row["run_date"], row["listing_id"], row["stay_date"])
        if primary_key in seen_keys:
            raise ValueError(f"Duplicate primary key found: {primary_key}")
        seen_keys.add(primary_key)
