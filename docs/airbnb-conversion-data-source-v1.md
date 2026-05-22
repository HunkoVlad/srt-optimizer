# Airbnb Conversion Data Source V1

## Purpose

Airbnb data is a diagnostic layer for visibility and conversion only. It helps explain why demand may or may not be converting on Airbnb, especially when Reason Review needs more context than PriceLabs market and booking data can provide.

Airbnb data may help answer:

- Are Airbnb page views rising or falling?
- Are similar listings receiving more visibility?
- Is the listing showing on the first page of search?
- Are search impressions turning into listing views?
- Are listing views turning into bookings?
- Are wishlists appearing without bookings?
- Is Airbnb-specific conversion behavior different from broader PriceLabs pace?

## Allowed Influence

Airbnb conversion data may influence diagnostic classifications and investigation prompts, such as:

- `market_weakness`
- `listing_or_conversion_issue`
- `price_or_rule_issue`
- `insufficient_data`

It may support notes like:

- possible Airbnb visibility issue
- possible title/photo/search appeal issue
- possible listing conversion friction
- possible booking-rule friction
- monitor because Airbnb signals are missing

Airbnb data should be used as supporting evidence only, not as the final performance truth.

## Explicitly Not Allowed

Airbnb must not be used as the source of truth for:

- occupancy
- ADR
- revenue
- booked nights
- total bookings
- cleaning count
- monthly revenue pace
- revenue captured
- open ask
- total calendar value
- revenue per cleaning
- portfolio-level performance truth

Do not use Airbnb values to overwrite or replace PriceLabs Monthly Trends, Bookings Report, future export, or existing monthly revenue pace logic.

## Source Of Truth Boundary

PriceLabs remains the source of truth for occupancy, ADR, revenue, bookings, and cleaning-efficiency reporting because the PriceLabs pipeline includes Airbnb, Vrbo, direct, and other booking sources together.

Current source roles remain:

- PriceLabs Monthly Trends: primary monthly truth for revenue, ADR, and occupancy.
- PriceLabs Bookings Report: cleanings/stays, LOS, booking source mix, and booking-window context.
- PriceLabs future export: future calendar, open ask, availability, min stay, and future booked proxy fallback.
- `price_occ.csv`: market context only.
- Airbnb conversion data: Airbnb visibility and conversion diagnosis only.

## Manual-First Workflow

Airbnb source capture is manual-first for this version. The operator may save Airbnb daily report pages as HTML or screenshots into the run folder when needed.

Automation is explicitly out of scope for this step:

- no scraper
- no Playwright automation
- no browser login handling
- no browser download automation
- no report integration
- no scheduler integration

## Preferred Source Shape

Airbnb daily HTML or screenshot data is preferred over a monthly CSV because weekly Reason Review needs daily or short-window signals.

Preferred daily source pages include:

- booking conversion daily view
- page views daily view
- wishlist additions daily view

The Airbnb monthly CSV may be stored as optional supporting context. It should not be used for portfolio-level performance truth or for revenue pace calculations.

## Analysis Layers

Airbnb diagnostics should have two separate analysis layers.

### Weekly Average Layer

The weekly average layer compares the most recent 7 days against previous weekly windows. It is used for trend direction and over-time Reason Review diagnosis.

This layer should be comparison-ready, not judgment-based. Do not classify Airbnb metrics as good or bad from bare values alone. Interpretive confidence depends on whether comparison data exists:

- no comparison data: low confidence
- previous-week comparison: medium confidence
- previous-week comparison plus 4 or more historical weekly windows: high confidence
- similar-listing benchmarks: Airbnb market context only

This layer can answer:

- Are page views improving or weakening versus prior weeks?
- Is search-to-listing conversion trending down?
- Is listing-to-booking conversion weaker than prior weeks?
- Are wishlists rising without bookings?
- Are Airbnb signals missing or too sparse for a recommendation?

Future output:

```text
data/runs/<run_date>/analysis/airbnb_weekly_conversion_summary_<run_date>.csv
```

