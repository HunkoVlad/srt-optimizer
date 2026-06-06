"""Review manually selected Airbnb competitor listing URLs.

Airbnb output is diagnostic only. This module does not create PriceLabs
recommendations and does not feed pricing rules.
"""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, date, datetime
from pathlib import Path
import re
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from airbnb.download_diagnostics import persistent_profile_path


INPUT_COLUMNS = ["rank_group", "source_note", "listing_url"]

REVIEW_COLUMNS = [
    "run_date",
    "rank_group",
    "source_note",
    "match_reason",
    "absolute_position",
    "listing_url",
    "listing_id",
    "listing_title",
    "location",
    "rating",
    "review_count",
    "guest_favorite_badge",
    "superhost_badge",
    "host_type_or_host_badge",
    "max_guests",
    "bedrooms",
    "beds",
    "baths",
    "visible_price_text",
    "cancellation_policy_text",
    "self_check_in_visible",
    "instant_book_visible",
    "pets_allowed_visible",
    "hot_tub_visible",
    "sauna_visible",
    "pool_visible",
    "game_room_visible",
    "theater_visible",
    "arcade_visible",
    "lake_access_visible",
    "waterfront_visible",
    "fire_pit_visible",
    "fireplace_visible",
    "grill_visible",
    "ev_charger_visible",
    "cold_plunge_visible",
    "private_pool_visible",
    "shared_pool_visible",
    "top_photo_1_caption_or_alt",
    "top_photo_2_caption_or_alt",
    "top_photo_3_caption_or_alt",
    "top_photo_4_caption_or_alt",
    "top_photo_5_caption_or_alt",
    "first_5_photo_alt_or_caption_text",
    "photo_count",
    "photo_tour_sections",
    "opening_description_text",
    "raw_visible_highlights_text",
    "scrape_status",
    "scrape_warning",
    "cover_photo_hook_guess",
    "primary_guest_value_hook",
    "trust_signal_strength",
    "amenity_signal_strength",
    "title_signal_strength",
]

SUMMARY_COLUMNS = [
    "run_date",
    "total_cards_inspected",
    "total_urls_collected",
    "total_listings_reviewed",
    "successful_scrapes",
    "failed_scrapes",
    "tier_1_direct_comp_count",
    "tier_2_market_pattern_count",
    "tier_3_outlier_pattern_count",
    "guest_favorite_count",
    "superhost_count",
    "new_listing_count",
    "average_rating",
    "median_review_count",
    "hot_tub_count",
    "sauna_count",
    "pool_count",
    "game_room_count",
    "theater_count",
    "arcade_count",
    "lake_access_count",
    "fire_pit_count",
    "fireplace_count",
    "exterior_twilight_or_firepit_cover_count",
    "spa_hook_count",
    "entertainment_hook_count",
    "lake_hook_count",
    "luxury_design_hook_count",
    "family_space_hook_count",
    "listings_with_clear_self_check_in",
    "listings_with_clear_pet_friendly_signal",
]

