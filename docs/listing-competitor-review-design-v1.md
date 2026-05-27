# Listing Competitor Review Design V1

## Purpose

This document designs a structured listing-side review workflow for open diagnostic issues such as `airbnb_visibility_up_conversion_down`.

The workflow exists because an Airbnb conversion issue can persist even when visibility improves. In that situation, the listing may be getting enough exposure, but guests may not be persuaded to click, stay, book, or accept the visible value proposition.

This is design only. It does not change recommendation logic, PriceLabs pricing rules, scheduler behavior, or email sending behavior.

## Guardrails

PriceLabs remains the source of truth for:

- revenue
- occupancy
- ADR
- booked nights
- booking totals
- cleaning count
- monthly revenue pace
- market benchmark context

Airbnb remains diagnostic only for:

- page views
- first-page search impressions
- wishlist additions
- conversion rates
- similar-listing benchmarks
- listing-side investigation context

The listing competitor review may suggest listing-side tests. It must not recommend PriceLabs rule changes from Airbnb or listing review alone.

Do not recommend:

- broad discounting
- lowering price from Airbnb diagnostics alone
- optimizing for occupancy alone
- manual calendar edits
- automatic PriceLabs rule changes

Preferred language:

- investigate
- compare
- test
- clarify value
- reduce booking hesitation
- protect premium positioning

## Why This Workflow Exists

Example from the 2026-05-25 run:

- First-page search impressions increased sharply.
- Airbnb visibility increased strongly.
- Conversion weakened or remained weak.
- PriceLabs rules did not materially change enough to explain the pattern.

This suggests the issue may be listing competitiveness, value perception, or booking friction rather than visibility alone. A weekly numeric report can flag the issue, but it cannot decide whether the cover photo, title, listing promise, amenities presentation, rules, fees, or competitor set is weakening conversion.

The listing competitor review turns that open diagnostic issue into a repeatable human review process.

## When It Runs

The workflow should run when `diagnostic_issue_tracker_<run_date>.csv` contains an active issue with:

- `status` in `open`, `improving`, or `monitoring`
- `signal_type = visibility_up_conversion_down`

It may also run for future issue types where listing-side investigation is appropriate, such as:

- `airbnb_listing_above_similar_but_booking_weak`
- persistent wishlist strength without bookings
- similar-listing benchmark weakness
- search-to-listing weakness with healthy impressions
- listing-to-booking weakness with healthy page views

The review should be optional and diagnostic. Missing listing review output should not fail the PriceLabs pipeline.

## Required Inputs

Required analysis inputs:

- `data/runs/<run_date>/analysis/diagnostic_issue_tracker_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_weekly_conversion_summary_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_weekly_history_comparison_<run_date>.csv`
- `data/runs/<run_date>/analysis/combined_market_listing_signal_<run_date>.csv`

Required manual review inputs:

- Current Airbnb listing page for Aloha Poconos
- Current visible search/listing card if available
- Current cover photo and first 5 photos
- Current title
- Current description opening
- Current visible amenities
- Current guest capacity, bedroom, bed, and bath presentation
- Current cancellation policy
- Current pet policy
- Current house rules
- Current visible fees and price presentation
- Current minimum stay and availability friction

The manual review inputs may initially be captured as notes, screenshots, or pasted structured observations. Do not store cookies, browser state, credentials, tokens, or private guest data.

## Optional Inputs

Optional Airbnb diagnostic inputs:

- `data/runs/<run_date>/analysis/airbnb_similar_listing_summary_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_daily_similar_listing_comparison_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_daily_week_over_week_conversion_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_daily_week_average_deviation_<run_date>.csv`
- `data/runs/<run_date>/analysis/airbnb_conversion_diagnostic_report_<run_date>.md`

Optional PriceLabs/core context:

- `data/runs/<run_date>/analysis/rolling_13_month_revenue_view_<run_date>.csv`
- `data/runs/<run_date>/analysis/future_window_summary_<run_date>.csv`
- `data/runs/<run_date>/analysis/future_window_signals_<run_date>.csv`
- `data/runs/<run_date>/analysis/performance_reason_review_<run_date>.csv`
- `data/runs/<run_date>/settings/pricelabs_settings_changes_<run_date>.csv`

PriceLabs/core context may explain revenue pace and booking-window pressure. It must not be replaced by Airbnb data.

## Outputs

### Markdown Review

`data/runs/<run_date>/analysis/listing_competitor_review_<run_date>.md`

Suggested sections:

