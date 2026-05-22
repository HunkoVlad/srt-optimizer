# Airbnb Weekly Conversion Contract V1

## Scope

This contract defines future Airbnb conversion inputs and normalized diagnostic output. It is documentation only for now.

Airbnb data is diagnostic only. It must not become the source of truth for revenue, ADR, occupancy, booked nights, booking value, total bookings, cleaning count, or monthly revenue pace.

## Raw Inputs

Preferred raw files:

```text
data/runs/<run_date>/raw/airbnb_booking_conversion_daily.html
data/runs/<run_date>/raw/airbnb_page_views_daily.html
data/runs/<run_date>/raw/airbnb_wishlist_additions_daily.html
```

Optional raw file:

```text
data/runs/<run_date>/raw/airbnb_monthly_report.csv
```

The daily HTML files are preferred because weekly Reason Review needs daily or short-window signals. The monthly CSV may be stored as supporting context, but it must not be used as portfolio-level performance truth.

Temporary Airbnb HTML files remain in `raw/` only until successful parsing. After parsing, the HTML files may be deleted, but the parsed extraction CSV is retained in `raw/` as the source-derived extraction record.

## Future Normalized Outputs

Retained parsed extraction output:

```text
data/runs/<run_date>/raw/airbnb_daily_conversion_parsed_<run_date>.csv
```

Weekly average summary output:

```text
data/runs/<run_date>/analysis/airbnb_weekly_conversion_summary_<run_date>.csv
```

Daily competitor comparison output:

```text
data/runs/<run_date>/analysis/airbnb_daily_competitor_conversion_<run_date>.csv
```

Daily week-over-week diagnostic output:

```text
data/runs/<run_date>/analysis/airbnb_daily_week_over_week_conversion_<run_date>.csv
```

Weekly retained-history comparison output:

```text
data/runs/<run_date>/analysis/airbnb_weekly_history_comparison_<run_date>.csv
```

Deprecated detailed extraction location:

```text
data/runs/<run_date>/analysis/airbnb_daily_conversion_<run_date>.csv
```

That older analysis path is retained only as a migration/preservation fallback. New detailed parsed extraction should be written to `raw/airbnb_daily_conversion_parsed_<run_date>.csv`.

## Analysis Layers

### Weekly Average Layer

The weekly average layer compares the last 7 days against previous weekly windows. It is used for trend direction and over-time Reason Review diagnosis.

Suggested columns for `airbnb_weekly_conversion_summary_<run_date>.csv`:

```text
run_date
metric_window_start
metric_window_end
airbnb_data_quality_status
comparison_type
comparison_window_start
comparison_window_end
page_views
first_page_search_impressions
wishlist_additions
average_overall_conversion_rate
first_page_search_impression_rate
search_to_listing_conversion_rate
listing_to_booking_conversion_rate
page_views_change_vs_previous_week
wishlist_additions_change_vs_previous_week
first_page_search_impressions_change_vs_previous_week
overall_conversion_change_vs_previous_week
search_to_listing_change_vs_previous_week
listing_to_booking_change_vs_previous_week
has_recent_history_baseline
has_similar_listing_benchmark
diagnostic_confidence
parsed_metric_pages
missing_metric_pages
diagnostic_summary
notes
```

The weekly summary is the clean analysis artifact. It should not include revenue, ADR, occupancy, booking counts, or cleaning efficiency. It should be comparison-ready, not judgment-based: do not classify Airbnb metrics as good or bad from bare values alone.

Diagnostic confidence rules:

- No comparison data: `diagnostic_confidence=low`.
- Previous-week comparison exists: `diagnostic_confidence=medium`.
- Previous-week comparison plus 4 or more historical weekly windows: `diagnostic_confidence=high`.
- Similar-listing benchmark data is Airbnb market context only.

Example neutral summaries:

