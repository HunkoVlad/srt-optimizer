# Weekly PriceLabs-to-CSV Pipeline

Status: Deprecated / historical reference.
This document may describe an earlier pipeline version. Current source strategy is defined in `docs/data-source-strategy-v1.md` and `docs/project-artifact-audit-v1.md`.

This repository is being prepared for a weekly pipeline that converts PriceLabs data into a contract-compliant CSV export. The initial repository structure is documentation-first and intentionally does not implement PriceLabs extraction.

## Current Scope

- Establish the folder layout for a repeatable weekly pipeline.
- Reserve a canonical home for the V1 contract.
- Document pipeline stages, operational expectations, and guardrails.
- Document the revised V1 split between available-date pricing analysis and booked-date value analysis.
- Keep extraction, authentication, and PriceLabs automation out of scope.

## Pipeline Shape

```text
PriceLabs source
  -> extract      # Future: fetch or receive PriceLabs data; not implemented yet
  -> transform    # Future: normalize records to the V1 standardized dataset
  -> validate     # Future: verify required fields and comparison guardrails
  -> export       # Future: write standardized/future_daily_pricing_<run_date>.csv
  -> archive/log  # Future: retain run metadata and troubleshooting context
```

## Repository Layout

```text
srt-optimizer/
|-- contracts/
|   `-- pricelabs-weekly-csv-v1.md   # Canonical V1 contract location
|-- docs/
|   |-- pricelabs-pipeline.md        # Pipeline architecture and operating notes
|   |-- standardized-output-contract-v1.md
|   |-- pricelabs-v1-source-to-target-mapping.md
|   |-- validation-checklist-v1.md
|   `-- runbook-weekly-pricelabs.md  # Weekly runbook scaffold
|-- src/
|   `-- pricelabs/
|       |-- README.md                # Source package boundaries
|       |-- extract/                 # Future extraction module placeholder
|       |-- transform/               # Future contract mapping module placeholder
|       |-- export/                  # Future CSV writer placeholder
|       `-- pipeline/                # Future orchestration placeholder
|-- config/
|   |-- pricelabs.example.env        # Documented environment template only
|   `-- pricelabs.single-listing.example.toml
|-- standardized/
|   `-- .gitkeep                     # Future standardized CSV output directory
|-- data/
|   |-- incoming/                    # Local input drop zone; gitignored
|   |-- processed/                   # Local normalized intermediates; gitignored
|   `-- exports/                     # Local CSV outputs; gitignored
`-- logs/                            # Local run logs; gitignored
```

## Stage Responsibilities

### Extract

Planned responsibility: acquire weekly PriceLabs source data and store it in a controlled incoming area.

Initial state: not implemented. This scaffold must not make assumptions about PriceLabs UI selectors, API availability, credentials, or source format.

### Transform

Planned responsibility: map extracted records into the V1 standardized dataset, including deterministic date, currency, number, and text formatting.

Initial state: not implemented. Mapping rules should preserve the V1 split between open-night pricing and booked-night value analysis.

### Validate

Planned responsibility: enforce the V1 contract before any CSV is accepted as a weekly output.

Initial state: documented only. Expected future checks include required columns, column order, row counts, field formats, duplicate detection, empty value policy, valid `status` values, and comparison guardrails.

### Export

Planned responsibility: write a weekly CSV artifact at `standardized/future_daily_pricing_<run_date>.csv`, using the encoding required by the V1 contract.

Initial state: not implemented. The `standardized/` directory is reserved for the V1 standardized CSV and remains gitignored except for `.gitkeep`. The `data/exports/` directory is reserved for any local delivery copies or downstream exports and also remains gitignored.

## Contract Handling

The V1 contract is the source of truth. Pipeline code should keep field names, business rules, and delivery conventions traceable to `contracts/pricelabs-weekly-csv-v1.md`.

Supporting documentation:

- `docs/standardized-output-contract-v1.md` defines the V1 output artifact and required columns.
- `docs/pricelabs-v1-source-to-target-mapping.md` defines the current PriceLabs source-to-target mapping.
- `docs/validation-checklist-v1.md` defines the non-executable validation checklist.

V1 defines one standardized dataset with required fields:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

Optional later fields from the same PriceLabs export:

- `market_price`
- `market_occupancy`

## Second PriceLabs Source: Price Occ

The operational V1 source remains the manually downloaded future pricing export. It remains primary for `listing_id`, `stay_date`, `nightly_price`, `min_stay`, and `status`.

`sample_data/Price Occ for 650255___717243.csv` is a benchmark/enrichment source only. It contains `Date`, market occupancy fields, market price percentile fields, median booked price, booking count, pickup, event, and listing-adjacent occupancy/price fields. It does not contain `listing_id` or `Min Stay`.

Minimal join:

- `standardized.stay_date` = Price Occ `Date`

Useful fields by analysis:

- Available-date pricing: `Market 50th Percentile Price`, `Market 25th Percentile Price`, `Market 75th Percentile Price`, `Market 90th Percentile Price`, `Prices with Default Customization`, `Holiday/Event`
- Booked-date value: `Median Booked Price`, `Number of Bookings`, `Market 50th Percentile Price`
- Window-level occupancy: `Market Occupancy`, optionally `7-day market pickup`

Minimum Price Occ contract columns:

- `Date`
- `Market Occupancy`
- `Market 50th Percentile Price`

Deferred:

- Whether to trust `Your Booked Occupancy`, `booked_occupancy`, and `unavailable_occupancy` as listing-specific fields, because the file has no `listing_id` column.

## Third PriceLabs Source: Historical Monthly

`sample_data/Monthly Trends for 650255___717243.csv` is a historical monthly performance source only. It is not used by the operational daily transform and does not replace the Price Occ future benchmark source.

Minimum contract columns:

- `month_year`
- `Revenue`
- `Occupancy`
- `Booked Occupancy`
- `Blocked Occupancy`
- `ADR`

Useful later comparison fields:

- `Revenue (LY)`, `Revenue (STLY)`, `Revenue STLY YoY Difference`
- `Occupancy (LY)`, `Occupancy (STLY)`, `Occupancy STLY YoY Difference %`
- `Booked Occupancy (LY)`, `Booked Occupancy (STLY)`
- `Blocked Occupancy (LY)`, `Blocked Occupancy (STLY)`
- `ADR (LY)`, `ADR (STLY)`, `ADR STLY YoY Difference`

Intended use:

- Monthly revenue, ADR, occupancy, and blocked occupancy trends
- Revenue pace vs annual goal

Limits:

- Monthly grain only; do not join it to daily rows as if it were daily data.
- Blank values should be treated as missing/unknown unless a future rule explicitly defines otherwise.
- Completeness may vary by month.

## Settings History Layer Design

The settings history layer is design-only for now. It supports strategy review by preserving what PriceLabs settings were active on a run date, what changed from the prior snapshot, and how the next signal report changed afterward.

### Settings Snapshot

Preferred file:

```text
analysis/pricelabs_settings_snapshot_<run_date>.json
```

JSON is preferred because several settings are complex rule sections rather than simple scalar fields.

Grain:

- One snapshot per `run_date` for one configured listing.

Required fields:

- `run_date`
- `listing_id`
- `pms_account`
- `listing_name`
- `base_price`
- `last_minute_rule`
- `orphan_day_prices`
- `booking_recency_factor`
- `minimum_stay_settings`
- `extra_person_fee`
- `occupancy_based_adjustments`
- `custom_seasonality_factor`
- `length_of_stay_based_pricing`
- `demand_factor_sensitivity`
- `far_out_premium`
- `safety_minimum_price_rule`

Use flat fields for identity and scalar settings. Preserve complex settings as grouped text blocks or nested JSON, including raw copied/exported text when available.

### Settings Changes

Derived file:

```text
analysis/pricelabs_settings_changes_<run_date>.csv
```

