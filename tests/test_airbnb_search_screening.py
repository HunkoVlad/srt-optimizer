import csv
from pathlib import Path

from airbnb import airbnb_search_screening


RUN_DATE = "2026-06-01"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str, count: int = 1, href: str = "") -> None:
        self.page = page
        self.selector = selector
        self._count = count
        self.href = href

    @property
    def first(self) -> "FakeLocator":
        return self

    def count(self) -> int:
        return self._count

    def click(self, timeout=None, force: bool = False) -> None:
        if (self.page.fail_click or self.selector in self.page.fail_selectors) and not force:
            raise RuntimeError("intercepts pointer events")
        self.page.clicked_selectors.append(self.selector)

    def filter(self, has_text=None) -> "FakeLocator":
        return self

    def get_attribute(self, name: str, timeout=None) -> str:
        if name == "href":
            return self.href
        return ""

    def scroll_into_view_if_needed(self, timeout=None) -> None:
        self.page.scrolled_selectors.append(self.selector)

    def screenshot(self, path: str) -> None:
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")


class FakeContext:
    def __init__(self) -> None:
        self.pages: list[FakeListingPage] = []

    def new_page(self) -> "FakeListingPage":
        page = FakeListingPage()
        self.pages.append(page)
        return page


class FakeListingPage:
    def __init__(self) -> None:
        self.url = ""
        self.screenshots: list[str] = []
        self.closed = False

    def goto(self, url: str, wait_until=None, timeout=None) -> None:
        self.url = url

    def wait_for_load_state(self, state: str, timeout=None) -> None:
        pass

    def wait_for_timeout(self, milliseconds: int) -> None:
        pass

    def get_by_role(self, role: str, name: str) -> FakeLocator:
        return FakeLocator(FakePage(), f"role:{role}:{name}", count=0)

    def screenshot(self, path: str, full_page: bool = False) -> None:
        self.screenshots.append(path)
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\n")

    def close(self) -> None:
        self.closed = True


class FakePage:
    def __init__(
        self,
        existing_selectors: set[str] | None = None,
        fail_click: bool = False,
        fail_selectors: set[str] | None = None,
    ) -> None:
        self.existing_selectors = existing_selectors or set()
        self.fail_click = fail_click
        self.fail_selectors = fail_selectors or set()
        self.context = FakeContext()
        self.clicked_selectors: list[str] = []
        self.scrolled_selectors: list[str] = []
        self.waited_timeouts: list[int] = []
        self.load_states: list[str] = []
        self.paused = False

    def locator(self, selector: str) -> FakeLocator:
        count = 1 if not self.existing_selectors or selector in self.existing_selectors else 0
        return FakeLocator(self, selector, count=count)

    def get_by_role(self, role: str, name=None, exact: bool | None = None) -> FakeLocator:
        return FakeLocator(self, f"role:{role}:{name}", count=1)

    def wait_for_timeout(self, milliseconds: int) -> None:
        self.waited_timeouts.append(milliseconds)

    def wait_for_load_state(self, state: str, timeout=None) -> None:
        self.load_states.append(state)

    def expect_popup(self, timeout=None):
        raise RuntimeError("no popup")

    def pause(self) -> None:
        self.paused = True


def found_result(
    scenario_name: str = "broad_weekend_first_visible_month",
    *,
    month_label: str = "June 2026",
    trip_length: str = "Weekend",
    filters_used: str = "none",
    cards_seen_before_match: int | None = 54,
    position_on_page: int | None = 3,
    search_card_screenshot_path: str = "data/runs/2026-06-01/downloads_staging/search.png",
    listing_page_top_screenshot_path: str = "data/runs/2026-06-01/downloads_staging/top.png",
) -> airbnb_search_screening.ScreeningResult:
    return airbnb_search_screening.ScreeningResult(
        scenario_name=scenario_name,
        month_label=month_label,
        trip_length=trip_length,
        found_status="found",
        page_number=4,
        pages_checked=4,
        max_pages_checked=15,
        filters_used=filters_used,
        cards_seen_before_match=cards_seen_before_match,
        position_on_page=position_on_page,
        absolute_position=(cards_seen_before_match + position_on_page) if cards_seen_before_match is not None and position_on_page is not None else None,
        visible_cards_on_found_page=18,
        result_count_visible_if_available=18,
        visible_title="Pocono Spa Escape",
        search_card_screenshot_path=search_card_screenshot_path,
        listing_page_top_screenshot_path=listing_page_top_screenshot_path,
        search_url="https://www.airbnb.com/rooms/123",
    )


