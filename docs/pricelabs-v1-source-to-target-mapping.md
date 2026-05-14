# PriceLabs V1 Source-to-Target Mapping

Status: Deprecated / historical reference.
This document may describe an earlier pipeline version. Current source strategy is defined in `docs/data-source-strategy-v1.md` and `docs/project-artifact-audit-v1.md`.

This document records the exact V1 mapping from the current PriceLabs export into the standardized daily pricing dataset.

Target file:

```text
standardized/future_daily_pricing_<run_date>.csv
```

## Mapping

| PriceLabs export source field | V1 target field | Source note |
| --- | --- | --- |
| `Listing ID` | `listing_id` | Direct mapping from export row. |
| `Date` | `stay_date` | Direct mapping from export row. |
| `Your Price` | `nightly_price` | Direct mapping from export row. |
| `Min Stay` | `min_stay` | Direct mapping from export row. |
| `Status` | `status` | Direct mapping from export row. |
| Pipeline metadata | `run_date` | Provided by pipeline metadata, not by the PriceLabs row. |

## V1 Required Target Columns

- `run_date`
- `listing_id`
- `stay_date`
- `nightly_price`
- `min_stay`
- `status`

## Scope

This file documents mapping only. It does not define extraction, validation behavior, business rules, or analytical calculations.

## Price Occ Benchmark Mapping Design

The current PriceLabs future pricing export remains the operational source for the standardized V1 output. The Price Occ file is a benchmark/enrichment source only.

File:

```text
sample_data/Price Occ for 650255___717243.csv
```

Practical join:

| Standardized field | Price Occ field | Note |
| --- | --- | --- |
| `stay_date` | `Date` | Minimal date-level join. |

Benchmark fields from the actual file:

| Price Occ field | Intended use |
| --- | --- |
| `Market 50th Percentile Price` | Primary market price benchmark. |
| `Market 25th Percentile Price` | Lower market price band. |
| `Market 75th Percentile Price` | Upper market price band. |
| `Market 90th Percentile Price` | High market price band. |
| `Market Occupancy` | Window-level occupancy benchmark only. |
| `Median Booked Price` | Booked-date value benchmark context. |
| `Number of Bookings` | Booked-date/window demand context. |
| `7-day market pickup` | Window-level demand context. |
| `Holiday/Event` | Date context for pricing review. |

Limits:

- No `listing_id` column is present.
- No `Min Stay` column is present.
- This source must not replace the operational mapping for `listing_id`, `nightly_price`, `min_stay`, or `status`.

## Historical Monthly Source Mapping Design

The historical monthly file is for historical analysis only and is not mapped into the operational daily standardized output.

File:

```text
sample_data/Monthly Trends for 650255___717243.csv
```

Minimum source fields:

| Historical field | Intended use |
| --- | --- |
| `month_year` | Monthly period key. |
| `Revenue` | Monthly revenue trend and revenue pace. |
| `Occupancy` | Monthly occupancy trend. |
| `Booked Occupancy` | Monthly booked occupancy context. |
| `Blocked Occupancy` | Monthly blocked occupancy trend. |
| `ADR` | Monthly ADR trend. |

Optional comparison fields:

| Historical field | Intended use |
| --- | --- |
| `Revenue (LY)` | Prior-year revenue comparison. |
| `Revenue (STLY)` | Same-time-last-year revenue comparison. |
| `Revenue STLY YoY Difference` | Revenue pace comparison. |
| `Occupancy (LY)` | Prior-year occupancy comparison. |
| `Occupancy (STLY)` | Same-time-last-year occupancy comparison. |
| `Occupancy STLY YoY Difference %` | Occupancy pace comparison. |
| `ADR (LY)` | Prior-year ADR comparison. |
| `ADR (STLY)` | Same-time-last-year ADR comparison. |
| `ADR STLY YoY Difference` | ADR pace comparison. |

Limits:

- Monthly grain only.
- No daily operational fields such as `stay_date`, `nightly_price`, `min_stay`, or `status`.
- Blank values may indicate missing data rather than zero.
