"""Generate listing-side competitor review prompts from open diagnostic issues."""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from statistics import median
import sys


ACTIVE_STATUSES = {"open", "improving", "monitoring"}
TARGET_ISSUE_ID = "airbnb_visibility_up_conversion_down"
TARGET_SIGNAL_TYPE = "visibility_up_conversion_down"
BLOCKED_REASON = "Airbnb/listing diagnostic review cannot create PriceLabs rule recommendations."

CSV_COLUMNS = [
    "run_date",
    "issue_id",
    "review_area",
    "current_observation",
    "risk_level",
    "suggested_investigation",
    "suggested_test",
    "price_rule_change_allowed",
    "notes",
]

RUBRIC_ROWS = [
    {
        "review_area": "search_card_appeal",
        "current_observation": "Airbnb visibility increased sharply, so the search card should be reviewed for click appeal and value clarity.",
        "risk_level": "high",
        "suggested_investigation": "Compare cover image, title, rating/review display, and visible value proposition against similar listings.",
        "suggested_test": "Test cover photo or title/opening value emphasis.",
    },
    {
        "review_area": "cover_photo_first_five_photos",
        "current_observation": "Conversion weakened despite stronger exposure; early photos may not be proving the premium stay quickly enough.",
        "risk_level": "medium",
        "suggested_investigation": "Review cover photo and first 5 photos for hot tub, sauna, game room, sleeping fit, and strongest differentiators.",
        "suggested_test": "Reorder the first 5 photos so the strongest premium differentiators appear earlier.",
    },
    {
        "review_area": "title_description_opening",
        "current_observation": "Guests may need clearer value framing before opening or booking the listing.",
        "risk_level": "medium",
        "suggested_investigation": "Review whether the title and first description lines clearly state the premium promise and best guest fit.",
        "suggested_test": "Test title or opening copy that clarifies the strongest differentiator and ideal trip type.",
    },
    {
        "review_area": "amenities_presentation",
        "current_observation": "Premium amenities may need clearer ordering or presentation to support conversion.",
        "risk_level": "medium",
        "suggested_investigation": "Check whether high-value amenities are visible early and easy to understand.",
        "suggested_test": "Clarify amenity order, captions, or opening-copy emphasis for premium features.",
    },
    {
        "review_area": "guest_fit_sleeping_capacity",
        "current_observation": "Conversion friction can happen when guests cannot quickly understand fit, comfort, or sleeping layout.",
        "risk_level": "medium",
        "suggested_investigation": "Review guest capacity, bedroom/bed presentation, bathroom clarity, and group comfort.",
        "suggested_test": "Clarify sleeping arrangements and group-fit language.",
    },
    {
        "review_area": "trust_review_signals",
        "current_observation": "Trust signals should reduce hesitation when guests are comparing similar stays.",
        "risk_level": "low",
        "suggested_investigation": "Review rating, review count, recent review themes, and visible trust badges.",
        "suggested_test": "Emphasize approved review themes or trust signals in listing copy where appropriate.",
    },
    {
        "review_area": "booking_friction_risks",
        "current_observation": "Guests may like the listing but hesitate because of rules, policy, fees, minimum stay, or availability friction.",
        "risk_level": "high",
        "suggested_investigation": "Review cancellation policy, pet policy, house rules, visible fees, minimum stay, and availability friction.",
        "suggested_test": "Clarify policies and booking expectations in listing copy without changing PriceLabs rules.",
    },
    {
        "review_area": "competitor_comparison",
        "current_observation": "No competitor findings are inferred in V1; compare against similar listings manually before drawing conclusions.",
        "risk_level": "medium",
        "suggested_investigation": "Compare Aloha Poconos against hand-selected similar listings for photo promise, amenities, trust, and booking friction.",
        "suggested_test": "Create a manual competitor comparison table before making listing-side changes.",
    },
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate listing competitor review outputs from diagnostic issues.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--issue-file", help="Diagnostic issue tracker CSV.")
    parser.add_argument("--competitor-file", help="Optional PriceLabs competitor list CSV.")
    parser.add_argument("--competitor-calendar-file", help="Optional normalized PriceLabs competitor calendar CSV.")
    parser.add_argument("--markdown-output", help="Listing competitor review markdown output.")
    parser.add_argument("--csv-output", help="Listing competitor review CSV output.")
    return parser.parse_args(argv)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in CSV_COLUMNS} for row in rows])


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def active_listing_issues(issue_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in issue_rows
        if row.get("status", "").strip().lower() in ACTIVE_STATUSES
        and (
            row.get("issue_id", "") == TARGET_ISSUE_ID
            or row.get("signal_type", "") == TARGET_SIGNAL_TYPE
        )
    ]