def not_found_result(
    scenario_name: str,
    *,
    month_label: str,
    trip_length: str,
    filters_used: str = "none",
    not_found_screenshot_path: str = "",
) -> airbnb_search_screening.ScreeningResult:
    return airbnb_search_screening.ScreeningResult(
        scenario_name=scenario_name,
        month_label=month_label,
        trip_length=trip_length,
        found_status="not_found",
        pages_checked=15,
        max_pages_checked=15,
        filters_used=filters_used,
        result_count_visible_if_available=18,
        not_found_screenshot_path=not_found_screenshot_path,
        search_url="https://www.airbnb.com/s/Pocono-Mountains--PA/homes",
    )


def test_parse_args_accepts_include_filtered_scenarios() -> None:
    args = airbnb_search_screening.parse_args(["--run-date", RUN_DATE, "--include-filtered-scenarios"])

    assert args.include_filtered_scenarios is True


def test_parse_args_default_omits_filtered_scenarios() -> None:
    args = airbnb_search_screening.parse_args(["--run-date", RUN_DATE])

    assert args.include_filtered_scenarios is False
    assert args.filtered_only is False
    assert args.manual_filter_fallback is False
    assert args.listing_id == airbnb_search_screening.DEFAULT_LISTING_ID


def test_parse_args_accepts_filtered_only() -> None:
    args = airbnb_search_screening.parse_args(["--run-date", RUN_DATE, "--include-filtered-scenarios", "--filtered-only"])

    assert args.include_filtered_scenarios is True
    assert args.filtered_only is True


def test_parse_args_accepts_manual_filter_fallback() -> None:
    args = airbnb_search_screening.parse_args(["--run-date", RUN_DATE, "--manual-filter-fallback"])

    assert args.manual_filter_fallback is True


def test_listing_title_terms_include_long_airbnb_card_title_aliases() -> None:
    terms = airbnb_search_screening.listing_title_terms("Pocono Spa Escape")

    assert "Pocono Spa Escape" in terms
    assert "Hot Tub, Sauna, Game Room" in terms
    assert "Pocono Spa Escape: Hot Tub" in terms


def test_listing_link_detects_empty_anchor_by_airbnb_room_id() -> None:
    selector = f'a[href*="/rooms/{airbnb_search_screening.DEFAULT_LISTING_ID}"]'
    page = FakePage(existing_selectors={selector})

    link = airbnb_search_screening.listing_link(page, "Missing title text")

    assert link is not None
    assert link.selector == selector


def test_open_listing_and_capture_uses_href_when_pointer_click_is_intercepted(tmp_path: Path) -> None:
    page = FakePage(fail_click=True)
    link = FakeLocator(
        page,
        "target-listing-link",
        href="/rooms/1313377469848413047?adults=8",
    )
    screenshot_path = tmp_path / "listing_page_top.png"

    url = airbnb_search_screening.open_listing_and_capture(page, link, screenshot_path)

    assert url == "https://www.airbnb.com/rooms/1313377469848413047?adults=8"
    assert page.context.pages[0].url == url
    assert page.context.pages[0].closed is True
    assert screenshot_path.exists()
    assert page.clicked_selectors == []


def test_apply_high_intent_filters_uses_recorded_selectors() -> None:
    page = FakePage()

    assert airbnb_search_screening.apply_high_intent_filters(page) is True

    assert page.clicked_selectors == [
        airbnb_search_screening.FILTER_BUTTON_SELECTOR,
        airbnb_search_screening.POOL_FILTER_SELECTOR,
        airbnb_search_screening.HOT_TUB_FILTER_SELECTOR,
        airbnb_search_screening.GUEST_FAVORITE_FILTER_SELECTOR,
        airbnb_search_screening.INSTANT_BOOK_FILTER_SELECTOR,
        airbnb_search_screening.SELF_CHECKIN_FILTER_SELECTOR,
        airbnb_search_screening.SHOW_FILTERED_PLACES_SELECTOR,
    ]
    assert page.waited_timeouts == [700, 700, 700, 700, 700, 700, 700, 1000]


def test_apply_pool_only_filter_uses_subset_of_recorded_selectors() -> None:
    page = FakePage()

    assert airbnb_search_screening.apply_scenario_filters(page, airbnb_search_screening.POOL_FILTERS) is True

    assert page.clicked_selectors == [
        airbnb_search_screening.FILTER_BUTTON_SELECTOR,
        airbnb_search_screening.POOL_FILTER_SELECTOR,
        airbnb_search_screening.SHOW_FILTERED_PLACES_SELECTOR,
    ]


