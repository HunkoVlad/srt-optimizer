# PriceLabs Weekly CSV Contract V1

Status: Current V1
Owner: SRT pipeline
Scope: Manual weekly PriceLabs pipeline for one listing

This contract defines the current Python-only V1 pipeline shape:

```text
manual raw PriceLabs files -> standardized daily CSV -> enriched daily CSV -> analysis/settings outputs
```

V1 is manual and local. It does not include browser automation, scheduling, Airbnb data, dashboards, or monthly revenue pace.

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

Current window summaries use market 75th percentile as context only. Revenue pace is the business goal, but `monthly_revenue_pace` is not implemented in V1 Step 1.

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
- No monthly revenue pace output.
- No final realized ADR claims from `upcoming_adr` or `booked_revenue_proxy`.
