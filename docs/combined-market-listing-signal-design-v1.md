# Combined Market Listing Signal Design V1

## Purpose

This document defines a future combined signal layer that connects PriceLabs market and revenue context with Airbnb visibility and conversion diagnostics.

The layer should answer three revenue-management questions before recommendations are made:

- What is market health doing?
- Is Aloha Poconos moving with or against the market?
- Does the pattern justify investigation, monitoring, or a PriceLabs rule-area review?

This is a design document only. It does not add implementation, scheduler changes, email sending changes, or automation.

## Source Of Truth Boundaries

PriceLabs remains the source of truth for:

- revenue
- occupancy
- ADR
- booked nights
- booking totals
- cleaning count
- monthly revenue pace
- market occupancy and market benchmark context

Airbnb remains diagnostic only for:

- page views
- first-page search impressions
- wishlist additions
- overall conversion rate
- search-to-listing conversion
- listing-to-booking conversion
- similar-listing benchmark

Airbnb data may raise or lower investigation priority. Airbnb data must not directly recommend PriceLabs rule changes, and it must not be used as the source of truth for revenue, ADR, occupancy, booked nights, booking totals, cleaning count, or monthly revenue pace.

## Core Questions

### Market Health In The Past Week

The combined layer should evaluate whether PriceLabs market context is strengthening, stable, weakening, or unavailable.

Examples:

- Is PriceLabs market occupancy or demand improving or weakening?
- Is market pacing up or down?
- Is market benchmark context strengthening or softening?
- Are upcoming open dates exposed because the market is weak or because listing-specific visibility is weak?

### Listing Correlation With Market

The combined layer should compare listing movement against market movement at window or week level.

Examples:

- Is Aloha Poconos moving with the market?
- Is Aloha outperforming the market?
- Is Aloha underperforming while the market improves?

Do not compare single-listing daily occupancy directly to daily market occupancy. Market/listing comparison should be at window, weekly, or monthly level.

### Divergence And Investigation Signals

The layer should flag deeper investigation when:

- PriceLabs market trend is up or stable and Airbnb listing visibility or conversion trend is down.
- PriceLabs market occupancy is above listing booked occupancy.
- Market demand strengthens while listing revenue pace or open value does not improve.

If booked occupancy is less than or equal to market occupancy, treat the signal as urgent.

## Required Input Files

### PriceLabs And Core Analysis

The future combined layer should reference these PriceLabs and core pipeline files when present:

- `analysis/monthly_revenue_summary_<run_date>.md`
- `analysis/email_revenue_report_<run_date>.md`
- `analysis/future_daily_pricing_enriched_<run_date>.csv`
- future window signals / future signals, if available
- `raw/price_occ.csv` as market context only
- `analysis/monthly_revenue_pace_<run_date>.csv`
- `analysis/future_window_summary_<run_date>.csv`
- `analysis/future_window_signals_<run_date>.csv`
- `analysis/performance_reason_review_<run_date>.csv`

### Airbnb Diagnostic Inputs

The future combined layer should reference these Airbnb diagnostic files when present:

- `analysis/airbnb_weekly_conversion_summary_<run_date>.csv`
- `analysis/airbnb_weekly_history_comparison_<run_date>.csv`
- `analysis/airbnb_daily_week_over_week_conversion_<run_date>.csv`
- `analysis/airbnb_daily_week_average_deviation_<run_date>.csv`
- `analysis/airbnb_similar_listing_summary_<run_date>.csv`
- `analysis/airbnb_daily_similar_listing_comparison_<run_date>.csv`

Airbnb inputs are diagnostic context only. They should never replace PriceLabs or core pipeline values.

## Combined Signal Categories

### Healthy Alignment

Category: `healthy_alignment`

Pattern:

- Market trend up.
- Listing trend up.

Meaning:

- Listing is moving with the market.
- Protect premium positioning.
- No Airbnb-driven discounting.

Typical priority: `none` or `low`

