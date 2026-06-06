"""Discover broad-search Airbnb competitor URLs, then run URL review.

This flow is Airbnb diagnostic/listing-side context only. It does not search
for Aloha, does not require PriceLabs raw files, and does not create pricing
or recommendation actions.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re
import sys

from playwright.sync_api import Page, sync_playwright

from airbnb import airbnb_competitor_url_review as url_review
from airbnb.airbnb_search_screening import (
    AIRBNB_URL,
    DEFAULT_GUEST_INCREMENT_CLICKS,
    DEFAULT_LOCATION,
    GUEST_COUNT,
    VIEWPORT,
    absolute_airbnb_url,
    click_result_page,
    listing_card_links,
    listing_href,
    room_id_from_href,
    scroll_results_top_to_bottom,
    setup_recorded_search,
)
from airbnb.download_diagnostics import persistent_profile_path


DEFAULT_MAX_CARDS = 100
DEFAULT_MAX_PAGES = 6
TARGET_MIN_URLS = 15
TARGET_MAX_URLS = 30

DISCOVERY_COLUMNS = [
    "run_date",
    "absolute_position",
    "page_number",
    "position_on_page",
    "rank_group",
    "source_note",
    "match_reason",
    "listing_url",
    "listing_id",
    "card_title",
    "card_location",
    "visible_price_text",
    "rating",
    "review_count",
    "badge_guest_favorite",
    "badge_superhost",
    "badge_new",
    "raw_card_text",
    "eligibility_score",
    "eligibility_reasons",
    "rejection_reason",
]

DEBUG_COLUMNS = [
    "run_date",
    "page_number",
    "position_on_page",
    "absolute_position",
    "card_title",
    "card_location",
    "listing_url",
    "listing_id",
    "visible_price_text",
    "rating",
    "review_count",
    "badge_guest_favorite",
    "badge_superhost",
    "badge_new",
    "raw_card_text",
    "eligibility_score",
    "eligibility_reasons",
    "would_collect",
    "rejection_reason",
]

DIRECT_LOCATIONS = (
    "long pond",
    "tobyhanna",
    "tobyhanna township",
    "pocono summit",
    "coolbaugh township",
)

MARKET_LOCATIONS = (
    *DIRECT_LOCATIONS,
    "east stroudsburg",
    "tannersville",
    "albrightsville",
    "lake harmony",
    "pocono lake",
)

AMENITY_TERMS = (
    "hot tub",
    "sauna",
    "pool",
    "game room",
    "arcade",
    "theater",
    "movie room",
    "fire pit",
    "fireplace",
    "lake",
    "lakefront",
    "beach",
    "dock",
    "kayaks",
    "pickleball",
    "karaoke",
    "ev charger",
    "cold plunge",
    "grill",
)

SPA_TERMS = ("hot tub", "sauna", "spa", "jacuzzi", "cold plunge")
ENTERTAINMENT_TERMS = ("game room", "arcade", "theater", "movie room", "pool table", "karaoke")
LAKE_TERMS = ("lake", "lakefront", "waterfront", "beach", "dock", "kayak")
LUXURY_TERMS = ("luxury", "modern", "designer", "chalet", "cabin", "retreat")
GROUP_TERMS = ("family", "large group", "group getaway", "sleeps")


@dataclass(frozen=True)
class Eligibility:
    include: bool
    rank_group: str
    match_reason: str
    source_note: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover and review broad-search Airbnb competitors.")
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--max-cards", type=int, default=DEFAULT_MAX_CARDS)
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--run-dir", help="Defaults to data/runs/<run-date>.")
    parser.add_argument("--input-file", help="Defaults to data/manual_inputs/airbnb_competitor_urls_<run-date>.csv.")
    parser.add_argument("--skip-url-review", action="store_true")
    return parser.parse_args(argv)


def run_dir_for(run_date: str, provided: Path | None = None) -> Path:
    return provided or Path("data") / "runs" / run_date


def input_file_for(run_date: str, provided: Path | None = None) -> Path:
    return provided or Path("data") / "manual_inputs" / f"airbnb_competitor_urls_{run_date}.csv"


def logs_dir(run_dir: Path) -> Path:
    return run_dir / "logs"


def analysis_dir(run_dir: Path) -> Path:
    return run_dir / "analysis"


def evidence_dir(run_dir: Path) -> Path:
    return run_dir / "evidence"


def debug_cards_path(run_date: str, run_dir: Path) -> Path:
    return analysis_dir(run_dir) / f"airbnb_competitor_discovery_debug_cards_{run_date}.csv"


def zero_urls_screenshot_path(run_date: str, run_dir: Path) -> Path:
    return evidence_dir(run_dir) / f"airbnb_competitor_discovery_zero_urls_{run_date}.png"


def write_log(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")
    print(line)


def normalize_text(value: str) -> str:
    text = value.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9$.,]+", " ", text)
    return " ".join(text.split())


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in terms)


def parse_rating(text: str) -> str:
    match = re.search(r"\b(\d\.\d{1,2})\b", text)
    if not match:
        return ""
    value = float(match.group(1))
    return f"{value:.2f}".rstrip("0").rstrip(".") if 0 <= value <= 5 else ""


def parse_review_count(text: str) -> str:
    match = re.search(r"\b(\d{1,5})\s+reviews?\b", text, re.I)
    return match.group(1) if match else ""


def parse_visible_price(text: str) -> str:
    match = re.search(r"\$[\d,]+(?:\.\d{2})?", text)
    return match.group(0) if match else ""


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def clean_listing_url(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"(https://www\.airbnb\.com)?/rooms/(\d+)", url)
    if not match:
        return url.split("?")[0]
    return f"https://www.airbnb.com/rooms/{match.group(2)}"


def listing_id_from_url(url: str) -> str:
    match = re.search(r"/rooms/(\d+)", url)
    return match.group(1) if match else ""


def card_title_from_text(text: str) -> str:
    for line in [line.strip() for line in text.splitlines() if line.strip()]:
        if "$" in line or "reviews" in line.lower() or line.lower() in {"guest favorite", "superhost", "new"}:
            continue
        return line[:160]
    return ""


def card_location_from_text(text: str) -> str:
    for line in [line.strip() for line in text.splitlines() if line.strip()]:
        if contains_any(line, MARKET_LOCATIONS):
            return line[:160]
    return ""


def high_trust_signal(text: str, absolute_position: int) -> bool:
    rating = parse_rating(text)
    reviews = parse_review_count(text)
    if contains_any(text, ("guest favorite", "superhost")):
        return True
    if rating and float(rating) >= 4.8 and reviews and int(reviews) >= 25:
        return True
    return contains_any(text, ("new",)) and absolute_position <= 30


def eligibility_signals(text: str, absolute_position: int) -> dict[str, bool]:
    return {
        "location": contains_any(text, MARKET_LOCATIONS),
        "direct_location": contains_any(text, DIRECT_LOCATIONS),
        "amenity": contains_any(text, AMENITY_TERMS),
        "trust": high_trust_signal(text, absolute_position),
        "pattern": contains_any(text, SPA_TERMS + ENTERTAINMENT_TERMS + LAKE_TERMS + LUXURY_TERMS + GROUP_TERMS),
    }


def eligibility_score(text: str, absolute_position: int, *, has_url: bool) -> int:
    signals = eligibility_signals(text, absolute_position)
    score = 0
    score += 10 if has_url else 0
    score += 4 if signals["direct_location"] else 0
    score += 2 if signals["location"] and not signals["direct_location"] else 0
    score += 3 if signals["amenity"] else 0
    score += 2 if signals["trust"] else 0
    score += 1 if signals["pattern"] else 0
    score += 1 if absolute_position <= 30 else 0
    return score


def eligibility_reason_text(text: str, absolute_position: int) -> str:
    signals = eligibility_signals(text, absolute_position)
    reasons = []
    if signals["direct_location"]:
        reasons.append("direct_location")
    elif signals["location"]:
        reasons.append("market_location")
    if signals["amenity"]:
        reasons.append("amenity")
    if signals["trust"]:
        reasons.append("trust")
    if signals["pattern"]:
        reasons.append("visual_or_value_pattern")
    if absolute_position <= 30:
        reasons.append("high_absolute_position")
    return "; ".join(reasons)


def match_reason_for(text: str, absolute_position: int) -> str:
    direct = contains_any(text, DIRECT_LOCATIONS)
    if direct and contains_any(text, ("hot tub", "sauna")):
        return "direct_location_hot_tub_sauna"
    if contains_any(text, ("guest favorite",)) and contains_any(text, ENTERTAINMENT_TERMS):
        return "guest_favorite_game_room"
    if contains_any(text, LAKE_TERMS) and absolute_position <= 50:
        return "lakefront_high_rank"
    if contains_any(text, ("new",)) and absolute_position <= 30:
        return "new_listing_high_rank"
    if contains_any(text, SPA_TERMS):
        return "luxury_spa_pattern"
    if contains_any(text, ENTERTAINMENT_TERMS + GROUP_TERMS):
        return "entertainment_group_pattern"
    if contains_any(text, LUXURY_TERMS):
        return "luxury_spa_pattern"
    return "market_pattern"


def classify_competitor(text: str, absolute_position: int) -> Eligibility:
    direct_location = contains_any(text, DIRECT_LOCATIONS)
    market_location = contains_any(text, MARKET_LOCATIONS)
    amenity_overlap = contains_any(text, AMENITY_TERMS)
    pattern_overlap = contains_any(text, SPA_TERMS + ENTERTAINMENT_TERMS + LAKE_TERMS + LUXURY_TERMS + GROUP_TERMS)
    trust = high_trust_signal(text, absolute_position)

    if direct_location and amenity_overlap:
        rank_group = "tier_1_direct_comp"
    elif market_location and (amenity_overlap or pattern_overlap or trust):
        rank_group = "tier_2_market_pattern"
    elif absolute_position <= 40 and (trust or pattern_overlap):
        rank_group = "tier_3_outlier_pattern"
    elif amenity_overlap and trust:
        rank_group = "tier_3_outlier_pattern"
    else:
        return Eligibility(False, "", "", "Excluded: not enough location, amenity, trust, or visual-card relevance.")

    reason = match_reason_for(text, absolute_position)
    signals = []
    if direct_location:
        signals.append("direct location")
    elif market_location:
        signals.append("market location")
    if amenity_overlap:
        signals.append("amenity overlap")
    if trust:
        signals.append("trust/high-rank signal")
    if pattern_overlap:
        signals.append("visual/card pattern")
    return Eligibility(True, rank_group, reason, "; ".join(signals))


def dedupe_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        key = row.get("listing_id") or row.get("listing_url")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def card_raw_text(link) -> str:
    try:
        text = link.inner_text(timeout=1500)
        if text.strip():
            return text
    except Exception:
        pass
    try:
        return str(
            link.evaluate(
                """
                element => {
                  const card = element.closest('[itemprop], [data-testid], article, div');
                  return (card || element).innerText || '';
                }
                """
            )
            or ""
        )
    except Exception:
        return ""


def card_base_values(
    *,
    run_date: str,
    link,
    page_number: int,
    position_on_page: int,
    cards_seen_before_page: int,
) -> dict[str, str]:
    absolute_position = cards_seen_before_page + position_on_page
    href = absolute_airbnb_url(listing_href(link))
    listing_url = clean_listing_url(href)
    listing_id = listing_id_from_url(listing_url) or room_id_from_href(href)
    raw_text = card_raw_text(link)
    has_url = bool(listing_id and listing_url)
    score = eligibility_score(raw_text, absolute_position, has_url=has_url)
    reasons = eligibility_reason_text(raw_text, absolute_position)
    return {
        "run_date": run_date,
        "absolute_position": str(absolute_position),
        "page_number": str(page_number),
        "position_on_page": str(position_on_page),
        "listing_url": listing_url,
        "listing_id": listing_id,
        "card_title": card_title_from_text(raw_text),
        "card_location": card_location_from_text(raw_text),
        "visible_price_text": parse_visible_price(raw_text),
        "rating": parse_rating(raw_text),
        "review_count": parse_review_count(raw_text),
        "badge_guest_favorite": bool_text(contains_any(raw_text, ("guest favorite",))),
        "badge_superhost": bool_text(contains_any(raw_text, ("superhost",))),
        "badge_new": bool_text(contains_any(raw_text, ("new",))),
        "raw_card_text": " ".join(raw_text.split())[:2500],
        "eligibility_score": str(score),
        "eligibility_reasons": reasons,
    }


def relaxed_rank_group(text: str, absolute_position: int) -> str:
    eligibility = classify_competitor(text, absolute_position)
    if eligibility.include:
        return eligibility.rank_group
    if contains_any(text, DIRECT_LOCATIONS):
        return "tier_1_direct_comp"
    if contains_any(text, MARKET_LOCATIONS) or contains_any(text, AMENITY_TERMS):
        return "tier_2_market_pattern"
    return "tier_3_outlier_pattern"


def relaxed_match_reason(text: str, absolute_position: int) -> str:
    eligibility = classify_competitor(text, absolute_position)
    if eligibility.include:
        return eligibility.match_reason
    if not text.strip():
        return "valid_url_card_text_missing"
    return "valid_url_broad_search"


def discovery_row_from_card(
    *,
    run_date: str,
    link,
    page_number: int,
    position_on_page: int,
    cards_seen_before_page: int,
) -> tuple[dict[str, str] | None, str]:
    row = card_base_values(
        run_date=run_date,
        link=link,
        page_number=page_number,
        position_on_page=position_on_page,
        cards_seen_before_page=cards_seen_before_page,
    )
    absolute_position = int(row["absolute_position"])
    raw_text = row["raw_card_text"]
    eligibility = classify_competitor(raw_text, absolute_position)
    has_valid_url = bool(row["listing_url"] and row["listing_id"])
    if not has_valid_url:
        return None, "Rejected: missing valid Airbnb /rooms/<id> URL."
    row.update(
        {
            "rank_group": relaxed_rank_group(raw_text, absolute_position),
            "source_note": eligibility.source_note if eligibility.include else "Relaxed validation: valid broad-search Airbnb room URL collected for manual review.",
            "match_reason": relaxed_match_reason(raw_text, absolute_position),
            "rejection_reason": "" if eligibility.include else eligibility.source_note,
        }
    )
    return row, ""


def write_discovery_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=DISCOVERY_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in DISCOVERY_COLUMNS} for row in rows])


def write_debug_cards_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=DEBUG_COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in DEBUG_COLUMNS} for row in rows])


def debug_row_from_card(
    *,
    run_date: str,
    link,
    page_number: int,
    position_on_page: int,
    cards_seen_before_page: int,
) -> dict[str, str]:
    row = card_base_values(
        run_date=run_date,
        link=link,
        page_number=page_number,
        position_on_page=position_on_page,
        cards_seen_before_page=cards_seen_before_page,
    )
    absolute_position = int(row["absolute_position"])
    eligibility = classify_competitor(row["raw_card_text"], absolute_position)
    has_valid_url = bool(row["listing_url"] and row["listing_id"])
    rejection = ""
    if not has_valid_url:
        rejection = "missing_valid_room_url"
    elif not eligibility.include:
        rejection = eligibility.source_note
    row.update(
        {
            "would_collect": bool_text(has_valid_url),
            "rejection_reason": rejection,
        }
    )
    return row


def discovery_counts(debug_rows: list[dict[str, str]], collected_rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "cards_inspected": len(debug_rows),
        "cards_with_non_empty_raw_card_text": sum(1 for row in debug_rows if row.get("raw_card_text")),
        "cards_with_listing_url": sum(1 for row in debug_rows if row.get("listing_url")),
        "cards_with_listing_id": sum(1 for row in debug_rows if row.get("listing_id")),
        "cards_passing_location_criteria": sum(1 for row in debug_rows if "location" in row.get("eligibility_reasons", "")),
        "cards_passing_amenity_criteria": sum(1 for row in debug_rows if "amenity" in row.get("eligibility_reasons", "")),
        "cards_passing_trust_criteria": sum(1 for row in debug_rows if "trust" in row.get("eligibility_reasons", "")),
        "cards_passing_final_eligibility": sum(
            1
            for row in debug_rows
            if classify_competitor(row.get("raw_card_text", ""), int(row.get("absolute_position") or 0)).include
        ),
        "urls_collected": len(collected_rows),
    }


def sort_collection_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        dedupe_rows(rows),
        key=lambda row: (-int(row.get("eligibility_score") or 0), int(row.get("absolute_position") or 999999)),
    )


def collect_competitor_rows(
    page: Page,
    *,
    run_date: str,
    location: str,
    max_cards: int,
    max_pages: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    setup_recorded_search(page, location=location, guest_increment_clicks=DEFAULT_GUEST_INCREMENT_CLICKS)
    qualified: list[dict[str, str]] = []
    debug_rows: list[dict[str, str]] = []
    cards_inspected = 0
    cards_seen_before_page = 0
    for page_number in range(1, max_pages + 1):
        if page_number > 1 and not click_result_page(page, page_number):
            break
        scroll_results_top_to_bottom(page)
        cards = listing_card_links(page)
        for position_on_page, link in enumerate(cards, start=1):
            if cards_inspected >= max_cards:
                return sort_collection_rows(qualified)[:TARGET_MAX_URLS], debug_rows
            cards_inspected += 1
            debug_rows.append(
                debug_row_from_card(
                    run_date=run_date,
                    link=link,
                    page_number=page_number,
                    position_on_page=position_on_page,
                    cards_seen_before_page=cards_seen_before_page,
                )
            )
            row, _ = discovery_row_from_card(
                run_date=run_date,
                link=link,
                page_number=page_number,
                position_on_page=position_on_page,
                cards_seen_before_page=cards_seen_before_page,
            )
            if row:
                qualified.append(row)
        cards_seen_before_page += len(cards)
    return sort_collection_rows(qualified)[:TARGET_MAX_URLS], debug_rows


def run_discovery(
    run_date: str,
    *,
    location: str,
    max_cards: int,
    max_pages: int,
    run_dir: Path,
    input_file: Path,
    skip_url_review: bool = False,
) -> int:
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir(run_dir) / f"airbnb_competitor_discovery_{run_date}.log"
    write_log(log_path, "Airbnb competitor discovery started.")
    write_log(log_path, f"Run date: {run_date}")
    write_log(log_path, f"Search setup: {location}; flexible weekend; {GUEST_COUNT} guests; no filters; Airbnb default sort.")
    write_log(log_path, "No PriceLabs preflight is run; no weekly report or PriceLabs recommendations are created.")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(persistent_profile_path()),
            headless=False,
            viewport=VIEWPORT,
            args=["--start-maximized"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        zero_screenshot = ""
        try:
            rows, debug_rows = collect_competitor_rows(
                page,
                run_date=run_date,
                location=location,
                max_cards=max_cards,
                max_pages=max_pages,
            )
            if debug_rows and not rows:
                screenshot_path = zero_urls_screenshot_path(run_date, run_dir)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(screenshot_path), full_page=False)
                    zero_screenshot = str(screenshot_path)
                except Exception as exc:
                    zero_screenshot = f"screenshot_failed: {exc}"
        finally:
            context.close()

    debug_path = debug_cards_path(run_date, run_dir)
    write_debug_cards_csv(debug_path, debug_rows)
    write_discovery_csv(input_file, rows)
    counts = discovery_counts(debug_rows, rows)
    write_log(log_path, f"Cards inspected: {counts['cards_inspected']}")
    write_log(log_path, f"Cards with non-empty raw_card_text: {counts['cards_with_non_empty_raw_card_text']}")
    write_log(log_path, f"Cards with listing_url: {counts['cards_with_listing_url']}")
    write_log(log_path, f"Cards with listing_id: {counts['cards_with_listing_id']}")
    write_log(log_path, f"Cards passing location criteria: {counts['cards_passing_location_criteria']}")
    write_log(log_path, f"Cards passing amenity criteria: {counts['cards_passing_amenity_criteria']}")
    write_log(log_path, f"Cards passing trust criteria: {counts['cards_passing_trust_criteria']}")
    write_log(log_path, f"Cards passing final eligibility: {counts['cards_passing_final_eligibility']}")
    write_log(log_path, f"Competitor URLs collected: {len(rows)}")
    if len(rows) < TARGET_MIN_URLS:
        write_log(log_path, f"Warning: fewer than {TARGET_MIN_URLS} qualified competitors were collected.")
    write_log(log_path, f"Debug cards CSV path: {debug_path}")
    write_log(log_path, f"Competitor URL input path: {input_file}")
    if zero_screenshot:
        write_log(log_path, f"Zero-URL screenshot path: {zero_screenshot}")

    if skip_url_review:
        write_log(log_path, "URL review skipped by CLI flag.")
        return 0

    exit_code = url_review.run_review(
        run_date,
        input_file=input_file,
        run_dir=run_dir,
        total_cards_inspected=counts["cards_inspected"],
    )
    write_log(log_path, "Airbnb competitor discovery finished.")
    return exit_code


def run(
    run_date: str,
    *,
    location: str = DEFAULT_LOCATION,
    max_cards: int = DEFAULT_MAX_CARDS,
    max_pages: int = DEFAULT_MAX_PAGES,
    run_dir: Path | None = None,
    input_file: Path | None = None,
    skip_url_review: bool = False,
) -> int:
    return run_discovery(
        run_date,
        location=location,
        max_cards=max_cards,
        max_pages=max_pages,
        run_dir=run_dir_for(run_date, run_dir),
        input_file=input_file_for(run_date, input_file),
        skip_url_review=skip_url_review,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(
        args.run_date,
        location=args.location,
        max_cards=args.max_cards,
        max_pages=args.max_pages,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        input_file=Path(args.input_file) if args.input_file else None,
        skip_url_review=args.skip_url_review,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
