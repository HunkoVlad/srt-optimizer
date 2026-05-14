# Validation Checklist V1

Status: Deprecated / historical reference.
This document may describe an earlier pipeline version. Current source strategy is defined in `docs/data-source-strategy-v1.md` and `docs/project-artifact-audit-v1.md`.

Implementation-oriented checklist for the current Python V1 PriceLabs transform.

## Happy Path

- [ ] Manually downloaded PriceLabs CSV can be read.
- [ ] Leading `#` note/comment lines before the header are ignored.
- [ ] Required source columns are present:
  - `Listing ID`
  - `Date`
  - `Your Price`
  - `Min Stay`
  - `Status`
- [ ] Output file is written to `standardized/future_daily_pricing_<run_date>.csv`.
- [ ] `manifest.json` is written with `status = "success"`.

## Standardized Output

- [ ] Output columns are present in this exact order:

```text
run_date,listing_id,stay_date,nightly_price,min_stay,status,analysis_status,status_confidence,status_reason
```

- [ ] PriceLabs `Listing ID` maps to `listing_id`.
- [ ] PriceLabs `Date` maps to `stay_date`.
- [ ] PriceLabs `Your Price` maps to `nightly_price`.
- [ ] PriceLabs `Min Stay` maps to `min_stay`.
- [ ] Normalized PriceLabs status maps to `status`.
- [ ] Analysis-aware status maps to `analysis_status`.
- [ ] Analysis status confidence maps to `status_confidence`.
- [ ] Analysis status reason maps to `status_reason`.
- [ ] Pipeline run date maps to `run_date`.

## Implemented Validation

- [ ] Missing input file fails the run.
- [ ] Missing required source column fails the run.
- [ ] Missing `Min Stay` source column fails the run.
- [ ] Duplicate primary key fails the run.
- [ ] Primary key is `run_date`, `listing_id`, `stay_date`.
- [ ] Output `status` is one of:
  - `available`
  - `booked`
  - `blocked`
  - `unavailable`
- [ ] Output `analysis_status` is one of:
  - `available`
  - `booked`
  - `blocked`
- [ ] Output `status_confidence` is one of:
  - `high`
  - `medium`
  - `low`
- [ ] `status_reason` is populated for every row.

## Tested Status Normalization

- [ ] `Status` containing `available` -> `available`.
- [ ] `Status` containing `reserved` -> `booked`.
- [ ] `Status` containing `booked` -> `booked`.
- [ ] `Status` containing `blocked` -> `blocked`.
- [ ] Blank or unmapped `Status` with `Available=True` -> `available`.
- [ ] Blank or unmapped `Status` with `Available=False` preserves raw `status = unavailable`.
- [ ] Blank or unmapped `Status` with `Available=False` sets `analysis_status = booked`.
- [ ] Explicit status matches set `status_confidence = high`.
- [ ] `Available=True` inference sets `status_confidence = high`.
- [ ] `Available=False` inference sets `status_confidence = low`.

## 180-Day Filter

- [ ] Rows before `run_date` are excluded.
- [ ] Rows from `run_date` through `run_date + 179 days` are included.
- [ ] Rows on or after `run_date + 180 days` are excluded.

## Failed-Run Manifest

- [ ] A failed run writes `manifest.json`.
- [ ] A failed run overwrites any previous success manifest.
- [ ] Failed manifest has `status = "failed"`.
- [ ] Failed manifest preserves available values:
  - `run_date`
  - `listing_id`
  - `source_file`
  - `standardized_file`
  - `raw_row_count`
  - `standardized_row_count`
- [ ] Failed manifest uses `null` for values unavailable at failure time.

## Price Occ Benchmark Design

- [ ] Current future pricing export remains the operational source.
- [ ] Price Occ file is benchmark/enrichment only.
- [ ] Practical join is `stay_date` to Price Occ `Date`.
- [ ] Minimum Price Occ design columns are present:
  - `Date`
  - `Market Occupancy`
  - `Market 50th Percentile Price`
- [ ] Daily comparisons use price benchmark fields only.
- [ ] Occupancy comparisons using `Market Occupancy` are window-level only.
- [ ] No Price Occ field replaces operational `listing_id`, `min_stay`, or `status`.
- [ ] Price Occ enrichment remains separate from the operational standardized transform.

## Historical Monthly Source Design

- [ ] Historical monthly file is separate from the operational future source.
- [ ] Historical monthly file is separate from the Price Occ future benchmark source.
- [ ] Minimum historical monthly columns are present:
  - `month_year`
  - `Revenue`
  - `Occupancy`
  - `Booked Occupancy`
  - `Blocked Occupancy`
  - `ADR`
- [ ] Optional comparison fields may be used later for LY/STLY and YoY review.
- [ ] Historical monthly source is used for monthly revenue, ADR, occupancy, blocked occupancy, and revenue pace review only.
- [ ] Historical monthly source is not used for the operational daily transform.
- [ ] Blank historical values are not treated as zero unless explicitly documented later.
- [ ] Historical source implementation is deferred.

## Enriched Future-Analysis Dataset Design

- [ ] Enriched future-analysis dataset does not replace the operational standardized dataset.
- [ ] Grain is one row per `stay_date`.
- [ ] Operational columns are carried through:
  - `run_date`
  - `listing_id`
  - `stay_date`
  - `nightly_price`
  - `min_stay`
  - `status`
- [ ] Price Occ required enrichment columns are documented:
  - `market_occupancy`
  - `market_50th_price`
  - `market_75th_price`
