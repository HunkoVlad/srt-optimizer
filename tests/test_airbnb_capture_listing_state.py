import json
from pathlib import Path

from airbnb import capture_listing_state


RUN_DATE = "2026-06-01"
EXTRA_GUEST_CONTEXT = (
    "Search uses 8 guests. Extra guest pricing may apply above 6 guests, so visible Airbnb prices may reflect "
    "target group pricing rather than base guest pricing."
)


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def staged_file(run_dir: Path, filename: str) -> Path:
    return run_dir / "downloads_staging" / "airbnb_listing_state" / filename


def analysis_file(run_dir: Path, filename: str) -> Path:
    return run_dir / "analysis" / filename


def write_png(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * size)


class FakePage:
    def __init__(self, content: bytes = b"\x89PNG\r\n\x1a\nfake screenshot") -> None:
        self.content = content
        self.screenshots: list[dict[str, object]] = []

    def screenshot(self, **kwargs) -> None:
        self.screenshots.append(kwargs)
        Path(str(kwargs["path"])).write_bytes(self.content)


class FakeBrowser:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakePlaywright:
    def __init__(self) -> None:
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


def test_dry_run_creates_staging_folder_and_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    manifest_path = capture_listing_state.run(RUN_DATE, "dry-run", run_dir=run_dir)
    manifest = read_manifest(manifest_path)

    assert manifest_path.exists()
    assert manifest_path.parent == run_dir / "downloads_staging" / "airbnb_listing_state"
    assert manifest["status"] == "dry_run"
    assert manifest["search_card_status"] == "not_checked"
    assert manifest["listing_page_top_status"] == "not_checked"


def test_manifest_contains_fixed_search_settings(tmp_path: Path) -> None:
    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "dry-run", run_dir=tmp_path / "run"))

    assert manifest["search_location"] == "Pocono Mountains, PA"
    assert manifest["guest_count"] == 8
    assert manifest["base_guest_count_included"] == 6
    assert manifest["target_visual_search_guest_count"] == 8
    assert manifest["date_rule"] == "flexible_weekend_next_target_month"
    assert manifest["filters"] == "none"
    assert manifest["browser_size"] == "1440x1000"
    assert manifest["extra_guest_pricing_context"] == EXTRA_GUEST_CONTEXT


def test_validate_manifest_includes_extra_guest_pricing_context(tmp_path: Path) -> None:
    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "validate-staged", run_dir=tmp_path / "run"))

    assert manifest["guest_count"] == 8
    assert manifest["date_rule"] == "flexible_weekend_next_target_month"
    assert manifest["extra_guest_pricing_context"] == EXTRA_GUEST_CONTEXT


def test_promote_manifest_includes_extra_guest_pricing_context(tmp_path: Path) -> None:
    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "promote-staged", run_dir=tmp_path / "run"))

    assert manifest["guest_count"] == 8
    assert manifest["date_rule"] == "flexible_weekend_next_target_month"
    assert manifest["extra_guest_pricing_context"] == EXTRA_GUEST_CONTEXT


def test_validate_staged_marks_missing_files_without_failing(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE

    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "validate-staged", run_dir=run_dir))
    statuses = {result["filename"]: result["status"] for result in manifest["validation_results"]}

    assert manifest["status"] == "no_valid_staged_files"
    assert statuses[f"listing_search_card_{RUN_DATE}.png"] == "missing"
    assert statuses[f"listing_page_top_{RUN_DATE}.png"] == "missing"


def test_validate_staged_marks_valid_png_files_as_valid(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_png(staged_file(run_dir, f"listing_search_card_{RUN_DATE}.png"), 12_000)
    write_png(staged_file(run_dir, f"listing_page_top_{RUN_DATE}.png"), 12_000)

    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "validate-staged", run_dir=run_dir))

    assert manifest["status"] == "valid_staged"
    assert manifest["search_card_status"] == "valid"
    assert manifest["listing_page_top_status"] == "valid"


def test_validate_staged_marks_tiny_png_files_as_too_small(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_png(staged_file(run_dir, f"listing_search_card_{RUN_DATE}.png"), 100)

    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "validate-staged", run_dir=run_dir))
    statuses = {result["filename"]: result["status"] for result in manifest["validation_results"]}

    assert statuses[f"listing_search_card_{RUN_DATE}.png"] == "too_small"
    assert statuses[f"listing_page_top_{RUN_DATE}.png"] == "missing"


def test_promote_staged_copies_valid_png_files_to_analysis(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    search_name = f"listing_search_card_{RUN_DATE}.png"
    top_name = f"listing_page_top_{RUN_DATE}.png"
    write_png(staged_file(run_dir, search_name), 12_000)
    write_png(staged_file(run_dir, top_name), 12_000)

    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "promote-staged", run_dir=run_dir))

    assert manifest["status"] == "promoted_all_valid"
    assert analysis_file(run_dir, search_name).exists()
    assert analysis_file(run_dir, top_name).exists()
    assert len(manifest["promoted_files"]) == 2


def test_promote_staged_does_not_overwrite_existing_analysis_files_by_default(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    filename = f"listing_search_card_{RUN_DATE}.png"
    write_png(staged_file(run_dir, filename), 12_000)
    existing = analysis_file(run_dir, filename)
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"existing")

    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "promote-staged", run_dir=run_dir))

    assert existing.read_bytes() == b"existing"
    assert {"filename": filename, "reason": "skipped_existing"} in manifest["skipped_files"]


def test_promote_staged_missing_or_invalid_files_do_not_fail_promotion(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    write_png(staged_file(run_dir, f"listing_search_card_{RUN_DATE}.png"), 100)

    manifest = read_manifest(capture_listing_state.run(RUN_DATE, "promote-staged", run_dir=run_dir))

    assert manifest["status"] == "nothing_promoted"
    assert manifest["promoted_files"] == []
    assert len(manifest["skipped_files"]) == 2


def test_capture_viewport_screenshot_writes_only_requested_png(tmp_path: Path) -> None:
    page = FakePage()
    output = tmp_path / "listing_search_card.png"

    capture_listing_state.capture_viewport_screenshot(page, output)

    assert output.exists()
    assert page.screenshots == [{"path": str(output), "full_page": False}]


def test_capture_headed_uses_manual_prompts_and_writes_staged_screenshots(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    fake_playwright = FakePlaywright()
    fake_browser = FakeBrowser()
    fake_page = FakePage()
    prompts: list[str] = []

    def fake_launch():
        return fake_playwright, fake_browser, fake_page

    def fake_prompt(message: str) -> str:
        prompts.append(message)
        return ""

    manifest_path = capture_listing_state.run_capture_headed(
        RUN_DATE,
        run_dir,
        launch_browser=fake_launch,
        prompt=fake_prompt,
    )
    manifest = read_manifest(manifest_path)

    assert manifest["status"] == "captured_all"
    assert manifest["mode"] == "capture-headed"
    assert manifest["manual_confirmation_required"] is True
    assert manifest["search_card_status"] == "captured"
    assert manifest["listing_page_top_status"] == "captured"
    assert len(manifest["captured_files"]) == 2
    assert staged_file(run_dir, f"listing_search_card_{RUN_DATE}.png").exists()
    assert staged_file(run_dir, f"listing_page_top_{RUN_DATE}.png").exists()
    assert len(prompts) == 2
    assert "search results page" in prompts[0]
    assert "listing page" in prompts[1]
    assert fake_browser.closed is True
    assert fake_playwright.stopped is True
