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