def build_review_rows(run_date: str, issue: dict[str, str] | None) -> list[dict[str, str]]:
    if not issue:
        return []
    rows: list[dict[str, str]] = []
    for rubric in RUBRIC_ROWS:
        rows.append(
            {
                "run_date": run_date,
                "issue_id": issue.get("issue_id", TARGET_ISSUE_ID),
                "review_area": rubric["review_area"],
                "current_observation": rubric["current_observation"],
                "risk_level": rubric["risk_level"],
                "suggested_investigation": rubric["suggested_investigation"],
                "suggested_test": rubric["suggested_test"],
                "price_rule_change_allowed": "false",
                "notes": "V1 template-based listing-side review. No competitor findings are inferred unless actual competitor data is provided.",
            }
        )
    return rows


def issue_summary(issue: dict[str, str]) -> str:
    evidence = issue.get("evidence_summary", "") or "Open Airbnb conversion issue requires listing-side investigation."
    investigation = issue.get("recommended_investigation", "") or "Review listing against competitors before changing PriceLabs rules."
    return f"{evidence} {investigation}"


def competitor_value(row: dict[str, str], column: str) -> str:
    return row.get(column, "").strip() or "-"


def competitor_set_section(competitor_rows: list[dict[str, str]]) -> list[str]:
    if not competitor_rows:
        return [
            "## Competitor Set",
            "",
            "No PriceLabs competitor list was provided for this run.",
            "",
        ]

    lines = [
        "## Competitor Set",
        "",
        "The competitors below come from the manually selected PriceLabs Competitor Calendar set. They are trusted review references, not scraped findings.",
        "",
        "| Competitor | Airbnb URL | Bedrooms | Rating | Reviews | Cleaning Fee | Service Fee Type | Notes |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in competitor_rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    competitor_value(row, "competitor_name"),
                    competitor_value(row, "airbnb_url"),
                    competitor_value(row, "bedrooms"),
                    competitor_value(row, "rating"),
                    competitor_value(row, "review_count"),
                    competitor_value(row, "cleaning_fee"),
                    competitor_value(row, "airbnb_service_fee_type"),
                    competitor_value(row, "notes"),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Use this competitor set when working through the review rubric. Do not infer strengths or weaknesses unless manual observations are added.",
            "",
        ]
    )
    return lines


def parse_number(value: str) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text.replace("$", "").replace(",", "").replace("%", ""))
    except InvalidOperation:
        return None


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return "-"
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded == rounded.to_integral():
        return str(rounded.to_integral())
    return str(rounded.normalize())


def average(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values) / Decimal(len(values))


def median_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return Decimal(str(median(values)))


def listing_metrics(rows: list[dict[str, str]]) -> dict[str, Decimal | int | str | None]:
    prices = [
        price
        for row in rows
        if row.get("competitor_available", "").strip() == "1"
        for price in [parse_number(row.get("competitor_price", ""))]
        if price is not None
    ]
    min_stays = [
        min_stay
        for row in rows
        for min_stay in [parse_number(row.get("competitor_min_stay", ""))]
        if min_stay is not None
    ]
    available_count = sum(1 for row in rows if row.get("competitor_available", "").strip() == "1")
    return {
        "name": rows[0].get("competitor_name", "") if rows else "",
        "average_price": average(prices),
        "average_min_stay": average(min_stays),
        "available_count": available_count,
    }