Allowed recommendation scope: monitor or no change.

### Market Softness

Category: `market_softness`

Pattern:

- Market trend down.
- Listing trend down.

Meaning:

- Weakness may be broader market softness.
- Do not blame listing conversion too quickly.
- PriceLabs market and revenue context is required before any rule change.

Typical priority: `low` or `medium`

Allowed recommendation scope: monitor unless PriceLabs revenue and occupancy data justify a rule-area review.

### Listing Outperforming Market

Category: `listing_outperforming_market`

Pattern:

- Market trend down.
- Listing trend up.

Meaning:

- Listing is competitive despite weaker market.
- Protect pricing.
- Avoid unnecessary discounts.

Typical priority: `none` or `low`

Allowed recommendation scope: no change or monitor.

### Outperformance Pricing-Efficiency Investigation

Category: `outperformance_pricing_efficiency_investigation`

Pattern:

- PriceLabs market trend is down or soft.
- Listing trend is up or materially stronger than market.
- Airbnb listing is above similar listings.
- Revenue pace, ADR, or open ask suggests the listing may be selling too easily.

Meaning:

- Listing is outperforming the market.
- This is positive, but it may indicate pricing power.
- Investigate whether base price, far-out premium, LOS discounts, orphan discount, or last-minute rules are too soft.
- Do not automatically raise prices.
- Only recommend PriceLabs rule changes if revenue pace, ADR, booking pace, and cleaning efficiency support it.

Typical priority: `medium`

Priority should become `high` if the listing is outperforming while ADR/open ask is weak or cleanings are high.

Allowed recommendation scope: investigate pricing efficiency first; consider PriceLabs rule-area review only with supporting PriceLabs revenue, ADR, booking pace, and cleaning-efficiency evidence.

### Listing-Specific Investigation Needed

Category: `listing_specific_investigation`

Pattern:

- Market trend up or stable.
- Listing trend down.

Meaning:

- Strong signal for deeper investigation.
- Check Airbnb visibility, similar-listing benchmark, conversion, PriceLabs open ask, minimum stay, LOS, orphan rules, and revenue pace.
- Do not automatically recommend discounts.
- PriceLabs rule changes are allowed only if PriceLabs revenue, occupancy, market, and calendar context supports them.

Typical priority: at least `high`

Allowed recommendation scope: investigate listing/conversion first; consider PriceLabs rule-area review only with supporting PriceLabs evidence.

### Urgent Revenue Occupancy Gap

Category: `urgent_revenue_occupancy_gap`

Pattern:

- Booked occupancy is less than or equal to market occupancy.

Meaning:

- Urgent review required.
- Analyze revenue pace vs target, open ask, cleaning efficiency, last-minute settings, orphan rules, LOS rules, and minimum stay.
- Recommendations must be through PriceLabs settings only.

Typical priority: `urgent`

Allowed recommendation scope: PriceLabs rule-area review may be considered if core PriceLabs evidence supports it.

### Insufficient Data

Category: `insufficient_data`

Pattern:

- Required market, listing, Airbnb, or revenue context is missing or not comparable.

Meaning:

- Do not assign cause.
- Do not recommend PriceLabs rule changes.

Typical priority: `none` or `low`

Allowed recommendation scope: collect/validate data.

## Future Output Concept

Future output:

`data/runs/<run_date>/analysis/combined_market_listing_signal_<run_date>.csv`

Suggested columns:

- `run_date`
- `window_name`
- `window_start`
- `window_end`
- `market_health_signal`
- `listing_airbnb_signal`
- `revenue_pace_signal`
- `occupancy_gap_signal`
- `cleaning_efficiency_signal`
- `combined_signal_category`
- `investigation_priority`
- `explanation`
- `allowed_recommendation_scope`
- `data_quality_status`
- `notes`

Allowed `combined_signal_category` values:

- `healthy_alignment`
- `market_softness`
- `listing_outperforming_market`
- `outperformance_pricing_efficiency_investigation`
- `listing_specific_investigation`
- `urgent_revenue_occupancy_gap`
- `insufficient_data`

Allowed `investigation_priority` values:

- `none`
- `low`
- `medium`
- `high`
- `urgent`

## Decision Rules

1. Airbnb data can increase or decrease investigation priority.
2. Airbnb data cannot directly recommend PriceLabs rule changes.
3. PriceLabs revenue pace, occupancy, market context, and cleaning efficiency decide whether PriceLabs settings need changes.
4. If market trend is up or stable and listing trend is down, mark at least `high` investigation priority.
5. If booked occupancy is less than or equal to market occupancy, mark `urgent`.
6. If listing is outperforming similar listings but revenue pace is weak, investigate PriceLabs/open calendar context before Airbnb listing quality.
7. If listing is weak versus similar listings and PriceLabs market is healthy, investigate listing visibility and conversion deeply.
8. If the market is soft but the listing is materially outperforming and ADR/open ask or cleaning efficiency suggests the listing may be selling too easily, mark `outperformance_pricing_efficiency_investigation`.
9. Do not recommend manual calendar edits.
10. Recommendations, when allowed, must be PriceLabs rule-area recommendations only.

## Example Interpretations

### Market Stable, Airbnb Visibility Down

Combined signal: `listing_specific_investigation`

Explanation:

Market context appears stable or improving, but Airbnb visibility is below recent baseline. Similar-listing benchmark should be checked before assigning cause. PriceLabs revenue pace and occupancy gap decide whether settings changes are justified.

### Market Weak, Airbnb Visibility Down

Combined signal: `market_softness`

Explanation:

Airbnb visibility is down, but market context is also weak. Do not treat Airbnb decline as a listing-specific problem until market context improves or listing underperformance becomes clear.

### Listing Beats Similar Listings, Revenue Pace Weak

Combined signal: `listing_specific_investigation` or `urgent_revenue_occupancy_gap`, depending on occupancy gap.

Explanation:

Airbnb benchmark is favorable, so the first investigation should focus on PriceLabs/open calendar context, revenue pace, open ask, stay rules, LOS, orphan rules, and minimum stay.

### Listing Beats Market While Pricing Looks Soft

Combined signal: `outperformance_pricing_efficiency_investigation`

Explanation:

The listing is outperforming a soft market and may have pricing power. This should trigger a pricing-efficiency review, not an automatic price increase. Check PriceLabs revenue pace, ADR, open ask, booking pace, cleaning efficiency, base price, far-out premium, LOS discounts, orphan discount, and last-minute rules before allowing a rule-area recommendation.

### Booked Occupancy Less Than Or Equal To Market Occupancy

Combined signal: `urgent_revenue_occupancy_gap`

Explanation:

Urgent review is required even if Airbnb visibility looks healthy. PriceLabs market and revenue context should drive any allowed rule-area recommendation.

## Future Email Behavior

The weekly email should eventually include a concise “Market vs Listing Signal” section before recommendations.

Example wording:

> Market/listing signal: Listing-specific investigation needed. Market context appears stable or improving, but Airbnb visibility is below recent baseline. Similar-listing benchmark remains favorable, so this is not yet a clear listing-quality issue. PriceLabs revenue pace and occupancy gap should decide whether settings changes are needed.

The section should remain short and should not repeat the full Airbnb diagnostic report.

## Forbidden Behavior

The combined layer must not:

- Use Airbnb as source of truth for revenue, ADR, occupancy, booked nights, booking totals, cleaning count, or monthly revenue pace.
- Recommend manual calendar edits.
- Recommend PriceLabs changes from Airbnb alone.
- Add scheduler changes in this design step.
- Change Gmail or email send mode in this design step.
- Treat Airbnb similar-listing comparison as a revenue or occupancy benchmark.

## Implementation Status

Status: design only.

No parser, pipeline, scheduler, email sending, or report integration changes are included in this step.
