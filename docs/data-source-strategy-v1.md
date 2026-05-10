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

## Historical Backfill Sources

`KPIs On The Books (current year).xlsx`:

Primary historical actuals source.

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

Secondary/optional historical source.

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
| `booked_revenue_proxy` | `priceLabs_future_export.csv` | none | Derived from future export `ADR` / `upcoming_adr`; proxy, not historical actual. |
| `open_revenue_ask` | `priceLabs_future_export.csv` | none | Derived from available-date asking price. |
| `total_future_revenue_proxy` | monthly revenue pace output | none | Sum of booked proxy plus open ask. |
| `historical_total_revenue` | `KPIs On The Books (current year).xlsx` | `Revenue On The Books.xlsx` | Historical actual, separate from future proxy. |
| `historical_booked_nights` | `KPIs On The Books (current year).xlsx` | Airbnb report if clearly labeled | Prefer PriceLabs KPI for revenue/occupancy consistency. |
| `historical_occupancy_pct` | `KPIs On The Books (current year).xlsx` | none | Use KPI definitions. |
| `historical_adr` | `KPIs On The Books (current year).xlsx` | Airbnb report if separately labeled | Keep Airbnb ADR separate if definitions differ. |
| `market_occupancy` | `price_occ.csv` | none | Market context only; aggregate before comparing to listing occupancy. |
| `market_price_percentiles` | `price_occ.csv` | none | Context only; market 75th percentile is not a target. |
| `booking_window` | Airbnb report | PriceLabs if available later | Use mainly for conversion/listing-performance context. |
| `average_length_of_stay` | Airbnb report | PriceLabs future proxy fields | Keep source definition visible. |
| `listing_conversion` | Airbnb report | none | Useful for view/contact/book funnel context. |
| `settings_snapshot` | `pricelabs_settings_manual_input.json` | future automated settings capture | Manual for now. |
| `settings_changes` | settings snapshot comparison | none | Rule-performance context. |

## Weekly Download Requirements

Required weekly now:

- `priceLabs_future_export.csv`
- `price_occ.csv`
- `pricelabs_settings_manual_input.json`

Optional weekly/monthly later:

- PriceLabs KPIs On The Books
- Airbnb monthly/listing performance report

## One-Time / Occasional Historical Backfill

Use PriceLabs KPI On The Books to backfill historical months that PriceLabs future exports do not cover.

Do not fake historical data. If no source exists for a historical month, keep:

- `data_availability = no_source_data`

## Implementation Roadmap

Step 12:

Normalize PriceLabs KPI On The Books into a monthly historical actuals file.

Step 13:

Merge KPI historical actuals into `rolling_13_month_revenue_view`.

Step 14:

Update monthly revenue summary to show historical actuals instead of `no_source_data` where available.

Step 15:

Add Airbnb listing/conversion context.

Step 16:

Create email-ready report.

## Guardrails

- Market 75th percentile is context only.
- Do not mix Airbnb net revenue with PriceLabs gross/proxy revenue without labeling.
- Historical actuals and future proxies must stay distinguishable.
- Recommendations must remain based on rule-performance logic, not blind market matching.
- PriceLabs executes rules; our pipeline evaluates rule effectiveness.
