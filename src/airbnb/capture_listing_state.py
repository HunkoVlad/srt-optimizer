"""Staging skeleton for Airbnb listing visual baseline capture."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import sys


SEARCH_LOCATION = "Pocono Mountains, PA"
BASE_GUEST_COUNT_INCLUDED = 6
TARGET_VISUAL_SEARCH_GUEST_COUNT = 8
GUEST_COUNT = TARGET_VISUAL_SEARCH_GUEST_COUNT
DATE_RULE = "flexible_weekend_next_target_month"
FILTERS = "none"
BROWSER_SIZE = "1440x1000"
AIRBNB_SEARCH_URL = "https://www.airbnb.com/s/Pocono-Mountains--PA/homes?adults=8"
MIN_PNG_SIZE_BYTES = 10 * 1024
SUPPORTED_MODES = {"dry-run", "validate-staged", "promote-staged", "capture-headed"}
EXTRA_GUEST_PRICING_CONTEXT = (
    "Search uses 8 guests. Extra guest pricing may apply above 6 guests, so visible Airbnb prices may reflect "
    "target group pricing rather than base guest pricing."
)


@dataclass(frozen=True)
class VisualTarget:
    key: str
    filename_template: str


VISUAL_TARGETS = (
    VisualTarget("search_card", "listing_search_card_{run_date}.png"),
    VisualTarget("listing_page_top", "listing_page_top_{run_date}.png"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare Airbnb listing visual baseline capture artifacts.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--mode", required=True, choices=sorted(SUPPORTED_MODES))
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--overwrite", action="store_true", help="Allow promote-staged to overwrite existing analysis PNGs.")
    return parser.parse_args(argv)


def staging_dir(run_dir: Path) -> Path:
    return run_dir / "downloads_staging" / "airbnb_listing_state"


def analysis_dir(run_dir: Path) -> Path:
    return run_dir / "analysis"


def target_filename(target: VisualTarget, run_date: str) -> str:
    return target.filename_template.format(run_date=run_date)


def base_manifest(run_date: str, mode: str, run_dir: Path) -> dict[str, object]:
    return {
        "run_date": run_date,
        "mode": mode,
        "status": "",
        "search_location": SEARCH_LOCATION,
        "guest_count": GUEST_COUNT,
        "base_guest_count_included": BASE_GUEST_COUNT_INCLUDED,
        "target_visual_search_guest_count": TARGET_VISUAL_SEARCH_GUEST_COUNT,
        "date_rule": DATE_RULE,
        "filters": FILTERS,
        "browser_size": BROWSER_SIZE,
        "extra_guest_pricing_context": EXTRA_GUEST_PRICING_CONTEXT,
        "staging_dir": str(staging_dir(run_dir)),
        "analysis_dir": str(analysis_dir(run_dir)),
        "search_card_status": "not_checked",
        "listing_page_top_status": "not_checked",
        "validation_results": [],
        "captured_files": [],
        "capture_results": [],
        "manual_confirmation_required": False,
        "promoted_files": [],
        "skipped_files": [],
        "errors": [],
        "generated_at": datetime.now(UTC).isoformat(),
    }


def manifest_path(run_date: str, run_dir: Path) -> Path:
    return staging_dir(run_dir) / f"listing_capture_manifest_{run_date}.json"


def write_manifest(manifest: dict[str, object], run_date: str, run_dir: Path) -> Path:
    path = manifest_path(run_date, run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def validate_png(path: Path) -> tuple[str, list[str]]:
    errors: list[str] = []
    if path.suffix.lower() != ".png":
        return "invalid_extension", ["expected .png extension"]
    if not path.exists():
        return "missing", ["file is missing"]
    size = path.stat().st_size
    if size <= MIN_PNG_SIZE_BYTES:
        errors.append(f"file size {size} is not greater than {MIN_PNG_SIZE_BYTES} bytes")
        return "too_small", errors
    return "valid", []


def validate_staged_files(run_date: str, run_dir: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for target in VISUAL_TARGETS:
        filename = target_filename(target, run_date)
        path = staging_dir(run_dir) / filename
        status, errors = validate_png(path)
        result = {
            "target": target.key,
            "filename": filename,
            "path": str(path),
            "status": status,
            "exists": path.exists(),
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "errors": errors,
        }
        results.append(result)
        manifest[f"{target.key}_status"] = status
    manifest["validation_results"] = results
    return results


def run_dry_run(run_date: str, run_dir: Path) -> Path:
    staging_dir(run_dir).mkdir(parents=True, exist_ok=True)
    manifest = base_manifest(run_date, "dry-run", run_dir)
    manifest["status"] = "dry_run"
    return write_manifest(manifest, run_date, run_dir)


def run_validate_staged(run_date: str, run_dir: Path) -> Path:
    staging_dir(run_dir).mkdir(parents=True, exist_ok=True)
    manifest = base_manifest(run_date, "validate-staged", run_dir)
    results = validate_staged_files(run_date, run_dir, manifest)
    if all(result["status"] == "valid" for result in results):
        manifest["status"] = "valid_staged"
    elif any(result["status"] == "valid" for result in results):
        manifest["status"] = "partial_staged"
    else:
        manifest["status"] = "no_valid_staged_files"
    return write_manifest(manifest, run_date, run_dir)


def run_promote_staged(run_date: str, run_dir: Path, *, overwrite: bool = False) -> Path:
    staging_dir(run_dir).mkdir(parents=True, exist_ok=True)
    analysis_dir(run_dir).mkdir(parents=True, exist_ok=True)
    manifest = base_manifest(run_date, "promote-staged", run_dir)
    results = validate_staged_files(run_date, run_dir, manifest)
    promoted_files: list[str] = []
    skipped_files: list[dict[str, str]] = []

    for result in results:
        filename = str(result["filename"])
        source = staging_dir(run_dir) / filename
        destination = analysis_dir(run_dir) / filename
        if result["status"] != "valid":
            skipped_files.append({"filename": filename, "reason": str(result["status"])})
            continue
        if destination.exists() and not overwrite:
            skipped_files.append({"filename": filename, "reason": "skipped_existing"})
            continue
        shutil.copy2(source, destination)
        promoted_files.append(str(destination))

    manifest["promoted_files"] = promoted_files
    manifest["skipped_files"] = skipped_files
    if promoted_files and len(promoted_files) == len(VISUAL_TARGETS):
        manifest["status"] = "promoted_all_valid"
    elif promoted_files:
        manifest["status"] = "promoted_partial"
    else:
        manifest["status"] = "nothing_promoted"
    return write_manifest(manifest, run_date, run_dir)


def browser_viewport() -> dict[str, int]:
    width, height = BROWSER_SIZE.lower().split("x", 1)
    return {"width": int(width), "height": int(height)}


def launch_headed_browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for capture-headed. Install Playwright before using this mode.") from exc

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(viewport=browser_viewport())
    page = context.new_page()
    try:
        page.goto(AIRBNB_SEARCH_URL, wait_until="domcontentloaded", timeout=15000)
    except Exception:
        pass
    return playwright, browser, page


def close_headed_browser(playwright, browser) -> None:
    try:
        browser.close()
    finally:
        playwright.stop()


def prompt_user(message: str) -> str:
    return input(message)


def capture_viewport_screenshot(page, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(output_path), full_page=False)


def capture_target(page, run_date: str, run_dir: Path, target: VisualTarget) -> dict[str, object]:
    filename = target_filename(target, run_date)
    output_path = staging_dir(run_dir) / filename
    try:
        capture_viewport_screenshot(page, output_path)
        exists = output_path.exists()
        size_bytes = output_path.stat().st_size if exists else 0
        status = "captured" if exists and size_bytes > 0 else "failed"
        return {
            "target": target.key,
            "filename": filename,
            "path": str(output_path),
            "status": status,
            "exists": exists,
            "size_bytes": size_bytes,
            "error": "",
        }
    except Exception as exc:
        return {
            "target": target.key,
            "filename": filename,
            "path": str(output_path),
            "status": "failed",
            "exists": output_path.exists(),
            "size_bytes": output_path.stat().st_size if output_path.exists() else 0,
            "error": str(exc),
        }


def run_capture_headed(
    run_date: str,
    run_dir: Path,
    *,
    launch_browser=launch_headed_browser,
    prompt=prompt_user,
) -> Path:
    staging_dir(run_dir).mkdir(parents=True, exist_ok=True)
    manifest = base_manifest(run_date, "capture-headed", run_dir)
    manifest["manual_confirmation_required"] = True
    manifest["airbnb_search_url"] = AIRBNB_SEARCH_URL
    captured_files: list[str] = []
    capture_results: list[dict[str, object]] = []
    playwright = browser = page = None
    try:
        playwright, browser, page = launch_browser()
        prompt(
            "Please log in to Airbnb if needed, then navigate to the search results page for "
            "Pocono Mountains, PA with Flexible dates, Weekend, next target month, 8 guests, no filters, "
            "and browser size 1440x1000. Press Enter when the target listing search card is visible."
        )
        search_result = capture_target(page, run_date, run_dir, VISUAL_TARGETS[0])
        capture_results.append(search_result)
        manifest["search_card_status"] = search_result["status"]
        if search_result["status"] == "captured":
            captured_files.append(str(search_result["path"]))

        prompt(
            "Please open the Aloha Poconos listing page and position the page top so the title, hero grid, "
            "trust signals, and booking widget are visible if possible. Press Enter when ready."
        )
        top_result = capture_target(page, run_date, run_dir, VISUAL_TARGETS[1])
        capture_results.append(top_result)
        manifest["listing_page_top_status"] = top_result["status"]
        if top_result["status"] == "captured":
            captured_files.append(str(top_result["path"]))
    except Exception as exc:
        manifest["errors"] = [str(exc)]
    finally:
        if playwright is not None and browser is not None:
            close_headed_browser(playwright, browser)

    manifest["captured_files"] = captured_files
    manifest["capture_results"] = capture_results
    if len(captured_files) == len(VISUAL_TARGETS):
        manifest["status"] = "captured_all"
    elif captured_files:
        manifest["status"] = "partial_capture"
    else:
        manifest["status"] = "capture_failed"
    return write_manifest(manifest, run_date, run_dir)


def run(run_date: str, mode: str, *, run_dir: Path | None = None, overwrite: bool = False) -> Path:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    resolved_run_dir = run_dir or Path("data") / "runs" / run_date
    if mode == "dry-run":
        return run_dry_run(run_date, resolved_run_dir)
    if mode == "validate-staged":
        return run_validate_staged(run_date, resolved_run_dir)
    if mode == "promote-staged":
        return run_promote_staged(run_date, resolved_run_dir, overwrite=overwrite)
    return run_capture_headed(run_date, resolved_run_dir)


def main() -> int:
    args = parse_args()
    output = run(
        args.run_date,
        args.mode,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        overwrite=args.overwrite,
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
