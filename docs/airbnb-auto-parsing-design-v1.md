# Airbnb Auto Parsing Design v1

## Purpose

This document designs a future automated Airbnb diagnostic capture flow for the weekly pipeline. It does not implement automation.

Airbnb remains diagnostic only. Airbnb may feed visibility, conversion, similar-listing context, and investigation priority. Airbnb must not become the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, or monthly revenue pace.

## Current Airbnb Data Flow

The current Airbnb flow is manual-first and local-file based.

Existing modules:

- `src/airbnb/parse_conversion_html.py`
  - Reads locally saved over-time Airbnb HTML files from `raw/`.
  - Writes parsed extraction to `raw/airbnb_daily_conversion_parsed_<run_date>.csv`.
  - Deletes temporary over-time HTML only after successful parsing.
- `src/airbnb/summarize_conversion.py`
  - Reads the parsed raw extraction CSV.
  - Writes `analysis/airbnb_weekly_conversion_summary_<run_date>.csv`.
- `src/airbnb/extract_daily_wow.py`
  - Reads parsed daily chart values.
  - Writes `analysis/airbnb_daily_week_over_week_conversion_<run_date>.csv`.
- `src/airbnb/compare_daily_to_weekly_avg.py`
  - Writes `analysis/airbnb_daily_week_average_deviation_<run_date>.csv`.
- `src/airbnb/compare_weekly_history.py`
  - Reads retained historical weekly Airbnb summaries.
  - Writes `analysis/airbnb_weekly_history_comparison_<run_date>.csv`.
- `src/airbnb/compare_similar_listings.py`
  - Reads locally saved similar-listing Airbnb HTML files from `raw/`.
  - Writes `analysis/airbnb_similar_listing_summary_<run_date>.csv`.
  - Writes `analysis/airbnb_daily_similar_listing_comparison_<run_date>.csv`.
  - Deletes successfully parsed similar-listing HTML only after both outputs are safely written.
- `src/airbnb/report_conversion.py`
  - Writes `analysis/airbnb_conversion_diagnostic_report_<run_date>.md`.

Current source shape:

- Manual HTML files are saved into `data/runs/<run_date>/raw/`.
- The parsed extraction CSV is retained in `raw/`.
- Clean diagnostic outputs live in `analysis/`.
- The weekly combined signal reads:
  - `analysis/airbnb_weekly_history_comparison_<run_date>.csv`
  - `analysis/airbnb_similar_listing_summary_<run_date>.csv`

There is no Airbnb browser automation or downloader today. Existing data comes from manually saved Airbnb HTML files and retained prior run outputs.

## Required Airbnb Metrics

Allowed diagnostic metrics:

- page views
- first-page search impressions
- wishlist additions
- average overall conversion rate
- first-page search impression rate
- search-to-listing conversion rate
- listing-to-booking conversion rate
- similar-listing benchmark values
- previous-week changes
- daily week-over-week chart values

Forbidden performance-truth metrics:

- revenue
- ADR
- occupancy
- booked nights
- booking value
- booking totals
- cleaning count
- monthly revenue pace

## Candidate Source Pages

Future automation should capture the same source pages the current parser already understands.

Over-time / previous-week mode:

- booking conversion daily page
- page views daily page
- wishlist additions daily page

Similar-listings mode:

- booking conversion similar-listings page
- page views similar-listings page
- wishlist additions similar-listings page

The automation should save source-derived files only for these diagnostic pages. It should not collect reservations, payouts, guest messages, or revenue pages.

## Proposed Staging Paths

Use staging first:

```text
data/runs/<run_date>/downloads_staging/airbnb/
```

Expected staged over-time files:

```text
data/runs/<run_date>/downloads_staging/airbnb/airbnb_booking_conversion_daily.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_page_views_daily.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_wishlist_additions_daily.html
```

Expected staged similar-listing files:

```text
data/runs/<run_date>/downloads_staging/airbnb/airbnb_booking_conversion_similar.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_page_views_similar.html
data/runs/<run_date>/downloads_staging/airbnb/airbnb_wishlist_additions_similar.html
```

