"""Open Airbnb in Playwright Inspector for recording search-screening steps.

This helper is intentionally separate from the weekly pipeline. It does not
scrape, save files, or promote artifacts. It only opens Airbnb in a headed
browser, waits for manual login if needed, and then pauses for Playwright
recording.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright


AIRBNB_URL = "https://www.airbnb.com"


def main() -> int:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            args=["--start-maximized"],
        )
        context = browser.new_context(no_viewport=True)
        page = context.new_page()

        page.goto(AIRBNB_URL, wait_until="domcontentloaded", timeout=30_000)

        input(
            "Log in to Airbnb manually if needed. When the Airbnb home/search page is ready, "
            "return to this terminal and press Enter to open Playwright Inspector."
        )

        print(
            "Opening Playwright Inspector now. Record the search-screening flow, "
            "then resume or close the browser when done."
        )
        page.pause()

        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
