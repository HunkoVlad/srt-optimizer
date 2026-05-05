# PriceLabs Weekly CSV Contract V1

Status: Revised V1
Owner: SRT pipeline
Scope: Weekly PriceLabs-to-CSV pipeline

This contract defines the initial standardized dataset and analytical interpretation for a weekly PriceLabs export. V1 supports two separate analysis tracks and intentionally does not implement extraction.

## Two Analysis Tracks

### A. Available-Date Pricing Analysis

Purpose: evaluate current asking price and restriction strategy for dates still open.

Use for:

- Pricing strength
- Weekend premium
- 1-night premium
- Min-stay behavior
- Market price positioning on open dates

### B. Booked-Date Value Analysis

Purpose: evaluate booked-value quality of dates already reserved.

Use for:

- Upcoming ADR quality
- Whether booked nights were captured at strong value
- Booked-window quality versus market benchmarks

This contract keeps these tracks separate so current asking price for open nights is not mixed with booked-value quality for reserved nights.

## Standardized Dataset

V1 keeps one minimal standardized file:

```text
standardized/future_daily_pricing_<run_date>.csv
```

Required columns:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

Optional later columns from the same PriceLabs export:

- `market_price`
- `market_occupancy`

Field source notes:

- `market_price` maps from PriceLabs `Market 50th Percentile Price`.
- `market_occupancy` maps from PriceLabs `Market Occupancy`.

## Price Occ Benchmark Source

The current operational PriceLabs export remains the primary V1 source for:

- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

The file `sample_data/Price Occ for 650255___717243.csv` is a second PriceLabs source for benchmark/enrichment design only. It is not a replacement for the operational source.

Actual columns present in the Price Occ file include:

- `Date`
- `Market Occupancy`
- `Market 25th Percentile Price`
- `Market 50th Percentile Price`
- `Market 75th Percentile Price`
- `Market 90th Percentile Price`
- `Median Booked Price`
- `Number of Bookings`
- `7-day market pickup`
- `Last Seen Price`
- `Final Price`
- `Your Booked Occupancy`
- `Prices with Default Customization`
- `booked_occupancy`
- `unavailable_occupancy`
- `Holiday/Event`
- `Upcoming Booking`

Practical join key:

- Join standardized `stay_date` to Price Occ `Date`.
- No `listing_id` is present in the Price Occ file, so listing identity must come from the operational source/config.

Minimum Price Occ benchmark columns for V1 design:

- `Date`
- `Market Occupancy`
- `Market 50th Percentile Price`

Useful optional benchmark columns:

- Price positioning: `Market 25th Percentile Price`, `Market 75th Percentile Price`, `Market 90th Percentile Price`, `Prices with Default Customization`
- Booked-value context: `Median Booked Price`, `Number of Bookings`
- Window-level demand context: `7-day market pickup`, `Holiday/Event`

Limits:

- The Price Occ file has no `listing_id`.
- The Price Occ file has no `Min Stay`.
- It is not suitable as the sole operational V1 source.
- Daily market occupancy must not be compared directly to single-listing daily occupancy.
- Occupancy comparison is valid only after aggregation across windows such as next 30/60/90 days.

## Historical Monthly Performance Source

The file `sample_data/Monthly Trends for 650255___717243.csv` is a third PriceLabs source for historical monthly performance analysis only. It is separate from the operational future source and the Price Occ future benchmark/enrichment source.

Actual columns present in the historical monthly file:

- `month_year`
- `Revenue`
- `Revenue (LY)`
- `Revenue (STLY)`
- `Revenue STLY YoY Difference`
- `Occupancy`
- `Occupancy (LY)`
- `Occupancy (STLY)`
- `Occupancy STLY YoY Difference %`
- `Booked Occupancy`
- `Booked Occupancy (LY)`
- `Booked Occupancy (STLY)`
- `Blocked Occupancy`
- `Blocked Occupancy (LY)`
- `Blocked Occupancy (STLY)`
- `ADR`
- `ADR (LY)`
- `ADR (STLY)`
- `ADR STLY YoY Difference`

Minimum historical monthly contract columns:

- `month_year`
- `Revenue`
- `Occupancy`
- `Booked Occupancy`
- `Blocked Occupancy`
- `ADR`

Useful optional comparison fields:

- Revenue comparison: `Revenue (LY)`, `Revenue (STLY)`, `Revenue STLY YoY Difference`
- Occupancy comparison: `Occupancy (LY)`, `Occupancy (STLY)`, `Occupancy STLY YoY Difference %`
- Booked/blocked comparison: `Booked Occupancy (LY)`, `Booked Occupancy (STLY)`, `Blocked Occupancy (LY)`, `Blocked Occupancy (STLY)`
- ADR comparison: `ADR (LY)`, `ADR (STLY)`, `ADR STLY YoY Difference`

Intended uses:

- Monthly revenue trend
- Monthly ADR trend
- Monthly occupancy trend
- Blocked occupancy trend
- Revenue pace vs annual goal

Limits:

- Monthly only, not daily.
- Not suitable for operational daily transform logic.
- Blank values may mean missing data, not zero.
- Completeness may vary by month.