AMENITY_FIELDS = {
    "hot_tub_visible": ("hot tub", "jacuzzi"),
    "sauna_visible": ("sauna",),
    "pool_visible": ("pool",),
    "game_room_visible": ("game room", "games"),
    "theater_visible": ("theater", "movie room", "cinema"),
    "arcade_visible": ("arcade", "pac man"),
    "lake_access_visible": ("lake access", "lake"),
    "waterfront_visible": ("waterfront", "lakefront", "streamfront"),
    "fire_pit_visible": ("fire pit", "firepit"),
    "fireplace_visible": ("fireplace",),
    "grill_visible": ("grill", "bbq"),
    "ev_charger_visible": ("ev charger", "ev charging"),
    "cold_plunge_visible": ("cold plunge",),
    "private_pool_visible": ("private pool",),
    "shared_pool_visible": ("shared pool",),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review manually selected Airbnb competitor listing URLs.")
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--input-file", help="Defaults to data/manual_inputs/airbnb_competitor_urls_<run-date>.csv.")
    parser.add_argument("--run-dir", help="Defaults to data/runs/<run-date>.")
    return parser.parse_args(argv)


def run_dir_for(run_date: str, provided: Path | None = None) -> Path:
    return provided or Path("data") / "runs" / run_date


def input_file_for(run_date: str, provided: Path | None = None) -> Path:
    return provided or Path("data") / "manual_inputs" / f"airbnb_competitor_urls_{run_date}.csv"


def analysis_dir(run_dir: Path) -> Path:
    return run_dir / "analysis"


def logs_dir(run_dir: Path) -> Path:
    return run_dir / "logs"


def write_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")
    print(line)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def normalize_text(value: str) -> str:
    text = value.lower().replace("&", " and ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in terms)


def listing_id_from_url(url: str) -> str:
    match = re.search(r"/rooms/(\d+)", url)
    return match.group(1) if match else ""


def parse_rating(text: str) -> str:
    match = re.search(r"\b(\d\.\d{1,2})\b", text)
    if not match:
        return ""
    value = float(match.group(1))
    return f"{value:.2f}".rstrip("0").rstrip(".") if 0 <= value <= 5 else ""


def parse_review_count(text: str) -> str:
    match = re.search(r"\b(\d{1,5})\s+reviews?\b", text, re.I)
    return match.group(1) if match else ""


def parse_number_before(label: str, text: str) -> str:
    match = re.search(rf"\b(\d+)\s+{label}\b", text, re.I)
    return match.group(1) if match else ""


def parse_visible_price(text: str) -> str:
    match = re.search(r"\$[\d,]+(?:\.\d{2})?", text)
    return match.group(0) if match else ""


def photo_alts(page) -> list[str]:
    alts: list[str] = []
    try:
        images = page.locator("img[alt]")
        count = min(images.count(), 5)
        for index in range(count):
            value = images.nth(index).get_attribute("alt", timeout=1000) or ""
            if value.strip():
                alts.append(" ".join(value.split()))
    except Exception:
        return alts
    return alts


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned
    return ""


def opening_description(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 80]
    return lines[0][:500] if lines else ""


def cancellation_policy(text: str) -> str:
    for line in text.splitlines():
        if "cancellation" in line.lower():
            return line.strip()[:250]
    return ""


def classify_cover_photo_hook(text: str, alts: list[str]) -> str:
    haystack = " ".join([*alts[:1], text])
    if contains_any(haystack, ("hot tub", "spa", "jacuzzi")):
        return "hot_tub"
    if contains_any(haystack, ("twilight", "night", "fire pit", "firepit")):
        return "exterior_twilight"
    if contains_any(haystack, ("lake", "water", "waterfront")):
        return "lake_or_water"
    if contains_any(haystack, ("living room", "great room")):
        return "great_room"
    if contains_any(haystack, ("game room", "arcade", "pool table")):
        return "game_room"
    if contains_any(haystack, ("bedroom",)):
        return "bedroom"
    if contains_any(haystack, ("pool",)):
        return "pool"
    if contains_any(haystack, ("sauna",)):
        return "sauna"
    return "unclear"


def classify_primary_guest_value_hook(text: str) -> str:
    if contains_any(text, ("hot tub", "sauna", "spa", "cold plunge")):
        return "spa"
    if contains_any(text, ("game room", "arcade", "theater", "karaoke", "pool table")):
        return "entertainment"
    if contains_any(text, ("lake", "waterfront", "beach", "dock")):
        return "lake_access"
    if contains_any(text, ("luxury", "design", "renovated", "modern")):
        return "luxury_design"
    if contains_any(text, ("family", "kids", "group", "guests")):
        return "family_space"
    if contains_any(text, ("celebration", "birthday", "bachelorette")):
        return "group_celebration"
    if contains_any(text, ("resort", "community", "amenities")):
        return "resort_amenities"
    return "unclear"


def strength_from_count(count: int) -> str:
    if count >= 4:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def title_signal_strength(title: str) -> str:
    strong_terms = ("hot tub", "sauna", "pool", "lake", "game", "arcade", "theater", "fire pit")
    count = sum(1 for term in strong_terms if contains_any(title, (term,)))
    return strength_from_count(count)


def trust_signal_strength(row: dict[str, str]) -> str:
    score = 0
    score += 1 if row.get("guest_favorite_badge") == "true" else 0
    score += 1 if row.get("superhost_badge") == "true" else 0
    reviews = int(row["review_count"]) if row.get("review_count", "").isdigit() else 0
    score += 1 if reviews >= 50 else 0
    score += 1 if row.get("rating") and float(row["rating"]) >= 4.8 else 0
    return strength_from_count(score)


def amenity_signal_strength(row: dict[str, str]) -> str:
    count = sum(1 for field in AMENITY_FIELDS if row.get(field) == "true")
    return strength_from_count(count)


def read_input_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing competitor URL input: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def extract_listing_row(page, input_row: dict[str, str], run_date: str) -> dict[str, str]:
    url = input_row.get("listing_url", "").strip()
    row = {column: "" for column in REVIEW_COLUMNS}
    row.update(
        {
            "run_date": run_date,
            "rank_group": input_row.get("rank_group", ""),
            "source_note": input_row.get("source_note", ""),
            "match_reason": input_row.get("match_reason", ""),
            "absolute_position": input_row.get("absolute_position", ""),
            "listing_url": url,
            "listing_id": listing_id_from_url(url),
        }
    )
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(1200)
        try:
            visible_text = page.locator("body").inner_text(timeout=10_000)
        except Exception:
            visible_text = ""
        try:
            title = page.locator("h1").first.inner_text(timeout=3000).strip()
        except Exception:
            title = first_nonempty_line(visible_text)
        alts = photo_alts(page)
        row.update(
            {
                "listing_title": title,
                "location": "",
                "rating": parse_rating(visible_text),
                "review_count": parse_review_count(visible_text),
                "guest_favorite_badge": bool_text(contains_any(visible_text, ("Guest favorite",))),
                "superhost_badge": bool_text(contains_any(visible_text, ("Superhost",))),
                "host_type_or_host_badge": "Superhost" if contains_any(visible_text, ("Superhost",)) else "",
                "max_guests": parse_number_before("guests?", visible_text),
                "bedrooms": parse_number_before("bedrooms?", visible_text),
                "beds": parse_number_before("beds?", visible_text),
                "baths": parse_number_before("baths?", visible_text),
                "visible_price_text": parse_visible_price(visible_text),
                "cancellation_policy_text": cancellation_policy(visible_text),
                "self_check_in_visible": bool_text(contains_any(visible_text, ("self check-in", "self check in"))),
                "instant_book_visible": bool_text(contains_any(visible_text, ("instant book",))),
                "pets_allowed_visible": bool_text(contains_any(visible_text, ("pets allowed", "pet friendly"))),
                "top_photo_1_caption_or_alt": alts[0] if len(alts) > 0 else "",
                "top_photo_2_caption_or_alt": alts[1] if len(alts) > 1 else "",
                "top_photo_3_caption_or_alt": alts[2] if len(alts) > 2 else "",
                "top_photo_4_caption_or_alt": alts[3] if len(alts) > 3 else "",
                "top_photo_5_caption_or_alt": alts[4] if len(alts) > 4 else "",
                "first_5_photo_alt_or_caption_text": " | ".join(alts[:5]),
                "photo_count": "",
                "photo_tour_sections": "",
                "opening_description_text": opening_description(visible_text),
                "raw_visible_highlights_text": visible_text[:2500],
                "scrape_status": "success",
                "scrape_warning": "",
            }
        )
        for field, terms in AMENITY_FIELDS.items():
            row[field] = bool_text(contains_any(visible_text, terms))
        row["cover_photo_hook_guess"] = classify_cover_photo_hook(visible_text, alts)
        row["primary_guest_value_hook"] = classify_primary_guest_value_hook(visible_text)
        row["trust_signal_strength"] = trust_signal_strength(row)
        row["amenity_signal_strength"] = amenity_signal_strength(row)
        row["title_signal_strength"] = title_signal_strength(title)
    except Exception as exc:
        row["scrape_status"] = "failed"
        row["scrape_warning"] = str(exc)
    return row


def parse_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def median(values: list[float]) -> str:
    if not values:
        return ""
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    value = ordered[midpoint] if len(ordered) % 2 else (ordered[midpoint - 1] + ordered[midpoint]) / 2
    return f"{value:.2f}".rstrip("0").rstrip(".")


def count_true(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if row.get(field) == "true")


def summary_rows(
    run_date: str,
    rows: list[dict[str, str]],
    *,
    total_cards_inspected: int | str | None = None,
) -> list[dict[str, str]]:
    successful = [row for row in rows if row.get("scrape_status") == "success"]
    ratings = [value for value in (parse_float(row.get("rating", "")) for row in successful) if value is not None]
    reviews = [value for value in (parse_float(row.get("review_count", "")) for row in successful) if value is not None]
    cards_inspected = "" if total_cards_inspected is None else str(total_cards_inspected)
    return [
        {
            "run_date": run_date,
            "total_cards_inspected": cards_inspected,
            "total_urls_collected": str(len(rows)),
            "total_listings_reviewed": str(len(rows)),
            "successful_scrapes": str(len(successful)),
            "failed_scrapes": str(len(rows) - len(successful)),
            "tier_1_direct_comp_count": str(sum(1 for row in rows if row.get("rank_group") == "tier_1_direct_comp")),
            "tier_2_market_pattern_count": str(sum(1 for row in rows if row.get("rank_group") == "tier_2_market_pattern")),
            "tier_3_outlier_pattern_count": str(sum(1 for row in rows if row.get("rank_group") == "tier_3_outlier_pattern")),
            "guest_favorite_count": str(count_true(successful, "guest_favorite_badge")),
            "superhost_count": str(count_true(successful, "superhost_badge")),
            "new_listing_count": str(sum(1 for row in rows if row.get("match_reason") == "new_listing_high_rank" or contains_any(row.get("source_note", ""), ("new listing",)))),
            "average_rating": f"{sum(ratings) / len(ratings):.2f}".rstrip("0").rstrip(".") if ratings else "",
            "median_review_count": median(reviews),
            "hot_tub_count": str(count_true(successful, "hot_tub_visible")),
            "sauna_count": str(count_true(successful, "sauna_visible")),
            "pool_count": str(count_true(successful, "pool_visible")),
            "game_room_count": str(count_true(successful, "game_room_visible")),
            "theater_count": str(count_true(successful, "theater_visible")),
            "arcade_count": str(count_true(successful, "arcade_visible")),
            "lake_access_count": str(count_true(successful, "lake_access_visible")),
            "fire_pit_count": str(count_true(successful, "fire_pit_visible")),
            "fireplace_count": str(count_true(successful, "fireplace_visible")),
            "exterior_twilight_or_firepit_cover_count": str(sum(1 for row in successful if row.get("cover_photo_hook_guess") in {"exterior_twilight", "fire_pit"})),
            "spa_hook_count": str(sum(1 for row in successful if row.get("primary_guest_value_hook") == "spa")),
            "entertainment_hook_count": str(sum(1 for row in successful if row.get("primary_guest_value_hook") == "entertainment")),
            "lake_hook_count": str(sum(1 for row in successful if row.get("primary_guest_value_hook") == "lake_access")),
            "luxury_design_hook_count": str(sum(1 for row in successful if row.get("primary_guest_value_hook") == "luxury_design")),
            "family_space_hook_count": str(sum(1 for row in successful if row.get("primary_guest_value_hook") == "family_space")),
            "listings_with_clear_self_check_in": str(count_true(successful, "self_check_in_visible")),
            "listings_with_clear_pet_friendly_signal": str(count_true(successful, "pets_allowed_visible")),
        }
    ]


def render_actionable_gaps(run_date: str, rows: list[dict[str, str]]) -> str:
    summary = summary_rows(run_date, rows)[0]
    tier_1 = [row for row in rows if row.get("rank_group") == "tier_1_direct_comp"][:8]
    direct_competitors = [
        f"- {row.get('listing_title') or row.get('listing_url')} ({row.get('match_reason') or 'source-backed competitor'})"
        for row in tier_1
    ]
    return "\n".join(
        [
            f"# Airbnb Competitor Actionable Gaps - {run_date}",
            "",
            "## Executive Summary",
            "",
            f"- Listings reviewed: {summary['total_listings_reviewed']}",
            f"- Successful reviews: {summary['successful_scrapes']}",
            f"- Competitor URLs collected: {summary.get('total_urls_collected', '')}",
            "- This review is Airbnb diagnostic/listing-side context only.",
            "",
            "## Repeated Winning Broad-Search Patterns",
            "",
            f"- Hot tub visible: {summary['hot_tub_count']}",
            f"- Sauna visible: {summary['sauna_count']}",
            f"- Game room visible: {summary['game_room_count']}",
            f"- Fireplace visible: {summary.get('fireplace_count', '')}",
            f"- Guest Favorite count: {summary['guest_favorite_count']}",
            f"- Spa hook count: {summary['spa_hook_count']}",
            f"- Entertainment hook count: {summary['entertainment_hook_count']}",
            "",
            "## Top Direct Competitors Discovered",
            "",
            *(direct_competitors or ["- No tier 1 direct competitors were source-backed in this run."]),
            "",
            "## What Aloha Appears To Already Match",
            "",
            "- Aloha already has premium spa/entertainment positioning, strong group-fit copy, and high-trust listing signals.",
            "",
            "## Directly Actionable Gaps For Aloha",
            "",
            "- Compare Aloha's title, cover photo, first five photos, and opening copy against the repeated visible hooks in this review.",
            "- Prioritize listing-side tests only when the pattern is source-backed by manually selected competitor URLs.",
            "",
            "## Non-Actionable Competitor Advantages",
            "",
            "- Location, property size, historical review base, and platform ranking are context signals, not direct rule-change inputs.",
            "",
            "## Recommended Next Listing-Side Tests",
            "",
            "- Use the manually reviewed competitor patterns to choose one listing-side test at a time.",
            "- Record any intentional listing changes in data/history/listing_change_log.csv before judging weekly Airbnb funnel movement.",
            "",
            "## Guardrail",
            "",
            "- No PriceLabs rule changes should be made from this Airbnb diagnostic alone.",
            "- PriceLabs remains the source of truth for pricing, revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.",
            "",
        ]
    )


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in columns} for row in rows])


