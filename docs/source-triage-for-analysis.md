# Source Triage For Analysis

This document summarizes the three PriceLabs source roles for analysis and design. It does not define new automation or change the current V1 transform.

## 1. Operational Future Source

Source name: PriceLabs future daily export

Example file:

```text
sample_data/pricelabs_future_export_sample.csv
```

Grain: daily

Primary purpose: operational V1 transform source for the standardized future daily pricing dataset.

Required fields:

- `Listing ID`
- `Date`
- `Your Price`
- `Min Stay`
- `Status`
- `Available`

Useful optional fields:

- `Available`
- `Recommended Price`
- `Price with Default Customization`
- `ADR`
- `Booked Date`

Should not be used for:

- Market benchmark analysis by itself.
- Historical monthly performance review.
- Multi-listing workflows.

Allowed analysis level:

- Daily: yes, for listing price, status, and min-stay review.
- Window-level: yes, after aggregation.
- Monthly: only after aggregation; not a historical source.

Join keys:

- Primary key in standardized output: `run_date`, `listing_id`, `stay_date`.
- Join to Price Occ benchmark source: `stay_date` = Price Occ `Date`.

Main risks / limitations:

- One listing only in V1.
- Booked-date `nightly_price` is a provisional booked-value proxy, not final realized ADR.
- Raw `status` is preserved for source traceability.
- Analysis uses `analysis_status`, `status_confidence`, and `status_reason`.
- Blank/unmapped `Status` with `Available=True` is treated as available for analysis with high confidence.
- Blank/unmapped `Status` with `Available=False` is treated as likely booked for analysis with low confidence.

## 2. Benchmark/Enrichment Future Source

Source name: PriceLabs Price Occ benchmark export

Example file:

```text
sample_data/Price Occ for 650255___717243.csv
```

Grain: daily

Primary purpose: market benchmark and enrichment context for future dates.

Required fields:

- `Date`
- `Market Occupancy`
- `Market 50th Percentile Price`

Useful optional fields:

- `Market 25th Percentile Price`
- `Market 75th Percentile Price`
- `Market 90th Percentile Price`
- `Median Booked Price`
- `Number of Bookings`
- `7-day market pickup`
- `Prices with Default Customization`
- `Holiday/Event`

Should not be used for:

- Replacing the operational future source.
- Producing `listing_id`, `min_stay`, or operational `status`.
- Daily market occupancy vs single-listing occupancy comparison.

Allowed analysis level:

- Daily: yes, for market price benchmark and event context.
- Window-level: required for occupancy comparisons.
- Monthly: only after aggregation; not a historical monthly source.

Join keys:

- `Date` to standardized `stay_date`.

Main risks / limitations:

- No `listing_id` column.
- No `Min Stay` column.
- Listing-specific occupancy fields are not trusted yet because the file has no `listing_id`.
- `Market Occupancy` must be aggregated before comparison to listing occupancy.

## 3. Historical Monthly Performance Source

Source name: PriceLabs Monthly Trends export

Example file:

```text
sample_data/Monthly Trends for 650255___717243.csv
```

Grain: monthly

Primary purpose: historical revenue, ADR, occupancy, blocked occupancy, and revenue pace context.

Required fields:

- `month_year`
- `Revenue`
- `Occupancy`
- `Booked Occupancy`
- `Blocked Occupancy`
- `ADR`

Useful optional fields:

- `Revenue (LY)`
- `Revenue (STLY)`
- `Revenue STLY YoY Difference`
- `Occupancy (LY)`
- `Occupancy (STLY)`
- `Occupancy STLY YoY Difference %`
- `ADR (LY)`
- `ADR (STLY)`
- `ADR STLY YoY Difference`

Should not be used for:

- Operational daily transform logic.
- Daily price/status/min-stay analysis.
- Daily joins as if monthly rows were stay dates.

Allowed analysis level:

- Daily: no.
- Window-level: no, unless a future design explicitly derives windows from monthly data.
- Monthly: yes.

Join keys:

- `month_year` for monthly trend analysis.
- No direct join to daily standardized rows in V1.

Main risks / limitations:

- Monthly only.
- Blank values may mean missing data, not zero.
- Completeness may vary by month.

## Recommended Analysis Usage

Use the operational future source when the business question is about current listing-level future dates:

- What is the current asking price?
- What is the current min-stay rule?
- Is the date available, booked, blocked, or unavailable?

Use the Price Occ benchmark source when the business question needs market context:

- How does current open-date price compare with market price percentiles?
- Is a future date affected by event context?
- How does listing booked share compare with market occupancy over isolated 0-15, 16-45, and 46-90-day horizon buckets?

Use the historical monthly source when the business question is historical performance:

- How are monthly revenue, ADR, and occupancy trending?
- How much blocked occupancy exists by month?
- How does revenue pace compare with annual goals or LY/STLY fields?

Use one source alone when the question matches its grain and role. Combine operational future and Price Occ data for future date price benchmark analysis using `stay_date` = `Date`. Use historical monthly data separately for monthly trend context.

## Proposed Enriched Future-Analysis Dataset

Name:

```text
analysis/future_daily_pricing_enriched_<run_date>.csv
```

Role: analysis-oriented daily dataset combining operational future rows with Price Occ benchmark fields. It does not replace the operational standardized dataset.

Grain: one row per `stay_date`.