- `Airbnb diagnostics parsed successfully, but interpretation is limited because no historical baseline is available.`
- `Airbnb page views declined versus the previous 7 days; compare with PriceLabs market context before assigning cause.`
- `Airbnb conversion signals are available for the selected week; no portfolio revenue conclusion should be made from Airbnb alone.`

Older proposed weekly trend columns may be added later if needed:

```text
comparison_window_start
comparison_window_end
listing_name
avg_page_views
prior_avg_page_views
page_views_trend
avg_similar_listing_page_views
avg_first_page_search_impression_rate
prior_avg_first_page_search_impression_rate
first_page_search_impression_trend
avg_search_to_listing_conversion_rate
prior_avg_search_to_listing_conversion_rate
search_to_listing_trend
avg_listing_to_booking_conversion_rate
prior_avg_listing_to_booking_conversion_rate
listing_to_booking_trend
avg_wishlist_additions
prior_avg_wishlist_additions
wishlist_trend
data_quality_status
notes
```

### Daily Competitor Layer

The daily competitor layer compares each day inside the week against similar listings or competitor benchmarks shown by Airbnb. It is used to identify daily visibility or conversion underperformance.

Suggested columns for `airbnb_daily_competitor_conversion_<run_date>.csv`:

```text
run_date
report_date
metric_window_start
metric_window_end
listing_name
page_views
first_page_search_impressions
similar_listing_page_views
page_views_vs_similar
first_page_search_impression_rate
similar_listing_first_page_search_impression_rate
first_page_search_impression_vs_similar
search_to_listing_conversion_rate
similar_listing_search_to_listing_conversion_rate
search_to_listing_vs_similar
listing_to_booking_conversion_rate
similar_listing_listing_to_booking_conversion_rate
listing_to_booking_vs_similar
wishlist_additions
similar_listing_wishlist_additions
wishlist_additions_vs_similar
source_file
extraction_method
data_quality_status
notes
```

### Detailed Daily Extraction Layer

Suggested columns for `raw/airbnb_daily_conversion_parsed_<run_date>.csv`:

```text
run_date
report_date
metric_window_start
metric_window_end
comparison_window_start
comparison_window_end
listing_name
airbnb_metric_page
page_views
first_page_search_impressions
similar_listing_page_views
average_overall_conversion_rate
similar_listing_overall_conversion_rate
first_page_search_impression_rate
search_to_listing_conversion_rate
listing_to_booking_conversion_rate
wishlist_additions
similar_listing_wishlist_additions
page_views_change_vs_previous_week
wishlist_additions_change_vs_previous_week
first_page_search_impressions_change_vs_previous_week
overall_conversion_change_vs_previous_week
search_to_listing_change_vs_previous_week
listing_to_booking_change_vs_previous_week
daily_chart_values_json
source_file
extraction_method
data_quality_status
notes
```

`daily_chart_values_json` preserves source-derived Airbnb `<dl>` chart points from temporary HTML before the HTML is cleaned up. It remains in the raw parsed extraction layer, not the business-ready summary layer.

### Daily Week-Over-Week Layer

Suggested columns for `airbnb_daily_week_over_week_conversion_<run_date>.csv`:

```text
run_date
metric_window_start
metric_window_end
comparison_window_start
comparison_window_end
report_date
weekday
comparison_report_date
airbnb_metric_page
metric_name
current_value
previous_week_value
change_vs_previous_week
percent_change_vs_previous_week
data_quality_status
notes
```

This output pairs each current-week Airbnb chart point with the same weekday from the previous-week range. It calculates changes only; it does not classify the daily values as good or bad.

### Weekly Retained-History Comparison Layer

Suggested columns for `airbnb_weekly_history_comparison_<run_date>.csv`:

```text
run_date
metric_window_start
metric_window_end
metric_name
current_value
previous_week_value
change_vs_previous_week
last_4_week_avg
change_vs_last_4_week_avg
recent_history_weeks_used
history_quality_status
notes
```

History quality values:

- `no_history`: no prior complete Airbnb weekly summaries.
- `previous_week_only`: one prior comparable week.
- `limited_history`: 2-3 prior comparable weeks.
- `recent_baseline_ready`: 4 or more prior comparable weeks and last-4-week averages are available.

