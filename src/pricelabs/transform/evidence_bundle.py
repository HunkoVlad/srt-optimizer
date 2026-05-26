"""Build a local evidence bundle for the weekly email report."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys


@dataclass(frozen=True)
class EvidenceSpec:
    relative_path: str
    category: str
    required: bool
    role: str
    source_of_truth_type: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a weekly email evidence bundle.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument(
        "--run-dir",
        help="Optional run directory. Defaults to data/runs/<run-date>.",
    )
    return parser.parse_args()


def core_specs(run_date: str) -> list[EvidenceSpec]:
    return [
        EvidenceSpec(
            f"analysis/email_revenue_report_{run_date}.md",
            "report",
            True,
            "email_report_markdown",
            "core",
        ),
        EvidenceSpec(
            f"analysis/rolling_13_month_revenue_view_{run_date}.csv",
            "pricelabs_core",
            True,
            "monthly_revenue_pace_and_cleaning_context",
            "core",
        ),
        EvidenceSpec(
            f"analysis/monthly_revenue_summary_{run_date}.md",
            "pricelabs_core",
            True,
            "monthly_summary_report",
            "core",
        ),
        EvidenceSpec(
            f"analysis/performance_reason_review_{run_date}.csv",
            "pricelabs_core",
            True,
            "reason_review_gates",
            "core",
        ),
        EvidenceSpec(
            f"analysis/future_window_summary_{run_date}.csv",
            "pricelabs_core",
            True,
            "future_window_summary",
            "core",
        ),
        EvidenceSpec(
            f"analysis/future_window_signals_{run_date}.csv",
            "pricelabs_core",
            True,
            "future_window_signal_labels",
            "core",
        ),
        EvidenceSpec(
            f"analysis/combined_market_listing_signal_{run_date}.csv",
            "pricelabs_core",
            True,
            "combined_market_listing_signal",
            "core",
        ),
        EvidenceSpec(
            f"analysis/diagnostic_issue_tracker_{run_date}.csv",
            "diagnostic_issue_tracker",
            False,
            "open_diagnostic_issue_history",
            "combined",
        ),
    ]


def high_priority_specs(run_date: str) -> list[EvidenceSpec]:
    return [
        EvidenceSpec(
            f"analysis/airbnb_conversion_diagnostic_report_{run_date}.md",
            "airbnb_diagnostic",
            False,
            "airbnb_funnel_diagnostic_report",
            "diagnostic",
        ),
        EvidenceSpec(
            f"analysis/airbnb_weekly_history_comparison_{run_date}.csv",
            "airbnb_diagnostic",
            False,
            "airbnb_retained_history_context",
            "diagnostic",
        ),
        EvidenceSpec(
            f"analysis/airbnb_similar_listing_summary_{run_date}.csv",
            "airbnb_diagnostic",
            False,
            "airbnb_similar_listing_benchmark",
            "diagnostic",
        ),
        EvidenceSpec(
            f"settings/pricelabs_settings_snapshot_{run_date}.json",
            "settings",
            False,
            "normalized_pricelabs_settings_snapshot",
            "configuration",
        ),
        EvidenceSpec(
            f"settings/pricelabs_settings_changes_{run_date}.csv",
            "settings",
            False,
            "normalized_pricelabs_settings_changes",
            "configuration",
        ),
    ]


def safe_bundle_name(run_date: str, spec: EvidenceSpec) -> str:
    return f"{run_date}__{spec.category}__{Path(spec.relative_path).name}"


def combined_signal_is_high_priority(path: Path) -> bool:
    if not path.exists():
        return False
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        for row in csv.DictReader(csv_file):
            if (row.get("investigation_priority") or "").strip().lower() == "high":
                return True
    return False


def build_file_entry(run_dir: Path, bundle_dir: Path, run_date: str, spec: EvidenceSpec) -> dict[str, object]:
    source_path = run_dir / spec.relative_path
    bundled_path = bundle_dir / safe_bundle_name(run_date, spec)
    exists = source_path.exists()
    copied = False
    size_bytes = 0

    if exists:
        shutil.copy2(source_path, bundled_path)
        copied = True
        size_bytes = bundled_path.stat().st_size

    return {
        "source_path": str(source_path),
        "bundled_path": str(bundled_path),
        "category": spec.category,
        "required": spec.required,
        "exists": exists,
        "copied": copied,
        "size_bytes": size_bytes,
        "role": spec.role,
        "source_of_truth_type": spec.source_of_truth_type,
    }


def build_manifest(run_date: str, run_dir: Path) -> dict[str, object]:
    analysis_dir = run_dir / "analysis"
    bundle_dir = analysis_dir / f"evidence_bundle_{run_date}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    specs = core_specs(run_date)
    combined_signal_path = run_dir / "analysis" / f"combined_market_listing_signal_{run_date}.csv"
    if combined_signal_is_high_priority(combined_signal_path):
        specs.extend(high_priority_specs(run_date))

    files = [build_file_entry(run_dir, bundle_dir, run_date, spec) for spec in specs]
    missing_required = [
        str(run_dir / spec.relative_path)
        for spec, entry in zip(specs, files, strict=True)
        if spec.required and not entry["exists"]
    ]
    missing_optional = [
        str(run_dir / spec.relative_path)
        for spec, entry in zip(specs, files, strict=True)
        if not spec.required and not entry["exists"]
    ]
    status = "partial" if missing_required else "complete"

    return {
        "run_date": run_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "bundle_path": str(bundle_dir),
        "attachment_mode": "bundle_only",
        "files": files,
        "missing_required_files": missing_required,
        "missing_optional_files": missing_optional,
        "status": status,
    }


def write_manifest(manifest: dict[str, object], run_date: str) -> Path:
    bundle_dir = Path(str(manifest["bundle_path"]))
    manifest_path = bundle_dir / f"evidence_manifest_{run_date}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run(run_date: str, run_dir: Path | None = None) -> Path:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    manifest = build_manifest(run_date, resolved_run_dir)
    return write_manifest(manifest, run_date)


def main() -> int:
    args = parse_args()
    manifest_path = run(args.run_date, Path(args.run_dir) if args.run_dir else None)
    print(f"Wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