def test_filters_button_uses_fallback_locator_when_recorded_locator_fails() -> None:
    fallback_selector = airbnb_search_screening.FILTER_BUTTON_FALLBACK_SELECTORS[0]
    page = FakePage(fail_selectors={airbnb_search_screening.FILTER_BUTTON_SELECTOR})

    assert airbnb_search_screening.click_filters_button(page) is True

    assert page.clicked_selectors == [fallback_selector]
    assert page.paused is False


def test_filter_setup_retry_attempts_allow_three_total_attempts() -> None:
    assert airbnb_search_screening.FILTER_SETUP_RETRY_ATTEMPTS == 2


def test_filter_setup_failed_result_records_noninteractive_skip() -> None:
    scenario = {
        "scenario_name": "broad_pool_weekend_first_visible_month",
        "trip_length": "Weekend",
        "filters_used": airbnb_search_screening.POOL_FILTERS,
    }

    result = airbnb_search_screening.scenario_filter_setup_failed_result(
        scenario,
        month_label="June 2026",
        max_pages=15,
        search_url="https://www.airbnb.com/s/Pocono-Mountains--PA/homes",
        error="Pool selector timed out",
    )

    assert result.found_status == "filter_setup_failed"
    assert result.pages_checked == 0
    assert result.filters_used == airbnb_search_screening.POOL_FILTERS
    assert result.scenario_started_from_clean_state is True
    assert result.prior_scenario_state_reused is False
    assert "Scenario was not scanned" in result.notes
    assert "Pool selector timed out" in result.notes


def test_scenario_failed_result_records_runtime_failure_without_losing_scenario() -> None:
    scenario = {
        "scenario_name": "broad_week_next_month",
        "trip_length": "Week",
    }

    result = airbnb_search_screening.scenario_failed_result(
        scenario,
        max_pages=15,
        search_url="https://www.airbnb.com",
        error="Week selector timed out",
    )

    assert result.found_status == "scenario_failed"
    assert result.pages_checked == 0
    assert result.scenario_name == "broad_week_next_month"
    assert result.filters_used == "none"
    assert "Week selector timed out" in result.notes


def test_absolute_position_calculation_in_found_result() -> None:
    result = airbnb_search_screening.scenario_found_result(
        {"scenario_name": "broad_pool_weekend_first_visible_month", "trip_length": "Weekend", "filters_used": "Pool"},
        month_label="June 2026",
        page_number=5,
        pages_checked=5,
        max_pages=15,
        result_count=17,
        search_url="https://www.airbnb.com/rooms/1313377469848413047",
        search_card_screenshot_path="search.png",
        listing_page_top_screenshot_path="top.png",
        visible_title="Pocono Spa Escape",
        cards_seen_before_match=72,
        position_on_page=4,
    )

    assert result.cards_seen_before_match == 72
    assert result.position_on_page == 4
    assert result.absolute_position == 76
    assert result.visible_cards_on_found_page == 17


def test_filtered_scenario_list_includes_required_progression() -> None:
    scenario_names = [scenario["scenario_name"] for scenario in airbnb_search_screening.FILTERED_SCENARIOS]

    assert scenario_names == [
        "broad_high_intent_filters_weekend_first_visible_month",
        "broad_pool_hot_tub_guest_favorite_weekend_first_visible_month",
        "broad_pool_hot_tub_weekend_first_visible_month",
        "broad_pool_weekend_first_visible_month",
    ]
    assert not any("map" in name for name in scenario_names)


def test_scenario_sequence_appends_filtered_scenarios_only_when_requested() -> None:
    default_names = [scenario["scenario_name"] for scenario in airbnb_search_screening.scenario_sequence(2, False)]
    filtered_names = [scenario["scenario_name"] for scenario in airbnb_search_screening.scenario_sequence(2, True)]
    filtered_only_names = [
        scenario["scenario_name"]
        for scenario in airbnb_search_screening.scenario_sequence(2, True, filtered_only=True)
    ]

    assert default_names == ["broad_weekend_first_visible_month", "broad_week_next_month"]
    assert filtered_names == [
        "broad_weekend_first_visible_month",
        "broad_week_next_month",
        "broad_high_intent_filters_weekend_first_visible_month",
        "broad_pool_hot_tub_guest_favorite_weekend_first_visible_month",
        "broad_pool_hot_tub_weekend_first_visible_month",
        "broad_pool_weekend_first_visible_month",
    ]
    assert filtered_only_names == [
        "broad_high_intent_filters_weekend_first_visible_month",
        "broad_pool_hot_tub_guest_favorite_weekend_first_visible_month",
        "broad_pool_hot_tub_weekend_first_visible_month",
        "broad_pool_weekend_first_visible_month",
    ]