Carry through from operational source:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`
- `analysis_status`
- `status_confidence`
- `status_reason`

Add from Price Occ:

- Required: `market_occupancy`, `market_50th_price`, `market_75th_price`
- Optional: `market_25th_price`, `market_90th_price`, `median_booked_price`, `last_seen_price`, `final_price`, `holiday_event`

Join:

- `operational.stay_date` = Price Occ `Date`

Use for:

- Available-date pricing analysis
- Booked-date value review
- Market pricing position review

Do not use for:

- Direct daily market occupancy vs single-listing occupancy comparison.
- Window-level occupancy metrics, which belong in the isolated horizon-bucket summary dataset.

## Future Window Summary Dataset

Name:

```text
analysis/future_window_summary_<run_date>.csv
```

Role: compact decision-support summary built from the enriched daily future-analysis dataset.

Grain: one row per isolated horizon bucket: `days_0_15`, `days_16_45`, and `days_46_90`.

Bucket definitions:

- `days_0_15`: immediate action zone, `stay_date` from `run_date` through `run_date + 14 days`.
- `days_16_45`: advisory zone, `stay_date` from `run_date + 15 days` through `run_date + 44 days`.
- `days_46_90`: informational / watch zone, `stay_date` from `run_date + 45 days` through `run_date + 89 days`.

Required fields:

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

Use for:

- Window-level listing booked share versus market occupancy.
- Available-date asking-price posture versus market 75th percentile.
- Booked-date value proxy review, kept separate from asking-price posture.
- Low-confidence booked day visibility.

Do not use for:

- Daily occupancy comparison.
- Treating asking-price averages as ADR.
- Recommendation scoring.
- Weighted confidence math.

## Future Window Signal Dataset

Name:

```text
analysis/future_window_signals_<run_date>.csv
```

Role: compact rule-based labels built from the isolated future window summary.

Grain: one row per isolated horizon bucket: `days_0_15`, `days_16_45`, and `days_46_90`.

Required fields:

- `run_date`
- `listing_id`
- `window_name`
- `pace_status`
- `price_position_status`
- `confidence_note`
- `urgency_flag`
- `short_reason`

Use for:

- Quick pace label from `occupancy_vs_market_pct`.
- Quick price-position label from `price_vs_market_75th_pct`.
- Low-confidence booked-day visibility.
- Near-term urgency triage.

Do not use for:

- Automated pricing changes.
- Full recommendation scoring.
- Weighted confidence math.

## PriceLabs Settings History Layer

Source name: PriceLabs settings snapshot

Example file:

```text
analysis/pricelabs_settings_snapshot_<run_date>.json
```

Grain: one snapshot per `run_date` for one listing

Primary purpose: preserve the PriceLabs strategy settings active at a run date, then compare settings changes against movement in future window signals.

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
- `occupancy_based_adjustments_snapshot`
- `custom_seasonality_factor`
- `length_of_stay_based_pricing`
- `demand_factor_sensitivity`
- `far_out_premium`
- `safety_minimum_price_rule`

Useful optional fields:

- Raw copied/exported settings text.
- Section labels or source notes for complex rule blocks.
- Capture timestamp if it differs from `run_date`.

Structured settings guidance:

- `orphan_day_prices` should preserve `weekday.adjustment`, `weekend.adjustment`, and `gap_rule` fields for min/max gaps and application horizon, with `raw_text` retained if useful.
- `minimum_stay_settings` should preserve `profile_name`, `default`, `last_minute`, `far_out`, `orphan_gaps`, and `lowest_minstay_allowed`, with `raw_text` retained if useful.
- `length_of_stay_based_pricing` should use stable keys such as `1_night`, `2_nights`, `3_nights`, and `4_plus_nights`, with `raw_text` retained if useful.
- `occupancy_based_adjustments` should separate static mode, such as `mode = "Market Driven"`.
- `occupancy_based_adjustments_snapshot` should preserve dynamic horizon buckets such as `days_0_15`, `days_16_30`, and `days_31_60`, with `adjustment` and `market_position_note`.
- Structured fields are the primary comparison source; raw text is backward traceability.
- Snapshot handling preserves nested objects as-is and does not flatten structured sections.

Should not be used for:

- Replacing the operational future source.
- Proving that a settings change caused a signal change.
- Automated pricing changes.

Allowed analysis level:

- Snapshot-level: yes.
- Change-level: yes, compared to the previous snapshot.
- Window-level: yes, only when paired with `future_window_signals`.

Derived changes file:

```text
analysis/pricelabs_settings_changes_<run_date>.csv
```

Minimum columns: `run_date`, `listing_id`, `field_name`, `previous_value`, `current_value`, `changed_flag`.

Signal comparison file:

```text
analysis/future_signal_change_review_<run_date>.csv
```

Minimum columns: `run_date`, `prior_run_date`, `listing_id`, `window_name`, `previous_pace_status`, `current_pace_status`, `previous_price_position_status`, `current_price_position_status`, `previous_urgency_flag`, `current_urgency_flag`, `changed_settings_count`, `changed_settings_summary`, `interpretation_note`.

Main risks / limitations:

- No automated settings capture yet.
- Complex settings may need raw text preservation before reliable parsing.
- Signal movement after a settings change is directional evidence only, not causal proof.

Invalid comparisons:

- Daily market occupancy vs single-listing daily occupancy.
- Monthly historical rows treated as daily stay-date rows.
- Price Occ used as the source for operational `listing_id`, `min_stay`, or `status`.
- Historical monthly source used as input to the daily transform.
