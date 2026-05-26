import json
from datetime import date

import pytest

from airbnb import download_diagnostics


RUN_DATE = "2026-05-20"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_dry_run_creates_staging_folder(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    manifest_path = download_diagnostics.run(RUN_DATE, run_dir=run_dir)

    assert manifest_path.parent == run_dir / "downloads_staging" / "airbnb"
    assert manifest_path.parent.exists()


def test_dry_run_writes_manifest_with_expected_files(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    manifest_path = download_diagnostics.run(RUN_DATE, run_dir=run_dir)
    manifest = read_json(manifest_path)

    assert manifest["run_date"] == RUN_DATE
    assert manifest["mode"] == "dry-run"
    assert manifest["status"] == "dry_run"
    assert manifest["expected_files"] == download_diagnostics.EXPECTED_FILES
    assert manifest["downloaded_files"] == []
    assert manifest["missing_files"] == download_diagnostics.EXPECTED_FILES
    assert manifest["promoted_files"] == []


def test_parse_args_rejects_unsupported_mode() -> None:
    with pytest.raises(SystemExit):
        download_diagnostics.parse_args(["--run-date", RUN_DATE, "--mode", "download-all"])


def test_run_rejects_unsupported_mode() -> None:
    with pytest.raises(ValueError, match="unsupported mode"):
        download_diagnostics.run(RUN_DATE, mode="download-all")


def test_dry_run_creates_no_raw_files(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    download_diagnostics.run(RUN_DATE, run_dir=run_dir)

    assert not (run_dir / "raw").exists()
    assert list((run_dir / "downloads_staging" / "airbnb").glob("*.html")) == []


def test_dry_run_does_not_reference_pipeline_or_secrets(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    manifest = read_json(download_diagnostics.run(RUN_DATE, run_dir=run_dir))
    text = json.dumps(manifest).lower()

    assert "run_weekly_pipeline" not in text
    assert "cookie" in text
    assert "token" in text
    assert "credential" in text
    assert "browser state" in text
    assert "password" not in text


def test_production_downloader_does_not_reference_sensitive_codegen_file() -> None:
    source = download_diagnostics.Path(download_diagnostics.__file__).read_text(encoding="utf-8").lower()

    assert "codegen" not in source


def test_capture_target_list_has_exactly_expected_files() -> None:
    assert [target.filename for target in download_diagnostics.CAPTURE_TARGETS] == download_diagnostics.EXPECTED_FILES
    assert len(download_diagnostics.CAPTURE_TARGETS) == 6


def test_capture_target_metadata_maps_metrics_and_compare_modes() -> None:
    metadata = {
        target.filename: (target.metric_link_name, target.expected_metric_text, target.compare_value)
        for target in download_diagnostics.CAPTURE_TARGETS
    }

    assert metadata == {
        "airbnb_booking_conversion_daily.html": ("Booking conversion", "Booking conversion", "YOY"),
        "airbnb_page_views_daily.html": ("Views", "Views", "YOY"),
        "airbnb_wishlist_additions_daily.html": ("Wishlist additions", "Wishlist additions", "YOY"),
        "airbnb_booking_conversion_similar.html": ("Booking conversion", "Booking conversion", "MARKET"),
        "airbnb_page_views_similar.html": ("Views", "Views", "MARKET"),
        "airbnb_wishlist_additions_similar.html": ("Wishlist additions", "Wishlist additions", "MARKET"),
    }


def test_calculate_airbnb_reporting_window_returns_previous_completed_sunday_window() -> None:
    assert download_diagnostics.calculate_airbnb_reporting_window(date(2026, 5, 25)) == (date(2026, 5, 17), date(2026, 5, 24))
    assert download_diagnostics.calculate_airbnb_reporting_window(date(2026, 5, 27)) == (date(2026, 5, 17), date(2026, 5, 24))
    assert download_diagnostics.calculate_airbnb_reporting_window(date(2026, 5, 24)) == (date(2026, 5, 17), date(2026, 5, 24))


def test_format_airbnb_date_input_uses_month_day_year() -> None:
    assert download_diagnostics.format_airbnb_date_input(date(2026, 5, 17)) == "05/17/2026"


def valid_html_for(filename: str) -> str:
    if "booking_conversion" in filename and "similar" in filename:
        body = "Airbnb performance insights Booking conversion Similar listings Your listings 1.2% Similar listings 0.4%"
    elif "page_views" in filename and "similar" in filename:
        body = "Airbnb performance insights Page views Similar listings Your listings 176 Similar listings 140"
    elif "wishlist_additions" in filename and "similar" in filename:
        body = "Airbnb performance insights Wishlist additions Similar listings Your listings 28 Similar listings 21"
    elif "booking_conversion" in filename:
        body = "Airbnb performance insights Booking conversion Average overall conversion rate Search-to-listing Listing-to-booking"
    elif "page_views" in filename:
        body = "Airbnb performance insights Average page views First-page search impressions"
    else:
        body = "Airbnb performance insights Average wishlist additions Wishlist additions"
    return f"<html><body>{body}</body></html>"


def write_all_valid_staged_files(run_dir) -> None:
    staging = run_dir / "downloads_staging" / "airbnb"
    staging.mkdir(parents=True, exist_ok=True)
    for filename in download_diagnostics.EXPECTED_FILES:
        (staging / filename).write_text(valid_html_for(filename), encoding="utf-8")


def file_status(manifest: dict, filename: str) -> str:
    return next(entry["validation_status"] for entry in manifest["files"] if entry["filename"] == filename)


def test_validate_staged_all_valid_files_sets_valid_status(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert manifest["mode"] == "validate-staged"
    assert manifest["status"] == "valid_staged"
    assert len(manifest["downloaded_files"]) == len(download_diagnostics.EXPECTED_FILES)
    assert all(entry["validation_status"] == "valid" for entry in manifest["files"])
    assert not (run_dir / "raw").exists()


def test_validate_staged_some_missing_files_sets_partial_status(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    missing = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_similar.html"
    missing.unlink()

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert manifest["status"] == "partial_staged"
    assert "airbnb_page_views_similar.html" in manifest["missing_files"]
    assert file_status(manifest, "airbnb_page_views_similar.html") == "missing"
    assert not (run_dir / "raw").exists()


def test_validate_staged_empty_file_status(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    target = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_daily.html"
    target.write_text("", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert manifest["status"] == "partial_staged"
    assert file_status(manifest, "airbnb_page_views_daily.html") == "empty"


def test_validate_staged_non_html_file_status(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    target = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_daily.html"
    target.write_text("not html", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert file_status(manifest, "airbnb_page_views_daily.html") == "not_html"


def test_validate_staged_login_page_status(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    target = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_daily.html"
    target.write_text("<html><body>Airbnb Log in Email Password</body></html>", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert file_status(manifest, "airbnb_page_views_daily.html") == "login_page"


def test_validate_staged_performance_indicators_override_generic_login_text(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    target = run_dir / "downloads_staging" / "airbnb" / "airbnb_booking_conversion_daily.html"
    target.write_text(
        "<html><body>Airbnb Booking conversion dsSelector performance shell email password</body></html>",
        encoding="utf-8",
    )

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert file_status(manifest, "airbnb_booking_conversion_daily.html") == "valid"


def test_validate_staged_booking_conversion_and_dsselector_are_valid(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    target = run_dir / "downloads_staging" / "airbnb" / "airbnb_booking_conversion_daily.html"
    target.write_text("<html><body>Airbnb Booking conversion dsSelector</body></html>", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert file_status(manifest, "airbnb_booking_conversion_daily.html") == "valid"


def test_validate_staged_error_page_status(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    target = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_daily.html"
    target.write_text("<html><body>Airbnb access denied error 403</body></html>", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert file_status(manifest, "airbnb_page_views_daily.html") == "error_page"


def test_validate_staged_unknown_airbnb_content_status(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    target = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_daily.html"
    target.write_text("<html><body>Airbnb account settings profile page</body></html>", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir))

    assert file_status(manifest, "airbnb_page_views_daily.html") == "unknown_airbnb_content"


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector

    @property
    def first(self) -> "FakeLocator":
        return self

    def click(self, timeout=None) -> None:
        if self.page.fail_date_selector and (
            self.selector == download_diagnostics.DATE_RANGE_SELECTOR or self.selector.startswith("role:button:")
        ):
            raise RuntimeError("date selector unavailable")
        self.page.clicked_selectors.append(self.selector)
        if self.selector == download_diagnostics.CONVERSION_LINK_SELECTOR:
            self.page.url = download_diagnostics.AIRBNB_CONVERSION_URL

    def fill(self, value, timeout=None) -> None:
        self.page.filled_inputs.append((self.selector, value))
        if not self.page.fill_does_not_update:
            self.page.input_values[self.selector] = value

    def type(self, value, timeout=None) -> None:
        self.page.typed_inputs.append((self.selector, value))
        if not self.page.type_does_not_update:
            self.page.input_values[self.selector] = value

    def press(self, key, timeout=None) -> None:
        self.page.pressed_keys.append((self.selector, key))
        if key in {"Backspace", "Delete"}:
            self.page.input_values[self.selector] = ""

    def evaluate(self, script, value):
        self.page.evaluated_inputs.append((self.selector, value))
        if not self.page.dom_events_do_not_update:
            self.page.input_values[self.selector] = value

    def select_option(self, value, timeout=None) -> None:
        self.page.selected_options.append((self.selector, value))

    def input_value(self, timeout=None):
        if self.selector in self.page.input_values:
            return self.page.input_values[self.selector]
        for selector, value in reversed(self.page.selected_options):
            if selector == self.selector:
                return value
        return ""

    def inner_text(self, timeout=None):
        return self.page.visible_text

    def wait_for(self, state=None, timeout=None) -> None:
        if self.page.fail_performance_indicator:
            raise RuntimeError("performance indicator unavailable")
        self.page.waited_selectors.append(self.selector)


class FakePage:
    def __init__(
        self,
        fail_date_selector: bool = False,
        fail_performance_indicator: bool = False,
        url: str = "",
        goto_error: str = "",
        goto_final_url: str = "",
        visible_text: str = "Airbnb Performance Booking conversion Page views Wishlist additions May 10 May 17",
        fill_does_not_update: bool = False,
        type_does_not_update: bool = False,
        dom_events_do_not_update: bool = False,
    ) -> None:
        self.counter = 0
        self.fail_date_selector = fail_date_selector
        self.fail_performance_indicator = fail_performance_indicator
        self.url = url or download_diagnostics.AIRBNB_CONVERSION_URL
        self.goto_error = goto_error
        self.goto_final_url = goto_final_url
        self.visible_text = visible_text
        self.fill_does_not_update = fill_does_not_update
        self.type_does_not_update = type_does_not_update
        self.dom_events_do_not_update = dom_events_do_not_update
        self.goto_urls: list[str] = []
        self.clicked_selectors: list[str] = []
        self.filled_inputs: list[tuple[str, str]] = []
        self.typed_inputs: list[tuple[str, str]] = []
        self.evaluated_inputs: list[tuple[str, str]] = []
        self.pressed_keys: list[tuple[str, str]] = []
        self.input_values: dict[str, str] = {}
        self.selected_options: list[tuple[str, str]] = []
        self.load_states: list[str] = []
        self.waited_selectors: list[str] = []
        self.pause_count = 0

    def goto(self, url: str) -> None:
        self.goto_urls.append(url)
        if self.goto_error:
            self.url = self.goto_final_url
            raise RuntimeError(self.goto_error)
        self.url = url
        if "ds-start=-8" in url and "ds-end=-1" in url:
            self.visible_text = "Airbnb Performance Booking conversion Page views Wishlist additions May 17 May 24"

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def get_by_role(self, role: str, name: str) -> FakeLocator:
        if role == "textbox" and name == "START DATE":
            return FakeLocator(self, download_diagnostics.START_DATE_INPUT_SELECTOR)
        if role == "textbox" and name == "END DATE":
            return FakeLocator(self, download_diagnostics.END_DATE_INPUT_SELECTOR)
        return FakeLocator(self, f"role:{role}:{name}")

    def get_by_label(self, name: str) -> FakeLocator:
        if name == "Compare":
            return FakeLocator(self, download_diagnostics.COMPARE_SELECTOR)
        return FakeLocator(self, f"label:{name}")

    def get_by_test_id(self, test_id: str) -> FakeLocator:
        if test_id == "dsDropdownApply":
            return FakeLocator(self, download_diagnostics.DATE_RANGE_APPLY_SELECTOR)
        return FakeLocator(self, f"testid:{test_id}")

    def wait_for_load_state(self, state: str, timeout=None) -> None:
        self.load_states.append(state)

    def pause(self) -> None:
        self.pause_count += 1

    def content(self) -> str:
        self.counter += 1
        return f"<html><body>Airbnb performance insights captured page {self.counter}</body></html>"


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakePlaywright:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def install_fake_capture(
    monkeypatch,
    fail_date_selector: bool = False,
    fail_performance_indicator: bool = False,
    url: str = "",
    visible_text: str = "Airbnb Performance Booking conversion Page views Wishlist additions May 10 May 17",
    fill_does_not_update: bool = False,
    type_does_not_update: bool = False,
    dom_events_do_not_update: bool = False,
):
    fake_playwright = FakePlaywright()
    fake_page = FakePage(
        fail_date_selector=fail_date_selector,
        fail_performance_indicator=fail_performance_indicator,
        url=url,
        visible_text=visible_text,
        fill_does_not_update=fill_does_not_update,
        type_does_not_update=type_does_not_update,
        dom_events_do_not_update=dom_events_do_not_update,
    )
    fake_browser = FakeBrowser(fake_page)
    prompts: list[str] = []

    monkeypatch.setattr(
        download_diagnostics,
        "launch_headed_browser",
        lambda: (fake_playwright, fake_browser, fake_page),
    )
    monkeypatch.setattr(
        download_diagnostics,
        "prompt_user",
        lambda message: prompts.append(message) or "",
    )
    return fake_playwright, fake_browser, fake_page, prompts


def test_ensure_airbnb_conversion_page_skips_goto_when_already_on_conversion_url() -> None:
    page = FakePage(url=download_diagnostics.AIRBNB_CONVERSION_URL)

    ok, error = download_diagnostics.ensure_airbnb_conversion_page(page)

    assert ok is True
    assert error == ""
    assert page.goto_urls == []


def test_safe_goto_treats_interrupted_navigation_as_success_when_final_url_matches() -> None:
    page = FakePage(
        goto_error='Page.goto: Navigation to "https://www.airbnb.com/performance/conversion/conversion_rate" is interrupted by another navigation',
        goto_final_url=download_diagnostics.AIRBNB_CONVERSION_URL,
    )

    ok, error = download_diagnostics.safe_goto(page, download_diagnostics.AIRBNB_CONVERSION_URL)

    assert ok is True
    assert error == ""


def test_safe_goto_returns_failure_when_interrupted_navigation_ends_on_wrong_url() -> None:
    page = FakePage(
        goto_error='Page.goto: Navigation to "https://www.airbnb.com/performance/conversion/conversion_rate" is interrupted by another navigation',
        goto_final_url="https://www.airbnb.com/login",
    )

    ok, error = download_diagnostics.safe_goto(page, download_diagnostics.AIRBNB_CONVERSION_URL)

    assert ok is False
    assert "interrupted by another navigation" in error


def test_views_and_wishlist_conversion_urls_are_accepted() -> None:
    assert download_diagnostics.is_airbnb_conversion_url("https://www.airbnb.com/performance/conversion/p3_impressions")
    assert download_diagnostics.is_airbnb_conversion_url("https://www.airbnb.com/performance/conversion/wishlist")


def test_capture_headed_writes_only_allowed_staged_filenames(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    _playwright, browser, page, prompts = install_fake_capture(monkeypatch)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    staged_files = sorted(path.name for path in (run_dir / "downloads_staging" / "airbnb").glob("*.html"))
    assert staged_files == sorted(download_diagnostics.EXPECTED_FILES)
    assert sorted(manifest["captured_files"]) == sorted(download_diagnostics.EXPECTED_FILES)
    assert manifest["status"] == "captured_all"
    assert manifest["conversion_url"] == download_diagnostics.AIRBNB_CONVERSION_URL
    assert manifest["reporting_window_start"] == "2026-05-10"
    assert manifest["reporting_window_end"] == "2026-05-17"
    assert manifest["requested_start_date"] == "2026-05-10"
    assert manifest["requested_end_date"] == "2026-05-17"
    assert manifest["requested_start_date_input"] == "05/10/2026"
    assert manifest["requested_end_date_input"] == "05/17/2026"
    assert manifest["date_range_automation_status"] == "applied"
    assert manifest["report_controls_ready"] is True
    assert all(result["capture_status"] == "captured" for result in manifest["capture_results"])
    assert all(result["metric_assertion_status"] == "passed" for result in manifest["capture_results"])
    assert all(result["date_range_assertion_status"] == "passed_visible_short_format" for result in manifest["capture_results"])
    assert all(result["compare_assertion_status"] == "passed" for result in manifest["capture_results"])
    assert page.goto_urls in ([], [download_diagnostics.AIRBNB_CONVERSION_URL])
    assert page.pause_count == 0
    assert download_diagnostics.COMPARE_SELECTOR in page.waited_selectors
    assert download_diagnostics.DATE_RANGE_SELECTOR in page.waited_selectors
    assert 'text="Booking conversion"' in page.waited_selectors
    assert download_diagnostics.DATE_RANGE_SELECTOR in page.clicked_selectors
    assert download_diagnostics.DATE_RANGE_APPLY_SELECTOR in page.clicked_selectors
    assert (download_diagnostics.START_DATE_INPUT_SELECTOR, "05/10/2026") in page.filled_inputs
    assert (download_diagnostics.END_DATE_INPUT_SELECTOR, "05/17/2026") in page.filled_inputs
    assert browser.closed is True
    assert len(prompts) == 1
    assert not (run_dir / "raw").exists()


def test_capture_headed_does_not_write_html_when_performance_page_not_confirmed(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    _playwright, browser, _page, prompts = install_fake_capture(monkeypatch, fail_performance_indicator=True)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["status"] == "auth_required"
    assert manifest["performance_page_confirmed"] is False
    assert manifest["report_controls_ready"] is False
    assert manifest["captured_files"] == []
    assert manifest["missing_files"] == download_diagnostics.EXPECTED_FILES
    assert list((run_dir / "downloads_staging" / "airbnb").glob("*.html")) == []
    assert len(prompts) == 2
    assert browser.closed is True
    assert not (run_dir / "raw").exists()


def test_capture_headed_blocks_when_visible_date_text_is_missing(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    install_fake_capture(monkeypatch, visible_text="Airbnb Performance Booking conversion Page views Wishlist additions")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["status"] == "capture_failed"
    assert manifest["date_range_automation_status"] == "failed"
    assert all(result["capture_status"] == "skipped_not_ready" for result in manifest["capture_results"])
    assert all(result["date_range_assertion_status"] == "failed_visible_range_mismatch" for result in manifest["capture_results"])
    assert list((run_dir / "downloads_staging" / "airbnb").glob("*.html")) == []
    assert not (run_dir / "raw").exists()


def test_capture_headed_blocks_when_visible_date_text_is_wrong_even_after_apply(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    install_fake_capture(monkeypatch, visible_text="Airbnb Performance Booking conversion Page views Wishlist additions Apr 25 May 25")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["status"] == "capture_failed"
    assert manifest["date_range_automation_status"] == "failed"
    assert manifest["visible_date_text_after_apply"] == "Airbnb Performance Booking conversion Page views Wishlist additions Apr 25 May 25"
    assert all(result["capture_status"] == "skipped_not_ready" for result in manifest["capture_results"])
    assert all(result["date_range_assertion_status"] == "failed_visible_range_mismatch" for result in manifest["capture_results"])
    assert all("Apr 25" in result["assertion_error"] for result in manifest["capture_results"])
    assert list((run_dir / "downloads_staging" / "airbnb").glob("*.html")) == []
    assert not (run_dir / "raw").exists()


def test_capture_headed_does_not_write_file_when_metric_assertion_fails(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    install_fake_capture(monkeypatch)

    monkeypatch.setattr(download_diagnostics, "assert_airbnb_metric_ready", lambda _page, _metric_name: (False, "metric missing"))

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["status"] == "capture_failed"
    assert all(result["capture_status"] == "skipped_not_ready" for result in manifest["capture_results"])
    assert all(result["metric_assertion_status"] == "failed" for result in manifest["capture_results"])
    assert list((run_dir / "downloads_staging" / "airbnb").glob("*.html")) == []
    assert not (run_dir / "raw").exists()


def test_capture_headed_does_not_write_file_when_compare_assertion_fails(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    install_fake_capture(monkeypatch)

    monkeypatch.setattr(download_diagnostics, "assert_airbnb_compare_mode", lambda _page, _compare_value: (False, "compare mismatch"))

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["status"] == "capture_failed"
    assert all(result["capture_status"] == "skipped_not_ready" for result in manifest["capture_results"])
    assert all(result["compare_assertion_status"] == "failed" for result in manifest["capture_results"])
    assert list((run_dir / "downloads_staging" / "airbnb").glob("*.html")) == []
    assert not (run_dir / "raw").exists()


def test_capture_headed_partial_capture_when_some_assertions_fail(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    install_fake_capture(monkeypatch)

    def fail_page_views(_page, metric_name):
        if metric_name == "Views":
            return False, "page views not visible"
        return True, ""

    monkeypatch.setattr(download_diagnostics, "assert_airbnb_metric_ready", fail_page_views)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["status"] == "partial_capture"
    assert len(manifest["captured_files"]) == 4
    assert [result["capture_status"] for result in manifest["capture_results"]].count("skipped_not_ready") == 2
    staged_files = sorted(path.name for path in (run_dir / "downloads_staging" / "airbnb").glob("*.html"))
    assert staged_files == sorted(
        [
            "airbnb_booking_conversion_daily.html",
            "airbnb_wishlist_additions_daily.html",
            "airbnb_booking_conversion_similar.html",
            "airbnb_wishlist_additions_similar.html",
        ]
    )
    assert not (run_dir / "raw").exists()


def test_capture_headed_manifest_records_skipped_not_ready_when_report_controls_fail_after_confirmation(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    _playwright, browser, page, _prompts = install_fake_capture(monkeypatch)

    def not_ready(_page, _target, _start_date, _end_date):
        return {
            "metric_navigation_status": "passed",
            "metric_assertion_status": "passed",
            "date_range_assertion_status": "failed",
            "compare_assertion_status": "passed",
            "report_ready_before_capture": False,
            "assertion_error": "report controls disappeared",
        }

    monkeypatch.setattr(download_diagnostics, "assert_airbnb_capture_ready", not_ready)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["status"] == "capture_failed"
    assert manifest["status"] != "captured_all"
    assert manifest["captured_files"] == []
    assert len(manifest["capture_results"]) == 6
    assert all(result["capture_status"] == "skipped_not_ready" for result in manifest["capture_results"])
    assert all(result["report_ready_before_capture"] is False for result in manifest["capture_results"])
    assert list((run_dir / "downloads_staging" / "airbnb").glob("*.html")) == []
    assert browser.closed is True
    assert page.selected_options
    assert not (run_dir / "raw").exists()


def test_capture_headed_selects_compare_values_for_each_capture_group(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    _playwright, _browser, page, _prompts = install_fake_capture(monkeypatch)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    selected_values = [value for _selector, value in page.selected_options]
    assert selected_values == ["YOY", "YOY", "YOY", "MARKET", "MARKET", "MARKET"]
    assert all(selector == download_diagnostics.COMPARE_SELECTOR for selector, _value in page.selected_options)
    assert manifest["captured_files"] == download_diagnostics.EXPECTED_FILES


def test_capture_headed_records_failed_date_range_automation(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    install_fake_capture(monkeypatch, fail_date_selector=True)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir))

    assert manifest["date_range_automation_status"] == "failed"
    assert "date_range_automation_error" in manifest
    assert manifest["requested_start_date_input"] == "05/10/2026"
    assert manifest["requested_end_date_input"] == "05/17/2026"
    assert manifest["status"] == "capture_failed"
    assert manifest["captured_files"] == []


def test_set_airbnb_reporting_window_uses_known_date_selectors() -> None:
    page = FakePage(visible_text="Airbnb Performance Booking conversion May 17 May 24")

    details = download_diagnostics.set_airbnb_reporting_window(page, date(2026, 5, 17), date(2026, 5, 24), date(2026, 5, 25))

    assert details["date_range_automation_status"] == "applied"
    assert details["date_range_automation_error"] == ""
    assert details["date_input_strategy_used"] == "fill_clear"
    assert details["start_input_value_after_set"] == "05/17/2026"
    assert details["end_input_value_after_set"] == "05/24/2026"
    assert details["apply_clicked"] is True
    assert page.clicked_selectors[0] == download_diagnostics.DATE_RANGE_SELECTOR
    assert page.clicked_selectors[-1] == download_diagnostics.DATE_RANGE_APPLY_SELECTOR
    assert page.filled_inputs == [
        (download_diagnostics.START_DATE_INPUT_SELECTOR, "05/17/2026"),
        (download_diagnostics.END_DATE_INPUT_SELECTOR, "05/24/2026"),
    ]
    assert (download_diagnostics.START_DATE_INPUT_SELECTOR, "ControlOrMeta+A") in page.pressed_keys
    assert (download_diagnostics.START_DATE_INPUT_SELECTOR, "Backspace") in page.pressed_keys
    assert (download_diagnostics.END_DATE_INPUT_SELECTOR, "ControlOrMeta+A") in page.pressed_keys
    assert (download_diagnostics.END_DATE_INPUT_SELECTOR, "Backspace") in page.pressed_keys


def test_set_airbnb_reporting_window_falls_back_to_type_clear() -> None:
    page = FakePage(visible_text="Airbnb Performance Booking conversion May 17 May 24", fill_does_not_update=True)

    details = download_diagnostics.set_airbnb_reporting_window(page, date(2026, 5, 17), date(2026, 5, 24), date(2026, 5, 25))

    assert details["date_range_automation_status"] == "applied"
    assert details["date_input_strategy_used"] == "type_clear"
    assert (download_diagnostics.START_DATE_INPUT_SELECTOR, "05/17/2026") in page.typed_inputs
    assert (download_diagnostics.END_DATE_INPUT_SELECTOR, "05/24/2026") in page.typed_inputs


def test_set_airbnb_reporting_window_falls_back_to_dom_events() -> None:
    page = FakePage(
        visible_text="Airbnb Performance Booking conversion May 17 May 24",
        fill_does_not_update=True,
        type_does_not_update=True,
    )

    details = download_diagnostics.set_airbnb_reporting_window(page, date(2026, 5, 17), date(2026, 5, 24), date(2026, 5, 25))

    assert details["date_range_automation_status"] == "applied"
    assert details["date_input_strategy_used"] == "dom_events"
    assert (download_diagnostics.START_DATE_INPUT_SELECTOR, "05/17/2026") in page.evaluated_inputs
    assert (download_diagnostics.END_DATE_INPUT_SELECTOR, "05/24/2026") in page.evaluated_inputs


def test_set_airbnb_reporting_window_fails_when_input_values_cannot_be_confirmed() -> None:
    page = FakePage(fill_does_not_update=True, type_does_not_update=True, dom_events_do_not_update=True)

    details = download_diagnostics.set_airbnb_reporting_window(page, date(2026, 5, 17), date(2026, 5, 24), date(2026, 5, 25))

    assert details["date_range_automation_status"] == "failed"
    assert details["date_input_strategy_used"] == "failed"
    assert details["apply_clicked"] is False


def test_airbnb_date_query_url_uses_run_date_relative_offsets() -> None:
    url = download_diagnostics.airbnb_date_query_url(
        "https://www.airbnb.com/performance/conversion/conversion_rate?ds-start=-30&ds-end=0",
        date(2026, 5, 17),
        date(2026, 5, 24),
        date(2026, 5, 25),
    )

    assert "ds-start=-8" in url
    assert "ds-end=-1" in url


def test_set_airbnb_reporting_window_uses_query_fallback_when_visible_range_does_not_update() -> None:
    page = FakePage(visible_text="Airbnb Performance Booking conversion Apr 25 May 25")

    details = download_diagnostics.set_airbnb_reporting_window(page, date(2026, 5, 17), date(2026, 5, 24), date(2026, 5, 25))

    assert details["date_range_automation_status"] == "applied_url_query"
    assert "ds-start=-8" in details["date_query_fallback_url"]
    assert "ds-end=-1" in details["date_query_fallback_url"]
    assert details["visible_date_text_after_apply"] == "Airbnb Performance Booking conversion Page views Wishlist additions May 17 May 24"


def test_capture_headed_playwright_unavailable_fails_clearly(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    def fail_launch():
        raise RuntimeError("Playwright is required for Airbnb capture modes.")

    monkeypatch.setattr(download_diagnostics, "launch_headed_browser", fail_launch)

    with pytest.raises(RuntimeError, match="Playwright is required"):
        download_diagnostics.run(RUN_DATE, mode="capture-headed", run_dir=run_dir)

    assert not (run_dir / "raw").exists()


def test_capture_headed_and_validate_runs_validation_after_capture(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    install_fake_capture(monkeypatch)

    def write_valid_html(_page, output_path):
        output_path.write_text(valid_html_for(output_path.name), encoding="utf-8")

    monkeypatch.setattr(download_diagnostics, "capture_page_html", write_valid_html)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="capture-headed-and-validate", run_dir=run_dir))

    assert manifest["mode"] == "capture-headed-and-validate"
    assert manifest["status"] == "captured_all"
    assert manifest["validation_summary"]["status"] == "valid_staged"
    assert len(manifest["validation_summary"]["valid_files"]) == 6
    assert all(entry["validation_status"] == "valid" for entry in manifest["files"])
    assert not (run_dir / "raw").exists()


def test_promote_staged_copies_valid_files_to_raw(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir))

    assert manifest["mode"] == "promote-staged"
    assert manifest["status"] == "promoted_all_valid"
    assert sorted(manifest["promoted_files"]) == sorted(download_diagnostics.EXPECTED_FILES)
    for filename in download_diagnostics.EXPECTED_FILES:
        assert (run_dir / "raw" / filename).exists()
        assert file_status(manifest, filename) == "valid"
        entry = next(item for item in manifest["files"] if item["filename"] == filename)
        assert entry["promotion_status"] == "promoted"
        assert entry["raw_target_path"].endswith(str(run_dir / "raw" / filename))


def test_promote_staged_does_not_copy_invalid_files(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    invalid = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_daily.html"
    invalid.write_text("<html><body>Airbnb Log in Email Password</body></html>", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir))

    assert manifest["status"] == "promoted_all_valid"
    assert "airbnb_page_views_daily.html" not in manifest["promoted_files"]
    assert not (run_dir / "raw" / "airbnb_page_views_daily.html").exists()
    skipped = next(item for item in manifest["skipped_files"] if item["filename"] == "airbnb_page_views_daily.html")
    assert skipped["reason"] == "login_page"


def test_promote_staged_does_not_overwrite_existing_raw_files(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    existing = run_dir / "raw" / "airbnb_page_views_daily.html"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("trusted existing raw", encoding="utf-8")

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir))

    assert existing.read_text(encoding="utf-8") == "trusted existing raw"
    assert "airbnb_page_views_daily.html" not in manifest["promoted_files"]
    skipped = next(item for item in manifest["skipped_files"] if item["filename"] == "airbnb_page_views_daily.html")
    assert skipped["reason"] == "skipped_existing"
    entry = next(item for item in manifest["files"] if item["filename"] == "airbnb_page_views_daily.html")
    assert entry["promotion_status"] == "skipped_existing"


def test_promote_staged_records_nothing_promoted_when_no_valid_files(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir))

    assert manifest["status"] == "nothing_promoted"
    assert manifest["promoted_files"] == []
    assert not (run_dir / "raw").exists()


def test_promote_staged_does_not_reference_browser_or_pipeline_behavior(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir))
    text = json.dumps(manifest).lower()

    assert "run_weekly_pipeline" not in text
    assert "browser was opened" in text
    assert "cookies" in text
    assert "tokens" in text
    assert "credentials" in text
    assert "password" not in text


def write_airbnb_diagnostic_output(run_dir) -> None:
    analysis_dir = run_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / f"airbnb_conversion_diagnostic_report_{RUN_DATE}.md").write_text("# Airbnb Report\n", encoding="utf-8")


def test_cleanup_staging_deletes_only_staged_html_after_successful_promotion_and_diagnostics(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    staging = run_dir / "downloads_staging" / "airbnb"
    manifest_path = download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir)
    write_airbnb_diagnostic_output(run_dir)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="cleanup-staging", run_dir=run_dir))

    assert manifest_path.exists()
    assert manifest["mode"] == "cleanup-staging"
    assert manifest["status"] == "cleanup_complete"
    assert sorted(manifest["deleted_files"]) == sorted(download_diagnostics.EXPECTED_FILES)
    assert list(staging.glob("airbnb_*.html")) == []
    for filename in download_diagnostics.EXPECTED_FILES:
        assert (run_dir / "raw" / filename).exists()
    assert (run_dir / "analysis" / f"airbnb_conversion_diagnostic_report_{RUN_DATE}.md").exists()


def test_cleanup_staging_keeps_manifest_file(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir)
    write_airbnb_diagnostic_output(run_dir)

    manifest_path = download_diagnostics.run(RUN_DATE, mode="cleanup-staging", run_dir=run_dir)

    assert manifest_path.exists()
    assert read_json(manifest_path)["status"] == "cleanup_complete"


def test_cleanup_staging_does_nothing_if_validation_or_promotion_failed(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    download_diagnostics.run(RUN_DATE, mode="validate-staged", run_dir=run_dir)
    write_airbnb_diagnostic_output(run_dir)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="cleanup-staging", run_dir=run_dir))

    assert manifest["status"] == "cleanup_skipped"
    assert manifest["promotion_succeeded"] is False
    for filename in download_diagnostics.EXPECTED_FILES:
        assert (run_dir / "downloads_staging" / "airbnb" / filename).exists()


def test_cleanup_staging_does_nothing_after_partial_promotion(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    invalid = run_dir / "downloads_staging" / "airbnb" / "airbnb_page_views_daily.html"
    invalid.write_text("<html><body>Airbnb Log in Email Password</body></html>", encoding="utf-8")
    promote_manifest = read_json(download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir))
    write_airbnb_diagnostic_output(run_dir)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="cleanup-staging", run_dir=run_dir))

    assert promote_manifest["status"] == "promoted_all_valid"
    assert "airbnb_page_views_daily.html" not in promote_manifest["promoted_files"]
    assert manifest["status"] == "cleanup_skipped"
    assert manifest["promotion_succeeded"] is False
    for filename in download_diagnostics.EXPECTED_FILES:
        assert (run_dir / "downloads_staging" / "airbnb" / filename).exists()


def test_cleanup_staging_does_nothing_if_diagnostics_missing(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir)

    manifest = read_json(download_diagnostics.run(RUN_DATE, mode="cleanup-staging", run_dir=run_dir))

    assert manifest["status"] == "cleanup_skipped"
    assert manifest["diagnostics_succeeded"] is False
    for filename in download_diagnostics.EXPECTED_FILES:
        assert (run_dir / "downloads_staging" / "airbnb" / filename).exists()


def test_cleanup_staging_does_not_delete_raw_or_analysis_outputs(tmp_path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_all_valid_staged_files(run_dir)
    download_diagnostics.run(RUN_DATE, mode="promote-staged", run_dir=run_dir)
    write_airbnb_diagnostic_output(run_dir)
    raw_file = run_dir / "raw" / "airbnb_page_views_daily.html"
    analysis_file = run_dir / "analysis" / f"airbnb_conversion_diagnostic_report_{RUN_DATE}.md"

    download_diagnostics.run(RUN_DATE, mode="cleanup-staging", run_dir=run_dir)

    assert raw_file.exists()
    assert analysis_file.exists()
