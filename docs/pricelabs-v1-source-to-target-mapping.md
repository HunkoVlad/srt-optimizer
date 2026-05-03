# PriceLabs V1 Source-to-Target Mapping

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