- [ ] Price Occ optional enrichment columns are documented:
  - `market_25th_price`
  - `market_90th_price`
  - `median_booked_price`
  - `last_seen_price`
  - `final_price`
  - `holiday_event`
- [ ] Join rule is `operational.stay_date = Price Occ Date`.
- [ ] Daily enriched dataset supports price benchmark analysis, not daily occupancy comparison.
- [ ] Window-level occupancy metrics are produced only by the separate future window summary.
- [ ] Enriched dataset implementation preserves operational row count unless duplicate Price Occ dates are found.

## Future Window Summary

- [ ] Input file is `analysis/future_daily_pricing_enriched_<run_date>.csv`.
- [ ] Output file is `analysis/future_window_summary_<run_date>.csv`.
- [ ] Required input columns are present:
  - `run_date`
  - `listing_id`
  - `stay_date`
  - `nightly_price`
  - `analysis_status`
  - `status_confidence`
  - `market_occupancy`
  - `market_75th_price`
- [ ] Output has exactly three rows:
  - `days_0_15`
  - `days_16_45`
  - `days_46_90`
- [ ] `days_0_15` covers `run_date` through `run_date + 14 days`.
- [ ] `days_16_45` covers `run_date + 15 days` through `run_date + 44 days`.
- [ ] `days_46_90` covers `run_date + 45 days` through `run_date + 89 days`.
- [ ] Output columns are present in this exact order:

```text
run_date,listing_id,window_name,listing_booked_pct,market_occupancy_avg,occupancy_vs_market_pct,booked_days,low_confidence_booked_days,blocked_days,avg_available_price,avg_market_75th_price,price_vs_market_75th_pct,avg_booked_price_proxy
```

- [ ] `listing_booked_pct` uses `analysis_status = booked`.
- [ ] `occupancy_vs_market_pct` is `listing_booked_pct - market_occupancy_avg`.
- [ ] `low_confidence_booked_days` counts booked rows with `status_confidence = low`.
- [ ] `avg_available_price` uses available rows only.
- [ ] `avg_booked_price_proxy` uses booked rows only and is not treated as final ADR.
- [ ] No daily market occupancy vs single-listing occupancy comparison is produced.

## Future Window Signals

- [ ] Input file is `analysis/future_window_summary_<run_date>.csv`.
- [ ] Output file is `analysis/future_window_signals_<run_date>.csv`.
- [ ] Required input columns are present:
  - `run_date`
  - `listing_id`
  - `window_name`
  - `occupancy_vs_market_pct`
  - `price_vs_market_75th_pct`
  - `low_confidence_booked_days`
- [ ] Output has exactly three rows:
  - `days_0_15`
  - `days_16_45`
  - `days_46_90`
- [ ] Output columns are present in this exact order:

```text
run_date,listing_id,window_name,pace_status,price_position_status,confidence_note,urgency_flag,short_reason
```

- [ ] `pace_status` uses `occupancy_vs_market_pct`.
- [ ] `price_position_status` uses `price_vs_market_75th_pct`.
- [ ] `confidence_note` uses `low_confidence_booked_days`.
- [ ] `urgency_flag` maps behind-market pace to `critical_now`, `advisory`, or `info_watch` by horizon bucket.
- [ ] Signal output is a compact label layer, not a full recommendation engine.

## Settings History Design

- [ ] Settings snapshot output is documented:
  - `analysis/pricelabs_settings_snapshot_<run_date>.json`
- [ ] Snapshot grain is one snapshot per `run_date` for one `listing_id`.
- [ ] JSON is the preferred snapshot format for complex settings traceability.
- [ ] Required snapshot fields are documented:
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
  - `occupancy_based_adjustments_snapshot`
  - `custom_seasonality_factor`
  - `length_of_stay_based_pricing`
  - `demand_factor_sensitivity`
  - `far_out_premium`
  - `safety_minimum_price_rule`
- [ ] `length_of_stay_based_pricing` uses structured keys such as `1_night`, `2_nights`, `3_nights`, and `4_plus_nights`.
- [ ] `orphan_day_prices` uses structured weekday/weekend adjustment fields plus `gap_rule` fields.
- [ ] `minimum_stay_settings` uses structured sections for profile, default, last-minute, far-out, orphan gaps, and lowest allowed min-stay.
- [ ] `occupancy_based_adjustments` stores static mode separately, such as `mode`.
- [ ] `occupancy_based_adjustments_snapshot` stores horizon buckets such as `days_0_15`, `days_16_30`, and `days_31_60`.
- [ ] Optional `raw_text` is preserved for traceability where complex settings are manually copied.
- [ ] Snapshot output preserves nested JSON objects without flattening structured sections into strings.
- [ ] Settings changes output is documented:
  - `analysis/pricelabs_settings_changes_<run_date>.csv`
- [ ] Settings changes compare current snapshot to previous snapshot.
- [ ] Settings changes emit one row per changed field.
- [ ] Settings changes minimum columns are documented:
  - `run_date`
  - `listing_id`
  - `field_name`
  - `previous_value`
  - `current_value`
  - `changed_flag`
- [ ] Signal change review output is documented:
  - `analysis/future_signal_change_review_<run_date>.csv`
- [ ] Signal change review compares the current and previous signal reports.
- [ ] Signal change review uses `days_0_15`, `days_16_45`, and `days_46_90`.
- [ ] Signal change review includes settings change count and summary.
- [ ] Design states that settings/signal comparison is directional, not causal proof.
- [ ] Settings capture automation is deferred.

## Out Of Scope

- [ ] No browser automation.
- [ ] No scheduling.
- [ ] No dashboards.
- [ ] No Airbnb.
- [ ] No multi-listing support.
