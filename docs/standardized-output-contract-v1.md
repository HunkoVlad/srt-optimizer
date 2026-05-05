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
| `analysis_status` | yes | Derived from `Status` and `Available` |
| `status_confidence` | yes | Derived status confidence |
| `status_reason` | yes | Derived status reason |

## Optional Later Columns

These fields are allowed only when they are available from an approved PriceLabs source and are explicitly added to the transform contract:

| Column | Source |
| --- | --- |
| `market_price` | PriceLabs `Market 50th Percentile Price` |
| `market_occupancy` | PriceLabs `Market Occupancy` |

V1 implementation should start with required columns only unless optional fields are intentionally enabled.

## Price Occ Enrichment Boundary

`sample_data/Price Occ for 650255___717243.csv` is a benchmark/enrichment source, not the operational standardized output source.

The standardized V1 output remains driven by the current operational PriceLabs export for:

- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`
- `analysis_status`
- `status_confidence`
- `status_reason`

If Price Occ enrichment is added later, the minimal join is:

```text
standardized.stay_date = Price Occ Date
```

Minimum required Price Occ columns for enrichment design:

- `Date`
- `Market Occupancy`
- `Market 50th Percentile Price`

Daily allowed:

- Compare standardized price fields to Price Occ market price percentile fields.
- Use `Holiday/Event` as date context.

Window-level only:

- Compare listing booked share to Price Occ `Market Occupancy`.
- Use occupancy over isolated 0-30, 31-60, and 61-90-day horizon buckets.

Not allowed:

- Daily row-level comparison of Price Occ `Market Occupancy` to single-listing occupancy.
- Using Price Occ as the sole source for `listing_id`, `min_stay`, or `status`.

## Historical Monthly Boundary

`sample_data/Monthly Trends for 650255___717243.csv` is a historical monthly performance source. It is not part of the operational standardized daily output contract.

Minimum historical monthly source columns:

- `month_year`
- `Revenue`
- `Occupancy`
- `Booked Occupancy`
- `Blocked Occupancy`
- `ADR`

Allowed uses:

- Monthly revenue trend
- Monthly ADR trend
- Monthly occupancy trend
- Monthly blocked occupancy trend
- Revenue pace vs annual goal

Not allowed:

- Using this source as input to the daily operational transform.
- Treating monthly rows as daily stay-date rows.
- Treating blanks as zero unless a later rule explicitly says so.

## Enriched Future-Analysis Dataset Boundary

The proposed enriched future-analysis dataset is analysis-oriented and does not replace the operational standardized dataset.

Proposed file:

```text
analysis/future_daily_pricing_enriched_<run_date>.csv
```

Grain:

- One row per `stay_date`.

Minimum operational columns:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`
- `analysis_status`
- `status_confidence`
- `status_reason`

Minimum Price Occ columns:

- `market_occupancy`
- `market_50th_price`
- `market_75th_price`

Useful optional Price Occ columns:

- `market_25th_price`
- `market_90th_price`
- `median_booked_price`
- `last_seen_price`
- `final_price`
- `holiday_event`

Join:

```text
operational.stay_date = Price Occ Date
```

Not allowed in this daily dataset:

- Direct daily market occupancy vs single-listing occupancy comparison.
- Window-level occupancy metrics such as horizon-bucket booked share vs market occupancy.
- Derived occupancy gaps or occupancy pace labels.

## Future Window Summary Dataset

The future window summary is an analysis-oriented output built from the enriched daily dataset. It keeps occupancy comparison at the required window level and separates open-date asking price posture from booked-date value proxy.

File:

```text
analysis/future_window_summary_<run_date>.csv
```

Grain:

- One row per isolated horizon bucket: `days_0_30`, `days_31_60`, and `days_61_90`.

Bucket definitions:

- `days_0_30`: `stay_date` from `run_date` through `run_date + 29 days`.
- `days_31_60`: `stay_date` from `run_date + 30 days` through `run_date + 59 days`.
- `days_61_90`: `stay_date` from `run_date + 60 days` through `run_date + 89 days`.

