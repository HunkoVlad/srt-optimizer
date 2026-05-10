# PriceLabs Weekly CSV Contract V1

Status: Current V1
Owner: SRT pipeline
Scope: Manual weekly PriceLabs pipeline for one listing

This contract defines the current Python-only V1 pipeline shape:

```text
manual raw PriceLabs files -> standardized daily CSV -> enriched daily CSV -> monthly revenue pace -> analysis/settings outputs
```

V1 is manual and local. It does not include browser automation, scheduling, Airbnb data, dashboards, or recommendation logic.

## Run Folder Contract

Real weekly runs live under:

```text
data/runs/<run_date>/
```

Required raw input files:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
data/runs/<run_date>/raw/price_occ.csv
data/runs/<run_date>/raw/pricelabs_settings_manual_input.json
```

Canonical filename casing:

```text
priceLabs_future_export.csv
```

Generated outputs are reproducible from the raw inputs and live under:

```text
data/runs/<run_date>/standardized/
data/runs/<run_date>/analysis/
data/runs/<run_date>/settings/
```

`sample_data/` is debug/test fixture data only. It is not operational input for real weekly runs.

## Source Roles

### Operational Future Source

File:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
```

Role: primary listing-level calendar source for the operational transform.

Required source fields:

- `Date`
- `Listing ID`
- `Price with Default Customization` or `Your Price`
- `Min Stay`
- `Status`
- `ADR`

Important mapping:

- `ADR` -> `upcoming_adr`

The raw future export is the authority for listing identity, stay dates, nightly asking price, min stay, status interpretation, and upcoming ADR proxy.

### Price Occ Benchmark Source

File:

```text
data/runs/<run_date>/raw/price_occ.csv
```

Role: market/context enrichment only.

Minimum useful source fields:

- `Date`
- `Market Occupancy`
- `Market 50th Percentile Price`
- `Market 75th Percentile Price`

Useful optional fields:

- `Market 25th Percentile Price`
- `Market 90th Percentile Price`
- `Median Booked Price`
- `Last Seen Price`
- `Final Price`
- `Holiday/Event`

Rules:

- Join to operational data on `Date` = `stay_date`.
- Do not use `price_occ.csv` for `upcoming_adr`.
- Do not use `price_occ.csv` as the sole operational source.
- Do not compare daily market occupancy directly to single-listing daily occupancy.

## Standardized Daily Contract

Output:

```text
data/runs/<run_date>/standardized/future_daily_pricing_<run_date>.csv
```

Grain:

- One row per `run_date`, `listing_id`, and `stay_date`.

Required output columns:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`
- `upcoming_adr`
- `analysis_status`
- `status_confidence`
- `status_reason`

Source-to-target mapping:

| Source field | Target field |
| --- | --- |
| pipeline metadata | `run_date` |
| `Listing ID` | `listing_id` |
| `Date` | `stay_date` |
| `Your Price` or `Price with Default Customization` | `nightly_price` |
| `Min Stay` | `min_stay` |
| `Status` plus availability fields | `status` |
| `ADR` | `upcoming_adr` |

Status interpretation keeps the raw operational `status` and adds analysis-aware fields:

- `analysis_status`
- `status_confidence`
- `status_reason`

## Enriched Daily Step 1 Contract

Output:

```text
data/runs/<run_date>/analysis/future_daily_pricing_enriched_<run_date>.csv
```

Role: analysis-oriented daily file combining operational future rows with Price Occ market/context fields and Step 1 revenue-proxy fields. It does not replace the standardized daily output.

Grain:

- One row per standardized `stay_date`.

Required operational carry-through columns:

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`
- `upcoming_adr`
- `analysis_status`
- `status_confidence`
- `status_reason`

Required Step 1 revenue-proxy columns:

- `booked_revenue_proxy`
- `open_revenue_ask`
- `previous_status`
- `previous_upcoming_adr`
- `booked_stay_start_proxy`
- `booked_stay_id_proxy`

Required market/context columns:

- `market_occupancy`
- `market_50th_price`
- `market_75th_price`

Optional market/context columns may include:

- `market_25th_price`
- `market_90th_price`
- `median_booked_price`
- `last_seen_price`
- `final_price`
- `holiday_event`

Step 1 business rules:

- `booked_revenue_proxy` = `upcoming_adr` when `status = booked`, else `0`.
- `open_revenue_ask` = `nightly_price` when `status = available`, else `0`.
- Unavailable, blocked, and unbookable rows contribute `0` to both revenue fields.
- `booked_stay_start_proxy = 1` when current `status = booked` and either previous status is not booked or rounded `upcoming_adr` differs from rounded `previous_upcoming_adr`.
- `booked_stay_id_proxy` is populated only for booked rows.
- Non-booked rows have null/blank `booked_stay_id_proxy`.

Limits:

- These are proxy fields, not exact reservation records.
- `upcoming_adr` comes from the raw future export `ADR` field.
- `price_occ.csv` must not provide `upcoming_adr`.

## Monthly Revenue Pace Step 2-3 Contract

Output:

```text
data/runs/<run_date>/analysis/monthly_revenue_pace_<run_date>.csv
```

Generated from:

```text
data/runs/<run_date>/analysis/future_daily_pricing_enriched_<run_date>.csv
```

Role: aggregation and diagnostic-only monthly revenue pace view from the enriched daily file. It does not implement PriceLabs recommendation logic.

Grain:

- One row per `run_date`, `listing_id`, and `stay_month`.
- `stay_month` is `YYYY-MM` from `stay_date`.

Required output columns:

- `run_date`
- `listing_id`
- `stay_month`
- `month_time_bucket`
- `days_in_scope`
- `days_in_month`
- `month_scope_status`
- `booked_nights`
- `available_nights`
- `unavailable_nights`
- `booked_revenue_proxy`
- `open_revenue_ask`
- `total_future_revenue_proxy`
- `monthly_target`
- `booked_gap_to_target`
- `total_gap_to_target`
- `booked_cleanings_proxy`
- `avg_stay_length_proxy`
- `revenue_per_cleaning_proxy`
- `booked_revenue_pct_of_target`
- `total_future_revenue_pct_of_target`
- `revenue_pace_status`
- `cleaning_efficiency_status`
- `month_action_level`

Step 2 business rules:

- `booked_nights` = count rows where `status = booked`.
- `available_nights` = count rows where `status = available`.
- `unavailable_nights` = count rows where `status` is not booked and not available.
- `booked_revenue_proxy` = sum `booked_revenue_proxy` from enriched daily.
- `open_revenue_ask` = sum `open_revenue_ask` from enriched daily.
- `total_future_revenue_proxy` = `booked_revenue_proxy + open_revenue_ask`.
- `monthly_target` = `10000` for now.
- `booked_gap_to_target` = `monthly_target - booked_revenue_proxy`.
- `total_gap_to_target` = `monthly_target - total_future_revenue_proxy`.
- `booked_cleanings_proxy` = sum `booked_stay_start_proxy`.
- `avg_stay_length_proxy` = `booked_nights / booked_cleanings_proxy`, blank/null if no cleanings.
- `revenue_per_cleaning_proxy` = `booked_revenue_proxy / booked_cleanings_proxy`, blank/null if no cleanings.

Step 3 diagnostic rules:

- `booked_revenue_pct_of_target` = `booked_revenue_proxy / monthly_target`, rounded to 4 decimals.
- `total_future_revenue_pct_of_target` = `total_future_revenue_proxy / monthly_target`, rounded to 4 decimals.
- `days_in_scope` = number of enriched daily rows for the `stay_month`.
- `days_in_month` = calendar days in the `stay_month`.

`month_time_bucket` values:

- `current_month`: `stay_month` equals the `run_date` month.
- `next_month`: `stay_month` is one month after the `run_date` month.
- `future_month`: `stay_month` is 2-3 months after the `run_date` month.
- `far_future_month`: `stay_month` is 4+ months after the `run_date` month.

`month_scope_status` values:

- `full_month`: `days_in_scope = days_in_month`.
- `partial_month`: `days_in_scope < days_in_month`.

`revenue_pace_status` values:

- `on_track`
- `watch`
- `conversion_risk`
- `behind`
- `urgent`
- `protect_open_value`
- `partial_horizon`
- `no_source_data`

Time-aware revenue pace interpretation:

- Current month can be `conversion_risk` when booked revenue is low but total future value is at or above target.
- Current month can be `partial_month` but must still use normal current-month revenue diagnostics.
- Next month can also be `conversion_risk`, with lower booked-revenue thresholds than current month.
- Future and far-future months with strong total future revenue value should be `protect_open_value`, not `conversion_risk`.
- `partial_horizon` applies only when `month_scope_status = partial_month` and `month_time_bucket = far_future_month`.
- `partial_horizon` uses `revenue_pace_status = partial_horizon` and `month_action_level = monitor`.

`cleaning_efficiency_status` values:

- `no_booked_cleanings`
- `strong`
- `acceptable`
- `watch`
- `inefficient`

`month_action_level` values:

- `critical_now`
- `advisory`
- `monitor`
- `protect`

Limits:

- This is aggregation and diagnostic status labeling only.
- No PriceLabs recommendations are generated.
- Market 75th percentile remains context only.

## Monthly Revenue Summary Step 4/6 Contract

Output:

```text
data/runs/<run_date>/analysis/monthly_revenue_summary_<run_date>.md
```

Generated from:

```text
data/runs/<run_date>/analysis/rolling_13_month_revenue_view_<run_date>.csv
```

The summary no longer reads directly from:

```text
data/runs/<run_date>/analysis/monthly_revenue_pace_<run_date>.csv
```

Purpose: human-readable monthly revenue summary based on revenue pace, open ask, cleaning efficiency, and diagnostic statuses.

Required sections:

- `Monthly Revenue Summary - <run_date>` title.
- Executive summary bullets.
- Executive Decision View.
- Interpretation.
- Monthly revenue pace table.
- Key diagnostics.

Required behavior:

- The summary table must include all 13 months from the rolling view.
- The table must include six historical months, the current month, and six future months.
- Historical `no_source_data` months must appear in the table.
- Historical `historical_actuals` months must appear in the table when available.
- `no_source_data` rows use `revenue_pace_status = no_source_data`.
- `no_source_data` rows use `month_action_level = monitor`.
- `no_source_data` rows must not create advisory or concern bullets.
- `historical_actuals` rows must not create Critical Now, Advisory, or Protect recommendations.
- `partial_horizon` rows must not create advisory or concern bullets.
- If historical actuals are available, Executive Summary should state which months have historical actuals and that missing historical months remain `no_source_data`.
- If no historical actuals are available, Executive Summary must include: `Historical months without source data are shown for context.`
- Executive Summary must always include: `Market benchmark is context only.`

Executive Decision View:

- Appears after Executive Summary and before Monthly Revenue Pace.
- Groups available months by `month_action_level`.
- Summarizes existing diagnostic statuses only.
- Must not include PriceLabs rule recommendations.
- Market benchmark remains context only.

`Critical Now` group:

- Includes months where `data_availability = available` and `month_action_level = critical_now`.
- If there are no matching months, show `None.`

`Advisory` group:

- Includes months where `data_availability = available` and `month_action_level = advisory`.
- Each row should include `stay_month`, `revenue_pace_status`, booked revenue, total future value, and `cleaning_efficiency_status`.

`Protect` group:

- Includes months where `data_availability = available` and `month_action_level = protect`.
- Each row should include `stay_month`, `revenue_pace_status`, and total future value.

`Monitor` group:

- Includes months where `data_availability = available` and `month_action_level = monitor`.

Executive Decision View rules:

- `no_source_data` rows must not be listed as action items.
- `partial_horizon` rows must not be listed as advisory.
- This section does not create pricing recommendations.

Interpretation:

- Appears after Executive Decision View and before Monthly Revenue Pace.
- Explains existing diagnostic statuses in plain English.
- Uses rows where `data_availability = available` or `data_availability = historical_actuals`.
- Keeps wording concise.
- Does not create PriceLabs setting recommendations.

Interpretation rules:

- `conversion_risk`: explain that booked revenue is low while total future value is at or above target. This means the issue is conversion risk, not weak open calendar value.
- `protect_open_value`: explain that far-out open calendar value is healthy and supports protecting premium positioning.
- `inefficient`: explain that revenue per cleaning is below the current efficiency threshold and should be monitored as a booking-quality concern.
- `partial_horizon`: explain that only part of the month is inside the current export horizon, so it should not be judged against the full monthly target.
- `historical_actuals`: explain that historical actuals are available from PriceLabs KPI data, including total revenue, booked nights, and ADR.
- `suspicious`: append a caution note that the PriceLabs historical denominator should be reviewed before using occupancy as final truth.
- Historical occupancy in the summary is calculated from booked nights divided by calendar days in the month.
- `no_source_data`: historical `no_source_data` rows should not create month-level interpretation bullets because they are already covered in the Executive Summary.

Interpretation text must not mention changing base price, min price, LOS, discounts, orphan rules, or other PriceLabs settings.

Limits:

- Step 4/6/7/8 is reporting, decision grouping, and interpretation only.
- It does not create PriceLabs recommendations.
- It does not create pricing recommendations.
- It does not modify window signals.
- Market benchmark remains context only.

## Rolling 13-Month Revenue View Step 5 Contract

Output:

```text
data/runs/<run_date>/analysis/rolling_13_month_revenue_view_<run_date>.csv
```

Generated from:

```text
data/runs/<run_date>/analysis/monthly_revenue_pace_<run_date>.csv
```

May also be enriched by Step 13 from:

```text
data/runs/<run_date>/analysis/historical_monthly_actuals_<run_date>.csv
```

Purpose: stable monthly reporting window covering six months before the `run_date` month, the `run_date` month, and six months after the `run_date` month.

Required behavior:

- Output must always contain exactly 13 rows.
- `month_relative_index` must run from `-6` through `6`.
- `month_relative_index = 0` means the `run_date` month.
- Missing months from `monthly_revenue_pace_<run_date>.csv` must still appear.
- Missing months must use `data_availability = no_source_data`.
- Missing months must use `revenue_pace_status = no_source_data`.
- Missing months must use `month_action_level = monitor`.
- Historical revenue values must not be faked.

Required output columns:

- `run_date`
- `listing_id`
- `stay_month`
- `month_relative_index`
- `month_window_position`
- `data_availability`
- `days_in_scope`
- `days_in_month`
- `month_scope_status`
- `booked_nights`
- `available_nights`
- `unavailable_nights`
- `booked_revenue_proxy`
- `open_revenue_ask`
- `total_future_revenue_proxy`
- `monthly_target`
- `booked_gap_to_target`
- `total_gap_to_target`
- `booked_cleanings_proxy`
- `avg_stay_length_proxy`
- `revenue_per_cleaning_proxy`
- `booked_revenue_pct_of_target`
- `total_future_revenue_pct_of_target`
- `month_time_bucket`
- `revenue_pace_status`
- `cleaning_efficiency_status`
- `month_action_level`
- `historical_bookable_nights`
- `historical_booked_nights`
- `historical_paid_occupancy_pct`
- `historical_occupancy_pct`
- `historical_calendar_occupancy_pct`
- `historical_rental_adr`
- `historical_rental_revpar`
- `historical_total_revenue`
- `historical_source`
- `historical_data_quality_flag`

`month_window_position` values:

- `historical`
- `current`
- `future`

`data_availability` values:

- `available`
- `no_source_data`
- `historical_actuals`

`revenue_pace_status` additionally allows:

- `historical_actuals`

Step 13 historical merge rules:

- Historical actuals may merge only into historical rows.
- Current and future PriceLabs pace rows must not be overwritten by historical actuals.
- If historical actuals exist for a historical month:
  - `data_availability = historical_actuals`
  - `revenue_pace_status = historical_actuals`
  - `month_action_level = monitor`
- If no historical actuals exist:
  - keep `data_availability = no_source_data`
  - keep `revenue_pace_status = no_source_data`
  - keep `month_action_level = monitor`
- Do not fake historical values.

Step 15 calculated historical occupancy:

- `historical_calendar_occupancy_pct = historical_booked_nights / days_in_month * 100`.
- Use `historical_calendar_occupancy_pct` as the main displayed historical occupancy for single-listing analysis.
- `historical_occupancy_pct` remains the raw PriceLabs KPI reported occupancy.
- Preserve `historical_occupancy_pct` for debugging and source comparison.
- `monthly_revenue_summary_<run_date>.md` should display `historical_calendar_occupancy_pct` for `historical_actuals` rows.
- Do not use `historical_bookable_nights` as the main occupancy denominator in the summary.
- This avoids portfolio-style or PriceLabs-specific denominators when analyzing one listing.

`historical_data_quality_flag` values:

- `no_historical_source`
- `ok`
- `suspicious`

`suspicious` applies when any of these are true:

- `historical_bookable_nights > days_in_month * 1.5`
- `historical_booked_nights > historical_bookable_nights`
- `historical_total_revenue < 0`
- `historical_occupancy_pct > 100`
- `historical_rental_adr < 0`

Limits:

- Step 5 is reporting/structure only.
- It does not create PriceLabs recommendations.
- Suspicious historical data should not fail the pipeline.
- Suspicious means use caution, not discard.
- Historical actuals are context and should not create PriceLabs recommendations.
- PriceLabs KPI denominators may differ from calendar-day assumptions.
- Market benchmark remains context only.

## Historical Monthly Actuals Step 12 Contract

Output:

```text
data/runs/<run_date>/analysis/historical_monthly_actuals_<run_date>.csv
```

Source:

```text
data/runs/<run_date>/raw/kpis_on_the_books.xlsx
```

Source type: PriceLabs KPIs On The Books historical report.

Important:

- This file is optional.
- If `kpis_on_the_books.xlsx` is missing, the pipeline should continue without failing.

Required output columns:

- `run_date`
- `stay_month`
- `historical_bookable_nights`
- `historical_booked_nights`
- `historical_paid_occupancy_pct`
- `historical_occupancy_pct`
- `historical_rental_adr`
- `historical_rental_revpar`
- `historical_total_revenue`
- `historical_source`

`historical_source` value:

- `pricelabs_kpis_on_the_books`

Rules:

- `stay_month` is normalized to `YYYY-MM`.
- Currency values are numeric after removing currency symbols and commas.
- Percentage values remain numeric percentage values, not fractions.
- Blank or missing values remain blank/null.
- Total or summary rows are excluded.
- Rows without a valid `stay_month` are excluded.

## Analysis Rules

V1 keeps available-date pricing analysis separate from booked-date value analysis.

Available-date pricing analysis uses:

- `status = available`
- `nightly_price`
- `open_revenue_ask`
- Price Occ market price context
- `min_stay`

Booked-date value analysis uses:

- `status = booked`
- `upcoming_adr`
- `booked_revenue_proxy`
- `booked_stay_start_proxy`
- `booked_stay_id_proxy`

Daily comparisons allowed:

- Available-date asking price vs market price context.
- Booked-date revenue proxy review by date.
- Min-stay inspection by date.

Daily comparisons not allowed:

- Single-listing daily occupancy vs daily market occupancy.

Window-level comparisons allowed:

- Listing booked share vs average market occupancy.
- Asking-price posture vs market price context.
- Booked revenue proxy trends by window.
- Monthly revenue pace vs monthly target.

Current window summaries use market 75th percentile as context only. Revenue pace is the business goal, and Step 5 adds a stable rolling monthly reporting structure only.

## Settings Outputs

Settings snapshot:

```text
data/runs/<run_date>/settings/pricelabs_settings_snapshot_<run_date>.json
```

Settings changes, when a prior snapshot exists:

```text
data/runs/<run_date>/settings/pricelabs_settings_changes_<run_date>.csv
```

Settings files are analysis context. They do not change the operational transform or Step 1 revenue-proxy logic.

## Non-Goals

- No browser automation.
- No scheduler.
- No Airbnb data.
- No dashboard.
- No recommendation logic.
- No final realized ADR claims from `upcoming_adr` or `booked_revenue_proxy`.