## Proposed Enriched Future-Analysis Dataset

This is a design-only dataset that combines the operational future daily data with Price Occ benchmark fields. It is analysis-oriented and does not replace the current operational standardized dataset.

Proposed file name:

```text
analysis/future_daily_pricing_enriched_<run_date>.csv
```

Grain:

- One row per `stay_date` for the configured listing.

Required operational columns carried through:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

Minimum Price Occ benchmark/enrichment columns:

- `market_occupancy` from `Market Occupancy`
- `market_50th_price` from `Market 50th Percentile Price`

Useful optional Price Occ enrichment columns:

- `market_25th_price` from `Market 25th Percentile Price`
- `market_75th_price` from `Market 75th Percentile Price`
- `market_90th_price` from `Market 90th Percentile Price`
- `median_booked_price` from `Median Booked Price`
- `last_seen_price` from `Last Seen Price`
- `final_price` from `Final Price`
- `holiday_event` from `Holiday/Event`

Join rule:

- `operational.stay_date` = Price Occ `Date`

Join assumptions and risks:

- Price Occ has no `listing_id`, so the configured operational listing remains the listing authority.
- Missing Price Occ dates should leave benchmark fields blank/null rather than dropping operational rows.
- Duplicate Price Occ `Date` rows are deferred; no rule is defined yet.

Intended support:

- Available-date pricing analysis
- Booked-date value review
- Market pricing position review

Not for direct daily use:

- Daily market occupancy vs single-listing daily occupancy comparison.

Belongs only in later window-level summaries:

- Listing booked share vs `market_occupancy`
- Average market occupancy over next 30/60/90 days
- Occupancy gap to market over next 30/60/90 days
- Share of booked nights above/below market price benchmark
- Average booked proxy value vs market benchmark by window

## Required V1 Base Fields

These are the minimum common fields for both analysis tracks:

| Field | Needed for available-date pricing | Needed for booked-date value | V1 status |
| --- | --- | --- | --- |
| `run_date` | yes | yes | required |
| `listing_id` | yes | yes | required |
| `stay_date` | yes | yes | required |
| `nightly_price` | yes | yes | required |
| `min_stay` | yes | not essential | required |
| `status` | yes | yes | required |
| `market_price` | useful | useful | optional later |
| `market_occupancy` | not for daily compare | yes, window-level only | optional later |

## Available-Date Pricing Analysis

Filter:

```text
status = available
```

Minimum useful fields:

- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

Main use:

- Current asking price analysis
- Market positioning
- Min-stay review

Optional later fields:

- `market_price`
- `market_occupancy`

Daily comparisons allowed:

- `nightly_price` vs `market_price`
- Weekday and weekend price pattern
- Min-stay by date
- Open-date pricing outliers
- Open-date orphan or gap candidate review later

Window-level comparisons allowed:

- Average open-date price vs average market price for the next 30/60/90 days
- Average open-date min stay for the next 30/60/90 days
- Overall available-date pricing posture by window

## Booked-Date Value Analysis

Filter:

```text
status = booked
```

Minimum useful fields:

- `stay_date`
- `nightly_price`
- `status`

Main use:

- Proxy booked-value quality analysis
- Upcoming ADR quality directionally
- Market-relative quality at window level

V1 interpretation:

- For booked dates, `nightly_price` may be treated as a proxy for booked-value quality only if PriceLabs export behavior is stable enough.
- If PriceLabs changes the displayed value after booking, `nightly_price` is only a weak proxy and must be labeled as such.
- Booked-date value analysis is provisional in V1.
- It is useful for directional review, not final truth for realized ADR.

Daily comparisons allowed:

- Inspect booked-date proxy value by date
- Inspect whether a booked date appears weak or strong relative to `market_price` on that date

Window-level comparisons preferred:

- Average booked-date proxy value for the next 30/60/90 days
- Booked-date average vs market average for the same booked dates
- Share of booked nights above or below market benchmark

## Comparison Rules

### Daily Comparisons

Allowed:

- Available-date `nightly_price` vs `market_price`
- Booked-date proxy value vs `market_price`
- Min-stay inspection by date
- Open-date pricing outlier review

Not allowed:

- Single-date booked occupancy vs single-date market occupancy

### Window-Level Comparisons

Window-level comparisons must aggregate over the next 30, 60, and 90 days.

Required for:

- Your booked share of nights vs market occupancy
- Booked-value quality trends
- Available-date pricing posture

Why: your listing is binary per date, while `market_occupancy` is a market-wide rate. Occupancy comparisons are valid only after aggregation across a window.

## Final V1 Rule

V1 treats the PriceLabs export as supporting two separate views:

1. Open-night pricing view: analyze current price and restrictions on available dates.
2. Booked-night value view: analyze booked-value quality directionally on reserved dates, mainly at 30/60/90-day windows.

V1 must not use daily row-level comparison of listing occupancy versus market occupancy. That comparison belongs only to aggregated windows.

## Non-Goals For V1 Scaffold

- No PriceLabs extraction is implemented.
- No browser automation is added for PriceLabs.
- No authenticated network access is configured.
- No production scheduling is enabled.
- No final realized ADR claims are made from booked-date `nightly_price`.
