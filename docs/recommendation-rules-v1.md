# Recommendation Rules V1

## Purpose

These rules define a future recommendation layer for the weekly report. They are design only and are not implemented yet.

The future recommendation layer should translate monthly diagnostic statuses into plain-English recommendation categories while keeping recommendation logic separate from metric calculations.

Current inputs:

- `rolling_13_month_revenue_view_<run_date>.csv`
- `monthly_revenue_summary_<run_date>.md`

Current diagnostic fields:

- `month_time_bucket`
- `month_scope_status`
- `data_availability`
- `revenue_pace_status`
- `cleaning_efficiency_status`
- `month_action_level`
- `booked_revenue_proxy`
- `open_revenue_ask`
- `total_future_revenue_proxy`
- `booked_revenue_pct_of_target`
- `total_future_revenue_pct_of_target`
- `revenue_per_cleaning_proxy`

Core rules:

- Do not recommend lowering price just because booked revenue is low.
- Market 75th percentile is context only, not a target.
- Protect premium positioning unless data clearly shows urgent revenue weakness.
- Current and next month can trigger advisory or critical review.
- Future and far-future months with strong open value should usually be protected.
- Cleaning efficiency matters because there is no cleaning fee.
- Recommendations should refer to PriceLabs rule areas only, not manual date edits.

## Allowed Recommendation Categories

- `critical_now`
- `advisory`
- `protect_no_change`
- `monitor`

## Allowed PriceLabs Rule Areas

- Booking Recency Factor
- last-minute behavior
- orphan discount
- minimum stay rules
- 1-night LOS premium
- 4+ night LOS discount
- far-out premium
- base/min price relationship
- seasonality/demand factor

## Recommendation Matrix

| month_time_bucket | revenue_pace_status | cleaning_efficiency_status | month_action_level | interpretation | recommendation_category | allowed_rule_area_to_review | prohibited_action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `current_month` | `urgent` | any | `critical_now` | Current-month total future value is materially below target. | `critical_now` | Booking Recency Factor; last-minute behavior; minimum stay rules | automatic base price reduction |
| `current_month` | `conversion_risk` | `inefficient` | `advisory` | Booked revenue is low, total future value is healthy, and revenue per cleaning is weak. | `advisory` | Booking Recency Factor; last-minute behavior; 1-night LOS premium | blanket discounting |
| `next_month` | `conversion_risk` | any | `advisory` | Next month has enough open value but booked revenue has not converted yet. | `advisory` | Booking Recency Factor; minimum stay rules; 1-night LOS premium | aggressive early discounting |
| `future_month` | `protect_open_value` | any | `protect` | Future-month open calendar value is healthy. | `protect_no_change` | far-out premium only if repeated weakness appears | lowering far-out pricing just to increase occupancy |
| `far_future_month` | `protect_open_value` | any | `protect` | Far-future open value is healthy and should not be pressured early. | `protect_no_change` | none unless repeated weak ask value appears | early discounting |
| any | `no_source_data` | any | `monitor` | No monthly source data is available. | `monitor` | none | any pricing conclusion |
| `far_future_month` | `partial_horizon` | any | `monitor` | Only part of the far-future month is visible in the export horizon. | `monitor` | none | judging against full monthly target |
| any | weak or `conversion_risk` | `inefficient` | `advisory` | Cleaning efficiency is weak and revenue status is also weak or conversion-risk. | `advisory` | 1-night LOS premium; orphan discount; minimum stay rules | penalizing one-night stays automatically |

## Plain-English Recommendation Style

Safe wording examples:

- “Review near-term conversion behavior before changing premium positioning.”
- “Protect far-out open value; no pricing-rule change is recommended now.”
- “Cleaning efficiency is weak, but this is a booking-quality signal, not an automatic pricing change.”

Prohibited wording examples:

- “Lower prices.”
- “Match the 75th percentile.”
- “Discount all open dates.”
- “Manually override these dates.”

## Implementation Notes For Later

Future Step 10 should generate recommendation text from this matrix. It should keep recommendation logic separate from metric calculations and should not mutate standardized, enriched, monthly pace, rolling view, or summary metrics.

Recommendation output should remain plain-English and rule-area oriented. It should not produce manual date edits or automatic PriceLabs setting changes.
