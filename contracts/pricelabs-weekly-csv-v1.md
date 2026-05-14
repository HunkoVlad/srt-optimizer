# PriceLabs Weekly CSV Contract V1

Status: Current V1
Owner: SRT pipeline
Scope: Manual weekly PriceLabs pipeline for one listing

This contract defines the current Python-only V1 pipeline shape:

```text
manual raw PriceLabs files -> standardized daily CSV -> enriched daily CSV -> monthly revenue pace -> analysis/settings outputs
```

V1 is local and raw-file driven. It does not include browser download automation, Airbnb data, dashboards, or automatic pricing-rule changes. The scheduler wrapper is a safe local runner around the same raw-file pipeline.

## Run Folder Contract

Real weekly runs live under:

```text
data/runs/<run_date>/
```

Required raw input files:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
data/runs/<run_date>/raw/price_occ.csv
data/runs/<run_date>/raw/monthly_trends.csv
data/runs/<run_date>/raw/bookings_report.xlsx
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

Raw files are the source of truth. Generated outputs are reproducible and should not be treated as primary input.

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

### Monthly Trends Source

File:

```text
data/runs/<run_date>/raw/monthly_trends.csv
```

Role: required monthly truth source for captured revenue, occupancy, and ADR.

Required source fields:

- `month_year`
- `Revenue`
- `Occupancy`
- `Booked Occupancy`
- `Blocked Occupancy`
- `ADR`

Rules:

- `month_year` normalizes to `month` as `YYYY-MM`.
- Revenue and ADR are numeric.
- Occupancy values are numeric percentage values.
- Monthly Trends is primary for current-month captured revenue, occupancy, and ADR.
- Monthly Trends historical rows are the primary historical actuals source when they pass quality checks.
- Monthly Trends future rows may represent known on-the-books revenue and must not be double-counted with future export booked proxy.

### Bookings Report Source

File:

```text
data/runs/<run_date>/raw/bookings_report.xlsx
```

Role: required reservation-level source for current/future cleanings, stays, length of stay, booking window, and booking source mix.

Useful source fields:

- `Listing ID`
- `Reservation ID`
- `Check-in Date`
- `Check-out Date`
- `Booked Date`
- `Booking Status`
- `Booking Source`
- `Length of Stay (Days)`
- `Booking Window (Days)`
- `Average Daily Rate`
- `Rental Revenue`
- `Total Revenue`

Rules:

- Count only booked reservations for booking metrics.
- `stay_month` is based on `Check-in Date` month for this contract.
- Booking source mix is informational only and does not adjust revenue.
- Bookings Report is not treated as exact historical truth unless a future enhancement validates historical coverage.

### Settings Source

File:

```text
data/runs/<run_date>/raw/pricelabs_settings_manual_input.json
```

Role: required manual PriceLabs rule snapshot input.

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

## Monthly Trends Normalization Step 26 Contract

Output:

```text
data/runs/<run_date>/analysis/monthly_trends_normalized_<run_date>.csv
```

Generated from:

```text
data/runs/<run_date>/raw/monthly_trends.csv
```

Role: normalize PriceLabs Monthly Trends into monthly truth fields for revenue, occupancy, and ADR.

Required output columns:

- `run_date`
- `month`
- `monthly_trends_revenue`
- `monthly_trends_occupancy_pct`
- `monthly_trends_booked_occupancy_pct`
- `monthly_trends_blocked_occupancy_pct`
- `monthly_trends_adr`
- `monthly_trends_source`

Rules:

- `month_year` values such as `May 2026` normalize to `YYYY-MM`.
- Revenue and ADR are numeric.
- Occupancy fields are numeric percentage values, for example `45` means `45%`.
- `monthly_trends_source = pricelabs_monthly_trends`.

## Bookings Report Normalization Step 26 Contract

Outputs:

```text
data/runs/<run_date>/analysis/bookings_report_normalized_<run_date>.csv
data/runs/<run_date>/analysis/monthly_booking_metrics_<run_date>.csv
```

Generated from:

```text
data/runs/<run_date>/raw/bookings_report.xlsx
```

Role: normalize reservation rows and aggregate monthly booking, cleaning, LOS, booking-window, and booking-source metrics.

Required normalized reservation columns:

- `run_date`
- `listing_id`
- `reservation_id`
- `check_in_date`
- `check_out_date`
- `booked_date`
- `stay_month`
- `booking_status`
- `booking_source`
- `length_of_stay_days`
- `booking_window_days`
- `average_daily_rate`
- `rental_revenue`
- `total_revenue`

Required monthly booking metrics columns:

- `run_date`
- `month`
- `bookings_report_bookings`
- `bookings_report_cleanings_proxy`
- `bookings_report_booked_nights`
- `bookings_report_avg_los`
- `bookings_report_rental_revenue`
- `bookings_report_total_revenue`
- `bookings_report_adr`
- `bookings_report_avg_booking_window`
- `airbnb_stays`
- `vrbo_stays`
- `direct_stays`
- `other_unknown_stays`
- `main_booking_source`
- `booking_source_mix_summary`

Rules:

- Count booked reservations for monthly booking metrics.
- `bookings_report_cleanings_proxy` equals booked reservation count for now.
- `bookings_report_booked_nights` sums `Length of Stay (Days)`.
- `bookings_report_avg_los = bookings_report_booked_nights / bookings_report_bookings`.
- `bookings_report_adr = bookings_report_rental_revenue / bookings_report_booked_nights`.
- Booking source mix counts reservations/stays, not nights.
- Airbnb, Vrbo, direct, and other/unknown source labels are normalized for analysis context only.
- Booking source does not change revenue values in this contract.

## Monthly Revenue Pace Step 2-3 Contract

Output:

```text
data/runs/<run_date>/analysis/monthly_revenue_pace_<run_date>.csv
```

Generated from:

```text
data/runs/<run_date>/analysis/future_daily_pricing_enriched_<run_date>.csv
data/runs/<run_date>/analysis/monthly_trends_normalized_<run_date>.csv
data/runs/<run_date>/analysis/monthly_booking_metrics_<run_date>.csv
```

Role: aggregation and diagnostic-only monthly revenue pace view from the enriched daily file, Monthly Trends, and Bookings Report metrics. It does not implement PriceLabs recommendation logic.

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
- `monthly_trends_revenue`
- `monthly_trends_occupancy_pct`
- `monthly_trends_booked_occupancy_pct`
- `monthly_trends_blocked_occupancy_pct`
- `monthly_trends_adr`
- `monthly_trends_source`
- `bookings_report_bookings`
- `bookings_report_cleanings_proxy`
- `bookings_report_booked_nights`
- `bookings_report_avg_los`
- `bookings_report_rental_revenue`
- `bookings_report_total_revenue`
- `bookings_report_adr`
- `bookings_report_avg_booking_window`
- `airbnb_stays`
- `vrbo_stays`
- `direct_stays`
- `other_unknown_stays`
- `main_booking_source`
- `booking_source_mix_summary`
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

Step 26 source precedence rules:

- Current month captured revenue, occupancy, and ADR use Monthly Trends when available.
- Current month open ask continues to come from the future export.
- Current month total calendar value is Monthly Trends revenue plus future export open ask when Monthly Trends revenue exists.
- Do not add future export booked proxy on top of Monthly Trends revenue for a month that has Monthly Trends revenue.
- Current/future cleanings and LOS use Bookings Report metrics when available.
- Future months use future export proxy/open ask unless Monthly Trends provides known on-the-books monthly revenue.
- Historical months use Monthly Trends as the primary actuals source when the row passes quality checks.
- KPI On The Books and Revenue On The Books are not primary sources for this contract.

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

- Current month can be `conversion_risk` when captured/booked revenue is low but total calendar value is at or above target.
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
- Historical `no_source_data` and `data_not_available` months must appear in the table.
- Historical Monthly Trends actual months must appear in the table when available.
- `no_source_data` rows use `revenue_pace_status = no_source_data`.
- `no_source_data` rows use `month_action_level = monitor`.
- `no_source_data` rows must not create advisory or concern bullets.
- Historical actual rows must not create Critical Now, Advisory, or Protect recommendations.
- `partial_horizon` rows must not create advisory or concern bullets.
- If historical actuals are available, Executive Summary should state which months have historical actuals and that missing historical months remain `no_source_data` or `data_not_available`.
- If no historical actuals are available, Executive Summary must include: `Historical months without source data are shown for context.`
- Executive Summary must always include: `Market benchmark is context only.`

Executive Decision View:

- Appears after Executive Summary and before Monthly Revenue Pace.
- Groups actionable current/future months by `month_action_level`.
- Summarizes existing diagnostic statuses only.
- Must not include PriceLabs rule recommendations.
- Market benchmark remains context only.

For Executive Decision View, actionable rows are current/future rows with `data_availability` in `monthly_trends_current`, `monthly_trends_future_on_books`, `future_calendar`, or `partial_horizon`.

`Critical Now` group:

- Includes actionable months where `month_action_level = critical_now`.
- If there are no matching months, show `None.`

`Advisory` group:

- Includes actionable months where `month_action_level = advisory`.
- Each row should include `stay_month`, `revenue_pace_status`, revenue captured, total calendar value, and `cleaning_efficiency_status`.

