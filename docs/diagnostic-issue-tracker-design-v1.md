# Diagnostic Issue Tracker Design V1

## Purpose

Weekly analysis is useful for the current operating decision, but it is not enough for recurring diagnostic patterns. Some issues only become meaningful when they persist, improve, or resolve across multiple weekly runs.

This design defines a persistent diagnostic issue tracker for recurring Airbnb and PriceLabs-core weaknesses. It is design only. It does not change recommendation logic, PriceLabs pricing rules, scheduler behavior, or email sending behavior.

PriceLabs remains the source of truth for revenue, occupancy, ADR, booked nights, booking totals, cleaning count, and monthly revenue pace. Airbnb remains diagnostic only for visibility, conversion, wishlist, and similar-listing context.

Airbnb issues can raise investigation priority. Airbnb issues cannot create PriceLabs recommendations by themselves.

## Why Weekly-Only Analysis Is Insufficient

A single weekly report can identify a signal, but it cannot reliably answer:

- Is this a new issue or a recurring issue?
- Did last week's investigation signal improve, worsen, or resolve?
- Is a weak conversion week isolated, or is it part of a pattern?
- Did a PriceLabs setting change precede a change in performance?
- Is the right next action still monitoring, or has the issue persisted long enough to require deeper investigation?

Example from the 2026-05-25 run:

- First-page search impressions increased sharply versus the prior week.
- Airbnb visibility increased strongly.
- Conversion remained weak.
- PriceLabs rules did not materially change enough to explain the whole pattern.

This points toward a possible listing competitiveness, value-perception, or booking-friction issue. The issue should stay open until future weekly data shows improvement, rather than being rediscovered from scratch each week.

## Outputs

### Per-Run Tracker

`data/runs/<run_date>/analysis/diagnostic_issue_tracker_<run_date>.csv`

This file records the issue state as of the current run. It should include newly detected issues, still-open issues carried from history, improving issues, resolved issues, and monitoring issues.

### Rolling History

`data/history/diagnostic_issue_tracker.csv`

This file is the durable issue ledger across runs. It should be append/update oriented and should preserve enough state to calculate `weeks_open`, status transitions, and recurring patterns.

The per-run tracker should be generated from current signals plus the rolling history file. After the per-run tracker is written, the rolling history file should be updated.

## Data Model

Columns:

- `issue_id`
- `issue_title`
- `first_seen_run_date`
- `last_seen_run_date`
- `status`
- `severity`
- `source_type`
- `signal_type`
- `current_value`
- `previous_value`
- `wow_change`
- `four_week_average`
- `weeks_open`
- `evidence_summary`
- `suspected_cause`
- `recommended_investigation`
- `blocked_recommendation_reason`
- `resolution_rule`
- `notes`

Allowed `status` values:

- `open`
- `improving`
- `resolved`
- `monitoring`

Allowed `severity` values:

- `low`
- `medium`
- `high`

Allowed `source_type` values:

- `pricelabs_core`
- `airbnb_diagnostic`
- `combined`

Issue IDs should be deterministic enough to carry state across runs. Suggested format:

`<signal_type>__<window_or_scope>`

Examples:

- `airbnb_visibility_up_conversion_down__weekly`
- `airbnb_listing_above_similar_but_booking_weak__weekly`
- `cleaning_efficiency_risk_persistent__portfolio`
- `price_rule_change_impact_watch__days_16_45`

## Inputs

Current run inputs:

- `analysis/airbnb_weekly_conversion_summary_<run_date>.csv`
- `analysis/airbnb_weekly_history_comparison_<run_date>.csv`
- `analysis/airbnb_similar_listing_summary_<run_date>.csv`
- `analysis/combined_market_listing_signal_<run_date>.csv`
- `analysis/performance_reason_review_<run_date>.csv`
- `settings/pricelabs_settings_changes_<run_date>.csv`
- `analysis/email_revenue_report_<run_date>.md`

