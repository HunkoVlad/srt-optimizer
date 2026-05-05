"""PriceLabs V1 source-to-standardized row mapping."""

from __future__ import annotations

from datetime import date, datetime, timedelta


REQUIRED_SOURCE_COLUMNS = ("Listing ID", "Date", "Your Price", "Min Stay", "Status")
OUTPUT_COLUMNS = (
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


def normalize_status(value: str, available: str = "") -> str:
    normalized = value.strip().lower()
    if "available" in normalized:
        return "available"
    if "reserved" in normalized or "booked" in normalized:
        return "booked"
    if "blocked" in normalized:
        return "blocked"

    fallback = available.strip().lower()
    if fallback == "true":
        return "available"
    if fallback == "false":
        return "unavailable"

    return "unavailable"


def analyze_status(value: str, available: str = "") -> tuple[str, str, str]:
    normalized = value.strip().lower()
    if "available" in normalized:
        return ("available", "high", "explicit_available")
    if "reserved" in normalized or "booked" in normalized:
        return ("booked", "high", "explicit_booked")
    if "blocked" in normalized:
        return ("blocked", "high", "explicit_blocked")

    fallback = available.strip().lower()
    if fallback == "true":
        return ("available", "high", "inferred_available_from_available_true")
    return ("booked", "low", "inferred_booked_from_available_false")


def parse_stay_date(value: str) -> date:
    stripped = value.strip()
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(stripped, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported Date value: {value!r}")


def is_within_next_180_days(stay_date: date, run_date: date) -> bool:
    return run_date <= stay_date < run_date + timedelta(days=180)


def map_row(source_row: dict[str, str], run_date: date) -> dict[str, str]:
    stay_date = parse_stay_date(source_row["Date"])
    analysis_status, status_confidence, status_reason = analyze_status(
        source_row["Status"],
        source_row.get("Available", ""),
    )
    return {
        "run_date": run_date.isoformat(),
        "listing_id": source_row["Listing ID"].strip(),
        "stay_date": stay_date.isoformat(),
        "nightly_price": source_row["Your Price"].strip(),
        "min_stay": source_row["Min Stay"].strip(),
        "status": normalize_status(source_row["Status"], source_row.get("Available", "")),
        "analysis_status": analysis_status,
        "status_confidence": status_confidence,
        "status_reason": status_reason,
    }
