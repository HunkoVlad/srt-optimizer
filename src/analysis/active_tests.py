"""Build the per-run active test registry for listing and PriceLabs changes."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
import re
import sys


COLUMNS = [
    "test_id",
    "canonical_test_id",
    "test_type",
    "duplicate_group_key",
    "change_date",
    "run_date_started",
    "related_issue_id",
    "change_area",
    "old_value",
    "new_value",
    "reason",
    "expected_effect",
    "primary_success_metrics",
    "guardrails",
    "review_after_run_date",
    "status",
    "review_due",
    "source",
    "merged_from_test_ids",
    "supporting_changes",
    "notes",
]

LISTING_CHANGE_INPUT_COLUMNS = [
    "change_date",
    "change_type",
    "old_value",
    "new_value",
    "reason",
    "expected_effect",
    "review_after_run_date",
    "notes",
]

ACTIVE_STATUSES = {"active", "monitoring"}
COMPLETED_STATUSES = {"completed", "superseded", "failed", "resolved", "closed", "inactive"}
PRICELABS_HINTS = ("pricelabs", "los", "length_of_stay", "length of stay", "pricing", "price", "rule")
CANONICAL_TEST_IDS = {"title_photo_search_card_test", "pricelabs_los_pricing_test", "competitiveness_booking_friction_test"}
MALFORMED_INPUT_REQUIRED_COLUMNS = ("test_id", "test_type", "status")


@dataclass(frozen=True)
class Paths:
    run_date: str
    run_dir: Path
    history_dir: Path
    analysis_dir: Path
    raw_dir: Path
    settings_dir: Path
    output_file: Path
    history_file: Path
    listing_change_log_file: Path
    listing_change_input_file: Path
    settings_changes_file: Path
    listing_snapshot_input_file: Path
    search_visibility_file: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate active listing and PriceLabs test registry.")
    parser.add_argument("--run-date", required=True, help="Pipeline run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--output-file", help="Per-run active test CSV. Defaults to analysis/active_tests_<run-date>.csv.")
    parser.add_argument("--history-file", help="Rolling active test history CSV. Defaults to data/history/active_tests.csv.")
    parser.add_argument("--listing-change-log-file", help="Listing change log CSV. Defaults to data/history/listing_change_log.csv.")
    parser.add_argument(
        "--listing-change-input-file",
        help="Manual per-run change input CSV. Defaults to raw/listing_change_input_<run-date>.csv.",
    )
    return parser.parse_args()


def resolve_paths(args: argparse.Namespace) -> Paths:
    run_dir = Path(args.run_dir or Path("data") / "runs" / args.run_date)
    analysis_dir = run_dir / "analysis"
    raw_dir = run_dir / "raw"
    settings_dir = run_dir / "settings"
    history_dir = run_dir.parents[1] / "history" if len(run_dir.parents) >= 2 else Path("data") / "history"
    output_file = Path(args.output_file or analysis_dir / f"active_tests_{args.run_date}.csv")
    history_file = Path(args.history_file or history_dir / "active_tests.csv")
    listing_change_log_file = Path(args.listing_change_log_file or history_dir / "listing_change_log.csv")
    listing_change_input_file = Path(args.listing_change_input_file or raw_dir / f"listing_change_input_{args.run_date}.csv")
    return Paths(
        run_date=args.run_date,
        run_dir=run_dir,
        history_dir=history_dir,
        analysis_dir=analysis_dir,
        raw_dir=raw_dir,
        settings_dir=settings_dir,
        output_file=output_file,
        history_file=history_file,
        listing_change_log_file=listing_change_log_file,
        listing_change_input_file=listing_change_input_file,
        settings_changes_file=settings_dir / f"pricelabs_settings_changes_{args.run_date}.csv",
        listing_snapshot_input_file=raw_dir / f"listing_state_snapshot_input_{args.run_date}.csv",
        search_visibility_file=analysis_dir / f"airbnb_search_visibility_{args.run_date}.csv",
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def with_priority_source(row: dict[str, str], priority_source: str) -> dict[str, str]:
    output = dict(row)
    output["_priority_source"] = priority_source
    return output


def write_csv_rows(path: Path, rows: list[dict[str, str]], columns: list[str] = COLUMNS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in columns} for row in rows])


def slug(value: str, fallback: str = "active_test") -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return cleaned or fallback


def infer_test_type(change_type: str, notes: str = "") -> str:
    text = f"{change_type} {notes}".lower()
    return "pricelabs" if any(hint in text for hint in PRICELABS_HINTS) else "listing"


def default_success_metrics(test_type: str, change_type: str) -> str:
    text = change_type.lower()
    if test_type == "pricelabs":
        return "revenue_per_cleaning; booked_nights; occupancy; ADR; monthly_revenue_pace"
    if "photo" in text or "title" in text or "search" in text:
        return "search_to_listing_conversion_rate; wishlist_additions; listing_to_booking_conversion_rate"
    return "search_to_listing_conversion_rate; listing_to_booking_conversion_rate; wishlist_additions"


def default_guardrails(test_type: str) -> str:
    if test_type == "pricelabs":
        return (
            "Track as a PriceLabs test only; do not let Airbnb diagnostics create automatic PriceLabs rule recommendations."
        )
    return (
        "Listing-side diagnostic only; do not create PriceLabs rule recommendations from Airbnb/listing signals alone."
    )


def build_test_row(
    *,
    run_date: str,
    source: str,
    change_type: str,
    change_date: str,
    run_date_started: str = "",
    related_issue_id: str = "",
    old_value: str = "",
    new_value: str = "",
    reason: str = "",
    expected_effect: str = "",
    status: str = "active",
    review_after_run_date: str = "",
    notes: str = "",
) -> dict[str, str]:
    test_type = infer_test_type(change_type, notes)
    normalized_status = (status or "active").strip().lower()
    review_due = bool(review_after_run_date and review_after_run_date <= run_date and normalized_status in ACTIVE_STATUSES)
    return {
        "test_id": slug(change_type),
        "canonical_test_id": "",
        "test_type": test_type,
        "duplicate_group_key": "",
        "change_date": change_date,
        "run_date_started": run_date_started or run_date,
        "related_issue_id": related_issue_id,
        "change_area": change_type,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "expected_effect": expected_effect,
        "primary_success_metrics": default_success_metrics(test_type, change_type),
        "guardrails": default_guardrails(test_type),
        "review_after_run_date": review_after_run_date,
        "status": normalized_status,
        "review_due": "true" if review_due else "false",
        "source": source,
        "merged_from_test_ids": "",
        "supporting_changes": "",
        "notes": notes,
    }


def normalize_existing_active_test_row(row: dict[str, str], run_date: str) -> dict[str, str]:
    output = {column: row.get(column, "") for column in COLUMNS}
    if not output["canonical_test_id"]:
        output["canonical_test_id"] = output["test_id"]
    if not output["duplicate_group_key"]:
        output["duplicate_group_key"] = canonical_group_key(output)
    status = (output.get("status") or "active").strip().lower()
    output["status"] = status
    review_after = output.get("review_after_run_date", "")
    output["review_due"] = "true" if review_after and review_after <= run_date and status in ACTIVE_STATUSES else "false"
    return with_priority_source(output, "active_tests_history")


def rows_from_active_tests_history(path: Path, run_date: str) -> list[dict[str, str]]:
    return [normalize_existing_active_test_row(row, run_date) for row in read_csv_rows(path)]


def rows_from_listing_change_log(path: Path, run_date: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in read_csv_rows(path):
        status = (row.get("status") or "active").strip().lower()
        if status in COMPLETED_STATUSES:
            continue
        rows.append(with_priority_source(
            build_test_row(
                run_date=run_date,
                source="manual_log",
                change_type=row.get("change_type", ""),
                change_date=row.get("change_date", ""),
                run_date_started=row.get("run_date", ""),
                related_issue_id=row.get("related_issue_id", ""),
                old_value=row.get("old_value", ""),
                new_value=row.get("new_value", ""),
                reason=row.get("reason", ""),
                expected_effect=row.get("expected_effect", ""),
                status=status or "active",
                review_after_run_date=row.get("review_after_run_date", ""),
                notes=row.get("notes", ""),
            )
            ,
            "listing_change_log_fallback",
        ))
    return rows


def parse_notes_field(notes: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in notes.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def is_valid_manual_active_test_row(row: dict[str, str]) -> bool:
    return all(row.get(column, "").strip() for column in MALFORMED_INPUT_REQUIRED_COLUMNS)


def rows_from_manual_input(path: Path, run_date: str) -> tuple[list[dict[str, str]], int, int, int]:
    rows: list[dict[str, str]] = []
    raw_rows = read_csv_rows(path)
    skipped = 0
    for row in raw_rows:
        if not is_valid_manual_active_test_row(row):
            skipped += 1
            print(
                "skipped_malformed_input: "
                f"test_id={row.get('test_id', '')!r} test_type={row.get('test_type', '')!r} status={row.get('status', '')!r}"
            )
            continue
        output = {column: row.get(column, "") for column in COLUMNS}
        output["test_id"] = row.get("test_id", "")
        output["canonical_test_id"] = row.get("canonical_test_id", "") or row.get("test_id", "")
        output["test_type"] = row.get("test_type", "")
        output["duplicate_group_key"] = row.get("duplicate_group_key", "") or canonical_group_key(output)
        output["change_area"] = row.get("change_area", "") or row.get("change_type", "") or row.get("test_id", "")
        output["source"] = row.get("source", "") or "user_declared"
        output["status"] = row.get("status", "").strip().lower()
        review_after = output.get("review_after_run_date", "")
        output["review_due"] = "true" if review_after and review_after <= run_date and output["status"] in ACTIVE_STATUSES else "false"
        rows.append(with_priority_source(output, "user_declared"))
    return rows, len(raw_rows), len(rows), skipped


def rows_from_settings_changes(path: Path, run_date: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in read_csv_rows(path):
        changed = row.get("changed_flag", "").strip().lower() == "true"
        field_name = row.get("field_name", "")
        if not changed or not any(hint in field_name.lower() for hint in PRICELABS_HINTS):
            continue
        rows.append(with_priority_source(
            build_test_row(
                run_date=run_date,
                source="settings_snapshot",
                change_type=f"pricelabs_{field_name}",
                change_date=run_date,
                old_value=row.get("previous_value", ""),
                new_value=row.get("current_value", ""),
                reason="PriceLabs settings snapshot changed.",
                expected_effect="Monitor PriceLabs core metrics before deciding whether the change helped.",
                review_after_run_date="",
                notes=f"listing_id={row.get('listing_id', '')}",
            )
            ,
            "settings_snapshot",
        ))
    return rows


def append_manual_inputs_to_listing_history(paths: Paths) -> None:
    manual_rows = read_csv_rows(paths.listing_change_input_file)
    if not manual_rows:
        return
    existing = read_csv_rows(paths.listing_change_log_file)
    existing_keys = {
        (
            row.get("change_date", ""),
            row.get("change_type", ""),
            row.get("new_value", ""),
            row.get("review_after_run_date", ""),
        )
        for row in existing
    }
    output_rows = list(existing)
    changed = False
    for row in manual_rows:
        key = (
            row.get("change_date", ""),
            row.get("change_type", ""),
            row.get("new_value", ""),
            row.get("review_after_run_date", ""),
        )
        if key in existing_keys:
            continue
        parsed_notes = parse_notes_field(row.get("notes", ""))
        output_rows.append(
            {
                "change_date": row.get("change_date", ""),
                "run_date": parsed_notes.get("run_date_started", paths.run_date),
                "related_issue_id": parsed_notes.get("related_issue_id", ""),
                "change_type": row.get("change_type", ""),
                "old_value": row.get("old_value", ""),
                "new_value": row.get("new_value", ""),
                "reason": row.get("reason", ""),
                "expected_effect": row.get("expected_effect", ""),
                "status": parsed_notes.get("status", "active"),
                "review_after_run_date": row.get("review_after_run_date", ""),
                "notes": row.get("notes", ""),
            }
        )
        changed = True
    if changed:
        write_csv_rows(
            paths.listing_change_log_file,
            output_rows,
            [
                "change_date",
                "run_date",
                "related_issue_id",
                "change_type",
                "old_value",
                "new_value",
                "reason",
                "expected_effect",
                "status",
                "review_after_run_date",
                "notes",
            ],
        )


def add_tracking_note(rows: list[dict[str, str]], paths: Paths) -> None:
    if paths.listing_snapshot_input_file.exists():
        return
    note = "Active test tracking is based only on history/manual inputs because no structured listing state input was available for this run."
    for row in rows:
        if row.get("test_type") != "listing":
            continue
        current = row.get("notes", "")
        if note not in current:
            row["notes"] = f"{current}; {note}" if current else note


def maybe_add_unlogged_change_note(rows: list[dict[str, str]], paths: Paths) -> None:
    if paths.listing_change_input_file.exists() or paths.listing_snapshot_input_file.exists():
        return
    visibility_rows = read_csv_rows(paths.search_visibility_file)
    title_evidence = next((row.get("visible_title", "") for row in visibility_rows if row.get("visible_title", "")), "")
    if not title_evidence:
        return
    known_new_values = " ".join(row.get("new_value", "") for row in rows).lower()
    if title_evidence.lower() not in known_new_values:
        print("Potential unlogged listing change detected.")


def is_booking_friction_competitiveness_test(row: dict[str, str]) -> bool:
    return (
        row.get("test_id", "") == "competitiveness_booking_friction_test"
        or row.get("duplicate_group_key", "") in {"booking_friction_competitiveness", "pricelabs_booking_friction_competitiveness"}
    )


def mentions_los_pricing(row: dict[str, str]) -> bool:
    text = " ".join(
        (
            row.get("test_id", ""),
            row.get("change_area", ""),
            row.get("old_value", ""),
            row.get("new_value", ""),
            row.get("reason", ""),
            row.get("expected_effect", ""),
            row.get("primary_success_metrics", ""),
            row.get("notes", ""),
        )
    ).lower()
    return "length_of_stay" in text or "length of stay" in text or "los" in text


def has_active_booking_friction_experiment(rows: list[dict[str, str]]) -> bool:
    return any(
        is_booking_friction_competitiveness_test(row)
        and row.get("status", "").strip().lower() in ACTIVE_STATUSES
        and (mentions_los_pricing(row) or "booking_friction" in row.get("duplicate_group_key", ""))
        for row in rows
    )


def is_settings_snapshot_row(row: dict[str, str]) -> bool:
    return row.get("_priority_source", "") == "settings_snapshot" or row.get("source", "") == "settings_snapshot"


def canonical_group_key(row: dict[str, str], *, booking_friction_experiment_active: bool = False) -> str:
    test_id = row.get("test_id", "")
    change_area = row.get("change_area", "")
    metrics = row.get("primary_success_metrics", "").lower()
    text = " ".join(
        (
            test_id,
            change_area,
            row.get("related_issue_id", ""),
            row.get("new_value", ""),
            row.get("expected_effect", ""),
            metrics,
        )
    ).lower()
    if is_booking_friction_competitiveness_test(row):
        return "pricelabs_booking_friction_competitiveness"
    if (
        booking_friction_experiment_active
        and row.get("test_type") == "pricelabs"
        and is_settings_snapshot_row(row)
        and mentions_los_pricing(row)
    ):
        return "pricelabs_booking_friction_competitiveness"
    if row.get("test_type") == "pricelabs" and ("los" in text or "length" in text):
        return "pricelabs_los_pricing"
    if row.get("test_type") == "listing" and (
        test_id in {"title_photo_search_card_test", "listing_title_search_card", "listing_photo_strategy"}
        or (
            "search_to_listing_conversion_rate" in metrics
            and any(token in text for token in ("search_card", "search-card", "title"))
        )
    ):
        return "listing_search_card_experiment"
    return f"{row.get('test_type', '')}:{test_id}"


def canonical_test_id_for_group(group_key: str, rows: list[dict[str, str]]) -> str:
    if group_key == "listing_search_card_experiment":
        return "title_photo_search_card_test"
    if group_key == "pricelabs_booking_friction_competitiveness":
        return "competitiveness_booking_friction_test"
    if group_key == "pricelabs_los_pricing":
        return "pricelabs_los_pricing_test"
    canonical = next((row.get("test_id", "") for row in rows if row.get("test_id", "") in CANONICAL_TEST_IDS), "")
    return canonical or rows[0].get("test_id", "")


def row_rank(row: dict[str, str], canonical_test_id: str) -> tuple[int, int, int]:
    source_rank = {
        "active_tests_history": 0,
        "user_declared": 1,
        "settings_snapshot": 2,
        "listing_change_log_fallback": 3,
    }.get(
        row.get("_priority_source", row.get("source", "")),
        4,
    )
    canonical_rank = 0 if row.get("test_id", "") == canonical_test_id else 1
    completeness = -sum(1 for field in ("old_value", "reason", "guardrails", "review_after_run_date") if row.get(field, ""))
    return source_rank, canonical_rank, completeness


def append_unique(existing: str, addition: str) -> str:
    if not addition:
        return existing
    parts = [part.strip() for part in existing.split(";") if part.strip()]
    if addition not in parts:
        parts.append(addition)
    return "; ".join(parts)


def unique_nonempty(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output


def compact_semicolon_text(value: str) -> str:
    return "; ".join(unique_nonempty([part.strip() for part in value.split(";")]))


def unique_rows_by_source_event(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            row.get("test_id", ""),
            row.get("_priority_source", row.get("source", "")),
            row.get("change_date", ""),
            row.get("status", ""),
        )
        existing = unique.get(key)
        if existing is None or row_rank(row, row.get("test_id", "")) < row_rank(existing, existing.get("test_id", "")):
            unique[key] = row
    return list(unique.values())


def merge_group(group_key: str, group_rows: list[dict[str, str]]) -> dict[str, str]:
    group_rows = unique_rows_by_source_event(group_rows)
    canonical_test_id = canonical_test_id_for_group(group_key, group_rows)
    has_settings_snapshot_support = any(is_settings_snapshot_row(row) for row in group_rows)
    if group_key == "pricelabs_booking_friction_competitiveness" and has_settings_snapshot_support:
        active_booking_friction_rows = [
            row
            for row in group_rows
            if is_booking_friction_competitiveness_test(row)
            and row.get("status", "").strip().lower() in ACTIVE_STATUSES
        ]
        if active_booking_friction_rows:
            candidate_rows = active_booking_friction_rows
        else:
            candidate_rows = group_rows
        winner = dict(sorted(candidate_rows, key=lambda row: row_rank(row, canonical_test_id))[0])
        supporting = [row for row in group_rows if row.get("test_id", "") != winner.get("test_id", "")]
        supporting_ids = unique_nonempty([row.get("test_id", "") for row in supporting])
        winner["canonical_test_id"] = canonical_test_id
        winner["duplicate_group_key"] = group_key
        winner["merged_from_test_ids"] = "; ".join(supporting_ids)
        winner["supporting_changes"] = "; ".join(
            unique_nonempty([row.get("change_area", "") or row.get("test_id", "") for row in supporting])
        )
        winner["notes"] = compact_semicolon_text(winner.get("notes", ""))
        return winner

    history_rows = [row for row in group_rows if row.get("_priority_source") == "active_tests_history"]
    if history_rows:
        latest_history_date = max(row.get("change_date", "") for row in history_rows)
        newer_non_history_rows = [
            row
            for row in group_rows
            if row.get("_priority_source") != "active_tests_history"
            and row.get("change_date", "")
            and row.get("change_date", "") > latest_history_date
        ]
        candidate_rows = newer_non_history_rows or history_rows
    else:
        candidate_rows = group_rows
    winner = dict(sorted(candidate_rows, key=lambda row: row_rank(row, canonical_test_id))[0])
    supporting = [row for row in group_rows if row.get("test_id", "") != winner.get("test_id", "")]
    supporting_ids = unique_nonempty([row.get("test_id", "") for row in supporting])
    winner["canonical_test_id"] = canonical_test_id
    winner["duplicate_group_key"] = group_key
    winner["merged_from_test_ids"] = "; ".join(supporting_ids)
    winner["supporting_changes"] = "; ".join(
        unique_nonempty([row.get("change_area", "") or row.get("test_id", "") for row in supporting])
    )
    for row in supporting:
        detail = "; ".join(
            part
            for part in (row.get("new_value", ""), row.get("expected_effect", ""), row.get("notes", ""))
            if part
        )
        if detail:
            winner["notes"] = append_unique(winner.get("notes", ""), f"{row.get('test_id', '')}: {detail}")
    winner["notes"] = compact_semicolon_text(winner.get("notes", ""))
    return winner


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    booking_friction_experiment_active = has_active_booking_friction_experiment(rows)
    for row in rows:
        grouped.setdefault(canonical_group_key(row, booking_friction_experiment_active=booking_friction_experiment_active), []).append(row)
    return [merge_group(group_key, group_rows) for group_key, group_rows in grouped.items()]


def run(
    run_date: str,
    *,
    run_dir: Path | None = None,
    output_file: Path | None = None,
    history_file: Path | None = None,
    listing_change_log_file: Path | None = None,
    listing_change_input_file: Path | None = None,
) -> Path:
    args = argparse.Namespace(
        run_date=run_date,
        run_dir=str(run_dir) if run_dir else None,
        output_file=str(output_file) if output_file else None,
        history_file=str(history_file) if history_file else None,
        listing_change_log_file=str(listing_change_log_file) if listing_change_log_file else None,
        listing_change_input_file=str(listing_change_input_file) if listing_change_input_file else None,
    )
    paths = resolve_paths(args)
    paths.analysis_dir.mkdir(parents=True, exist_ok=True)
    paths.history_dir.mkdir(parents=True, exist_ok=True)

    print("== Active tests ==")
    history_rows = rows_from_active_tests_history(paths.history_file, run_date)
    manual_rows, manual_total, manual_valid, manual_skipped = rows_from_manual_input(paths.listing_change_input_file, run_date)
    settings_rows = rows_from_settings_changes(paths.settings_changes_file, run_date)
    listing_fallback_rows = []
    if not history_rows:
        listing_fallback_rows = rows_from_listing_change_log(paths.listing_change_log_file, run_date)

    rows = dedupe_rows([*history_rows, *manual_rows, *settings_rows, *listing_fallback_rows])
    add_tracking_note(rows, paths)
    maybe_add_unlogged_change_note(rows, paths)

    write_csv_rows(paths.output_file, rows)
    if not paths.history_file.exists() and rows:
        write_csv_rows(paths.history_file, rows)
        print(f"Wrote {paths.history_file}")
    elif manual_valid or settings_rows:
        write_csv_rows(paths.history_file, rows)
        print(f"Wrote {paths.history_file}")
    else:
        print(f"Preserved {paths.history_file}")
    active_listing_count = sum(1 for row in rows if row.get("test_type") == "listing" and row.get("status") == "active")
    active_pricelabs_count = sum(1 for row in rows if row.get("test_type") == "pricelabs" and row.get("status") == "active")
    superseded_count = sum(1 for row in rows if row.get("status") == "superseded")
    print(f"Source data/history/active_tests.csv rows: {len(history_rows)}")
    print(
        f"Source raw/listing_change_input_{run_date}.csv rows: {manual_total}, "
        f"valid: {manual_valid}, skipped_malformed: {manual_skipped}"
    )
    print(f"Source data/history/listing_change_log.csv fallback rows used: {len(listing_fallback_rows)}")
    print(f"Wrote {paths.output_file}")
    print(f"Active listing tests: {active_listing_count}")
    print(f"Active PriceLabs tests: {active_pricelabs_count}")
    print(f"Superseded tests: {superseded_count}")
    return paths.output_file


def main() -> int:
    args = parse_args()
    run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        output_file=Path(args.output_file) if args.output_file else None,
        history_file=Path(args.history_file) if args.history_file else None,
        listing_change_log_file=Path(args.listing_change_log_file) if args.listing_change_log_file else None,
        listing_change_input_file=Path(args.listing_change_input_file) if args.listing_change_input_file else None,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
