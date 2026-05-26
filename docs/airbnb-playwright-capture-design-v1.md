# Airbnb Playwright Capture Design v1

## Purpose

This document designs the first browser-assisted Airbnb diagnostic capture flow. It does not implement automation.

Airbnb remains optional and diagnostic-only. It may provide visibility, conversion, and similar-listing context, but it must not become the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, or monthly revenue pace.

The capture flow should populate:

```text
data/runs/<run_date>/downloads_staging/airbnb/
```

Expected staged files:

- `airbnb_booking_conversion_daily.html`
- `airbnb_page_views_daily.html`
- `airbnb_wishlist_additions_daily.html`
- `airbnb_booking_conversion_similar.html`
- `airbnb_page_views_similar.html`
- `airbnb_wishlist_additions_similar.html`

## Current Safe Flow

Existing safe commands:

```powershell
python -m airbnb.download_diagnostics --run-date <run_date> --mode dry-run
python -m airbnb.download_diagnostics --run-date <run_date> --mode validate-staged
python -m airbnb.download_diagnostics --run-date <run_date> --mode promote-staged
python -m airbnb.run_diagnostics --run-date <run_date>
```

The future browser capture should only add files into staging. Validation, promotion, and parsing should remain separate and explicit at first.

## Proposed Browser Flow

First implementation should be headed/manual-login only.

Recommended flow:

1. Launch headed Playwright browser.
2. Open Airbnb host performance/insights area.
3. Print:
   `Please log in to Airbnb manually in the opened browser. Complete MFA if required. When you can see the Airbnb performance/insights area for Aloha Poconos, return to this terminal and press Enter.`
4. After Enter, keep the same browser session open.
5. For each capture target:
   - navigate or ask the user to navigate to the correct Airbnb report state
   - wait for user confirmation
   - validate visible page state lightly
   - save current page HTML into `downloads_staging/airbnb/<target_filename>`
   - run immediate staged-file validation for that file or the full staged set
6. After all targets are attempted, write/update `airbnb_download_manifest_<run_date>.json`.
7. Run `validate-staged` automatically in `capture-headed-and-validate` mode, or leave validation as the next manual command in `capture-headed` mode.
8. Do not promote to raw automatically.

## Capture Targets

### Over-Time / Previous-Week Mode

These pages compare the selected week to previous 7 days or retained over-time context.

| Target file | Airbnb report state | Expected page hints |
| --- | --- | --- |
| `airbnb_booking_conversion_daily.html` | Booking conversion, Over time / previous week | booking conversion, average overall conversion rate, search-to-listing, listing-to-booking |
| `airbnb_page_views_daily.html` | Page views, Over time / previous week | page views, first-page search impressions |
| `airbnb_wishlist_additions_daily.html` | Wishlist additions, Over time / previous week | wishlist additions |

### Similar-Listings Mode

These pages compare the listing to similar listings. The page must contain actual paired benchmark values, not only a dropdown option.

| Target file | Airbnb report state | Expected page hints |
| --- | --- | --- |
| `airbnb_booking_conversion_similar.html` | Booking conversion, Similar listings | Your listings or Your performance, Similar listings, conversion values |
| `airbnb_page_views_similar.html` | Page views, Similar listings | Your listings or Your performance, Similar listings, page-view values |
| `airbnb_wishlist_additions_similar.html` | Wishlist additions, Similar listings | Your listings or Your performance, Similar listings, wishlist values |

## User Confirmation Prompts

The first implementation should avoid brittle Airbnb UI automation. Use user-confirmed page states.

Recommended prompts:

1. Login checkpoint:
   `Please log in to Airbnb manually in the opened browser. Complete MFA if required. When you can see the Airbnb performance/insights area for Aloha Poconos, return to this terminal and press Enter.`

2. Over-time booking conversion:
   `Open the Airbnb Booking conversion performance page for Aloha Poconos. Set the date range to the target weekly range and choose Over time / previous-week comparison. When the page shows booking conversion metrics, return to this terminal and press Enter to capture airbnb_booking_conversion_daily.html.`

3. Over-time page views:
   `Open the Airbnb Page views performance page for Aloha Poconos. Keep the same weekly date range and Over time / previous-week comparison. When page views and first-page search impressions are visible, return to this terminal and press Enter to capture airbnb_page_views_daily.html.`

4. Over-time wishlist additions:
   `Open the Airbnb Wishlist additions performance page for Aloha Poconos. Keep the same weekly date range and Over time / previous-week comparison. When wishlist additions are visible, return to this terminal and press Enter to capture airbnb_wishlist_additions_daily.html.`