This layer provides retained Airbnb context only. It does not make pricing, revenue, occupancy, booking, or cleaning conclusions.

Do not include columns in any Airbnb normalized output such as:

- ADR
- occupancy
- revenue
- booked nights
- booking value
- total bookings
- cleaning count
- monthly revenue pace

Those fields remain owned by the PriceLabs / existing pipeline source model.

## Field Notes

- `run_date`: pipeline run date in `YYYY-MM-DD`.
- `report_date`: Airbnb metric date when the source provides daily rows.
- `metric_window_start`: first date covered by the extracted metric window.
- `metric_window_end`: last date covered by the extracted metric window.
- `listing_name`: Airbnb listing name as shown in the source.
- `airbnb_metric_page`: source page type, such as `booking_conversion`, `page_views`, or `wishlist_additions`.
- `page_views`: listing page views.
- `first_page_search_impressions`: Airbnb first-page search impression count when visible. This is a visibility diagnostic metric only.
- `similar_listing_page_views`: comparable listing page views when visible.
- `average_overall_conversion_rate`: Airbnb overall conversion benchmark when visible.
- `similar_listing_overall_conversion_rate`: similar listing conversion benchmark when visible.
- `first_page_search_impression_rate`: share/rate of first-page search visibility when visible.
- `search_to_listing_conversion_rate`: search-to-listing conversion rate when visible.
- `listing_to_booking_conversion_rate`: listing-to-booking conversion rate when visible.
- `wishlist_additions`: wishlist additions for the listing.
- `similar_listing_wishlist_additions`: comparable wishlist additions when visible.
- `source_file`: raw Airbnb file path or filename.
- `extraction_method`: `manual_html`, `manual_screenshot`, `manual_csv`, or future extraction method.
- `data_quality_status`: `ok`, `partial`, `missing`, `ambiguous`, or `needs_review`.
- `notes`: concise extraction or interpretation notes.

## Reason Review Usage

Airbnb conversion output may support Reason Review diagnostics, but it must remain subordinate to the existing PriceLabs truth sources.

Use the weekly average layer for trend direction over time. Use the daily competitor layer for same-day visibility and conversion comparison against similar listings. Do not mix either layer into PriceLabs revenue pace calculations.

Diagnostic examples:

- Views down plus PriceLabs market weak: likely `market_weakness`.
- Views down plus PriceLabs market not weak: possible Airbnb visibility issue.
- Views healthy plus search-to-listing weak: possible title/photo/search appeal issue.
- Views healthy plus listing-to-booking weak: possible listing conversion, price friction, or booking-rule friction.
- Wishlist additions healthy plus bookings weak: possible price or booking friction.
- Airbnb signals missing: `insufficient_data`.

Recommendation gating still applies:

- `market_weakness`: no PriceLabs rule change justified yet.
- `insufficient_data`: no recommendation allowed.
- `listing_or_conversion_issue`: investigate listing/conversion before changing PriceLabs.
- `price_or_rule_issue`: PriceLabs rule areas may be considered only when `recommendation_allowed=true`.
- `settings_change_impact`: evaluate prior setting impact before changing again.

## Out Of Scope

This contract does not implement:

- scraper code
- Playwright automation
- HTML parsing
- screenshot OCR
- normalized CSV generation
- pipeline integration
- report integration
- scheduler integration

## Source Boundary

The required PriceLabs raw files remain the operational source model for the weekly report:

```text
data/runs/<run_date>/raw/priceLabs_future_export.csv
data/runs/<run_date>/raw/price_occ.csv
data/runs/<run_date>/raw/monthly_trends.csv
data/runs/<run_date>/raw/bookings_report.xlsx
data/runs/<run_date>/raw/pricelabs_settings_snapshot_from_ui.json
```

Airbnb conversion files are optional diagnostic evidence. They do not replace or override those inputs.
