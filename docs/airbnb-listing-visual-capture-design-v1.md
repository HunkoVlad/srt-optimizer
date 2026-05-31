# Airbnb Listing Visual Capture Design v1

## Purpose

This design defines a future automated Airbnb listing visual capture flow for weekly listing-side conversion diagnostics.

The immediate use case is monitoring listing-side tests related to the open diagnostic issue:

- `airbnb_visibility_up_conversion_down`

The goal is to create comparable weekly visual evidence for:

- Airbnb search result card presentation
- Airbnb listing page top / hero-grid presentation
- Optional visible listing text fields that support the listing state snapshot schema

This is design only. It does not implement browser capture, scheduled behavior, PriceLabs rule recommendations, or email sending changes.

## Fixed Search Parameters

Weekly screenshots must be comparable, so the search setup should be fixed unless deliberately changed and recorded in `data/history/listing_change_log.csv`.

Recommended default parameters:

- `search_location`: `Pocono Mountains, PA`
- `guest_count`: `8`
- `date_rule`: `flexible_weekend_next_target_month`
- `filters`: none
- `browser_size`: `1440x1000`
- `logged_in_state`: headed manual-login pattern when needed

The date rule should resolve deterministically from `run_date`. `flexible_weekend_next_target_month` represents a typical high-value short group stay search: Airbnb Flexible dates, Weekend trip length, and the next target month, such as June 2026 for the 2026-06-01 visual baseline.

## Extra Guest Pricing Context

Aloha Poconos has extra guest pricing above 6 guests. The visual capture uses 8 guests intentionally because it represents a high-value target group search.

This means visible Airbnb prices in search-card or listing-page screenshots may reflect target group pricing rather than base guest pricing.

Screenshots are diagnostic only and should not be used as PriceLabs revenue or ADR source of truth. PriceLabs remains the source of truth for revenue, occupancy, ADR, bookings, cleaning count, and revenue pace.

## Capture Outputs

Promoted files should be saved to:

`data/runs/<run_date>/analysis/`

Required outputs:

- `listing_search_card_<run_date>.png`
- `listing_page_top_<run_date>.png`

Optional later output:

- `listing_first_5_photos_<run_date>.png`

The separate first-5-photos screenshot is optional when `listing_page_top_<run_date>.png` clearly captures the Airbnb hero grid / first five photos.

## Search-Card Capture Rules

The search-card screenshot should include the subject listing card with:

- Cover photo
- Title
- Rating and reviews, if visible
- Visible price
- Badge, if visible
- Capacity summary, if visible

Nearby competing cards may be visible naturally in the screenshot, but they should not be treated as structured competitor data. PriceLabs competitor calendar remains the selected competitor context source for this workflow.

## Listing-Page-Top Capture Rules

The listing-page-top screenshot should include:

- Listing title
- Hero photo grid / first five photos
- Rating and reviews
- Guest, bed, and bath summary
- Visible trust signals
- Booking price widget, if visible

The screenshot should not be cropped so tightly that the booking widget or trust signals are lost when they are visible in the normal viewport.

## Optional Extraction Fields

A future capture module may extract visible text fields and write them into:

`data/runs/<run_date>/raw/listing_state_snapshot_input_<run_date>.csv`

Where possible, map extracted values to the Step 93 listing snapshot schema:

- `listing_title`
- `rating`
- `review_count`
- `guest_capacity`
- `bedrooms`
- `beds`
- `bathrooms`
- `opening_description_text`
- `trust_signal_notes`
- `fees_visibility_notes`
- `booking_widget_notes`

Extraction should be conservative. If a field is not clearly visible, leave it blank or mark it as not confirmed rather than guessing.

## Staging-First Flow

Future capture should use a staging-first workflow:

`data/runs/<run_date>/downloads_staging/airbnb_listing_state/`

Suggested staged files:

- `listing_search_card_<run_date>.png`
- `listing_page_top_<run_date>.png`
- `listing_capture_manifest_<run_date>.json`

Only promote screenshots to `analysis/` after validation confirms:

- File exists
- File size is above a minimum threshold
- File is a readable PNG
- File is not obviously blank, if basic validation is available
- Manifest was written successfully

Promotion should never overwrite trusted existing analysis screenshots unless an explicit future override flag is added.

## Manifest Proposal

Manifest path:

`data/runs/<run_date>/downloads_staging/airbnb_listing_state/listing_capture_manifest_<run_date>.json`

Suggested fields:

- `run_date`
- `mode`
- `search_location`
- `guest_count`
- `date_rule`
- `browser_size`
- `search_card_status`
- `listing_page_top_status`
- `promoted_files`
- `errors`
- `generated_at`

Optional future fields:

- `resolved_search_dates`
- `listing_url`
- `capture_targets`
- `validation_results`
- `manual_login_required`
- `notes`

## Future CLI Proposal

Suggested module:

`src/airbnb/capture_listing_state.py`

Suggested commands:

```powershell
python -m airbnb.capture_listing_state --run-date 2026-06-01 --mode dry-run
python -m airbnb.capture_listing_state --run-date 2026-06-01 --mode capture-headed
```

Future modes:

- `dry-run`: write manifest only, no browser and no screenshots.
- `capture-headed`: open headed browser, allow manual login/MFA if needed, capture staged screenshots, write manifest.
- `validate-staged`: validate staged screenshots without promotion.
- `promote-staged`: promote valid staged screenshots into `analysis/`.

## Guardrails

- Airbnb listing visual capture is diagnostic only.
- PriceLabs remains the source of truth for revenue, occupancy, ADR, bookings, cleaning count, and revenue pace.
- Captured screenshots or visible text cannot create automatic PriceLabs rule recommendations.
- Listing screenshots may raise investigation context, but they do not create pricing actions.
- `data/history/listing_change_log.csv` remains manual because it records intentional business changes and expected effects.
- Do not store Airbnb credentials, cookies, browser state, tokens, screenshots outside approved staged/analysis paths, HAR files, or unrelated raw HTML.

## Failure Behavior

Capture should be non-blocking for the weekly PriceLabs pipeline.

If capture fails:

- Write a manifest with failure status and errors.
- Do not promote invalid screenshots.
- Do not delete existing trusted analysis screenshots.
- Do not fail PriceLabs revenue processing.
- Email/reporting should simply omit visual baseline references unless valid promoted screenshots exist.

## Tests Needed Later

When implementation begins, add tests for:

- Dry-run writes manifest with fixed search parameters.
- Capture target list contains exactly the expected screenshot names.
- Staged screenshots are not promoted unless validation passes.
- Existing analysis screenshots are not overwritten by default.
- Missing screenshots do not fail the pipeline.
- Manifest records capture and promotion statuses.
- Listing snapshot email note appears when promoted visual files exist.
- No recommendation or pricing logic changes.