def test_writes_csv_output_with_one_found_scenario(tmp_path: Path) -> None:
    csv_path, md_path = airbnb_search_screening.write_outputs(
        RUN_DATE,
        [found_result()],
        run_dir=tmp_path / "data" / "runs" / RUN_DATE,
        generated_at="2026-06-01T00:00:00+00:00",
    )

    rows = read_csv(csv_path)

    assert csv_path == tmp_path / "data" / "runs" / RUN_DATE / "analysis" / f"airbnb_search_screening_{RUN_DATE}.csv"
    assert md_path == tmp_path / "data" / "runs" / RUN_DATE / "analysis" / f"airbnb_search_screening_{RUN_DATE}.md"
    assert rows[0]["scenario_name"] == "broad_weekend_first_visible_month"
    assert rows[0]["found_status"] == "found"
    assert rows[0]["page_number"] == "4"
    assert rows[0]["cards_seen_before_match"] == "54"
    assert rows[0]["position_on_page"] == "3"
    assert rows[0]["absolute_position"] == "57"
    assert rows[0]["visible_cards_on_found_page"] == "18"
    assert rows[0]["scenario_isolation_mode"] == "fresh_browser_context"
    assert rows[0]["scenario_started_from_clean_state"] == "true"
    assert rows[0]["scenario_start_url"] == "https://www.airbnb.com"
    assert rows[0]["filters_applied_for_scenario"] == "none"
    assert rows[0]["prior_scenario_state_reused"] == "false"
    assert rows[0]["search_card_screenshot_path"].endswith("search.png")


