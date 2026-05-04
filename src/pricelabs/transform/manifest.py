"""Manifest generation for the PriceLabs V1 transform."""

from __future__ import annotations

import json
from pathlib import Path


def build_manifest(
    *,
    run_date: str,
    listing_id: str,
    source_file: Path,
    standardized_file: Path,
    raw_row_count: int,
    standardized_row_count: int,
    status: str,
) -> dict[str, object]:
    return {
        "run_date": run_date,
        "listing_id": listing_id,
        "source_file": str(source_file),
        "standardized_file": str(standardized_file),
        "raw_row_count": raw_row_count,
        "standardized_row_count": standardized_row_count,
        "status": status,
    }


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
