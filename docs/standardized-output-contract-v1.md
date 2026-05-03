# Standardized Output Contract V1

This document defines the V1 standardized CSV output for the weekly PriceLabs transform. It documents the output artifact only; it does not implement extraction, transformation, validation code, Playwright tests, dashboards, or multi-listing support.

## Output File

Path template:

```text
standardized/future_daily_pricing_<run_date>.csv
```

One pipeline run produces one standardized output file for one listing.

## Required Columns

Columns must appear in this exact order:

| Column | Required | Source |
| --- | --- | --- |
| `run_date` | yes | Pipeline metadata |
| `listing_id` | yes | PriceLabs `Listing ID` |
| `stay_date` | yes | PriceLabs `Date` |
| `nightly_price` | yes | PriceLabs `Your Price` |
| `min_stay` | yes | PriceLabs `Min Stay` |
| `status` | yes | PriceLabs `Status` |

## Optional Later Columns

These fields are allowed only when they are available from the same PriceLabs export and are explicitly added to the transform contract:

| Column | Source |
| --- | --- |
| `market_price` | PriceLabs `Market 50th Percentile Price` |
| `market_occupancy` | PriceLabs `Market Occupancy` |

V1 implementation should start with required columns only unless optional fields are intentionally enabled.

## Field Expectations

`run_date`:

- Comes from pipeline metadata.
- Uses a stable date format selected by the pipeline before output is generated.
- Must be populated on every row.

`listing_id`:

- Comes from the PriceLabs `Listing ID` export field.
- V1 supports one configured listing only.
- Every output row must match the configured `listing_id`.

`stay_date`:

- Comes from the PriceLabs `Date` export field.
- Represents the future stay night being analyzed.
- Must be populated on every row.

`nightly_price`:

- Comes from the PriceLabs `Your Price` export field.
- For available dates, represents current asking price.
- For booked dates, is only a provisional booked-value proxy and not final realized ADR.

`min_stay`:

- Comes from the PriceLabs `Min Stay` export field.
- Required in the output even though it is not essential for booked-date value analysis.

`status`:

- Comes from the PriceLabs `Status` export field.
- V1 analysis expects at least `available` and `booked` rows.

## Analytical Boundaries

Available-date pricing view:

- Filter to `status = available`.
- Use for current asking price and restriction review.

Booked-date value view:

- Filter to `status = booked`.
- Use `nightly_price` only as a provisional booked-value proxy.

Occupancy comparison boundary:

- Do not compare listing occupancy against market occupancy at the daily row level.
- Occupancy comparisons belong only to aggregated 30/60/90-day windows.