Columns, in order:

- `run_date`
- `listing_id`
- `window_name`
- `listing_booked_pct`
- `market_occupancy_avg`
- `occupancy_vs_market_pct`
- `booked_days`
- `low_confidence_booked_days`
- `blocked_days`
- `avg_available_price`
- `avg_market_75th_price`
- `price_vs_market_75th_pct`
- `avg_booked_price_proxy`

Metric rules:

- `listing_booked_pct` is booked days divided by total days in the window.
- `market_occupancy_avg` is average `market_occupancy` where present.
- `occupancy_vs_market_pct` is `listing_booked_pct - market_occupancy_avg`, expressed as a percentage-point difference.
- `low_confidence_booked_days` counts booked rows where `status_confidence = low`.
- `avg_available_price` averages `nightly_price` only for `analysis_status = available`.
- `avg_booked_price_proxy` averages `nightly_price` only for `analysis_status = booked`.
- `price_vs_market_75th_pct` compares `avg_available_price` against `avg_market_75th_price`.

Not included:

- Daily occupancy comparisons.
- ADR claims from asking-price averages.
- Recommendation scoring.
- Weighted confidence metrics.

## Future Window Signal Dataset

The future window signal dataset is a small interpretation layer built from the isolated future window summary. It is not a full recommendation engine.

File:

```text
analysis/future_window_signals_<run_date>.csv
```

Grain:

- One row per isolated horizon bucket: `days_0_30`, `days_31_60`, and `days_61_90`.

Columns, in order:

- `run_date`
- `listing_id`
- `window_name`
- `pace_status`
- `price_position_status`
- `confidence_note`
- `urgency_flag`
- `short_reason`

Signal rules:

- `pace_status` uses `occupancy_vs_market_pct`: `ahead_of_market` at `>= 5.0`, `near_market` above `-5.0` and below `5.0`, and `behind_market` at `<= -5.0`.
- `price_position_status` uses `price_vs_market_75th_pct`: `above_75th` above `10.0`, `near_75th` from `-10.0` through `10.0`, and `below_75th` below `-10.0`.
- `confidence_note` uses `low_confidence_booked_days`: `clean` at `0`, `some_low_confidence_bookings` at `1-2`, and `many_low_confidence_bookings` above `2`.
- `urgency_flag` is `critical_now` only for `days_0_30` behind market, `advisory` for later buckets behind market, and `monitor` otherwise.

Not included:

- Recommendation scoring.
- Automated actions.
- Weighted confidence metrics.

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
- Preserves current raw/source-driven V1 status behavior for traceability.
- Allowed values remain `available`, `booked`, `blocked`, and `unavailable`.

`analysis_status`:

- Used for analysis-aware status interpretation.
- Explicit blocked stays `blocked`.
- Explicit booked/reserved stays `booked`.
- Explicit available stays `available`.
- Blank or unmapped `Status` with `Available=True` becomes `available`.
- Blank or unmapped `Status` with `Available=False` becomes `booked`.
- Allowed values are `available`, `booked`, and `blocked`.

`status_confidence`:

- `high` for explicit `Status` matches.
- `high` for blank/unmapped `Status` inferred from `Available=True`.
- `low` for blank/unmapped `Status` inferred from `Available=False`.

`status_reason`:

- Stable reason code for the analysis status.
- Allowed values:
  - `explicit_available`
  - `explicit_booked`
  - `explicit_blocked`
  - `inferred_available_from_available_true`
  - `inferred_booked_from_available_false`

## Analytical Boundaries

Available-date pricing view:

- Filter to `analysis_status = available`.
- Use for current asking price and restriction review.

Booked-date value view:

- Filter to `analysis_status = booked`.
- Use `nightly_price` only as a provisional booked-value proxy.

Occupancy comparison boundary:

- Do not compare listing occupancy against market occupancy at the daily row level.
- Occupancy comparisons belong only to aggregated horizon buckets.