`Protect` group:

- Includes actionable months where `month_action_level = protect`.
- Each row should include `stay_month`, `revenue_pace_status`, and total calendar value.

`Monitor` group:

- Includes actionable months where `month_action_level = monitor`.

Executive Decision View rules:

- `no_source_data`, `data_not_available`, and historical actual rows must not be listed as action items.
- `partial_horizon` rows must not be listed as advisory.
- This section does not create pricing recommendations.

Interpretation:

- Appears after Executive Decision View and before Monthly Revenue Pace.
- Explains existing diagnostic statuses in plain English.
- Uses rows where `data_availability` has current/future Monthly Trends, future calendar, partial horizon, or valid historical Monthly Trends actuals.
- Keeps wording concise.
- Does not create PriceLabs setting recommendations.

Interpretation rules:

- `conversion_risk`: explain that captured/booked revenue is low while total calendar value is at or above target. This means the issue is conversion risk, not weak open calendar value.
- `protect_open_value`: explain that far-out open calendar value is healthy and supports protecting premium positioning.
- `inefficient`: explain that revenue per cleaning is below the current efficiency threshold and should be monitored as a booking-quality concern.
- `partial_horizon`: explain that only part of the month is inside the current export horizon, so it should not be judged against the full monthly target.
- `historical_actuals` or `monthly_trends_actuals`: explain that historical actuals are available from PriceLabs Monthly Trends, including captured revenue, occupancy, and ADR.
- `data_not_available`: explain that missing, zero, or suspicious historical monthly rows are excluded from decision signals.
- Historical occupancy in the summary uses Monthly Trends when the month passes quality checks.
- Historical booked nights are estimated from Monthly Trends revenue divided by Monthly Trends ADR.
- Historical cleanings are estimated from Monthly Trends booked-night estimates and observed current/future Bookings Report LOS when available.
- `no_source_data`: historical `no_source_data` rows should not create month-level interpretation bullets because they are already covered in the Executive Summary.

Interpretation text must not mention changing base price, min price, LOS, discounts, orphan rules, or other PriceLabs settings.

Limits:

- Step 4/6/7/8 is reporting, decision grouping, and interpretation only.
- It does not create PriceLabs recommendations.
- It does not create pricing recommendations.
- It does not modify window signals.
- Market benchmark remains context only.

## Email Revenue Report Step 16 Contract

Output:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

Generated from:

```text
data/runs/<run_date>/analysis/rolling_13_month_revenue_view_<run_date>.csv
data/runs/<run_date>/analysis/monthly_revenue_summary_<run_date>.md
```

Purpose: concise email-ready markdown report for the weekly revenue snapshot, analysis, and recommendation review.

Required sections:

- Subject line.
- Executive Snapshot.
- What Needs Attention.
- What To Protect.
- Recommendation Review.
- Key Monthly Snapshot.
- Data Notes.

Rules:

- This file is email-ready content only.
- It must not send email.
- It must not include manual date-level recommendations.
- It must not include exact price recommendations.
- It must keep Airbnb revenue separate unless a dedicated Airbnb field is added later.
- Historical `no_source_data` rows should be excluded from the Key Monthly Snapshot.
- Historical actuals should be included where available.
- Partial horizon months may be included as monitor context.
- Market benchmark remains context only.

Limits:

- Step 16 is the final report content layer before optional email delivery.
- It does not modify metric calculations, recommendation logic, or window signals.

## Email Draft And SMTP Send Step 19/21 Contract

Generated outputs:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.eml
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.html
```

Source:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

Behavior:

- The email report `.md` is always generated.
- The local `.eml` draft file is always generated.
- The HTML email report is always generated.
- SMTP send mode is optional and explicit.
- SMTP send mode must not change revenue calculations, recommendation logic, or window signals.

Default development config:

```toml
[email]
mode = "draft"

[smtp]
enabled = false
```

Real send requires both:

```toml
[email]
mode = "send"

[smtp]
enabled = true
```

Credential rules:

- Gmail App Password must be stored in environment variable `ALOHA_GMAIL_APP_PASSWORD`.
- The environment variable name is configured by `[smtp].password_env_var`.
- Passwords must not be stored in `config/email.toml`.
- Passwords and real credentials must not be committed.
- A persistent Windows user environment variable can be used for scheduled automation later.

Failure behavior:

- If `config/email.toml` is missing, send is skipped and `.eml` remains available.
- If `[email].mode = "draft"`, send is skipped and `.eml` remains available.
- If send mode is enabled and the password environment variable is missing, the pipeline fails clearly at `Email send mode`.
- For development, switch back to draft mode to avoid sending test emails.

Step 22 HTML report:

Output:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.html
```