Optional staging manifest:

```text
data/runs/<run_date>/downloads_staging/airbnb/airbnb_staging_manifest_<run_date>.json
```

The staging manifest should record URL or page label, capture timestamp, target listing, selected date range, file size, validation status, and diagnostic mode. It must not store cookies, tokens, browser state, screenshots, credentials, or MFA details.

## Raw Promotion Paths

Only validated staged files should be promoted to `raw/`.

Promoted over-time files:

```text
data/runs/<run_date>/raw/airbnb_booking_conversion_daily.html
data/runs/<run_date>/raw/airbnb_page_views_daily.html
data/runs/<run_date>/raw/airbnb_wishlist_additions_daily.html
```

Promoted similar-listing files:

```text
data/runs/<run_date>/raw/airbnb_booking_conversion_similar.html
data/runs/<run_date>/raw/airbnb_page_views_similar.html
data/runs/<run_date>/raw/airbnb_wishlist_additions_similar.html
```

The existing parsers may then produce:

```text
data/runs/<run_date>/raw/airbnb_daily_conversion_parsed_<run_date>.csv
data/runs/<run_date>/analysis/airbnb_weekly_conversion_summary_<run_date>.csv
data/runs/<run_date>/analysis/airbnb_weekly_history_comparison_<run_date>.csv
data/runs/<run_date>/analysis/airbnb_similar_listing_summary_<run_date>.csv
data/runs/<run_date>/analysis/airbnb_daily_similar_listing_comparison_<run_date>.csv
```

Temporary HTML in `raw/` should still be deleted only after successful parsing, preserving the current cleanup rules.

## Validation Rules

Reject staged files when any of these are true:

- file is missing
- file is empty
- file is too small to plausibly be the report page
- file looks like an Airbnb login page
- file looks like an HTML error page or access-denied page
- file is for the wrong listing
- file does not contain the expected metric page labels
- file has the wrong diagnostic mode
- file has unsupported structure
- selected date range is not the intended Sunday-to-Sunday weekly range
- similar-listings file contains only a dropdown option but no actual similar-listing values
- parsed output would contain forbidden performance-truth fields

Minimum validation by file:

- over-time files must contain current-week and previous-week context, or be marked as incomplete/manual-review.
- similar-listing files must contain both `Your listings` or `Your performance` and `Similar listings` with actual comparable values.
- date range must be extractable and checked against expected weekly bounds.
- listing identity should match the configured Airbnb listing name or listing ID when available.

## Promotion Rules

Promotion from `downloads_staging/airbnb/` to `raw/` should be conservative:

- Do not overwrite existing raw Airbnb files by default.
- If raw Airbnb files already exist, stop with a clear message unless an explicit future `--force` or archive mode exists.
- Promote only validated files.
- Failed validation leaves staging files in place and leaves raw unchanged.
- Promotion may be partial by diagnostic mode only if clearly logged, but the preferred first implementation is all-or-nothing per mode:
  - over-time set all three files
  - similar-listing set all three files
- PriceLabs raw files must never be touched by Airbnb promotion.

## Failure Behavior

Automation failure should not break the weekly PriceLabs report.

If Airbnb capture fails:

- leave staged files for troubleshooting
- write a high-level log under `logs/`
- do not promote invalid files to raw
- do not touch PriceLabs raw files
- do not overwrite existing valid Airbnb parsed outputs
- allow the combined market/listing signal to run with missing Airbnb data and lower confidence

If Airbnb parsing fails after promotion:

- keep unparsed HTML in raw for manual debugging
- mark diagnostic outputs as missing, incomplete, or parser-review as appropriate
- do not make revenue or pricing conclusions from partial Airbnb data

## Manual Fallback

Manual fallback remains required.

If automation fails or Airbnb changes its UI, the operator can manually save the same six HTML files:

```text
airbnb_booking_conversion_daily.html
airbnb_page_views_daily.html
airbnb_wishlist_additions_daily.html
airbnb_booking_conversion_similar.html
airbnb_page_views_similar.html
airbnb_wishlist_additions_similar.html
```