def write_outputs(
    run_date: str,
    rows: list[dict[str, str]],
    run_dir: Path,
    *,
    total_cards_inspected: int | str | None = None,
) -> tuple[Path, Path, Path]:
    output_dir = analysis_dir(run_dir)
    review_path = output_dir / f"airbnb_competitor_url_review_{run_date}.csv"
    summary_path = output_dir / f"airbnb_competitor_pattern_summary_{run_date}.csv"
    gaps_path = output_dir / f"airbnb_competitor_actionable_gaps_{run_date}.md"
    write_csv(review_path, rows, REVIEW_COLUMNS)
    write_csv(summary_path, summary_rows(run_date, rows, total_cards_inspected=total_cards_inspected), SUMMARY_COLUMNS)
    gaps_path.write_text(render_actionable_gaps(run_date, rows), encoding="utf-8")
    return review_path, summary_path, gaps_path


def run_review(
    run_date: str,
    *,
    input_file: Path,
    run_dir: Path,
    total_cards_inspected: int | str | None = None,
) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir(run_dir).mkdir(parents=True, exist_ok=True)
    log_path = logs_dir(run_dir) / f"airbnb_competitor_url_review_{run_date}.log"
    input_rows = read_input_rows(input_file)
    write_log(log_path, "Airbnb competitor URL review started.")
    write_log(log_path, f"Run date: {run_date}")
    write_log(log_path, f"Input file: {input_file}")
    write_log(log_path, "No PriceLabs preflight is run; no PriceLabs recommendations are created.")
    rows: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(persistent_profile_path()),
            headless=False,
            viewport={"width": 1440, "height": 1000},
            args=["--start-maximized"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for index, input_row in enumerate(input_rows, start=1):
                write_log(log_path, f"Reviewing competitor URL {index} of {len(input_rows)}.")
                rows.append(extract_listing_row(page, input_row, run_date))
                page.wait_for_timeout(1200)
        finally:
            context.close()
    review_path, summary_path, gaps_path = write_outputs(
        run_date,
        rows,
        run_dir,
        total_cards_inspected=total_cards_inspected,
    )
    write_log(log_path, f"Reviewed listings: {len(rows)}")
    write_log(log_path, f"Successful scrapes: {sum(1 for row in rows if row.get('scrape_status') == 'success')}")
    write_log(log_path, f"Review output path: {review_path}")
    write_log(log_path, f"Summary output path: {summary_path}")
    write_log(log_path, f"Actionable gaps output path: {gaps_path}")
    write_log(log_path, "Airbnb competitor URL review finished.")
    return 0


def run(run_date: str, *, input_file: Path | None = None, run_dir: Path | None = None) -> int:
    return run_review(
        run_date,
        input_file=input_file_for(run_date, input_file),
        run_dir=run_dir_for(run_date, run_dir),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(
        args.run_date,
        input_file=Path(args.input_file) if args.input_file else None,
        run_dir=Path(args.run_dir) if args.run_dir else None,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