def materially_different(subject: Decimal | None, competitor: Decimal | None, threshold: Decimal = Decimal("0.10")) -> str:
    if subject is None or competitor is None or competitor == 0:
        return ""
    ratio = (subject - competitor) / competitor
    if ratio >= threshold:
        return "above"
    if ratio <= -threshold:
        return "below"
    return ""


def build_competitor_calendar_context(rows: list[dict[str, str]]) -> dict[str, str]:
    if not rows:
        return {}
    stay_dates = sorted({row.get("stay_date", "") for row in rows if row.get("stay_date", "")})
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row.get("competitor_name", ""), []).append(row)
    subject_groups = [
        group_rows
        for group_rows in grouped.values()
        if any(row.get("is_subject_listing", "").strip().lower() == "true" for row in group_rows)
    ]
    competitor_groups = [
        group_rows
        for group_rows in grouped.values()
        if not any(row.get("is_subject_listing", "").strip().lower() == "true" for row in group_rows)
    ]
    if not stay_dates or not subject_groups or not competitor_groups:
        return {}

    subject = listing_metrics(subject_groups[0])
    competitor_metrics = [listing_metrics(group_rows) for group_rows in competitor_groups]
    competitor_avg_prices = [value for metric in competitor_metrics for value in [metric["average_price"]] if isinstance(value, Decimal)]
    competitor_avg_min_stays = [value for metric in competitor_metrics for value in [metric["average_min_stay"]] if isinstance(value, Decimal)]
    competitor_available_counts = [
        Decimal(str(metric["available_count"]))
        for metric in competitor_metrics
        if isinstance(metric["available_count"], int)
    ]

    subject_avg_price = subject["average_price"] if isinstance(subject["average_price"], Decimal) else None
    competitor_median_price = median_decimal(competitor_avg_prices)
    subject_avg_min_stay = subject["average_min_stay"] if isinstance(subject["average_min_stay"], Decimal) else None
    competitor_median_min_stay = median_decimal(competitor_avg_min_stays)
    subject_available = Decimal(str(subject["available_count"])) if isinstance(subject["available_count"], int) else None
    competitor_median_available = median_decimal(competitor_available_counts)

    notable: list[str] = []
    price_direction = materially_different(subject_avg_price, competitor_median_price)
    if price_direction:
        notable.append(f"Subject listing average price is materially {price_direction} the selected comp median.")
    if subject_avg_min_stay is not None and competitor_median_min_stay is not None and subject_avg_min_stay > competitor_median_min_stay:
        notable.append("Subject listing average min stay is more restrictive than the selected comp median.")
    availability_direction = materially_different(subject_available, competitor_median_available)
    if availability_direction:
        notable.append(f"Subject listing available date count materially differs from the selected comp median ({availability_direction}).")

    return {
        "window_start": stay_dates[0],
        "window_end": stay_dates[-1],
        "competitor_count": str(len(competitor_groups)),
        "subject_average_price": format_decimal(subject_avg_price),
        "competitor_median_average_price": format_decimal(competitor_median_price),
        "subject_average_min_stay": format_decimal(subject_avg_min_stay),
        "competitor_median_min_stay": format_decimal(competitor_median_min_stay),
        "subject_available_date_count": format_decimal(subject_available),
        "competitor_median_available_date_count": format_decimal(competitor_median_available),
        "notable_context": " ".join(notable) if notable else "No material price, min-stay, or availability gap was detected from the selected PriceLabs comp set.",
    }