Historical input:

- `data/history/diagnostic_issue_tracker.csv`

Airbnb inputs must be treated as diagnostic context only. They must not populate revenue, occupancy, ADR, booked nights, booking totals, cleaning count, or monthly revenue pace.

## Initial Issue Types

### 1. Airbnb Visibility Up, Conversion Down

`signal_type`: `airbnb_visibility_up_conversion_down`

Trigger:

- `first_page_search_impressions` increases more than 3x week over week.
- One or more conversion rates are down, weak, or materially below recent baseline:
  - `average_overall_conversion_rate`
  - `search_to_listing_conversion_rate`
  - `listing_to_booking_conversion_rate`
- No meaningful PriceLabs rule change is detected for the relevant window or rule family.

Example evidence from 2026-05-25:

- `first_page_search_impressions`: 3535
- Previous week: 489
- Week-over-week change: 3046
- Search-to-listing conversion rate: 9.48%, down from 35.99
- Listing-to-booking conversion rate: 1.49%, down from 3.98

Interpretation:

Airbnb is showing the listing more, but guests are not converting at the same rate. Prioritize listing, competitor, value-perception, and booking-friction review before PriceLabs rule changes.

Recommended investigation:

- Review Airbnb search card appeal: lead photo, title, price presentation, badges, and competing listings.
- Review listing page conversion: photos, amenities, cancellation policy, fees guests see, minimum stay, and booking rules.
- Compare similar-listing benchmarks.
- Check PriceLabs open ask and rules only after PriceLabs revenue, occupancy, ADR, booking pace, and cleaning efficiency support a rule review.

Blocked recommendation reason:

Airbnb visibility/conversion data is diagnostic only and cannot directly recommend PriceLabs rule changes.

Resolution rule:

Resolve when first-page search impressions remain healthy or stable and conversion rates recover to either:

- at or above the prior 4-week average for 2 consecutive runs, or
- no longer materially below previous week/recent baseline while PriceLabs core signals are not weak.

Status transitions:

- `open`: trigger is met.
- `improving`: visibility remains healthy and conversion improves but has not met resolution rule.
- `resolved`: resolution rule is met.
- `monitoring`: trigger no longer fires for one run, but there is not enough evidence to resolve.

### 2. Airbnb Listing Above Similar Listings But Booking Weak

`signal_type`: `airbnb_listing_above_similar_but_booking_weak`

Trigger:

- `listing_airbnb_signal = above_similar` from combined market/listing signal.
- `revenue_pace_signal = weak`.
- `occupancy_gap_signal = behind`.

Interpretation:

Airbnb similar-listing diagnostics look favorable, but PriceLabs core revenue/occupancy signals remain weak. This suggests investigation should focus on PriceLabs/core context, open calendar value, booking-window mix, and cleaning efficiency before assuming listing quality is the blocker.

Recommended investigation:

- Review PriceLabs revenue pace and open ask.
- Review occupancy gap by actionable windows.
- Review booking window and ADR.
- Review cleaning efficiency before filling gaps with low-value turnovers.
- Review Airbnb similar-listing context as diagnostic support only.

Blocked recommendation reason:

Airbnb outperformance can raise investigation priority, but PriceLabs revenue, occupancy, ADR, booking pace, and cleaning efficiency must justify any rule-change recommendation.

Resolution rule:

Resolve when either:

- revenue pace is no longer weak and occupancy gap is no longer behind, or
- combined signal category no longer indicates listing outperformance with weak PriceLabs-core metrics for 2 consecutive runs.

### 3. Cleaning Efficiency Risk Persistent

`signal_type`: `cleaning_efficiency_risk_persistent`

Trigger:

- `cleaning_efficiency_signal = inefficient` for 2 or more consecutive runs.

Interpretation:

The listing may be collecting bookings in a way that creates too many low-value turnovers. Since there is no cleaning fee, occupancy alone is not the goal.