Compare the current snapshot with the previous snapshot and emit one row per changed field.

Minimum columns:

- `run_date`
- `listing_id`
- `field_name`
- `previous_value`
- `current_value`
- `changed_flag`

### Signal Change Review

Derived comparison file:

```text
analysis/future_signal_change_review_<run_date>.csv
```

Compare the current and prior `future_window_signals` files, then include current settings-change context.

Minimum columns:

- `run_date`
- `prior_run_date`
- `listing_id`
- `window_name`
- `previous_pace_status`
- `current_pace_status`
- `previous_price_position_status`
- `current_price_position_status`
- `previous_urgency_flag`
- `current_urgency_flag`
- `changed_settings_count`
- `changed_settings_summary`
- `interpretation_note`

Rules:

- Use `days_0_15`, `days_16_45`, and `days_46_90`.
- Show settings changes and signal changes together.
- Treat the review as directional context, not proof of causation.
- No automation, scheduler, recommendation scoring, or Airbnb inputs are included.

## Proposed Enriched Future-Analysis Dataset

Design-only output:

```text
analysis/future_daily_pricing_enriched_<run_date>.csv
```

This dataset would combine the current operational daily output with Price Occ benchmark fields for analysis. It does not replace `standardized/future_daily_pricing_<run_date>.csv`.

Grain:

- One row per `stay_date`.

Carry through from operational source:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

Add from Price Occ:

- Required: `market_occupancy`, `market_50th_price`
- Optional: `market_25th_price`, `market_75th_price`, `market_90th_price`, `median_booked_price`, `last_seen_price`, `final_price`, `holiday_event`

Join:

- `operational.stay_date` = Price Occ `Date`

Purpose:

- Available-date pricing analysis
- Booked-date value review
- Market pricing position review

Daily allowed:

- Price comparisons against market price percentile fields.
- Event/context review using `holiday_event`.

Window-level only:

- Any occupancy comparison involving `market_occupancy`.
- Listing booked share vs market occupancy for next 30/60/90 days.
- Average booked proxy value vs market benchmark by window.

Deferred:

- Handling duplicate Price Occ `Date` rows.
- Whether to add derived price-position labels or ratios.

## Analytical Views

### Available Dates

Filter to `status = available`.

Use this view for current asking price analysis, market positioning, weekend and 1-night premiums, min-stay review, and open-date outlier review.

Daily comparisons are allowed for price and restriction decisions, including `nightly_price` vs `market_price` when `market_price` is present.

### Booked Dates

Filter to `status = booked`.

Use this view for directional booked-value quality analysis and upcoming ADR quality. In V1, `nightly_price` on booked dates is only a proxy for booked value, and the output must label it as provisional if PriceLabs changes displayed values after booking.

Daily booked-date value inspection is allowed, but booked-value trends are more meaningful at the next 30/60/90-day windows.

## Comparison Guardrails

Allowed daily:

- Available-date `nightly_price` vs `market_price`
- Booked-date proxy value vs `market_price`
- Min-stay inspection by date
- Standardized `nightly_price` vs Price Occ market price percentiles

Required at 30/60/90-day windows:

- Your booked share of nights vs `market_occupancy`
- Booked-value quality trends
- Available-date pricing posture
- Any comparison involving Price Occ `Market Occupancy`

Not allowed:

- Daily row-level comparison of listing occupancy versus market occupancy.

## Implementation Guardrails

- Do not commit secrets, downloaded PriceLabs data, generated CSV files, or logs.
- V1 configuration is for one listing only: one `listing_id`, one `input_path`, and one `output_path`.
- Keep extraction separate from transformation and validation.
- Prefer deterministic fixtures for tests once the contract is known.
- Make every generated CSV reproducible from recorded input plus configuration.
- Fail closed when contract-required fields are absent or malformed.
- Keep available-date pricing analysis separate from booked-date value analysis.
- Label booked-date `nightly_price` as a proxy, not final realized ADR.