This is the clean business-ready Airbnb diagnostic summary. It combines parsed booking conversion, page views, and wishlist rows into one weekly status row.

Example neutral summary wording:

- Airbnb diagnostics parsed successfully, but interpretation is limited because no historical baseline is available.
- Airbnb page views declined versus the previous 7 days; compare with PriceLabs market context before assigning cause.
- Airbnb conversion signals are available for the selected week; no portfolio revenue conclusion should be made from Airbnb alone.

### Daily Competitor Layer

The daily competitor layer compares each day inside the week against similar listings or competitor benchmarks shown by Airbnb. It is used to identify daily visibility or conversion underperformance.

This layer can answer:

- Did a specific day have unusually low page views versus similar listings?
- Did first-page search visibility fall below comparable listings?
- Did listing-to-booking conversion trail Airbnb's similar-listing benchmark?
- Did wishlist activity lag similar listings on specific days?

Future output:

```text
data/runs/<run_date>/analysis/airbnb_daily_competitor_conversion_<run_date>.csv
```

These layers are diagnostic. They do not produce occupancy, ADR, revenue, booked nights, booking totals, cleaning counts, or monthly revenue pace.

### Daily Week-Over-Week Layer

The daily week-over-week layer pairs each current-week Airbnb chart point with the same weekday in the previous-week range. It helps show whether a visibility or interest change happened across the whole selected week or only on specific days.

Output:

```text
data/runs/<run_date>/analysis/airbnb_daily_week_over_week_conversion_<run_date>.csv
```

This layer calculates daily changes only. It does not classify daily values as good or bad and does not make portfolio revenue conclusions.

### Retained-History Layer

The retained-history layer compares the current Airbnb weekly summary to prior complete Airbnb weekly summaries retained in previous run folders.

Output:

```text
data/runs/<run_date>/analysis/airbnb_weekly_history_comparison_<run_date>.csv
```

This layer can provide:

- previous-week value and change
- last-4-week average when at least 4 prior complete weekly summaries exist
- `history_quality_status`, such as `no_history`, `previous_week_only`, `limited_history`, or `recent_baseline_ready`

`has_recent_history_baseline` should remain false until retained history is `recent_baseline_ready`. Airbnb retained history is still diagnostic context only.

## Diagnostic Examples

Airbnb conversion data may support Reason Review examples like:

- Views down plus PriceLabs market weak: likely `market_weakness`.
- Views down plus PriceLabs market not weak: possible Airbnb visibility issue.
- Views healthy plus search-to-listing weak: possible title, photo, or search appeal issue.
- Views healthy plus listing-to-booking weak: possible listing conversion, price friction, or booking-rule friction.
- Wishlist additions healthy plus bookings weak: possible price or booking friction.
- Airbnb signals missing: `insufficient_data`.

These diagnostics should not directly recommend broad price cuts. They should first classify the likely reason, then gate any PriceLabs rule recommendation through the existing Reason Review logic.

## Storage

Airbnb raw files, if captured, should live under:

```text
data/runs/<run_date>/raw/
```

Temporary Airbnb HTML files live in `raw/` only until successful parsing:

```text
data/runs/<run_date>/raw/airbnb_booking_conversion_daily.html
data/runs/<run_date>/raw/airbnb_page_views_daily.html
data/runs/<run_date>/raw/airbnb_wishlist_additions_daily.html
```

The retained parsed extraction CSV also lives in `raw/` because it is source-derived extraction, not business-ready analysis:

```text
data/runs/<run_date>/raw/airbnb_daily_conversion_parsed_<run_date>.csv
```

This parsed CSV may retain source-derived daily chart points from the temporary Airbnb HTML as `daily_chart_values_json` so the HTML can be cleaned up while preserving diagnostic extraction evidence.

The old detailed extraction path is deprecated and should be used only as a migration fallback:

```text
data/runs/<run_date>/analysis/airbnb_daily_conversion_<run_date>.csv
```

Clean diagnostic summaries live under:

```text
data/runs/<run_date>/analysis/
```

Raw Airbnb files are supporting diagnostic evidence. They do not replace the required PriceLabs raw files.
