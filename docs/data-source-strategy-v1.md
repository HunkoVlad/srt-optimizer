# Data Source Strategy V1

## Purpose

This document defines which source owns each metric, what should be downloaded weekly, what can be downloaded once or occasionally for historical backfill, and how revenue definitions should stay separate.

The goal is to keep future revenue proxies, historical actuals, market benchmarks, settings history, and Airbnb conversion context clearly labeled before adding more data sources.

## Current Core Pipeline Sources

Required weekly PriceLabs files:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
data/runs/<run_date>/raw/price_occ.csv
data/runs/<run_date>/raw/pricelabs_settings_manual_input.json
data/runs/<run_date>/raw/monthly_trends.csv
data/runs/<run_date>/raw/bookings_report.xlsx
```

`priceLabs_future_export.csv` role:

- future listing calendar
- status
- nightly price / open ask
- min stay
- `ADR` -> `upcoming_adr`
- booked revenue proxy
- open revenue ask

`price_occ.csv` role:

- market occupancy
- market price percentiles
- median booked price
- final price / last seen price
- holiday/event context
- market context only
- must not provide `upcoming_adr`

`pricelabs_settings_manual_input.json` role:

- PriceLabs rule snapshot
- settings changes
- rule-performance context

`monthly_trends.csv` role:

- primary monthly revenue, occupancy, and ADR truth
- current-month revenue captured
- historical monthly actuals when present
- known future on-the-books monthly revenue when PriceLabs provides it
- prevents double-counting future booked proxy and monthly revenue actuals
- source label owner for `monthly_trends_current`, `monthly_trends_actuals`, and `monthly_trends_future_on_books`

`bookings_report.xlsx` role:

- reservation-level booking truth
- cleaning proxy from booked reservations
- length-of-stay context
- booking-window context
- booking source mix
- booked-night totals for stay/cleaning efficiency metrics
- revenue-per-cleaning denominator when Monthly Trends revenue is available

## Historical Backfill Sources

`KPIs On The Books (current year).xlsx`:

Optional/deprecated historical actuals source for now. `monthly_trends.csv` is the primary monthly truth source.

Useful fields:

- Bookable Nights
- Booked Nights
- Paid Occupancy %
- Occupancy %
- Rental ADR
- Rental RevPAR
- Total Revenue

Use for:

- historical monthly revenue actuals
- historical booked nights
- historical occupancy
- historical ADR
- historical RevPAR
- historical layer in rolling 13-month view

`Revenue On The Books.xlsx`:

Secondary/optional historical source. Do not use it as the primary source for the current monthly reporting flow.

Use only if the KPI file lacks a needed metric or reconciliation is required.

## Airbnb Sources

Airbnb is a separate source, not a replacement for PriceLabs revenue definitions.

Useful Airbnb fields may include:

- bookings
- booking value
- nights booked
- average daily rate
- average length of stay
- average booking window
- view-to-contact rate
- contact-to-book rate
- listing performance/conversion fields

Important revenue-definition rule:

Airbnb revenue can differ from PriceLabs revenue because Airbnb may deduct its service fee, around 15.5%, before showing revenue.

Therefore:

- Do not mix Airbnb revenue directly into PriceLabs revenue proxy fields.
- Airbnb should be used mainly for conversion/listing-performance context unless a dedicated Airbnb revenue metric is created.
- If Airbnb revenue is used later, label it separately, for example `airbnb_booking_value` or `airbnb_net_revenue`.

## Metric Ownership Matrix

| metric | primary_source | secondary_source | notes |
| --- | --- | --- | --- |
| `booked_revenue_proxy` | `priceLabs_future_export.csv` | `monthly_trends.csv` | Future export proxy is used only when Monthly Trends does not provide monthly revenue. |
| `open_revenue_ask` | `priceLabs_future_export.csv` | none | Derived from available-date asking price. |
| `total_future_revenue_proxy` | monthly revenue pace output | none | Monthly Trends revenue when available plus future export open ask; avoids double counting future booked proxy. |
| `historical_total_revenue` | `monthly_trends.csv` | `KPIs On The Books (current year).xlsx` | Historical actual, separate from future proxy. |
| `historical_booked_nights` | `monthly_trends.csv` | `bookings_report.xlsx` for future coverage validation later | Historical booked nights are estimated from Monthly Trends revenue / ADR because historical Bookings Report coverage can be partial. |
| `historical_occupancy_pct` | `monthly_trends.csv` | none | Monthly Trends is the main occupancy display source. |
| `historical_adr` | `monthly_trends.csv` | Airbnb report if separately labeled | Keep Airbnb ADR separate if definitions differ. |
| `market_occupancy` | `price_occ.csv` | none | Market context only; aggregate before comparing to listing occupancy. |
| `market_price_percentiles` | `price_occ.csv` | none | Context only; market 75th percentile is not a target. |
| `booking_window` | `bookings_report.xlsx` | Airbnb report later | Use mainly for conversion/listing-performance context. |
| `average_length_of_stay` | `bookings_report.xlsx` | Airbnb report later | Current weekly cleaning/LOS metrics come from Bookings Report. |
| `booking_source_mix` | `bookings_report.xlsx` | Airbnb report later | Context only; no channel-specific revenue adjustment yet. |
| `listing_conversion` | Airbnb report | none | Useful for view/contact/book funnel context. |
| `settings_snapshot` | `pricelabs_settings_manual_input.json` | future automated settings capture | Manual for now. |
| `settings_changes` | settings snapshot comparison | none | Rule-performance context. |

## Monthly Reporting Source Labels

Use explicit source labels in the rolling view and reports:

- `monthly_trends_current`: current run-date month uses Monthly Trends for captured revenue/ADR/occupancy and the future calendar export for open ask.
- `monthly_trends_actuals`: historical month uses Monthly Trends actuals.
- `monthly_trends_future_on_books`: future month has Monthly Trends revenue already on the books.
- `future_calendar`: future month uses only future calendar export proxy/open ask.
- `partial_horizon`: future export only covers part of the final horizon month.
- `no_source_data`: no monthly row exists outside the historical quality-review path.
- `data_not_available`: historical month has missing, zero, or suspicious Monthly Trends values and should not be used as a trend point.

Do not display `available` as a source label for monthly report rows.

Historical Monthly Trends rows are usable only when revenue, occupancy, and ADR are present and greater than zero. Historical revenue below `$1,000` is treated as `data_not_available` unless exact Bookings Report reservations support the month.

Historical booked nights and cleanings use this source priority:

1. Estimate booked nights from Monthly Trends revenue divided by Monthly Trends ADR.
2. Estimate cleanings from estimated booked nights divided by observed average LOS from current/future Bookings Report rows in the rolling period.
3. Otherwise mark the trend value as `data_not_available`.

Bookings Report is not treated as exact historical truth because historical coverage can be partial unless a future enhancement validates coverage.

Reports show `Booked Nights` and `Cleanings / Stays` as separate metrics. `Revenue / Cleaning` uses `Cleanings / Stays` as the denominator, not booked nights. Historical rows with missing, zero, or suspicious Monthly Trends values should display `data_not_available` with blank/dash metric fields rather than `$0` or `0.0%`.

Booking source mix is analysis context only for now. Airbnb, Vrbo, direct, and other/unknown stay counts are exposed from Bookings Report, but revenue adjustments by source are not implemented yet.

## Weekly Download Requirements

Required weekly now:

- `priceLabs_future_export.csv`
- `price_occ.csv`
- `pricelabs_settings_manual_input.json`
- `monthly_trends.csv`
- `bookings_report.xlsx`

Optional weekly/monthly later:

- PriceLabs KPIs On The Books, optional/deprecated for now
- Revenue On The Books, optional/deprecated reconciliation source only
- Airbnb monthly/listing performance report

## One-Time / Occasional Historical Backfill

Use Monthly Trends first to backfill historical months that PriceLabs future exports do not cover. KPIs On The Books is optional/deprecated for now and should be used only for reconciliation or missing fields.

Do not fake historical data. If no source exists for a historical month, keep:

- `data_availability = no_source_data`

## Implementation Roadmap

Current Step 26 source model:

Normalize Monthly Trends and Bookings Report into monthly truth and booking metrics.

Next documentation/cleanup steps:

- Keep contracts/runbooks aligned to Monthly Trends + Bookings Report.
- Archive or retire KPI-only artifacts only after review.

Later data-source expansion:

Add Airbnb listing/conversion context.

Later reporting expansion:

Create email delivery automation only after the raw-file workflow and scheduler wrapper are stable.

## Guardrails

- Market 75th percentile is context only.
- Do not mix Airbnb net revenue with PriceLabs gross/proxy revenue without labeling.
- Historical actuals and future proxies must stay distinguishable.
- Recommendations must remain based on rule-performance logic, not blind market matching.
- PriceLabs executes rules; our pipeline evaluates rule effectiveness.