Source:

```text
data/runs/<run_date>/analysis/email_revenue_report_<run_date>.md
```

Purpose: readable HTML version of the weekly revenue email report for Gmail/SMTP delivery.

Rules:

- Markdown report is still generated.
- Plain-text `.eml` draft is still generated.
- HTML report is generated for readable email delivery.
- HTML uses simple inline/internal styling.
- No external CSS.
- No images.
- No scripts.
- SMTP sender may use HTML when `config/email.toml` has:

```toml
[report]
format = "html"
```

- If `[report].format = "markdown"`, sender uses plain text.
- Draft mode still skips sending.
- Send mode still requires:
  - `[email].mode = "send"`
  - `[smtp].enabled = true`
  - `ALOHA_GMAIL_APP_PASSWORD` available in the environment.

## Rolling 13-Month Revenue View Step 5 Contract

Output:

```text
data/runs/<run_date>/analysis/rolling_13_month_revenue_view_<run_date>.csv
```

Generated from:

```text
data/runs/<run_date>/analysis/monthly_revenue_pace_<run_date>.csv
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
- Historical months with missing, zero, or suspicious Monthly Trends values must use `data_availability = data_not_available`, `revenue_pace_status = data_not_available`, and `month_action_level = monitor`.

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
- `monthly_trends_revenue`
- `monthly_trends_occupancy_pct`
- `monthly_trends_booked_occupancy_pct`
- `monthly_trends_blocked_occupancy_pct`
- `monthly_trends_adr`
- `monthly_trends_source`
- `bookings_report_bookings`
- `bookings_report_cleanings_proxy`
- `bookings_report_booked_nights`
- `bookings_report_avg_los`
- `bookings_report_rental_revenue`
- `bookings_report_total_revenue`
- `bookings_report_adr`
- `bookings_report_avg_booking_window`
- `airbnb_stays`
- `vrbo_stays`
- `direct_stays`
- `other_unknown_stays`
- `main_booking_source`
- `booking_source_mix_summary`
- `month_time_bucket`
- `revenue_pace_status`
- `cleaning_efficiency_status`
- `month_action_level`
- `historical_bookable_nights`
- `historical_booked_nights`
- `historical_booked_nights_source`
- `historical_cleanings_proxy`
- `historical_cleanings_source`
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

- `monthly_trends_current`
- `monthly_trends_actuals`
- `monthly_trends_future_on_books`
- `future_calendar`
- `partial_horizon`
- `no_source_data`
- `data_not_available`
- `historical_actuals` only for deprecated KPI-era artifacts

`revenue_pace_status` additionally allows:

- `historical_actuals`
- `data_not_available`

Current Monthly Trends historical rules:

- Historical actuals come from Monthly Trends when revenue, occupancy, and ADR are present and greater than zero.
- Historical revenue below `$1,000` is treated as `data_not_available` unless a future validation rule changes that decision.
- If Monthly Trends actuals pass quality checks:
  - `data_availability = monthly_trends_actuals`
  - `revenue_pace_status = historical_actuals`
  - `month_action_level = monitor`
- If no valid monthly source exists:
  - `data_availability = data_not_available` or `no_source_data`
  - `revenue_pace_status = data_not_available` or `no_source_data`
  - keep `month_action_level = monitor`
- Do not fake historical values.

Historical booked nights and cleanings:

- `historical_booked_nights = round(monthly_trends_revenue / monthly_trends_adr)` for valid historical Monthly Trends rows.
- `historical_booked_nights_source = estimated_from_monthly_trends`.
- `historical_cleanings_proxy = round(historical_booked_nights / observed_avg_los)` when observed average LOS can be calculated from current/future Bookings Report rows.
- `historical_cleanings_source = estimated_from_monthly_trends` when that estimate is available.
- Monthly Trends occupancy is the main displayed historical occupancy for valid historical months.
- `historical_calendar_occupancy_pct` is retained only for compatibility with older outputs and should not replace Monthly Trends occupancy in the current summary.
- Do not use historical Bookings Report rows as exact historical truth unless a future enhancement validates historical coverage.

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

## Deprecated Optional KPI Historical Actuals Contract

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
- This path is deprecated for the current monthly reporting flow.
- Monthly Trends is the primary monthly truth source for captured revenue, occupancy, and ADR.
- Revenue On The Books is not the primary source and should only be used for future reconciliation if explicitly designed.

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
- No Playwright download automation.
- No Windows Task Scheduler configuration in the pipeline contract.
- No Airbnb data.
- No dashboard.
- No recommendation logic.
- No final realized ADR claims from `upcoming_adr` or `booked_revenue_proxy`.