- Executive summary
- Open issue being investigated
- Listing strengths
- Listing weaknesses
- Competitor comparison
- Booking-friction risks
- Suggested listing tests
- What not to change yet
- What to check next week

### Structured CSV

`data/runs/<run_date>/analysis/listing_competitor_review_<run_date>.csv`

Suggested columns:

- `run_date`
- `issue_id`
- `review_area`
- `finding_type`
- `finding`
- `evidence`
- `competitor_context`
- `severity`
- `suggested_listing_test`
- `expected_signal_to_watch`
- `price_rule_change_allowed`
- `blocked_recommendation_reason`
- `status`
- `notes`

Allowed `review_area` values:

- `cover_photo`
- `first_five_photos`
- `title`
- `description_opening`
- `amenities_presentation`
- `guest_fit`
- `review_rating`
- `review_count`
- `cancellation_policy`
- `pet_policy`
- `house_rules`
- `fees_price_perception`
- `minimum_stay_availability`
- `competitor_comparison`
- `booking_friction`

Allowed `finding_type` values:

- `strength`
- `weakness`
- `risk`
- `test_candidate`
- `monitor`

`price_rule_change_allowed` should default to `false` unless a separate PriceLabs recommendation layer independently supports rule review.

## Review Rubric

### 1. Search Card Appeal

Question:

Does the listing earn the click when Airbnb shows it more often?

Review:

- Cover photo clarity and emotional pull
- Whether the first visible image communicates the premium promise
- Title clarity and differentiation
- Rating and review count visibility
- Price perception versus nearby alternatives
- Similar-listing search card comparison

Possible listing-side tests:

- Cover photo test
- Title test
- First-photo order test
- Badge/value emphasis test

Do not infer a pricing problem from this section alone.

### 2. First 5 Photos

Question:

Do the first 5 photos quickly prove the stay is worth attention?

Review:

- Hot tub, sauna, game room, or strongest differentiators
- Sleeping spaces and guest fit
- Seasonal or exterior context
- Photo brightness and quality
- Whether photos answer the guest's likely first objections

Possible listing-side tests:

- Reorder photos so the strongest premium differentiators appear earlier
- Replace weak early photos
- Add captions where they clarify value

### 3. Title And Description Opening

Question:

Does the copy make the value obvious before guests lose attention?

Review:

- Title specificity
- First sentence clarity
- Premium differentiators
- Guest use case: couples, families, groups, remote work, pets
- Avoid generic claims that similar listings also use

Possible listing-side tests:

- Test a title that leads with the strongest differentiator
- Rewrite opening copy to clarify who the stay is best for
- Clarify premium value before secondary details

### 4. Amenities Presentation

Question:

Are high-value amenities visible and easy to understand?

Review:

- Hot tub
- Sauna
- Game room
- Fireplace/fire pit if applicable
- Workspace/Wi-Fi
- Pet-friendly details if applicable
- Kitchen, parking, EV charging, AC, laundry

Possible listing-side tests:

- Reorder amenities presentation
- Mention high-value amenities earlier in copy
- Add photo captions for premium amenities

### 5. Guest Fit And Sleeping Capacity

Question:

Does the listing clearly match the group Airbnb is showing it to?

Review:

- Guest count clarity
- Bedroom and bed setup
- Bathroom count
- Family/group suitability
- Privacy and comfort tradeoffs
- Whether the listing appears too large, too small, or unclear for the visible price

Possible listing-side tests:

- Clarify sleeping arrangements
- Add or improve floor-plan style copy
- Emphasize group comfort rather than only capacity

### 6. Trust And Review Signals

Question:

Does the listing reduce risk for the guest?

Review:

- Rating
- Review count
- Recent review themes
- Superhost or guest favorite signals if visible
- Accuracy, cleanliness, communication, location, value subthemes

Possible listing-side tests:

- Pull review language into listing copy where allowed
- Emphasize trust signals in description opening
- Address recurring guest hesitation if reviews reveal it

### 7. Booking-Friction Risks

Question:

Could guests like the listing but hesitate before booking?

Review:

- Cancellation policy
- Pet policy
- House rules
- Fees and total price perception
- Minimum stay
- Availability gaps
- Check-in/check-out constraints
- Booking lead time expectations

Possible listing-side tests:

- Clarify policies in friendlier language
- Reduce uncertainty in house rules
- Clarify what fees include
- Check if minimum stay creates visible friction

Do not recommend changing PriceLabs minimum-stay rules from this review alone. Route rule questions back to PriceLabs/core recommendation logic.

### 8. Competitor Comparison

Question:

What do similar listings communicate better or worse?

Review:

- Cover photo promise
- Amenity stack
- Guest fit clarity
- Review/rating credibility
- Cancellation/pet/rule friction
- Visible total price perception
- Calendar availability friction

Possible listing-side tests:

- Borrow communication patterns, not pricing actions
- Clarify value gaps that competitors make obvious
- Protect Aloha Poconos premium positioning when the listing is genuinely stronger

## Example Issue: Airbnb Visibility Up, Conversion Down

Input issue:

- `issue_id = airbnb_visibility_up_conversion_down`
- `status = open`
- `severity = high`
- `source_type = airbnb_diagnostic`
- Evidence: first-page search impressions increased sharply while conversion weakened or remained weak.

Review interpretation:

Airbnb is creating more exposure, but guests are not converting at the same rate. This suggests the review should prioritize:

- search card appeal
- cover photo
- title and opening copy
- amenities differentiation
- competitor value perception
- booking-friction risks

Suggested executive summary wording:

`Airbnb visibility increased sharply, but conversion weakened. This review should focus on whether the listing presentation, competitor comparison, or booking friction is preventing guests from converting. This is not a PriceLabs rule-change recommendation.`

## How Findings Appear In Email

Future email section:

`## Listing Competitor Review`

Placement:

After `## Open Diagnostic Issues` and before `## Recommendation Review`.

Suggested compact wording:

- `Listing review: Open Airbnb conversion issue needs listing-side investigation. Focus areas: cover photo, title/opening copy, amenities presentation, and booking friction. Suggested tests are listing-side only; PriceLabs rule changes remain gated by PriceLabs core recommendation logic.`

Rules:

- Show only concise active findings.
- Do not include long competitor notes in the email body.
- Do not recommend broad discounting.
- Do not recommend PriceLabs rule changes from listing review alone.
- Link or refer to the markdown review in the evidence bundle once attachments are supported.

## How Findings Appear In Evidence Bundle

Future evidence bundle additions:

- `analysis/listing_competitor_review_<run_date>.md`
- `analysis/listing_competitor_review_<run_date>.csv`

Suggested metadata:

Markdown review:

- `category = listing_competitor_review`
- `role = listing_side_investigation_report`
- `source_of_truth_type = diagnostic`

CSV review:

- `category = listing_competitor_review`
- `role = structured_listing_side_findings`
- `source_of_truth_type = diagnostic`

The evidence bundle should not include raw screenshots, browser cache, cookies, session state, or private guest data. If screenshots are ever added, they need a separate privacy review and explicit opt-in.

## Future Automation Options

Manual-first V1:

- Operator reviews listing and competitors manually.
- Operator records findings in a structured template.
- Pipeline reads the template and renders markdown/CSV outputs.

Assisted capture V2:

- Capture public listing page snapshots manually or with a headed browser.
- Capture only public listing presentation, not account/session state.
- Require user confirmation before saving any page content.
- Validate listing identity and date before storing.

Structured comparison V3:

- Normalize competitor observations into CSV rows.
- Compare Aloha Poconos against 3-5 hand-selected competitors.
- Score review areas using a rubric, but avoid automatic pricing conclusions.

AI-assisted review V4:

- Use saved public listing text and selected images to draft observations.
- Require human approval.
- Keep outputs as suggested listing tests, not direct operational changes.

## Tests Needed Later

Unit tests:

- Review runs only when active diagnostic issue exists.
- `airbnb_visibility_up_conversion_down` produces listing-side review focus areas.
- Missing listing review inputs do not fail the weekly pipeline.
- Markdown review contains required sections.
- CSV review contains allowed columns only.
- Review output does not include PriceLabs recommendation actions.
- Review output does not include forbidden Airbnb source-of-truth fields.
- Suggested tests are listing-side only.

Integration tests:

- Email includes compact Listing Competitor Review section when review output exists.
- Email keeps Recommendation Review unchanged.
- Evidence bundle includes markdown and CSV review outputs when present.
- Missing review outputs do not fail evidence bundle generation.
- No raw browser state, cookies, tokens, credentials, or private guest data are bundled.

## Risks And Unknowns

- Competitor selection can bias conclusions if the comp set is weak.
- Airbnb visible price can vary by guest, date, fees, and logged-in state.
- Listing page content and search card presentation can vary by device and market.
- Photos are subjective; changes should be tested rather than assumed.
- Airbnb conversion weakness can reflect market mix, guest intent, or platform ranking changes, not only listing quality.
- Some booking friction may be intentional to protect premium positioning.
- A listing-side review can identify hypotheses, but future measured Airbnb and PriceLabs/core data should decide whether the issue improves.