Recommended investigation:

- Review revenue per cleaning.
- Review average length of stay.
- Review 1-night stays, orphan windows, last-minute settings, LOS discounts, and minimum-stay rules.
- Avoid filling open dates with low-value turnovers unless PriceLabs core revenue pace and booking-window data justify it.

Blocked recommendation reason:

Do not recommend a rule change from cleaning signal alone. PriceLabs revenue pace, ADR/open ask, booking pace, and occupancy gap must support any settings change.

Resolution rule:

Resolve when cleaning efficiency is not `inefficient` for 2 consecutive runs, or when revenue per cleaning recovers above the configured operating threshold for 2 consecutive runs.

### 4. Price Rule Change Impact Watch

`signal_type`: `price_rule_change_impact_watch`

Trigger:

- `settings/pricelabs_settings_changes_<run_date>.csv` shows a PriceLabs setting changed.
- Subsequent revenue, occupancy, conversion, or reason-review signal worsens in the affected window.

Interpretation:

A recent settings change may have influenced performance. This is a watch item, not proof that the change was harmful.

Recommended investigation:

- Identify the changed setting and affected date/window.
- Compare performance before and after the change.
- Check whether market context moved at the same time.
- Check Airbnb visibility/conversion diagnostics as supporting context only.

Blocked recommendation reason:

Do not revert or change PriceLabs settings automatically. Evaluate whether the observed performance change is likely caused by settings, market movement, listing conversion, or insufficient data.

Resolution rule:

Resolve when post-change performance stabilizes or improves for 2 consecutive runs, or when Reason Review no longer identifies settings-change impact.

## Trigger Logic Detail

### Comparison Inputs

Use retained-history comparison first when available:

- `current_value`
- `previous_week_value`
- `change_vs_previous_week`
- `last_4_week_avg`
- `change_vs_last_4_week_avg`
- `history_quality_status`

If retained history is unavailable, use weekly summary previous-week fields. If neither exists, mark issue evidence as insufficient and do not open a new persistent issue unless PriceLabs-core signals alone trigger it.

### Meaningful PriceLabs Rule Change

Use `settings/pricelabs_settings_changes_<run_date>.csv`.

A future implementation should classify changes by field family:

- base price or minimum price
- occupancy-based adjustments
- far-out premium
- last-minute rules
- orphan rules
- minimum stay
- LOS discounts or premiums
- booking recency factor

For the first implementation, a simple `changed_flag=true` can be used as supporting context. Later versions should map specific setting families to impacted windows.

### Weeks Open

`weeks_open` should be calculated from the number of run dates where the issue remained open, improving, or monitoring since `first_seen_run_date`.

If runs are skipped, calculate by observed run count first. Calendar-week duration can be added later as a separate field if useful.

## Resolution And Carry-Forward Rules

Every run should:

1. Load open/improving/monitoring issues from history.
2. Re-evaluate trigger and resolution rules.
3. Update `last_seen_run_date`.
4. Increment or recalculate `weeks_open`.
5. Write current issue state to the per-run CSV.
6. Update rolling history.

Do not drop an issue just because its trigger does not fire once. Move it to `monitoring` unless the resolution rule is met.

Suggested status lifecycle:

`open -> improving -> resolved`

or

`open -> monitoring -> resolved`

If an issue recurs after resolution, reopen with the same `signal_type` but preserve the original `first_seen_run_date` in history and update `last_seen_run_date`.

## Email Report Behavior

Future email report section:

`## Persistent Diagnostic Issues`

Placement:

After `## Airbnb Funnel Signals` and before `## Recommendation Review`.

Suggested compact format:

- `Open issue: Airbnb visibility up, conversion down. First seen 2026-05-25; weeks open: 1. Visibility is up sharply, but conversion remains below recent baseline. Investigate listing appeal, competitor context, and booking friction before PriceLabs rule changes.`
- `Monitoring issue: Cleaning efficiency risk. Cleaning efficiency improved this run but needs one more clean run before resolving.`

