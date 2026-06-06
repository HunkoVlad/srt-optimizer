"""Headed Airbnb broad-search screening diagnostic.

This module is diagnostic only. It captures whether the listing appears in
two broad Airbnb flexible-date scenarios and writes structured outputs for
week-over-week comparison. It does not feed PriceLabs recommendations.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
import re
import sys

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


AIRBNB_URL = "https://www.airbnb.com"
DEFAULT_LOCATION = "Pocono Mountains, PA"
DEFAULT_LISTING_TITLE = "Pocono Spa Escape"
DEFAULT_LISTING_ID = "1313377469848413047"
DEFAULT_LISTING_ALIASES = (
    "Pocono Spa Escape",
    "Hot Tub, Sauna, Game Room",
    "Pocono Spa Escape: Hot Tub",
)
DEFAULT_MAX_PAGES = 15
DEFAULT_MAX_MONTHS = 2
DEFAULT_GUEST_INCREMENT_CLICKS = 7
EXPECTED_LISTINGS_PER_PAGE = 18
GUEST_COUNT = 8
VIEWPORT = {"width": 1440, "height": 1000}
SCENARIO_ISOLATION_MODE = "fresh_browser_context"
FILTER_SETUP_RETRY_ATTEMPTS = 2
FAILED_SCENARIO_STATUSES = {"filter_setup_failed", "scenario_failed"}
HIGH_INTENT_FILTERS = "Pool; Hot tub; Guest Favorite; Instant Book; Self check-in"
POOL_FILTERS = "Pool"
POOL_HOT_TUB_FILTERS = "Pool; Hot tub"
POOL_HOT_TUB_GUEST_FAVORITE_FILTERS = "Pool; Hot tub; Guest Favorite"
FILTER_BUTTON_SELECTOR = "#filter-menu-chip-group button"
FILTER_BUTTON_FALLBACK_SELECTORS = (
    '#filter-menu-chip-group button:has-text("Filters")',
    'button:has-text("Filters")',
    'div[role="button"]:has-text("Filters")',
)
POOL_FILTER_SELECTOR = "body > div:nth-child(59) > div > div > section > div > div > div.p1psejvv.atm_9s_1bgihbq.dir.dir-ltr > div > div.ctiimno.atm_9s_1bgihbq.dir.dir-ltr > div > div:nth-child(1) > div > div > section > div:nth-child(3) > div > div > div:nth-child(2) > button"
HOT_TUB_FILTER_SELECTOR = "body > div:nth-child(59) > div > div > section > div > div > div.p1psejvv.atm_9s_1bgihbq.dir.dir-ltr > div > div.ctiimno.atm_9s_1bgihbq.dir.dir-ltr > div > div:nth-child(1) > div > div > section > div:nth-child(3) > div > div > div:nth-child(3) > button"
GUEST_FAVORITE_FILTER_SELECTOR = "body > div:nth-child(59) > div > div > section > div > div > div.p1psejvv.atm_9s_1bgihbq.dir.dir-ltr > div > div.ctiimno.atm_9s_1bgihbq.dir.dir-ltr > div > div:nth-child(7) > div > div > section > div:nth-child(3) > div > div > button:nth-child(1)"
INSTANT_BOOK_FILTER_SELECTOR = "#filter-item-ib"
SELF_CHECKIN_FILTER_SELECTOR = "#filter-item-amenities-51"
SHOW_FILTERED_PLACES_SELECTOR = "body > div:nth-child(59) > div > div > section > div > div > div.p1psejvv.atm_9s_1bgihbq.dir.dir-ltr > div > div.ctiimno.atm_9s_1bgihbq.dir.dir-ltr > footer > div > a"

SCENARIOS = (
    {
        "scenario_name": "broad_weekend_first_visible_month",
        "month_index": 0,
        "trip_length": "Weekend",
    },
    {
        "scenario_name": "broad_week_next_month",
        "month_index": 1,
        "trip_length": "Week",
    },
)

FILTERED_SCENARIOS = (
    {
        "scenario_name": "broad_high_intent_filters_weekend_first_visible_month",
        "month_index": 0,
        "trip_length": "Weekend",
        "filters_used": HIGH_INTENT_FILTERS,
    },
    {
        "scenario_name": "broad_pool_hot_tub_guest_favorite_weekend_first_visible_month",
        "month_index": 0,
        "trip_length": "Weekend",
        "filters_used": POOL_HOT_TUB_GUEST_FAVORITE_FILTERS,
    },
    {
        "scenario_name": "broad_pool_hot_tub_weekend_first_visible_month",
        "month_index": 0,
        "trip_length": "Weekend",
        "filters_used": POOL_HOT_TUB_FILTERS,
    },
    {
        "scenario_name": "broad_pool_weekend_first_visible_month",
        "month_index": 0,
        "trip_length": "Weekend",
        "filters_used": POOL_FILTERS,
    },
)

COLUMNS = [
    "run_date",
    "generated_at",
    "scenario_name",
    "search_location",
    "date_mode",
    "scenario_isolation_mode",
    "scenario_started_from_clean_state",
    "scenario_start_url",
    "filters_applied_for_scenario",
    "prior_scenario_state_reused",
    "month_label",
    "trip_length",
    "guest_count",
    "filters_used",
    "found_status",
    "page_number",
    "cards_seen_before_match",
    "position_on_page",
    "absolute_position",
    "visible_cards_on_found_page",
    "pages_checked",
    "max_pages_checked",
    "result_count_visible_if_available",
    "visible_price",
    "visible_cover_photo",
    "cover_photo_status",
    "visible_badges",
    "visible_title",
    "search_card_screenshot_path",
    "listing_page_top_screenshot_path",
    "not_found_screenshot_path",
    "search_url",
    "notes",
]


@dataclass
class ScreeningResult:
    scenario_name: str
    month_label: str
    trip_length: str
    found_status: str
    pages_checked: int
    max_pages_checked: int
    search_url: str = ""
    page_number: int | None = None
    cards_seen_before_match: int | None = None
    position_on_page: int | None = None
    absolute_position: int | None = None
    visible_cards_on_found_page: int | None = None
    result_count_visible_if_available: int | None = None
    scenario_isolation_mode: str = SCENARIO_ISOLATION_MODE
    scenario_started_from_clean_state: bool = True
    scenario_start_url: str = AIRBNB_URL
    filters_applied_for_scenario: str = "none"
    prior_scenario_state_reused: bool = False
    visible_price: str = ""
    visible_cover_photo: str = ""
    cover_photo_status: str = ""
    visible_badges: str = ""
    visible_title: str = ""
    search_card_screenshot_path: str = ""
    listing_page_top_screenshot_path: str = ""
    not_found_screenshot_path: str = ""
    filters_used: str = "none"
    notes: str = ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Screen Airbnb broad search visibility and capture listing screenshots.")
    parser.add_argument("--run-date", default=date.today().isoformat(), help="Run date used in output filenames.")
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument(
        "--listing-title",
        default=DEFAULT_LISTING_TITLE,
        help="Text used to identify the target listing in search results.",
    )
    parser.add_argument(
        "--listing-id",
        default=DEFAULT_LISTING_ID,
        help="Airbnb room id used to identify the target listing when card title text is not rendered.",
    )
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--max-months", type=int, default=DEFAULT_MAX_MONTHS)
    parser.add_argument(
        "--pause-after-first-month",
        action="store_true",
        help="Pause with Playwright Inspector after the first month/page scan before selecting the next month.",
    )
    parser.add_argument(
        "--include-filtered-scenarios",
        action="store_true",
        help="Also run high-intent filtered search scenarios after the broad no-filter scenarios.",
    )
    parser.add_argument(
        "--filtered-only",
        action="store_true",
        help="Debug mode: run only filtered scenarios and skip the broad no-filter scenarios.",
    )
    parser.add_argument(
        "--manual-filter-fallback",
        action="store_true",
        help=(
            "If automated filter setup fails, pause for manual filter setup. "
            "Default is non-interactive: record filter_setup_failed and continue."
        ),
    )
    parser.add_argument(
        "--guest-increment-clicks",
        type=int,
        default=DEFAULT_GUEST_INCREMENT_CLICKS,
        help="Airbnb starts with 1 adult; 7 adult-stepper clicks produces the 8-person search setup.",
    )
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Screenshot staging directory. Defaults to data/runs/<run-date>/downloads_staging/airbnb_listing_state/search_screening.",
    )
    return parser.parse_args(argv)


def run_dir_for(run_date: str, provided: Path | None = None) -> Path:
    return provided or Path("data") / "runs" / run_date


def output_dir(run_date: str, run_dir: Path, provided: Path | None = None) -> Path:
    if provided is not None:
        return provided
    return run_dir / "downloads_staging" / "airbnb_listing_state" / "search_screening"


def analysis_dir(run_dir: Path) -> Path:
    return run_dir / "analysis"


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return cleaned or "listing"


def relative_path(path: str | Path) -> str:
    if not path:
        return ""
    candidate = Path(path)
    try:
        return candidate.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return candidate.as_posix()


def click_if_present(locator, *, timeout: int = 1500) -> bool:
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        return False


def listing_title_terms(listing_title: str) -> tuple[str, ...]:
    terms = [listing_title, *DEFAULT_LISTING_ALIASES]
    seen: set[str] = set()
    cleaned_terms: list[str] = []
    for term in terms:
        cleaned = " ".join(term.split())
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            cleaned_terms.append(cleaned)
    return tuple(cleaned_terms)


def wait_after_action(page: Page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(1000)


def scroll_results_top_to_bottom(page: Page) -> int:
    """Scroll the current results page so lazy-loaded listing cards render."""
    try:
        page.locator('a[href*="/rooms/"]').first.wait_for(timeout=15_000)
    except PlaywrightTimeoutError:
        pass

    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(750)

    best_count = 0
    previous_y = -1
    for _ in range(24):
        try:
            best_count = max(best_count, page.locator('a[href*="/rooms/"]').count())
        except Exception:
            pass
        current = page.evaluate(
            """
            () => ({
              y: Math.round(window.scrollY),
              height: Math.round(document.body.scrollHeight),
              viewport: Math.round(window.innerHeight),
            })
            """
        )
        current_y = int(current["y"])
        if current_y == previous_y and current_y + int(current["viewport"]) >= int(current["height"]) - 20:
            break
        previous_y = current_y
        page.evaluate("window.scrollBy(0, Math.round(window.innerHeight * 0.85))")
        page.wait_for_timeout(700)

    try:
        best_count = max(best_count, page.locator('a[href*="/rooms/"]').count())
    except Exception:
        pass
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    return best_count


def month_tile_buttons(page: Page):
    return page.locator('[data-testid="carousel-chip"] button')


def selected_month_label(page: Page) -> str:
    try:
        selected = month_tile_buttons(page).locator('[aria-pressed="true"]').first
        return " ".join(selected.inner_text(timeout=1000).split())
    except Exception:
        return ""


def click_flexible_month_tile(page: Page, month_index: int) -> str:
    month_buttons = month_tile_buttons(page)
    count = month_buttons.count()
    if month_index >= count:
        raise RuntimeError(f"Requested flexible month index {month_index}, but only {count} month tiles are visible.")
    month_button = month_buttons.nth(month_index)
    label = " ".join(month_button.inner_text(timeout=5000).split())
    month_button.click(timeout=10_000)
    return label


def select_trip_length(page: Page, label: str) -> None:
    selected = click_if_present(
        page.get_by_test_id("shimmer-css-variable-index-0").get_by_text(label, exact=True),
        timeout=3000,
    )
    if not selected:
        selected = click_if_present(page.get_by_role("radio", name=label, exact=True), timeout=3000)
    if not selected:
        selected = click_if_present(
            page.locator("label").filter(has_text=re.compile(rf"^{re.escape(label)}$", re.I)).first,
            timeout=3000,
        )
    if not selected:
        page.get_by_text(label, exact=True).first.click(timeout=5000)
    try:
        page.get_by_role("radio", name=label, exact=True).press("Enter", timeout=5000)
    except Exception:
        pass


def assert_search_ready(page: Page, *, location: str, trip_length: str) -> None:
    location_input = page.get_by_test_id("structured-search-input-field-query")
    value = location_input.input_value(timeout=5000)
    if value.strip() != location:
        raise RuntimeError(f"Search location was not set correctly: expected '{location}', got '{value}'.")

    summary_label = f"Any {trip_length.lower()}"
    try:
        page.locator("body").filter(has_text=re.compile(rf"\b{re.escape(summary_label)}\b", re.I)).wait_for(
            timeout=1500
        )
    except PlaywrightTimeoutError:
        print(f"Trip-length summary '{summary_label}' was not visible after opening guests; continuing after click.")
    page.locator("div").filter(has_text=re.compile(r"^8\s+guests$", re.I)).first.wait_for(timeout=5000)


def setup_recorded_search(page: Page, *, location: str, guest_increment_clicks: int) -> str:
    page.goto(AIRBNB_URL, wait_until="domcontentloaded", timeout=30_000)
    click_if_present(page.get_by_role("button", name="Got it"), timeout=3000)
    query = page.get_by_test_id("structured-search-input-field-query")
    query.click(timeout=10_000)
    query.fill(location, timeout=5000)
    query.press("Enter", timeout=5000)
    page.get_by_test_id("expanded-searchbar-dates-flexible-tab").click(timeout=10_000)
    month_label = click_flexible_month_tile(page, 0)
    select_trip_length(page, "Weekend")
    page.get_by_role("button", name="Who Add guests").click(timeout=10_000)

    adult_stepper = page.get_by_test_id("stepper-adults-increase-button")
    for _ in range(guest_increment_clicks):
        adult_stepper.click(timeout=5000)
    adult_stepper.press("Enter", timeout=5000)

    assert_search_ready(page, location=location, trip_length="Weekend")
    page.get_by_test_id("structured-search-input-search-button").click(timeout=10_000)
    wait_after_action(page)
    return month_label


def select_next_search_month(page: Page, month_index: int, *, location: str, trip_length: str) -> str:
    page.get_by_test_id("little-search-date").click(timeout=10_000)
    select_trip_length(page, trip_length)
    month_label = click_flexible_month_tile(page, month_index)
    assert_search_ready(page, location=location, trip_length=trip_length)
    page.get_by_test_id("structured-search-input-search-button").click(timeout=10_000)
    wait_after_action(page)
    return month_label


def click_filters_button(page: Page) -> bool:
    """Open Airbnb filters, pausing for DOM inspection only if every known Filters locator fails."""
    filter_locators = [(page.locator(FILTER_BUTTON_SELECTOR).first, FILTER_BUTTON_SELECTOR)]
    for selector in FILTER_BUTTON_FALLBACK_SELECTORS:
        filter_locators.append((page.locator(selector).first, selector))

    for locator, selector in filter_locators:
        try:
            print(f"Trying Filters locator: {selector}")
            locator.click(timeout=5000)
            page.wait_for_timeout(700)
            return True
        except Exception as exc:
            print(f"Filters locator failed: {selector}: {exc}")

    print("Could not find/click the Airbnb Filters button. Opening Playwright Inspector for DOM lookup.")
    try:
        page.pause()
    except Exception as exc:
        print(f"Playwright pause failed or is unavailable: {exc}")

    for locator, selector in filter_locators:
        try:
            print(f"Retrying Filters locator after pause: {selector}")
            locator.click(timeout=5000)
            page.wait_for_timeout(700)
            return True
        except Exception as exc:
            print(f"Filters locator still failed after pause: {selector}: {exc}")
    return False


def filter_step_locators(page: Page, selector: str, label: str) -> list[tuple[object, str]]:
    locators: list[tuple[object, str]] = [(page.locator(selector).first, selector)]
    locators.append((page.get_by_role("button", name=re.compile(rf"^{re.escape(label)}$", re.I)).first, f'button role "{label}"'))
    locators.append((page.locator("button").filter(has_text=re.compile(rf"^{re.escape(label)}$", re.I)).first, f'button text "{label}"'))
    return locators


def click_filter_step(page: Page, selector: str, label: str) -> bool:
    for locator, description in filter_step_locators(page, selector, label):
        try:
            print(f"Applying filter step: {label} via {description}")
            locator.click(timeout=10_000)
            page.wait_for_timeout(700)
            return True
        except Exception as exc:
            print(f"Filter step failed: {label} via {description}: {exc}")
    return False


def apply_scenario_filters(page: Page, filters_used: str) -> bool:
    """Apply filtered Airbnb scenarios using recorded selectors, with conservative fallbacks."""
    if not click_filters_button(page):
        return False
    steps: list[tuple[str, str]] = []
    if "Pool" in filters_used:
        steps.append((POOL_FILTER_SELECTOR, "Pool"))
    if "Hot tub" in filters_used:
        steps.append((HOT_TUB_FILTER_SELECTOR, "Hot tub"))
    if "Guest Favorite" in filters_used:
        steps.append((GUEST_FAVORITE_FILTER_SELECTOR, "Guest Favorite"))
    if "Instant Book" in filters_used:
        steps.append((INSTANT_BOOK_FILTER_SELECTOR, "Instant Book"))
    if "Self check-in" in filters_used:
        steps.append((SELF_CHECKIN_FILTER_SELECTOR, "Self check-in"))
    try:
        for selector, label in steps:
            if not click_filter_step(page, selector, label):
                return False
        show_places = page.locator(SHOW_FILTERED_PLACES_SELECTOR).first
        print("Applying filter step: Show places")
        show_places.click(timeout=10_000)
        page.wait_for_timeout(700)
        wait_after_action(page)
        return True
    except Exception as exc:
        print(f"Automated filter application did not complete: {exc}")
        return False


def apply_high_intent_filters(page: Page) -> bool:
    return apply_scenario_filters(page, HIGH_INTENT_FILTERS)


def listing_link(page: Page, title: str, listing_id: str = DEFAULT_LISTING_ID):
    if listing_id:
        id_selectors = [
            f'a[href*="/rooms/{listing_id}"]',
            f'a[target="listing_{listing_id}"]',
            f'a[aria-labelledby="title_{listing_id}"]',
        ]
        for selector in id_selectors:
            candidate = page.locator(selector).first
            try:
                if candidate.count() > 0:
                    return candidate
            except Exception:
                continue
    for term in listing_title_terms(title):
        title_pattern = re.compile(re.escape(term), re.I)
        candidates = [
            page.get_by_role("link", name=title_pattern).first,
            page.locator("a").filter(has_text=title_pattern).first,
        ]
        for candidate in candidates:
            try:
                if candidate.count() > 0:
                    return candidate
            except Exception:
                continue
    for candidate in listing_card_links(page):
        if link_matches_listing(candidate, title, listing_id):
            return candidate
    return None


def find_listing_on_current_page(page: Page, title: str, listing_id: str = DEFAULT_LISTING_ID):
    link = listing_link(page, title, listing_id)
    if link is None:
        return None
    try:
        link.scroll_into_view_if_needed(timeout=5000)
        return link
    except Exception:
        return None


def click_result_page(page: Page, page_number: int) -> bool:
    locator = page.get_by_role("link", name=str(page_number), exact=True)
    if not click_if_present(locator, timeout=5000):
        return False
    wait_after_action(page)
    return True


def screenshot_listing_card(page: Page, link, screenshot_path: Path) -> None:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.screenshot(path=str(screenshot_path))
    except Exception:
        page.screenshot(path=str(screenshot_path), full_page=False)


def listing_href(link) -> str:
    try:
        return str(link.get_attribute("href", timeout=1000) or "")
    except Exception:
        return ""


def absolute_airbnb_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{AIRBNB_URL}{href}"
    return href


def room_id_from_href(href: str) -> str:
    match = re.search(r"/rooms/(\d+)", href)
    return match.group(1) if match else ""


def listing_card_links(page: Page) -> list[object]:
    links = page.locator('a[href*="/rooms/"]')
    try:
        count = links.count()
    except Exception:
        return []
    cards: list[object] = []
    seen_keys: set[str] = set()
    for index in range(count):
        candidate = links.nth(index)
        href = listing_href(candidate)
        room_id = room_id_from_href(href)
        key = room_id or href or f"index:{index}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        cards.append(candidate)
    return cards


def link_matches_listing(link, title: str, listing_id: str = DEFAULT_LISTING_ID) -> bool:
    if listing_id:
        try:
            values = [
                listing_href(link),
                str(link.get_attribute("target", timeout=1000) or ""),
                str(link.get_attribute("aria-labelledby", timeout=1000) or ""),
            ]
        except Exception:
            values = [listing_href(link)]
        if any(listing_id in value for value in values):
            return True
    try:
        text = " ".join(link.inner_text(timeout=1000).split()).lower()
    except Exception:
        text = ""
    return any(term.lower() in text for term in listing_title_terms(title))


def open_listing_and_capture(page: Page, link, screenshot_path: Path) -> str:
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.scroll_into_view_if_needed(timeout=5000)
        page.wait_for_timeout(500)
    except Exception:
        pass
    href = absolute_airbnb_url(listing_href(link))
    try:
        with page.expect_popup(timeout=5000) as popup_info:
            link.click(timeout=5000)
        listing_page = popup_info.value
    except Exception:
        if href:
            listing_page = page.context.new_page()
            listing_page.goto(href, wait_until="domcontentloaded", timeout=30_000)
        else:
            try:
                link.click(timeout=5000, force=True)
            except Exception:
                pass
            listing_page = page
    wait_after_action(listing_page)
    click_if_present(listing_page.get_by_role("button", name="Close"), timeout=3000)
    listing_page.screenshot(path=str(screenshot_path), full_page=False)
    listing_url = listing_page.url
    if listing_page is not page:
        try:
            listing_page.close()
        except Exception:
            pass
    return listing_url


def result_to_row(result: ScreeningResult, *, run_date: str, generated_at: str, search_location: str) -> dict[str, str]:
    values = {
        "run_date": run_date,
        "generated_at": generated_at,
        "scenario_name": result.scenario_name,
        "search_location": search_location,
        "date_mode": "flexible",
        "scenario_isolation_mode": result.scenario_isolation_mode,
        "scenario_started_from_clean_state": str(result.scenario_started_from_clean_state).lower(),
        "scenario_start_url": result.scenario_start_url,
        "filters_applied_for_scenario": result.filters_applied_for_scenario,
        "prior_scenario_state_reused": str(result.prior_scenario_state_reused).lower(),
        "month_label": result.month_label,
        "trip_length": result.trip_length,
        "guest_count": str(GUEST_COUNT),
        "filters_used": result.filters_used,
        "found_status": result.found_status,
        "page_number": str(result.page_number or ""),
        "cards_seen_before_match": str(result.cards_seen_before_match or ""),
        "position_on_page": str(result.position_on_page or ""),
        "absolute_position": str(result.absolute_position or ""),
        "visible_cards_on_found_page": str(result.visible_cards_on_found_page or ""),
        "pages_checked": str(result.pages_checked),
        "max_pages_checked": str(result.max_pages_checked),
        "result_count_visible_if_available": str(result.result_count_visible_if_available or ""),
        "visible_price": result.visible_price,
        "visible_cover_photo": result.visible_cover_photo,
        "cover_photo_status": result.cover_photo_status,
        "visible_badges": result.visible_badges,
        "visible_title": result.visible_title,
        "search_card_screenshot_path": relative_path(result.search_card_screenshot_path),
        "listing_page_top_screenshot_path": relative_path(result.listing_page_top_screenshot_path),
        "not_found_screenshot_path": relative_path(result.not_found_screenshot_path),
        "search_url": result.search_url,
        "notes": result.notes,
    }
    return {column: values.get(column, "") for column in COLUMNS}


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in COLUMNS} for row in rows])


def status_line(row: dict[str, str] | None) -> str:
    if not row:
        return "not run"
    if row.get("found_status") == "found":
        page = row.get("page_number") or "unknown"
        position = row.get("position_on_page")
        absolute_position = row.get("absolute_position")
        detail = f"found on page {page}"
        if absolute_position:
            detail += f", absolute position {absolute_position}"
        if position:
            detail += f", position {position}"
        return detail
    return f"not found after {row.get('pages_checked') or row.get('max_pages_checked') or 'unknown'} pages checked"


def best_found_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    return next((row for row in rows if row.get("found_status") == "found"), None)


def best_found_by_absolute_position(rows: list[dict[str, str]]) -> dict[str, str] | None:
    found_rows = [row for row in rows if row.get("found_status") == "found"]
    with_positions = [row for row in found_rows if row.get("absolute_position")]
    if with_positions:
        return min(with_positions, key=lambda row: int(row["absolute_position"]))
    return found_rows[0] if found_rows else None


def render_markdown(run_date: str, rows: list[dict[str, str]]) -> str:
    first = next((row for row in rows if row.get("scenario_name") == "broad_weekend_first_visible_month"), None)
    second = next((row for row in rows if row.get("scenario_name") == "broad_week_next_month"), None)
    filtered_rows = [row for row in rows if row.get("filters_used") and row.get("filters_used") != "none"]
    filtered_best = best_found_by_absolute_position(filtered_rows)
    best = best_found_by_absolute_position(rows)
    total_pages = sum(int(row.get("pages_checked") or 0) for row in rows)

    lines = [
        f"# Airbnb Search Screening - {run_date}",
        "",
        "## Executive Summary",
        "",
    ]
    if first:
        lines.append(f"- First scenario status: {status_line(first)}.")
    if second:
        lines.append(f"- Second scenario status: {status_line(second)}.")
    if not first and filtered_rows:
        lines.append("- Filtered-only debug run: broad no-filter scenarios were intentionally skipped.")
    if best:
        lines.append(
            f"- Best found scenario: {best.get('scenario_name')} on page {best.get('page_number') or 'unknown'}"
            f" at absolute position {best.get('absolute_position') or 'unknown'}."
        )
    else:
        lines.append(f"- Listing not found after {total_pages} total pages checked.")
    if filtered_rows:
        high_intent = next((row for row in filtered_rows if row.get("scenario_name") == "broad_high_intent_filters_weekend_first_visible_month"), None)
        if filtered_best:
            lines.append(
                f"- Best filtered scenario: {filtered_best.get('scenario_name')} at absolute position "
                f"{filtered_best.get('absolute_position') or 'unknown'}."
            )
        lines.append(f"- High-intent filtered status: {status_line(high_intent)}.")

    lines.extend(["", "## Scenario Results", ""])
    lines.append(
        "- Each scenario was run from a fresh browser context and clean Airbnb search URL "
        "to reduce Airbnb state carryover."
    )
    if all(row.get("found_status") not in FAILED_SCENARIO_STATUSES for row in rows):
        lines.append("- Final verification: all scenarios completed cleanly.")
    else:
        failed = ", ".join(row.get("scenario_name", "") for row in rows if row.get("found_status") in FAILED_SCENARIO_STATUSES)
        lines.append(f"- Final verification: scenario setup failed for {failed}.")
    for row in rows:
        lines.append(
            f"- {row.get('scenario_name')}: {row.get('found_status')} | "
            f"{row.get('month_label')} | {row.get('trip_length')} | page: {row.get('page_number') or 'not found'} | "
            f"absolute position: {row.get('absolute_position') or 'unknown'} | "
            f"position on page: {row.get('position_on_page') or 'unknown'} | "
            f"visible cards on found page: {row.get('visible_cards_on_found_page') or 'unknown'} | "
            f"result count: {row.get('result_count_visible_if_available') or 'unknown'} | "
            f"filters: {row.get('filters_used') or 'none'} | pages checked: {row.get('pages_checked')}."
        )

    if filtered_rows:
        lines.extend(["", "## Filtered Scenario Results", ""])
        for row in filtered_rows:
            lines.append(
                f"- {row.get('scenario_name')}: {row.get('found_status')} | "
                f"page: {row.get('page_number') or 'not found'} | "
                f"absolute position: {row.get('absolute_position') or 'unknown'} | "
                f"position on page: {row.get('position_on_page') or 'unknown'} | "
                f"visible cards on found page: {row.get('visible_cards_on_found_page') or 'unknown'} | "
                f"result count: {row.get('result_count_visible_if_available') or 'unknown'} | "
                f"filters: {row.get('filters_used')} | "
                f"screenshot: {row.get('search_card_screenshot_path') or row.get('not_found_screenshot_path') or 'unavailable'}."
            )

    lines.extend(["", "## Screenshot Evidence", ""])
    screenshot_lines = []
    for row in rows:
        for key, label in [
            ("search_card_screenshot_path", "Search card"),
            ("listing_page_top_screenshot_path", "Listing page top"),
            ("not_found_screenshot_path", "Not found"),
        ]:
            if row.get(key):
                screenshot_lines.append(f"- {label}: {row[key]}")
    lines.extend(screenshot_lines or ["- Screenshot evidence unavailable."])

    lines.extend(["", "## Discovery Interpretation", ""])
    if best:
        lines.append(
            f"- Airbnb broad screening found the listing under {best.get('scenario_name')} "
            f"on page {best.get('page_number') or 'unknown'}."
        )
    else:
        lines.append("- Airbnb broad screening did not find the listing in the tested broad scenarios.")
    if filtered_rows:
        high_intent = next((row for row in filtered_rows if row.get("scenario_name") == "broad_high_intent_filters_weekend_first_visible_month"), None)
        if high_intent and high_intent.get("found_status") == "found":
            lines.append(
                f"- High-intent filtered screening found the listing on page "
                f"{high_intent.get('page_number') or 'unknown'} at absolute position "
                f"{high_intent.get('absolute_position') or 'unknown'}."
            )
        else:
            lines.append("- High-intent filtered screening did not find the listing in the tested filtered scenario.")
        lines.append("- Filtered visibility is diagnostic only and does not justify PriceLabs changes by itself.")
        lines.append("- Absolute position is the preferred benchmark because Airbnb page sizes can vary.")
    lines.extend(
        [
            "- This is discovery context only; it is not a pricing issue by itself.",
            "",
            "## Guardrails",
            "",
            "- Airbnb search screening is diagnostic only and does not create a PriceLabs rule recommendation.",
            "- PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    run_date: str,
    results: list[ScreeningResult],
    *,
    run_dir: Path | None = None,
    search_location: str = DEFAULT_LOCATION,
    generated_at: str | None = None,
) -> tuple[Path, Path]:
    resolved_run_dir = run_dir_for(run_date, run_dir)
    output_dir_path = analysis_dir(resolved_run_dir)
    generated = generated_at or datetime.now(UTC).isoformat()
    rows = [result_to_row(result, run_date=run_date, generated_at=generated, search_location=search_location) for result in results]
    csv_path = output_dir_path / f"airbnb_search_screening_{run_date}.csv"
    md_path = output_dir_path / f"airbnb_search_screening_{run_date}.md"
    write_csv(csv_path, rows)
    md_path.write_text(render_markdown(run_date, rows), encoding="utf-8")
    return csv_path, md_path


def scenario_not_found_result(
    scenario: dict[str, object],
    *,
    month_label: str,
    pages_checked: int,
    max_pages: int,
    result_count: int,
    search_url: str,
    not_found_screenshot_path: str = "",
    scenario_start_url: str = AIRBNB_URL,
) -> ScreeningResult:
    return ScreeningResult(
        scenario_name=str(scenario["scenario_name"]),
        month_label=month_label,
        trip_length=str(scenario["trip_length"]),
        filters_used=str(scenario.get("filters_used", "none")),
        found_status="not_found",
        pages_checked=pages_checked,
        max_pages_checked=max_pages,
        scenario_start_url=scenario_start_url,
        filters_applied_for_scenario=str(scenario.get("filters_used", "none")),
        result_count_visible_if_available=result_count,
        search_url=search_url,
        not_found_screenshot_path=not_found_screenshot_path,
        notes="Target listing was not found in this scenario.",
    )


def scenario_found_result(
    scenario: dict[str, object],
    *,
    month_label: str,
    page_number: int,
    pages_checked: int,
    max_pages: int,
    result_count: int,
    search_url: str,
    search_card_screenshot_path: str,
    listing_page_top_screenshot_path: str,
    visible_title: str,
    cards_seen_before_match: int | None = None,
    position_on_page: int | None = None,
    scenario_start_url: str = AIRBNB_URL,
) -> ScreeningResult:
    absolute_position = None
    if cards_seen_before_match is not None and position_on_page is not None:
        absolute_position = cards_seen_before_match + position_on_page
    return ScreeningResult(
        scenario_name=str(scenario["scenario_name"]),
        month_label=month_label,
        trip_length=str(scenario["trip_length"]),
        filters_used=str(scenario.get("filters_used", "none")),
        found_status="found",
        page_number=page_number,
        cards_seen_before_match=cards_seen_before_match,
        position_on_page=position_on_page,
        absolute_position=absolute_position,
        visible_cards_on_found_page=result_count,
        pages_checked=pages_checked,
        max_pages_checked=max_pages,
        scenario_start_url=scenario_start_url,
        filters_applied_for_scenario=str(scenario.get("filters_used", "none")),
        result_count_visible_if_available=result_count,
        visible_title=visible_title,
        search_card_screenshot_path=search_card_screenshot_path,
        listing_page_top_screenshot_path=listing_page_top_screenshot_path,
        search_url=search_url,
        notes="Target listing was found in this scenario.",
    )


def scan_scenario_pages(
    page: Page,
    *,
    max_pages: int,
    listing_title: str,
    listing_id: str = DEFAULT_LISTING_ID,
) -> tuple[int, int, object | None, int | None, int | None]:
    last_result_count = 0
    target_link = None
    pages_checked = 0
    cards_seen_before_match = 0
    for page_number in range(1, max_pages + 1):
        if page_number > 1 and not click_result_page(page, page_number):
            print(f"Could not navigate to result page {page_number}; stopping this scenario.")
            break
        pages_checked = page_number
        listing_count = scroll_results_top_to_bottom(page)
        cards = listing_card_links(page)
        if cards:
            listing_count = len(cards)
        last_result_count = listing_count
        if listing_count < EXPECTED_LISTINGS_PER_PAGE:
            print(
                f"Checked result page {page_number}; observed {listing_count} room links after scrolling "
                f"(expected about {EXPECTED_LISTINGS_PER_PAGE}; Airbnb may show fewer on the final page or while lazy loading)."
            )
        else:
            print(f"Checked result page {page_number}; observed at least {EXPECTED_LISTINGS_PER_PAGE} room links after scrolling.")
        for position, candidate in enumerate(cards, start=1):
            if link_matches_listing(candidate, listing_title, listing_id):
                target_link = candidate
                try:
                    target_link.scroll_into_view_if_needed(timeout=5000)
                except Exception:
                    pass
                return page_number, last_result_count, target_link, position, cards_seen_before_match
        target_link = find_listing_on_current_page(page, listing_title, listing_id)
        if target_link is not None:
            return page_number, last_result_count, target_link, None, cards_seen_before_match
        print(f"Target listing not found on result page {page_number}.")
        cards_seen_before_match += listing_count
    return pages_checked, last_result_count, None, None, None


def scan_and_record_scenario(
    page: Page,
    *,
    scenario: dict[str, object],
    run_date: str,
    month_label: str,
    listing_title: str,
    listing_id: str,
    listing_slug: str,
    max_pages: int,
    screenshot_dir: Path,
    scenario_start_url: str,
) -> tuple[ScreeningResult, bool]:
    page_number, result_count, target_link, position_on_page, cards_seen_before_match = scan_scenario_pages(
        page,
        max_pages=max_pages,
        listing_title=listing_title,
        listing_id=listing_id,
    )
    if target_link is None:
        return (
            scenario_not_found_result(
                scenario,
                month_label=month_label or selected_month_label(page),
                pages_checked=page_number,
                max_pages=max_pages,
                result_count=result_count,
                search_url=page.url,
                scenario_start_url=scenario_start_url,
            ),
            False,
        )

    month_slug = safe_name(month_label or selected_month_label(page) or "month")
    scenario_slug = safe_name(str(scenario["scenario_name"]))
    search_path = screenshot_dir / f"listing_search_card_{run_date}_{scenario_slug}_{month_slug}_page_{page_number}_{listing_slug}.png"
    listing_path = screenshot_dir / f"listing_page_top_{run_date}_{scenario_slug}_{month_slug}_page_{page_number}_{listing_slug}.png"
    screenshot_listing_card(page, target_link, search_path)
    listing_url = open_listing_and_capture(page, target_link, listing_path)
    print(f"Found target listing on {month_label or 'selected month'}, result page {page_number}.")
    print(f"Saved search card screenshot: {search_path}")
    print(f"Saved listing top screenshot: {listing_path}")
    print(f"Listing URL: {listing_url}")
    return (
        scenario_found_result(
            scenario,
            month_label=month_label or selected_month_label(page),
            page_number=page_number,
            cards_seen_before_match=cards_seen_before_match,
            position_on_page=position_on_page,
            pages_checked=page_number,
            max_pages=max_pages,
            result_count=result_count,
            search_url=listing_url or page.url,
            search_card_screenshot_path=str(search_path),
            listing_page_top_screenshot_path=str(listing_path),
            visible_title=listing_title,
            scenario_start_url=scenario_start_url,
        ),
        True,
    )


def prompt_for_scenario_filters(filters_used: str) -> None:
    print(
        f"Please apply these Airbnb filters now: {filters_used}. Click Airbnb Search/Show results if needed, "
        "then return here and press Enter."
    )
    input()


def scenario_filter_setup_failed_result(
    scenario: dict[str, object],
    *,
    month_label: str,
    max_pages: int,
    search_url: str,
    scenario_start_url: str = AIRBNB_URL,
    error: str = "",
) -> ScreeningResult:
    filters_used = str(scenario.get("filters_used", "none"))
    notes = (
        "Automated filter setup failed before scanning. Scenario was not scanned so results from another "
        "filter state are not mixed into this scenario."
    )
    if error:
        notes = f"{notes} Error: {error}"
    return ScreeningResult(
        scenario_name=str(scenario["scenario_name"]),
        month_label=month_label,
        trip_length=str(scenario["trip_length"]),
        filters_used=filters_used,
        found_status="filter_setup_failed",
        pages_checked=0,
        max_pages_checked=max_pages,
        scenario_start_url=scenario_start_url,
        filters_applied_for_scenario=filters_used,
        result_count_visible_if_available=0,
        search_url=search_url,
        notes=notes,
    )


def scenario_failed_result(
    scenario: dict[str, object],
    *,
    month_label: str = "",
    max_pages: int,
    search_url: str = "",
    scenario_start_url: str = AIRBNB_URL,
    error: str = "",
) -> ScreeningResult:
    notes = "Scenario failed before a clean result could be recorded."
    if error:
        notes = f"{notes} Error: {error}"
    return ScreeningResult(
        scenario_name=str(scenario["scenario_name"]),
        month_label=month_label,
        trip_length=str(scenario["trip_length"]),
        filters_used=str(scenario.get("filters_used", "none")),
        found_status="scenario_failed",
        pages_checked=0,
        max_pages_checked=max_pages,
        scenario_start_url=scenario_start_url,
        filters_applied_for_scenario=str(scenario.get("filters_used", "none")),
        result_count_visible_if_available=0,
        search_url=search_url,
        notes=notes,
    )
def scenario_sequence(
    max_months: int,
    include_filtered_scenarios: bool,
    *,
    filtered_only: bool = False,
) -> list[dict[str, object]]:
    scenarios = [] if filtered_only else list(SCENARIOS[:max_months])
    if include_filtered_scenarios:
        scenarios.extend(FILTERED_SCENARIOS)
    return scenarios


def prepare_scenario_search(
    page: Page,
    scenario: dict[str, object],
    *,
    location: str,
    guest_increment_clicks: int,
    manual_filter_fallback: bool = False,
) -> tuple[str, bool]:
    month_label = setup_recorded_search(page, location=location, guest_increment_clicks=guest_increment_clicks)
    month_index = int(scenario.get("month_index", 0))
    trip_length = str(scenario.get("trip_length", "Weekend"))
    if month_index > 0 or trip_length != "Weekend":
        month_label = select_next_search_month(page, month_index, location=location, trip_length=trip_length)
    filters_used = str(scenario.get("filters_used", "none"))
    if filters_used != "none":
        filters_applied = apply_scenario_filters(page, filters_used)
        if not filters_applied:
            if not manual_filter_fallback:
                return month_label, False
            prompt_for_scenario_filters(filters_used)
        wait_after_action(page)
    return month_label, True


def run_screening(
    *,
    run_date: str,
    location: str,
    listing_title: str,
    listing_id: str,
    max_pages: int,
    max_months: int,
    guest_increment_clicks: int,
    run_dir: Path,
    screenshot_dir: Path,
    pause_after_first_month: bool = False,
    include_filtered_scenarios: bool = False,
    manual_filter_fallback: bool = False,
    filtered_only: bool = False,
) -> int:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    listing_slug = safe_name(listing_title)
    results: list[ScreeningResult] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, args=["--start-maximized"])

        found = False
        last_page = None
        scenarios = scenario_sequence(max_months, include_filtered_scenarios, filtered_only=filtered_only)

        def attempt_scenario(scenario_index: int, scenario: dict[str, object], *, retry_pass: bool = False) -> tuple[ScreeningResult, bool]:
            nonlocal last_page
            scenario_start_url = AIRBNB_URL
            result: ScreeningResult | None = None
            scenario_found = False
            for attempt in range(FILTER_SETUP_RETRY_ATTEMPTS + 1):
                context = browser.new_context(no_viewport=True, viewport=VIEWPORT)
                page = context.new_page()
                last_page = page
                try:
                    month_label, scenario_ready = prepare_scenario_search(
                        page,
                        scenario,
                        location=location,
                        guest_increment_clicks=guest_increment_clicks,
                        manual_filter_fallback=manual_filter_fallback,
                    )
                    if not scenario_ready:
                        if attempt < FILTER_SETUP_RETRY_ATTEMPTS:
                            print(
                                f"Filter setup failed for scenario {scenario['scenario_name']}; "
                                "retrying this scenario from a fresh browser context."
                            )
                            continue
                        print(
                            f"Skipping scenario {scenario['scenario_name']} because automated filter setup failed "
                            "after retry. No manual Enter prompt is used unless --manual-filter-fallback is supplied."
                        )
                        result = scenario_filter_setup_failed_result(
                            scenario,
                            month_label=month_label or selected_month_label(page),
                            max_pages=max_pages,
                            search_url=page.url,
                            scenario_start_url=scenario_start_url,
                            error="filter setup failed after fresh-context retry",
                        )
                        break
                    print(
                        f"Searching scenario {scenario['scenario_name']}: "
                        f"{month_label or selected_month_label(page)} / {scenario['trip_length']} / "
                        f"{scenario.get('filters_used', 'none')}"
                    )
                    result, scenario_found = scan_and_record_scenario(
                        page,
                        scenario=scenario,
                        run_date=run_date,
                        month_label=month_label or selected_month_label(page),
                        listing_title=listing_title,
                        listing_id=listing_id,
                        listing_slug=listing_slug,
                        max_pages=max_pages,
                        screenshot_dir=screenshot_dir,
                        scenario_start_url=scenario_start_url,
                    )
                    if not scenario_found:
                        not_found_path = screenshot_dir / f"airbnb_search_not_found_{run_date}_{safe_name(str(scenario['scenario_name']))}_max_{max_pages}_pages.png"
                        page.screenshot(path=str(not_found_path), full_page=False)
                        result.not_found_screenshot_path = str(not_found_path)
                        print(f"Saved not-found screenshot: {not_found_path}")
                        if pause_after_first_month and scenario_index == 0 and max_months > 1 and not retry_pass:
                            print("Debug pause after first scenario scan. Inspect locators, then resume to continue.")
                            page.pause()
                    break
                except Exception as exc:
                    print(f"Scenario {scenario['scenario_name']} failed before completion: {exc}")
                    result = scenario_failed_result(
                        scenario,
                        month_label="",
                        max_pages=max_pages,
                        search_url=getattr(page, "url", ""),
                        scenario_start_url=scenario_start_url,
                        error=str(exc),
                    )
                    break
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
            if result is None:
                result = scenario_failed_result(
                    scenario,
                    month_label="",
                    max_pages=max_pages,
                    scenario_start_url=scenario_start_url,
                    error="scenario produced no result",
                )
            return result, scenario_found

        for scenario_index, scenario in enumerate(scenarios):
            result, scenario_found = attempt_scenario(scenario_index, scenario)
            results.append(result)
            found = found or scenario_found
            write_outputs(run_date, results, run_dir=run_dir, search_location=location)
            if found and not include_filtered_scenarios:
                break

        failed_indexes = [index for index, result in enumerate(results) if result.found_status in FAILED_SCENARIO_STATUSES]
        for result_index in failed_indexes:
            scenario = next(
                scenario
                for scenario in scenarios
                if str(scenario["scenario_name"]) == results[result_index].scenario_name
            )
            print(f"Retrying failed scenario {scenario['scenario_name']} from a fresh browser context.")
            retry_result, scenario_found = attempt_scenario(result_index, scenario, retry_pass=True)
            if retry_result.found_status not in FAILED_SCENARIO_STATUSES:
                results[result_index] = retry_result
                found = found or scenario_found
                print(f"Retry passed for scenario {scenario['scenario_name']}.")
            else:
                results[result_index] = retry_result
                print(f"Retry still failed for scenario {scenario['scenario_name']}.")
            write_outputs(run_date, results, run_dir=run_dir, search_location=location)

        if not found:
            not_found_path = screenshot_dir / f"airbnb_search_not_found_{run_date}_{len(results)}_scenarios_max_{max_pages}_pages.png"
            if last_page is not None:
                try:
                    last_page.screenshot(path=str(not_found_path), full_page=False)
                except Exception:
                    pass
            if results:
                results[-1].not_found_screenshot_path = str(not_found_path)
            print(f"Target listing was not found within {max_pages} pages across {len(results)} scenarios.")
            print(f"Saved not-found screenshot: {not_found_path}")
        browser.close()

    csv_path, md_path = write_outputs(run_date, results, run_dir=run_dir, search_location=location)
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    failed = any(result.found_status in FAILED_SCENARIO_STATUSES for result in results)
    if failed:
        print("Final verification: one or more scenarios did not complete cleanly.")
        return 2
    print("Final verification: all scenarios completed cleanly.")
    return 0


def run(
    run_date: str,
    *,
    location: str = DEFAULT_LOCATION,
    listing_title: str = DEFAULT_LISTING_TITLE,
    listing_id: str = DEFAULT_LISTING_ID,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_months: int = DEFAULT_MAX_MONTHS,
    guest_increment_clicks: int = DEFAULT_GUEST_INCREMENT_CLICKS,
    run_dir: Path | None = None,
    screenshot_dir: Path | None = None,
    pause_after_first_month: bool = False,
    include_filtered_scenarios: bool = False,
    manual_filter_fallback: bool = False,
    filtered_only: bool = False,
) -> int:
    resolved_run_dir = run_dir_for(run_date, run_dir)
    return run_screening(
        run_date=run_date,
        location=location,
        listing_title=listing_title,
        listing_id=listing_id,
        max_pages=max_pages,
        max_months=max_months,
        guest_increment_clicks=guest_increment_clicks,
        run_dir=resolved_run_dir,
        screenshot_dir=output_dir(run_date, resolved_run_dir, screenshot_dir),
        pause_after_first_month=pause_after_first_month,
        include_filtered_scenarios=include_filtered_scenarios,
        manual_filter_fallback=manual_filter_fallback,
        filtered_only=filtered_only,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(
        args.run_date,
        location=args.location,
        listing_title=args.listing_title,
        listing_id=args.listing_id,
        max_pages=args.max_pages,
        max_months=args.max_months,
        guest_increment_clicks=args.guest_increment_clicks,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        screenshot_dir=args.output_dir,
        pause_after_first_month=args.pause_after_first_month,
        include_filtered_scenarios=args.include_filtered_scenarios,
        manual_filter_fallback=args.manual_filter_fallback,
        filtered_only=args.filtered_only,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