def competitor_calendar_context_section(context: dict[str, str]) -> list[str]:
    lines = ["## PriceLabs Competitor Calendar Context", ""]
    if not context:
        lines.extend(["No normalized PriceLabs competitor calendar context was available for this run.", ""])
        return lines
    lines.extend(
        [
            f"- 90-day window: {context['window_start']} to {context['window_end']}.",
            f"- Selected competitors: {context['competitor_count']}.",
            f"- Subject listing average price over available dates: {context['subject_average_price']}.",
            f"- Competitor median average price over available dates: {context['competitor_median_average_price']}.",
            f"- Subject listing average min stay: {context['subject_average_min_stay']}.",
            f"- Competitor median min stay: {context['competitor_median_min_stay']}.",
            f"- Subject listing available date count: {context['subject_available_date_count']}.",
            f"- Competitor median available date count: {context['competitor_median_available_date_count']}.",
            f"- Notable context: {context['notable_context']}",
            "- This is diagnostic context from selected PriceLabs competitors only. It is not a revenue or occupancy source of truth and does not create price-rule recommendations.",
            "",
        ]
    )
    return lines


def build_markdown(
    run_date: str,
    issue_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    competitor_rows: list[dict[str, str]] | None = None,
    competitor_calendar_rows: list[dict[str, str]] | None = None,
) -> str:
    active = active_listing_issues(issue_rows)
    resolved_competitor_rows = competitor_rows or []
    competitor_context = build_competitor_calendar_context(competitor_calendar_rows or [])
    lines = [
        f"# Listing Competitor Review - {run_date}",
        "",
    ]
    if not active:
        lines.extend(
            [
                "## Executive Summary",
                "",
                "No active listing competitor review issue was found for this run.",
                "",
                "## Guardrail",
                "",
                "No listing-side or PriceLabs rule recommendation is created by this report.",
                "",
            ]
        )
        return "\n".join(lines)

    issue = active[0]
    lines.extend(
        [
            "## Executive Summary",
            "",
            "Airbnb visibility increased sharply, but conversion weakened or remained weak. This review should focus on listing presentation, competitor comparison, value perception, and booking friction before any PriceLabs rule review.",
            "",
            "## Open Issue Being Investigated",
            "",
            f"- Issue: {issue.get('issue_title', issue.get('issue_id', TARGET_ISSUE_ID))}",
            f"- Status: {issue.get('status', 'unknown')}",
            f"- Severity: {issue.get('severity', 'unknown')}",
            f"- Evidence: {issue.get('evidence_summary', 'Evidence unavailable.')}",
            f"- Investigation: {issue.get('recommended_investigation', 'Review listing against competitors before changing PriceLabs rules.')}",
            f"- Guardrail: {issue.get('blocked_recommendation_reason', BLOCKED_REASON)}",
            "",
            "## Why This Points To Listing / Competitor / Value Perception Review",
            "",
            issue_summary(issue),
            "Airbnb diagnostics can identify conversion friction, but they cannot create PriceLabs rule recommendations. PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.",
            "",
        ]
    )
    lines.extend(competitor_set_section(resolved_competitor_rows))
    lines.extend(competitor_calendar_context_section(competitor_context))
    lines.extend(["## Review Rubric", ""])
    for row in review_rows:
        lines.extend(
            [
                f"### {row['review_area'].replace('_', ' ').title()}",
                "",
                f"- Current observation: {row['current_observation']}",
                f"- Risk level: {row['risk_level']}",
                f"- Suggested investigation: {row['suggested_investigation']}",
                f"- Suggested listing test: {row['suggested_test']}",
                "- Price rule change allowed: false",
                "",
            ]
        )
    lines.extend(
        [
            "## Suggested Listing-Side Tests",
            "",
            "- Cover photo test.",
            "- Title or opening-copy test.",
            "- First-five-photo ordering test.",
            "- Amenities presentation test.",
            "- Booking-friction copy clarification.",
            "- Manual competitor comparison table.",
            "",
            "## What Not To Change Yet",
            "",
            "- Do not use this listing review to create automatic PriceLabs rule changes.",
            "- Do not recommend broad discounting.",
            "- Do not optimize for occupancy alone.",
            "- Do not change minimum stay, LOS, orphan, base price, or discount rules unless PriceLabs core recommendation logic independently supports it.",
            "",
            "## What To Check Next Week",
            "",
            "- Whether first-page search impressions remain elevated.",
            "- Whether search-to-listing conversion improves.",
            "- Whether listing-to-booking conversion improves.",
            "- Whether wishlist additions move with or against conversion.",
            "- Whether the diagnostic issue remains open, improves, or moves to monitoring.",
            "",
        ]
    )
    return "\n".join(lines)