Guardrails:

- The section may raise investigation priority.
- The section must not add PriceLabs rule recommendations by itself.
- PriceLabs rule recommendations remain controlled by existing PriceLabs recommendation logic.
- Airbnb issue text must use diagnostic wording: investigate, monitor, compare, review.
- Avoid automatic action language such as discount, raise price, lower price, or change rule unless the existing recommendation source already supports it.

## Evidence Bundle Behavior

Future evidence bundle additions:

Always include when present:

- `analysis/diagnostic_issue_tracker_<run_date>.csv`

Include rolling history when persistent issues are open, improving, or monitoring:

- `data/history/diagnostic_issue_tracker.csv`

Categories:

- Per-run issue tracker:
  - `category = diagnostic_issue_tracker`
  - `role = current_run_persistent_issue_state`
  - `source_of_truth_type = diagnostic`

- Rolling issue tracker:
  - `category = diagnostic_issue_tracker`
  - `role = rolling_persistent_issue_history`
  - `source_of_truth_type = diagnostic`

The rolling history file should be copied into the evidence bundle, not edited inside the bundle.

## Tests Needed Later

Unit tests:

- Opens `airbnb_visibility_up_conversion_down` when first-page search impressions increase more than 3x and conversion rates weaken.
- Does not open `airbnb_visibility_up_conversion_down` when visibility rises and conversion also improves.
- Opens `airbnb_listing_above_similar_but_booking_weak` from combined signal above-similar plus weak/behind PriceLabs core fields.
- Opens `cleaning_efficiency_risk_persistent` only after 2 consecutive inefficient runs.
- Opens `price_rule_change_impact_watch` when a setting changed and subsequent signals worsen.
- Airbnb-only issues do not create PriceLabs recommendation actions.
- Existing open issue carries forward when still unresolved.
- Issue moves to `improving` when values improve but do not meet resolution rule.
- Issue moves to `resolved` only when resolution rule is met.
- Rolling history updates without duplicating the same issue for the same run.

Integration tests:

- Per-run tracker CSV is created under `analysis/`.
- Rolling history file is created under `data/history/`.
- Email report renders persistent issue section when issue tracker exists.
- Email report omits or marks unavailable when tracker is missing.
- Evidence bundle includes per-run issue tracker when present.
- Evidence bundle includes rolling history when persistent issues are active.
- No Airbnb revenue, ADR, occupancy, booked nights, booking totals, cleaning count, or monthly revenue pace fields are added.

## Future Implementation Steps

1. Add issue tracker module:
   `src/analysis/diagnostic_issue_tracker.py`
2. Add CLI:
   `python -m analysis.diagnostic_issue_tracker --run-date <run_date>`
3. Load current inputs and rolling history.
4. Detect initial issue types.
5. Apply carry-forward and resolution rules.
6. Write:
   - `analysis/diagnostic_issue_tracker_<run_date>.csv`
   - `data/history/diagnostic_issue_tracker.csv`
7. Add the issue tracker step after combined market/listing signal and before email report.
8. Add a compact email section.
9. Add issue tracker files to evidence bundle.
10. Keep recommendations unchanged until a separate, explicitly approved recommendation-design step.

## Risks And Unknowns

- Airbnb chart/export labels may change, so issue triggers should rely on normalized analysis outputs instead of raw HTML.
- A sharp impressions increase can reflect Airbnb placement, seasonality, market demand, or algorithm changes; it is not proof of listing quality trouble.
- Similar-listing benchmarks are useful but may not represent a perfect comp set.
- PriceLabs setting changes need field-family mapping before they can be connected confidently to specific windows.
- Some issues need multiple runs before severity is reliable.
- Missing weekly runs can complicate `weeks_open`.
- The tracker must avoid creating a feedback loop where diagnostic issue language sounds like a rule recommendation.