5. Similar-listing booking conversion:
   `Switch Booking conversion to Similar listings comparison. Confirm the page shows actual Your listings / Similar listings values, not just a dropdown option. Return to this terminal and press Enter to capture airbnb_booking_conversion_similar.html.`

6. Similar-listing page views:
   `Switch Page views to Similar listings comparison. Confirm actual Your listings / Similar listings values are visible. Return to this terminal and press Enter to capture airbnb_page_views_similar.html.`

7. Similar-listing wishlist additions:
   `Switch Wishlist additions to Similar listings comparison. Confirm actual Your listings / Similar listings values are visible. Return to this terminal and press Enter to capture airbnb_wishlist_additions_similar.html.`

Each prompt should include the intended run date and target date range when available.

## File Naming

Captured HTML should be saved exactly as:

```text
data/runs/<run_date>/downloads_staging/airbnb/airbnb_booking_conversion_daily.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_page_views_daily.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_wishlist_additions_daily.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_booking_conversion_similar.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_page_views_similar.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_wishlist_additions_similar.html
```

Do not save screenshots, PDFs, HAR files, cookies, storage state, or unrelated page HTML.

## Validation After Capture

After each page capture, run conservative validation against the staged file.

Use existing validation statuses:

- `valid`
- `missing`
- `empty`
- `not_html`
- `login_page`
- `error_page`
- `unknown_airbnb_content`

For `capture-headed-and-validate`, run the equivalent of:

```powershell
python -m airbnb.download_diagnostics --run-date <run_date> --mode validate-staged
```

Validation should reject:

- login pages
- access denied or error pages
- empty files
- non-HTML files
- pages without Airbnb diagnostic hints
- similar-listing pages without actual Your listings / Similar listings paired values
- wrong listing or wrong date range once listing/date checks are implemented

## Failure Behavior

Airbnb capture failure must be non-blocking.

If any capture fails:

- leave successfully captured staged files in `downloads_staging/airbnb/`
- write manifest with partial status
- do not promote to raw
- do not run parsing automatically unless explicitly requested
- do not fail the PriceLabs weekly pipeline
- tell the user which target files are missing or invalid

Promotion should remain a separate explicit command:

```powershell
python -m airbnb.download_diagnostics --run-date <run_date> --mode promote-staged
```

## Security And Privacy Rules

Do not store:

- Airbnb username or password
- cookies
- tokens
- browser local/session storage
- MFA codes
- browser profile
- screenshots
- HAR/network captures
- unrelated account pages

Do not log:

- credentials
- cookies
- tokens
- full page HTML
- private account data

Only save the six expected diagnostic HTML files into the run's staging folder. Raw HTML should be temporary and should be cleaned by the existing parser after successful parsing/promotion flow.

## Future CLI Modes

Suggested modes for `airbnb.download_diagnostics`:

```powershell
python -m airbnb.download_diagnostics --run-date <run_date> --mode capture-headed
python -m airbnb.download_diagnostics --run-date <run_date> --mode capture-headed-and-validate
```

Mode behavior:

- `capture-headed`
  - headed browser
  - manual login/MFA
  - user-confirmed captures
  - writes staged HTML
  - writes manifest
  - does not validate automatically unless per-file lightweight validation is trivial
  - does not promote

- `capture-headed-and-validate`
  - same as `capture-headed`
  - runs staged validation after capture
  - writes manifest with validation statuses
  - does not promote

Promotion remains:

```powershell
python -m airbnb.download_diagnostics --run-date <run_date> --mode promote-staged
```

Parsing remains:

```powershell
python -m airbnb.run_diagnostics --run-date <run_date>
```

## Tests Needed

Future capture tests should mock Playwright and avoid real Airbnb login.

Suggested tests:

- `capture-headed` accepts the mode but uses headed browser only.
- login checkpoint text is printed.
- each target prompt includes filename and diagnostic mode.
- page content is saved to the correct staging filename.
- no raw files are created during capture.
- no screenshots, cookies, tokens, browser state, or credentials are written.
- `capture-headed-and-validate` runs staged validation after capture.
- partial capture writes manifest with missing targets.
- login page capture is marked invalid by validation.
- similar-listing dropdown-only page is rejected.
- promotion remains separate and explicit.

## Risks And Unknowns

- Airbnb UI labels and navigation may change.
- Airbnb may require MFA every run.
- The report pages may use client-rendered content that is not fully represented in static page HTML.
- Similar-listing mode may be visually present but lack extractable paired values.
- Date-range controls may be hard to automate reliably.
- Captured HTML may contain private account context; retention should be short and limited to run folders.
- Headless mode is not recommended for the first implementation.