Manual files should be placed into either:

- `downloads_staging/airbnb/` for validation and promotion, preferred for future workflow
- `raw/` for direct use by the current parser workflow

The existing parser chain should continue to support manual raw files.

## Security And Privacy Rules

Do not store or commit:

- Airbnb credentials
- cookies
- tokens
- local storage
- browser state
- MFA codes
- screenshots containing private account information
- raw HTML outside the run folder

Future automation should prefer local-only credentials only if explicitly requested and gitignored, following the PriceLabs pattern. Persistent browser session storage should be avoided unless proven safe and gitignored. Logs must not include credential values, cookies, tokens, or page HTML.

## Recommended Automation Approach

Use a new Airbnb-specific downloader module rather than mixing Airbnb into the PriceLabs downloader:

```text
src/airbnb/download_diagnostics.py
```

Suggested CLI:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m airbnb.download_diagnostics --run-date YYYY-MM-DD
```

Potential modes:

- `--capture-over-time`
- `--capture-similar-listings`
- `--download-all`
- `--promote-to-raw`
- `--headless`
- `--use-local-credentials`, only if explicitly designed later

Preferred weekly automation sequence:

1. Capture Airbnb diagnostic pages into `downloads_staging/airbnb/`.
2. Validate staged Airbnb files.
3. Promote validated files into `raw/`.
4. Run existing Airbnb parsers:
   - `airbnb.parse_conversion_html`
   - `airbnb.summarize_conversion`
   - `airbnb.extract_daily_wow`
   - `airbnb.compare_daily_to_weekly_avg`
   - `airbnb.compare_weekly_history`
   - `airbnb.compare_similar_listings`
   - `airbnb.report_conversion`
5. Run combined market/listing signal.

PriceLabs pipeline should remain able to run without Airbnb automation.

## Pipeline Integration Design

Future pipeline should treat Airbnb as optional diagnostic input.

Recommended integration points:

1. Optional Airbnb capture wrapper before `run_weekly_pipeline.ps1`.
2. Airbnb parse/summary steps inside weekly pipeline only if raw Airbnb files or parsed Airbnb source files exist.
3. Combined market/listing signal reads Airbnb analysis outputs if present.
4. Missing Airbnb outputs result in lower diagnostic confidence, not pipeline failure.

Do not make Airbnb files required for scheduled pipeline preflight.

## Tests Needed Later

Downloader/staging tests:

- staging folder is created under `downloads_staging/airbnb/`
- valid over-time HTML is staged and validated
- valid similar-listing HTML is staged and validated
- login page is rejected
- HTML error page is rejected
- empty file is rejected
- wrong listing is rejected
- wrong date range is rejected or warned according to policy
- unsupported structure is rejected
- raw files are not overwritten by default
- PriceLabs raw files are never touched
- secrets, cookies, tokens, screenshots, and browser state are not written

Promotion tests:

- validated staged files promote to raw
- invalid staged files leave raw unchanged
- partial mode failure is logged clearly
- manual files in staging can be promoted

Parser integration tests:

- promoted over-time HTML feeds existing parser chain
- promoted similar-listing HTML feeds existing similar-listing parser
- temporary raw HTML cleanup still occurs only after successful parsing
- Airbnb analysis outputs remain diagnostic-only and exclude forbidden performance-truth fields

Pipeline tests:

- weekly pipeline succeeds with no Airbnb files
- weekly pipeline uses Airbnb diagnostics when present
- combined signal confidence decreases when Airbnb files are missing
- Airbnb diagnostics never create PriceLabs recommendations by themselves

## Risks And Unknowns

- Airbnb UI and labels may change often.
- Airbnb may require MFA or interactive verification.
- Saved HTML may contain private account information, so retention should be short-lived.
- Similar-listing mode can be confused with a dropdown option; validation must require actual paired values.
- Date ranges can be custom or off-cycle; validation must protect Sunday-to-Sunday comparability.
- Headless browser behavior may differ from headed behavior.
- Automation may be brittle enough that manual fallback remains the most reliable weekly approach.
