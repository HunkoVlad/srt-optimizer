"""Manual PriceLabs CSV to V1 standardized CSV transform."""

from __future__ import annotations

import argparse
import csv
from datetime import date
import io
from pathlib import Path
import sys
import tomllib

from pricelabs.transform.manifest import build_manifest, write_manifest
from pricelabs.transform.mapping import OUTPUT_COLUMNS, is_within_next_180_days, map_row, parse_stay_date
from pricelabs.transform.validation import (
    require_input_file,
    require_source_columns,
    validate_standardized_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transform a manually downloaded PriceLabs CSV into V1 output.")
    parser.add_argument("--config", required=True, help="Path to single-listing TOML config.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument("--manifest-path", default="manifest.json", help="Path for manifest.json.")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, str]:
    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    required = ("listing_id", "input_path", "output_path")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"Config is missing required keys: {', '.join(missing)}")
    return {key: str(data[key]) for key in required}


def read_source_rows(path: Path) -> tuple[list[dict[str, str]], int]:
    require_input_file(path)
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        lines = csv_file.readlines()
        while lines and lines[0].startswith("#"):
            lines.pop(0)
        reader = csv.DictReader(io.StringIO("".join(lines)))
        fieldnames = [field.strip() for field in reader.fieldnames] if reader.fieldnames else None
        require_source_columns(fieldnames)
        rows = []
        for row in reader:
            rows.append({key.strip(): (value or "") for key, value in row.items()})
    return rows, len(rows)


def write_standardized_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest_path)
    failed_manifest: dict[str, object] = {
        "run_date": None,
        "listing_id": None,
        "source_file": None,
        "standardized_file": None,
        "raw_row_count": None,
        "standardized_row_count": None,
        "status": "failed",
    }

    try:
        config_path = Path(args.config)
        run_date = date.fromisoformat(args.run_date)
        failed_manifest["run_date"] = run_date.isoformat()
        config = load_config(config_path)
        failed_manifest["listing_id"] = config["listing_id"]

        input_path = Path(config["input_path"])
        output_path = Path(config["output_path"].replace("<run_date>", run_date.isoformat()))
        failed_manifest["source_file"] = str(input_path)
        failed_manifest["standardized_file"] = str(output_path)

        source_rows, raw_row_count = read_source_rows(input_path)
        failed_manifest["raw_row_count"] = raw_row_count
        standardized_rows = []

        for source_row in source_rows:
            stay_date = parse_stay_date(source_row["Date"])
            if not is_within_next_180_days(stay_date, run_date):
                continue
            mapped_row = map_row(source_row, run_date)
            if mapped_row["listing_id"] != config["listing_id"]:
                continue
            standardized_rows.append(mapped_row)

        failed_manifest["standardized_row_count"] = len(standardized_rows)
        validate_standardized_rows(standardized_rows)
        write_standardized_rows(output_path, standardized_rows)

        manifest = build_manifest(
            run_date=run_date.isoformat(),
            listing_id=config["listing_id"],
            source_file=input_path,
            standardized_file=output_path,
            raw_row_count=raw_row_count,
            standardized_row_count=len(standardized_rows),
            status="success",
        )
        write_manifest(manifest_path, manifest)
        print(f"Wrote {output_path}")
        print(f"Wrote {manifest_path}")
        return 0
    except Exception:
        write_manifest(manifest_path, failed_manifest)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