def default_issue_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"diagnostic_issue_tracker_{run_date}.csv"


def default_markdown_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"listing_competitor_review_{run_date}.md"


def default_csv_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"listing_competitor_review_{run_date}.csv"


def default_competitor_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "raw" / f"pricelabs_competitor_list_{run_date}.csv"


def default_competitor_calendar_path(run_dir: Path, run_date: str) -> Path:
    return run_dir / "analysis" / f"pricelabs_competitor_calendar_{run_date}.csv"


def run(
    run_date: str,
    *,
    run_dir: Path | None = None,
    issue_file: Path | None = None,
    competitor_file: Path | None = None,
    competitor_calendar_file: Path | None = None,
    markdown_output: Path | None = None,
    csv_output: Path | None = None,
) -> tuple[Path, Path]:
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    resolved_issue_file = issue_file or default_issue_path(resolved_run_dir, run_date)
    resolved_competitor_file = competitor_file or default_competitor_path(resolved_run_dir, run_date)
    resolved_competitor_calendar_file = competitor_calendar_file or default_competitor_calendar_path(resolved_run_dir, run_date)
    resolved_markdown = markdown_output or default_markdown_path(resolved_run_dir, run_date)
    resolved_csv = csv_output or default_csv_path(resolved_run_dir, run_date)
    issue_rows = read_csv_rows(resolved_issue_file)
    competitor_rows = read_csv_rows(resolved_competitor_file)
    competitor_calendar_rows = read_csv_rows(resolved_competitor_calendar_file)
    active = active_listing_issues(issue_rows)
    review_rows = build_review_rows(run_date, active[0] if active else None)
    if active and competitor_calendar_rows:
        review_rows.append(
            {
                "run_date": run_date,
                "issue_id": active[0].get("issue_id", TARGET_ISSUE_ID),
                "review_area": "competitor_calendar_context",
                "current_observation": "Selected PriceLabs competitor calendar provides 90-day price, min-stay, and availability context.",
                "risk_level": "medium",
                "suggested_investigation": "Review competitor price/min-stay/availability context before interpreting conversion weakness.",
                "suggested_test": "Use computed competitor calendar facts as diagnostic context only; do not create PriceLabs rule changes from this layer.",
                "price_rule_change_allowed": "false",
                "notes": "Diagnostic benchmark context only; competitor data is not revenue or occupancy source of truth.",
            }
        )
    write_csv(resolved_csv, review_rows)
    write_markdown(
        resolved_markdown,
        build_markdown(run_date, issue_rows, review_rows, competitor_rows, competitor_calendar_rows),
    )
    return resolved_markdown, resolved_csv


def main() -> int:
    args = parse_args()
    markdown, csv_path = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        issue_file=Path(args.issue_file) if args.issue_file else None,
        competitor_file=Path(args.competitor_file) if args.competitor_file else None,
        competitor_calendar_file=Path(args.competitor_calendar_file) if args.competitor_calendar_file else None,
        markdown_output=Path(args.markdown_output) if args.markdown_output else None,
        csv_output=Path(args.csv_output) if args.csv_output else None,
    )
    print(f"Wrote {markdown}")
    print(f"Wrote {csv_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