def test_writes_csv_output_with_first_not_found_and_second_found(tmp_path: Path) -> None:
    results = [
        not_found_result("broad_weekend_first_visible_month", month_label="June 2026", trip_length="Weekend"),
        found_result("broad_week_next_month", month_label="July 2026", trip_length="Week"),
    ]

    csv_path, md_path = airbnb_search_screening.write_outputs(
        RUN_DATE,
        results,
        run_dir=tmp_path / "run",
        generated_at="2026-06-01T00:00:00+00:00",
    )
    rows = read_csv(csv_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert [row["found_status"] for row in rows] == ["not_found", "found"]
    assert rows[1]["scenario_name"] == "broad_week_next_month"
    assert "Second scenario status: found on page 4" in markdown


def test_writes_filtered_scenario_row_and_markdown_section(tmp_path: Path) -> None:
    results = [
        not_found_result("broad_weekend_first_visible_month", month_label="June 2026", trip_length="Weekend"),
        found_result(
            "broad_high_intent_filters_weekend_first_visible_month",
            month_label="June 2026",
            trip_length="Weekend",
            filters_used=airbnb_search_screening.HIGH_INTENT_FILTERS,
        ),
    ]

    csv_path, md_path = airbnb_search_screening.write_outputs(
        RUN_DATE,
        results,
        run_dir=tmp_path / "run",
        generated_at="2026-06-01T00:00:00+00:00",
    )
    rows = read_csv(csv_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert rows[1]["scenario_name"] == "broad_high_intent_filters_weekend_first_visible_month"
    assert rows[1]["filters_used"] == airbnb_search_screening.HIGH_INTENT_FILTERS
    assert "## Filtered Scenario Results" in markdown
    assert "High-intent filtered status: found on page 4" in markdown
    assert "absolute position 57" in markdown
    assert "Pool; Hot tub; Guest Favorite; Instant Book; Self check-in" in markdown
    assert "High-intent filtered screening found the listing on page 4 at absolute position 57." in markdown
    assert "Absolute position is the preferred benchmark because Airbnb page sizes can vary." in markdown


def test_filtered_only_markdown_omits_broad_not_run_summary() -> None:
    rows = [
        airbnb_search_screening.result_to_row(
            found_result(
                "broad_high_intent_filters_weekend_first_visible_month",
                filters_used=airbnb_search_screening.HIGH_INTENT_FILTERS,
            ),
            run_date=RUN_DATE,
            generated_at="2026-06-01T00:00:00+00:00",
            search_location="Pocono Mountains, PA",
        )
    ]

    markdown = airbnb_search_screening.render_markdown(RUN_DATE, rows)

    assert "Filtered-only debug run: broad no-filter scenarios were intentionally skipped." in markdown
    assert "First scenario status: not run" not in markdown


def test_markdown_omits_filtered_section_when_no_filtered_rows() -> None:
    rows = [
        airbnb_search_screening.result_to_row(
            found_result(),
            run_date=RUN_DATE,
            generated_at="2026-06-01T00:00:00+00:00",
            search_location="Pocono Mountains, PA",
        )
    ]

    markdown = airbnb_search_screening.render_markdown(RUN_DATE, rows)

    assert "## Filtered Scenario Results" not in markdown
    assert "Filtered high-intent status" not in markdown


def test_writes_csv_output_with_both_scenarios_not_found(tmp_path: Path) -> None:
    results = [
        not_found_result("broad_weekend_first_visible_month", month_label="June 2026", trip_length="Weekend"),
        not_found_result(
            "broad_week_next_month",
            month_label="July 2026",
            trip_length="Week",
            not_found_screenshot_path="data/runs/2026-06-01/downloads_staging/not_found.png",
        ),
    ]

    csv_path, md_path = airbnb_search_screening.write_outputs(
        RUN_DATE,
        results,
        run_dir=tmp_path / "run",
        generated_at="2026-06-01T00:00:00+00:00",
    )
    rows = read_csv(csv_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert [row["found_status"] for row in rows] == ["not_found", "not_found"]
    assert rows[1]["not_found_screenshot_path"].endswith("not_found.png")
    assert "Listing not found after 30 total pages checked." in markdown


def test_markdown_report_includes_executive_summary_and_screenshot_paths() -> None:
    rows = [
        airbnb_search_screening.result_to_row(
            found_result(),
            run_date=RUN_DATE,
            generated_at="2026-06-01T00:00:00+00:00",
            search_location="Pocono Mountains, PA",
        )
    ]

    markdown = airbnb_search_screening.render_markdown(RUN_DATE, rows)

    assert "## Executive Summary" in markdown
    assert "## Screenshot Evidence" in markdown
    assert "Each scenario was run from a fresh browser context and clean Airbnb search URL" in markdown
    assert "Final verification: all scenarios completed cleanly." in markdown
    assert "search.png" in markdown
    assert "Airbnb broad screening found the listing" in markdown


def test_markdown_report_flags_filter_setup_failures() -> None:
    result = airbnb_search_screening.scenario_filter_setup_failed_result(
        {
            "scenario_name": "broad_high_intent_filters_weekend_first_visible_month",
            "trip_length": "Weekend",
            "filters_used": airbnb_search_screening.HIGH_INTENT_FILTERS,
        },
        month_label="June 2026",
        max_pages=15,
        search_url="https://www.airbnb.com",
    )
    rows = [
        airbnb_search_screening.result_to_row(
            result,
            run_date=RUN_DATE,
            generated_at="2026-06-01T00:00:00+00:00",
            search_location="Pocono Mountains, PA",
        )
    ]

    markdown = airbnb_search_screening.render_markdown(RUN_DATE, rows)

    assert "Final verification: scenario setup failed for broad_high_intent_filters_weekend_first_visible_month." in markdown
    assert "filter_setup_failed" in markdown


def test_missing_optional_fields_do_not_fail(tmp_path: Path) -> None:
    result = airbnb_search_screening.ScreeningResult(
        scenario_name="broad_weekend_first_visible_month",
        month_label="June 2026",
        trip_length="Weekend",
        found_status="not_found",
        pages_checked=15,
        max_pages_checked=15,
    )

    csv_path, _ = airbnb_search_screening.write_outputs(
        RUN_DATE,
        [result],
        run_dir=tmp_path / "run",
        generated_at="2026-06-01T00:00:00+00:00",
    )
    row = read_csv(csv_path)[0]

    assert row["visible_price"] == ""
    assert row["search_card_screenshot_path"] == ""


def test_csv_columns_match_contract(tmp_path: Path) -> None:
    csv_path, _ = airbnb_search_screening.write_outputs(
        RUN_DATE,
        [found_result()],
        run_dir=tmp_path / "run",
        generated_at="2026-06-01T00:00:00+00:00",
    )

    with csv_path.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        columns = next(reader)

    assert columns == airbnb_search_screening.COLUMNS
