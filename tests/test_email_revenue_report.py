import csv
import sys

from pricelabs.transform.email_revenue_report import build_markdown, run


def rolling_row(
    stay_month: str,
    position: str,
    data: str,
    bucket: str = "",
    scope: str = "",
    booked_revenue: str = "",
    open_ask: str = "",
    total_calendar_value: str = "",
    booked_nights: str = "",
    cleanings: str = "",
    days_in_scope: str = "",
    revenue_per_cleaning: str = "",
    revenue_status: str = "no_source_data",
    cleaning_status: str = "",
    action_level: str = "monitor",
    historical_booked_nights: str = "",
    historical_calendar_occupancy_pct: str = "",
    historical_total_revenue: str = "",
    historical_rental_adr: str = "",
    historical_booked_nights_source: str = "",
    historical_cleanings_proxy: str = "",
    historical_cleanings_source: str = "",
    monthly_trends_revenue: str = "",
    monthly_trends_occupancy_pct: str = "",
    monthly_trends_adr: str = "",
    airbnb_stays: str = "",
    vrbo_stays: str = "",
    direct_stays: str = "",
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "stay_month": stay_month,
        "month_relative_index": "",
        "month_window_position": position,
        "data_availability": data,
        "days_in_scope": days_in_scope,
        "days_in_month": "",
        "month_scope_status": scope,
        "booked_nights": booked_nights,
        "available_nights": "",
        "unavailable_nights": "",
        "booked_revenue_proxy": booked_revenue,
        "open_revenue_ask": open_ask,
        "total_future_revenue_proxy": total_calendar_value,
        "monthly_target": "10000" if data not in {"no_source_data", "data_not_available", "historical_actuals", "monthly_trends_actuals"} else "",
        "booked_gap_to_target": "",
        "total_gap_to_target": "",
        "booked_cleanings_proxy": cleanings,
        "avg_stay_length_proxy": "",
        "revenue_per_cleaning_proxy": revenue_per_cleaning,
        "booked_revenue_pct_of_target": "",
        "total_future_revenue_pct_of_target": "",
        "month_time_bucket": bucket,
        "revenue_pace_status": revenue_status,
        "cleaning_efficiency_status": cleaning_status,
        "month_action_level": action_level,
        "historical_bookable_nights": "",
        "historical_booked_nights": historical_booked_nights,
        "historical_booked_nights_source": historical_booked_nights_source,
        "historical_cleanings_proxy": historical_cleanings_proxy,
        "historical_cleanings_source": historical_cleanings_source,
        "historical_paid_occupancy_pct": "",
        "historical_occupancy_pct": "",
        "historical_calendar_occupancy_pct": historical_calendar_occupancy_pct,
        "historical_rental_adr": historical_rental_adr,
        "historical_rental_revpar": "",
        "historical_total_revenue": historical_total_revenue,
        "historical_source": "pricelabs_monthly_trends" if data == "monthly_trends_actuals" else "pricelabs_kpis_on_the_books" if data == "historical_actuals" else "",
        "historical_data_quality_flag": "",
        "monthly_trends_revenue": monthly_trends_revenue,
        "monthly_trends_occupancy_pct": monthly_trends_occupancy_pct,
        "monthly_trends_booked_occupancy_pct": monthly_trends_occupancy_pct,
        "monthly_trends_blocked_occupancy_pct": "",
        "monthly_trends_adr": monthly_trends_adr,
        "monthly_trends_source": "pricelabs_monthly_trends" if monthly_trends_revenue else "",
        "bookings_report_bookings": "",
        "bookings_report_cleanings_proxy": cleanings,
        "bookings_report_booked_nights": "",
        "bookings_report_avg_los": "",
        "bookings_report_rental_revenue": "",
        "bookings_report_total_revenue": "",
        "bookings_report_adr": "",
        "bookings_report_avg_booking_window": "",
        "airbnb_stays": airbnb_stays,
        "vrbo_stays": vrbo_stays,
        "direct_stays": direct_stays,
        "other_unknown_stays": "",
        "main_booking_source": "airbnb" if airbnb_stays else "vrbo" if vrbo_stays else "direct" if direct_stays else "",
        "booking_source_mix_summary": ", ".join(
            part
            for part in (
                f"Airbnb {airbnb_stays}" if airbnb_stays else "",
                f"Vrbo {vrbo_stays}" if vrbo_stays else "",
                f"Direct {direct_stays}" if direct_stays else "",
            )
            if part
        ),
    }


def sample_rows() -> list[dict[str, str]]:
    return [
        rolling_row("2025-11", "historical", "no_source_data"),
        rolling_row(
            "2026-03",
            "historical",
            "monthly_trends_actuals",
            revenue_status="historical_actuals",
            historical_booked_nights="23",
            historical_booked_nights_source="estimated_from_monthly_trends",
            historical_cleanings_proxy="11",
            historical_cleanings_source="estimated_from_monthly_trends",
            historical_calendar_occupancy_pct="74.2",
            historical_total_revenue="8887.86",
            historical_rental_adr="351.26",
            revenue_per_cleaning="807.99",
        ),
        rolling_row(
            "2026-05",
            "current",
            "monthly_trends_current",
            "current_month",
            "partial_month",
            "2834",
            "7425",
            "10259",
            "7",
            "6",
            "24",
            "472.33",
            "conversion_risk",
            "inefficient",
            "advisory",
            monthly_trends_revenue="2834",
            monthly_trends_occupancy_pct="55",
            monthly_trends_adr="425",
            airbnb_stays="5",
            vrbo_stays="1",
        ),
        rolling_row(
            "2026-06",
            "future",
            "future_calendar",
            "next_month",
            "full_month",
            "314",
            "14090",
            "14404",
            "1",
            "1",
            "30",
            "314",
            "conversion_risk",
            "inefficient",
            "advisory",
        ),
        rolling_row(
            "2026-07",
            "future",
            "future_calendar",
            "future_month",
            "full_month",
            "0",
            "22614",
            "22614",
            "0",
            "",
            "31",
            "",
            "protect_open_value",
            "no_booked_cleanings",
            "protect",
        ),
        rolling_row(
            "2026-11",
            "future",
            "partial_horizon",
            "far_future_month",
            "partial_month",
            "0",
            "988",
            "988",
            "0",
            "",
            "3",
            "",
            "partial_horizon",
            "no_booked_cleanings",
            "monitor",
        ),
    ]


def reason_row(
    scope_name: str,
    observed_issue: str,
    likely_reason: str,
    recommendation_allowed: str = "false",
    recommendation_type: str = "monitor",
    market_context: str = "market_normal",
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "scope_type": "window",
        "scope_name": scope_name,
        "observed_issue": observed_issue,
        "relevant_setting_change": "none",
        "last_setting_change_date": "",
        "setting_change_summary": "",
        "performance_after_change": "neutral",
        "market_context": market_context,
        "likely_reason": likely_reason,
        "confidence": "medium",
        "recommendation_allowed": recommendation_allowed,
        "recommendation_type": recommendation_type,
        "explanation_note": "",
    }


def combined_signal_row(
    category: str = "outperformance_pricing_efficiency_investigation",
    market: str = "down",
    listing: str = "above_similar",
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "window_name": "weekly",
        "window_start": "2026-05-01",
        "window_end": "2026-05-08",
        "market_health_signal": market,
        "listing_airbnb_signal": listing,
        "revenue_pace_signal": "weak",
        "occupancy_gap_signal": "behind",
        "cleaning_efficiency_signal": "inefficient",
        "combined_signal_category": category,
        "investigation_priority": "medium",
        "explanation": "Listing signals are stronger than a soft market; investigate pricing efficiency before any rule change.",
        "allowed_recommendation_scope": "pricelabs_rule_review_only_if_core_metrics_support_it",
        "data_quality_status": "complete",
        "notes": "Airbnb can raise investigation priority, not recommend changes.",
        "average_overall_conversion_rate": "1.65",
        "first_page_search_impression_rate": "55.6",
        "search_to_listing_conversion_rate": "35.99",
        "listing_to_booking_conversion_rate": "3.98",
    }


def airbnb_summary_row() -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "metric_window_start": "2026-05-17",
        "metric_window_end": "2026-05-24",
        "airbnb_data_quality_status": "complete",
        "comparison_type": "previous_week",
        "comparison_window_start": "2026-05-10",
        "comparison_window_end": "2026-05-17",
        "page_views": "335",
        "first_page_search_impressions": "3535",
        "estimated_relevant_searches": "5804.6",
        "estimated_relevant_searches_per_day": "829.23",
        "wishlist_additions": "36",
        "average_overall_conversion_rate": "0.14%",
        "first_page_search_impression_rate": "60.9%",
        "search_to_listing_conversion_rate": "9.48%",
        "listing_to_booking_conversion_rate": "1.49%",
        "page_views_change_vs_previous_week": "159",
        "wishlist_additions_change_vs_previous_week": "8",
        "first_page_search_impressions_change_vs_previous_week": "",
        "overall_conversion_change_vs_previous_week": "",
        "search_to_listing_change_vs_previous_week": "",
        "listing_to_booking_change_vs_previous_week": "",
        "has_recent_history_baseline": "true",
        "has_similar_listing_benchmark": "true",
        "diagnostic_confidence": "high",
        "benchmark_type": "all_available_history",
        "relevant_searches_wow_change": "-255.4",
        "relevant_searches_vs_trailing_benchmark_pct": "-8.2",
        "search_to_listing_conversion_vs_benchmark_pct": "6.1",
        "listing_to_booking_conversion_vs_benchmark_pct": "-1.3",
        "market_demand_status": "normal",
        "visibility_status": "stable_or_strong",
        "search_card_status": "stable_or_strong",
        "listing_conversion_status": "stable_or_strong",
        "airbnb_diagnostic_category": "balanced_monitor_only",
        "parsed_metric_pages": "booking_conversion;page_views;wishlist_additions",
        "missing_metric_pages": "",
        "diagnostic_summary": "Airbnb conversion signals are available for the selected week.",
        "notes": "Airbnb diagnostic only.",
    }


def airbnb_weekly_history_rows() -> list[dict[str, str]]:
    metrics = [
        ("page_views", "333", "335", "-2"),
        ("first_page_search_impressions", "3280", "3535", "-255"),
        ("estimated_relevant_searches", "5805.31", "5804.6", "0.71"),
        ("estimated_relevant_searches_per_day", "829.33", "829.23", "0.1"),
        ("wishlist_additions", "35", "36", "-1"),
        ("average_overall_conversion_rate", "0.15%", "0.14", "0.01"),
        ("first_page_search_impression_rate", "56.5%", "60.9", "-4.4"),
        ("search_to_listing_conversion_rate", "10.15%", "9.48", "0.67"),
        ("listing_to_booking_conversion_rate", "1.50%", "1.49", "0.01"),
    ]
    return [
        {
            "run_date": "2026-06-01",
            "metric_window_start": "2026-05-24",
            "metric_window_end": "2026-05-31",
            "metric_name": metric_name,
            "current_value": current,
            "previous_week_value": previous,
            "change_vs_previous_week": change,
            "last_4_week_avg": "",
            "change_vs_last_4_week_avg": "",
            "recent_history_weeks_used": "6",
            "history_quality_status": "recent_baseline_ready",
            "notes": "Airbnb retained-history comparison only.",
        }
        for metric_name, current, previous, change in metrics
    ]


def diagnostic_issue_row(status: str = "open", *, last_seen_run_date: str = "2026-05-25") -> dict[str, str]:
    return {
        "issue_id": "airbnb_visibility_up_conversion_down",
        "issue_title": "Airbnb visibility up, conversion down",
        "first_seen_run_date": "2026-05-25",
        "last_seen_run_date": last_seen_run_date,
        "status": status,
        "severity": "high",
        "source_type": "airbnb_diagnostic",
        "signal_type": "visibility_up_conversion_down",
        "current_value": "3535",
        "previous_value": "489",
        "wow_change": "3046",
        "four_week_average": "654",
        "weeks_open": "1",
        "evidence_summary": "First-page search impressions increased sharply: 3535 vs 489. Conversion weakened / remained weak.",
        "suspected_cause": "listing competitiveness / value perception / booking friction",
        "recommended_investigation": "Review listing against competitors before changing PriceLabs rules.",
        "blocked_recommendation_reason": "Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation.",
        "resolution_rule": "Resolve after conversion improves for 2 consecutive runs.",
        "notes": "Diagnostic issue only; no recommendation action is created.",
    }


def listing_review_row(review_area: str = "search_card_appeal") -> dict[str, str]:
    return {
        "run_date": "2026-05-25",
        "issue_id": "airbnb_visibility_up_conversion_down",
        "review_area": review_area,
        "current_observation": "Airbnb visibility increased sharply, so the search card should be reviewed.",
        "risk_level": "high",
        "suggested_investigation": "Compare listing presentation against similar listings.",
        "suggested_test": "Test cover photo or title/opening value emphasis.",
        "price_rule_change_allowed": "false",
        "notes": "V1 template-based listing-side review.",
    }


def listing_change_row(status: str = "active", review_after_run_date: str = "2026-06-01") -> dict[str, str]:
    return {
        "change_date": "2026-05-26",
        "run_date": "2026-05-25",
        "related_issue_id": "airbnb_visibility_up_conversion_down",
        "change_type": "cover_photo_test",
        "old_value": "Hot tub hero photo",
        "new_value": "Updated hero grid/copy baseline",
        "reason": "Monitor conversion after listing-side baseline change.",
        "expected_effect": "Improve search-to-listing and listing-to-booking conversion.",
        "status": status,
        "review_after_run_date": review_after_run_date,
        "notes": "No additional listing changes until one full diagnostic cycle completes.",
    }


def stayfi_anniversary_summary_row() -> dict[str, str]:
    return {
        "run_date": "2026-06-01",
        "anniversary_audience_window_start": "2025-06-01",
        "anniversary_audience_window_end": "2025-06-07",
        "total_stayfi_rows_checked": "42",
        "eligible_guests": "3",
        "drafts_created": "0",
        "drafts_prepared_csv": "3",
        "gmail_drafts_created": "0",
        "gmail_draft_failures": "1",
        "excluded_invalid_emails": "2",
        "excluded_no_opt_in": "5",
        "excluded_bad_rating": "1",
        "skipped_duplicates": "4",
        "skipped_duplicates_from_log": "4",
        "rating_missing": "7",
        "detected_columns": "Contact Email | First Seen | Location | Status | Opt-in",
        "date_column_used": "First Seen",
        "email_column_used": "Contact Email",
        "rows_in_audience_window": "15",
        "excluded_missing_email": "1",
        "excluded_wrong_property": "2",
        "date_parse_failed": "3",
        "missing_required_columns": "",
        "stayfi_input_file": "StayFi Guests.csv",
        "source_file_status": "available",
        "draft_mode": "manual_gmail_draft_prepared_only",
    }


def stayfi_anniversary_send_result_rows() -> list[dict[str, str]]:
    return [
        {
            "email": "guest1@example.com",
            "subject": "Thinking about another Pocono getaway?",
            "gmail_message_id": "msg-1",
            "send_status": "sent",
            "error_message": "",
            "sent_at": "2026-06-01T00:00:00+00:00",
        },
        {
            "email": "guest-dry-run@example.com",
            "subject": "Thinking about another Pocono getaway?",
            "gmail_message_id": "",
            "send_status": "dry_run_would_send",
            "error_message": "",
            "sent_at": "",
        },
        {
            "email": "guest2@example.com",
            "subject": "Thinking about another Pocono getaway?",
            "gmail_message_id": "",
            "send_status": "failed",
            "error_message": "api failed",
            "sent_at": "",
        },
        {
            "email": "guest3@example.com",
            "subject": "Thinking about another Pocono getaway?",
            "gmail_message_id": "",
            "send_status": "skipped_duplicate_logged",
            "error_message": "already_logged",
            "sent_at": "",
        },
    ]


def airbnb_search_visibility_rows() -> list[dict[str, str]]:
    return [
        {
            "run_date": "2026-06-01",
            "scenario_name": "broad_no_filters",
            "found_status": "not_found",
            "max_pages_checked": "15",
            "page_number": "",
            "position_on_page": "",
            "cover_photo_status": "current_cover",
            "classifications": "broad_not_found",
        },
        {
            "run_date": "2026-06-01",
            "scenario_name": "broad_high_intent_filters",
            "found_status": "found",
            "max_pages_checked": "5",
            "page_number": "4",
            "position_on_page": "3",
            "cover_photo_status": "current_cover",
            "classifications": "high_intent_found;high_intent_found_deep;filtered_visibility_improved",
        },
    ]


def competitor_calendar_rows() -> list[dict[str, str]]:
    return [
        {
            "run_date": "2026-05-25",
            "stay_date": "2026-05-27",
            "competitor_name": "Comp A",
            "competitor_listing_id": "111",
            "airbnb_url": "https://www.airbnb.com/rooms/111",
            "is_subject_listing": "false",
            "competitor_price": "400",
            "competitor_available": "1",
            "competitor_min_stay": "2",
            "source_file": "source.csv",
        },
        {
            "run_date": "2026-05-25",
            "stay_date": "2026-05-28",
            "competitor_name": "Comp A",
            "competitor_listing_id": "111",
            "airbnb_url": "https://www.airbnb.com/rooms/111",
            "is_subject_listing": "false",
            "competitor_price": "500",
            "competitor_available": "1",
            "competitor_min_stay": "2",
            "source_file": "source.csv",
        },
        {
            "run_date": "2026-05-25",
            "stay_date": "2026-05-27",
            "competitor_name": "Comp B",
            "competitor_listing_id": "222",
            "airbnb_url": "https://www.airbnb.com/rooms/222",
            "is_subject_listing": "false",
            "competitor_price": "469.29",
            "competitor_available": "1",
            "competitor_min_stay": "1.96",
            "source_file": "source.csv",
        },
        {
            "run_date": "2026-05-25",
            "stay_date": "2026-05-28",
            "competitor_name": "Your Listing - Aloha Poconos",
            "competitor_listing_id": "",
            "airbnb_url": "",
            "is_subject_listing": "true",
            "competitor_price": "999",
            "competitor_available": "1",
            "competitor_min_stay": "7",
            "source_file": "source.csv",
        },
    ]


def test_email_revenue_report_content() -> None:
    markdown = build_markdown("2026-05-08", sample_rows())

    assert "Subject: Aloha Poconos Weekly Revenue Snapshot — 2026-05-08" in markdown
    assert "## Executive Snapshot" in markdown
    assert "## What Needs Attention" in markdown
    assert "## What To Protect" in markdown
    assert "## Market vs Listing Signal" in markdown
    assert "## Airbnb Funnel Signals" in markdown
    assert "## Open Diagnostic Issues" in markdown
    assert "## Listing Review Needed" in markdown
    assert "## Recommendation Review" in markdown
    assert "## Booking Source Notes" in markdown
    assert "## Data Notes" in markdown
    assert "Current month 2026-05 is conversion_risk." in markdown
    assert "Next month 2026-06 is conversion_risk." in markdown
    assert "Protected future months: 2026-07." in markdown
    assert "Historical actuals available: 2026-03." in markdown
    assert "| 2025-11 |" not in markdown
    assert "Cleanings / Stays" in markdown
    assert "| 2026-03 | monthly_trends_actuals | $8,888 | - | $8,888 | 23 | 11 | 74.2% | $351 | $808 | historical_actuals | monitor |" in markdown
    assert "| 2026-05 | monthly_trends_current | $2,834 | $7,425 | $10,259 | 7 | 6 | 55.0% | $425 | $472 | conversion_risk | advisory |" in markdown
    assert "- 2026-05: Airbnb 5, Vrbo 1. Main source: airbnb." in markdown
    assert "| 2026-06 | future_calendar | $314 | $14,090 | $14,404 | 1 | 1 | 3.3% | $314 | $314 | conversion_risk | advisory |" in markdown
    assert "| 2026-07 | future_calendar | $0 | $22,614 | $22,614 | 0 | - | 0.0% | - | - | protect_open_value | protect |" in markdown
    assert "| 2026-11 | partial_horizon | $0 | $988 | $988 | 0 | - | - | - | - | partial_horizon | monitor |" in markdown
    assert "Partial horizon monitor note: 2026-11 is inside the export horizon only partially." in markdown
    assert "Historical occupancy is calculated from booked nights divided by calendar days." in markdown
    assert "Future full-month occupancy is calculated from booked nights divided by days in scope." in markdown
    assert "Current and partial horizon month occupancy is hidden unless Monthly Trends provides monthly occupancy." in markdown
    assert "Revenue Captured uses Monthly Trends when available" in markdown
    assert "Cleaning and length-of-stay metrics use Bookings Report when available." in markdown
    assert "Historical booked nights are estimated from Monthly Trends revenue divided by ADR." in markdown
    assert "Historical cleanings are estimated from Monthly Trends booked-night estimates and observed current/future Bookings Report LOS." in markdown
    assert "Bookings Report is not treated as exact historical truth unless a future enhancement validates coverage." in markdown
    assert "Revenue / Cleaning is calculated using Cleanings / Stays, not Booked Nights." in markdown
    assert "data_not_available" in markdown
    assert "Airbnb revenue is not mixed into this report." in markdown
    assert "Historical actuals come from PriceLabs KPI On The Books." not in markdown

    prohibited = (
        "lower prices",
        "match the 75th percentile",
        "discount all open dates",
        "manually override",
        "change base price to",
    )
    for phrase in prohibited:
        assert phrase not in markdown.lower()


def test_airbnb_funnel_section_includes_count_and_rate_separately() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), airbnb_summary_rows=[airbnb_summary_row()])
    section = markdown.split("## Airbnb Funnel Signals", 1)[1].split("## Recommendation Review", 1)[0]

    assert "- Metric window: 2026-05-17 to 2026-05-24." in section
    assert "- Page views: 335." in section
    assert "- First-page search impressions: 3535." in section
    assert "- Estimated relevant searches: 5804.6." in section
    assert "- Estimated relevant searches/day: 829.23." in section
    assert "- First-page search impression rate: 60.9%." in section
    assert "- Average overall conversion rate: 0.14%." in section
    assert "- Search-to-listing conversion rate: 9.48%." in section
    assert "- Listing-to-booking conversion rate: 1.49%." in section
    assert "First-page search impressions: 3535%." not in section
    assert "- Relevant search benchmark: all_available_history." in section
    assert "- Market demand status: normal." in section
    assert "- Airbnb diagnostic category: balanced_monitor_only." in section


def test_airbnb_funnel_week_over_week_section_uses_history_comparison() -> None:
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        airbnb_summary_rows=[airbnb_summary_row()],
        airbnb_weekly_history_rows=airbnb_weekly_history_rows(),
    )
    section = markdown.split("## Airbnb Funnel Week-over-Week", 1)[1].split("## Open Diagnostic Issues", 1)[0]

    assert "- Page views: 335 \u2192 333 (-2)" in section
    assert "- First-page search impressions: 3535 \u2192 3280 (-255)" in section
    assert "- Estimated relevant searches: 5804.6 \u2192 5805.31 (+0.71)" in section
    assert "- Estimated relevant searches/day: 829.23 \u2192 829.33 (+0.1)" in section
    assert "- Wishlist additions: 36 \u2192 35 (-1)" in section
    assert "- Average overall conversion rate: 0.14% \u2192 0.15% (+0.01 pp)" in section
    assert "- First-page search impression rate: 60.9% \u2192 56.5% (-4.4 pp)" in section
    assert "- Search-to-listing conversion rate: 9.48% \u2192 10.15% (+0.67 pp)" in section
    assert "- Listing-to-booking conversion rate: 1.49% \u2192 1.50% (+0.01 pp)" in section
    assert "Diagnostic only; this does not create a PriceLabs rule recommendation." in section


def test_airbnb_funnel_week_over_week_unavailable_does_not_fail_report() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), airbnb_summary_rows=[airbnb_summary_row()])
    section = markdown.split("## Airbnb Funnel Week-over-Week", 1)[1].split("## Open Diagnostic Issues", 1)[0]

    assert "Airbnb funnel week-over-week comparison unavailable for this run." in section


def test_airbnb_funnel_section_handles_missing_summary() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), airbnb_summary_rows=[])
    section = markdown.split("## Airbnb Funnel Signals", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Airbnb funnel diagnostics unavailable for this run." in section
    assert "Manual action required before final report: run Airbnb capture with browser login/MFA" in section
    assert "airbnb.download_diagnostics --run-date <run_date> --mode capture-headed-and-validate" in section
    assert "airbnb.download_diagnostics --run-date <run_date> --mode promote-staged" in section
    assert "airbnb.run_diagnostics --run-date <run_date>" in section
    assert "Airbnb funnel signals are diagnostic only." in section
    assert "- 2026-06: Monitor" in markdown


def test_airbnb_funnel_section_does_not_change_recommendation_logic() -> None:
    markdown = build_markdown(
        "2026-05-08",
        sample_rows(),
        combined_signal_rows=[combined_signal_row()],
        airbnb_summary_rows=[airbnb_summary_row()],
    )
    recommendation_section = markdown.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]

    assert "- 2026-06: Monitor" in recommendation_section
    assert "Airbnb Funnel Signals" not in recommendation_section
    assert "lower price" not in recommendation_section.lower()
    assert "raise price" not in recommendation_section.lower()


def test_open_diagnostic_issues_section_appears_when_open_issue_exists() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row()],
        diagnostic_issue_tracker_available=True,
    )
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "High/Open: Airbnb visibility up, conversion down." in section
    assert "First seen: 2026-05-25. Weeks open: 1." in section
    assert "Evidence: First-page search impressions increased sharply: 3535 vs 489. Conversion weakened / remained weak." in section
    assert "Investigation: Review listing against competitors before changing PriceLabs rules." in section
    assert "Guardrail: Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation." in section
    assert "Diagnostic issues are informational only." in section


def test_improving_diagnostic_issue_appears_active_with_next_check() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row(status="improving")],
        diagnostic_issue_tracker_available=True,
    )
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Improving: Airbnb visibility up, conversion down." in section
    assert "Next check: Resolve after conversion improves for 2 consecutive runs." in section
    assert "Guardrail: Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation." in section


def test_monitoring_diagnostic_issue_appears_active() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row(status="monitoring")],
        diagnostic_issue_tracker_available=True,
    )
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Monitoring: Airbnb visibility up, conversion down." in section
    assert "Investigation: Review listing against competitors before changing PriceLabs rules." in section


def test_open_diagnostic_issues_section_handles_missing_tracker() -> None:
    markdown = build_markdown("2026-05-08", sample_rows())
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "No diagnostic issue tracker available for this run." in section


def test_open_diagnostic_issues_section_omits_resolved_only_tracker() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row(status="resolved")],
        diagnostic_issue_tracker_available=True,
    )
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recently Resolved Diagnostic Issues", 1)[0]

    assert "No active diagnostic issues." in section
    assert "Airbnb visibility up, conversion down" not in section


def test_resolved_issue_appears_under_recently_resolved_when_resolved_this_run() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row(status="resolved")],
        diagnostic_issue_tracker_available=True,
    )
    section = markdown.split("## Recently Resolved Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Resolved: Airbnb visibility up, conversion down." in section
    assert "First seen: 2026-05-25. Resolved on: 2026-05-25." in section
    assert "Resolution rule: Resolve after conversion improves for 2 consecutive runs." in section


def test_resolved_issue_from_prior_run_does_not_show_recently_resolved() -> None:
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row(status="resolved", last_seen_run_date="2026-05-25")],
        diagnostic_issue_tracker_available=True,
    )

    assert "## Recently Resolved Diagnostic Issues" not in markdown


def test_open_diagnostic_issues_do_not_change_recommendation_review() -> None:
    without_issue = build_markdown("2026-05-08", sample_rows())
    with_issue = build_markdown(
        "2026-05-08",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row()],
        diagnostic_issue_tracker_available=True,
    )

    without_recommendations = without_issue.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    with_recommendations = with_issue.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    assert with_recommendations == without_recommendations


def test_listing_review_needed_section_appears_when_active_review_exists() -> None:
    markdown = build_markdown(
        "2026-05-08",
        sample_rows(),
        listing_review_rows=[
            listing_review_row("search_card_appeal"),
            listing_review_row("cover_photo_first_five_photos"),
            listing_review_row("title_description_opening"),
            listing_review_row("amenities_presentation"),
            listing_review_row("guest_fit_sleeping_capacity"),
            listing_review_row("trust_review_signals"),
            listing_review_row("booking_friction_risks"),
            listing_review_row("competitor_comparison"),
        ],
        listing_review_available=True,
    )
    section = markdown.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Listing-side review is recommended because an open diagnostic issue shows Airbnb visibility increased sharply while conversion weakened or remained weak." in section
    assert "Focus review areas: search card appeal, cover/first photos, title/opening copy, amenities presentation, guest fit, trust signals, booking friction, competitor comparison." in section
    assert "This is diagnostic only and does not create a PriceLabs rule recommendation." in section


def test_listing_review_needed_section_references_full_review_when_markdown_exists() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        listing_review_markdown_available=True,
    )
    section = markdown.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Full review: see listing_competitor_review_2026-05-25.md in the evidence bundle." in section


def test_listing_review_needed_section_references_listing_snapshot_when_exists() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        listing_snapshot_available=True,
    )
    section = markdown.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Listing snapshot: see listing_state_snapshot_2026-05-25.md in the evidence bundle." in section


def test_listing_review_needed_section_references_visual_baseline_only_when_exists() -> None:
    with_visuals = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        listing_visual_baseline_available=True,
    )
    without_visuals = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        listing_visual_baseline_available=False,
    )

    visual_section = with_visuals.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]
    no_visual_section = without_visuals.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Visual baseline files are included in the evidence bundle when available." in visual_section
    assert "Visual baseline files are included" not in no_visual_section


def test_listing_review_needed_section_references_competitor_list_when_exists() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        competitor_list_available=True,
    )
    section = markdown.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Competitor set: see pricelabs_competitor_list_2026-05-25.csv in the evidence bundle." in section


def test_listing_review_needed_section_includes_competitor_calendar_context_when_exists() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        competitor_calendar_rows=competitor_calendar_rows(),
        competitor_calendar_available=True,
    )
    section = markdown.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Competitor context: selected PriceLabs comps show median average price of $459.65" in section
    assert "median minimum stay of 1.98 nights" in section
    assert "median available date count of 1.5 across the 90-day window" in section
    assert "Subject listing metrics are intentionally excluded from this competitor context" in section
    assert "Subject listing average price" not in section
    assert "Subject listing average min stay" not in section
    assert "Subject listing available date count" not in section
    assert "$999" not in section


def test_listing_review_needed_section_does_not_reference_missing_full_review() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        listing_review_markdown_available=False,
    )
    section = markdown.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Full review:" not in section
    assert "listing_competitor_review_2026-05-25.md" not in section
    assert "Listing snapshot:" not in section
    assert "listing_state_snapshot_2026-05-25.md" not in section
    assert "Visual baseline files" not in section
    assert "Competitor set:" not in section
    assert "pricelabs_competitor_list_2026-05-25.csv" not in section
    assert "Competitor context:" not in section


def test_listing_review_needed_section_handles_missing_or_empty_review() -> None:
    missing = build_markdown("2026-05-08", sample_rows())
    empty = build_markdown("2026-05-08", sample_rows(), listing_review_rows=[], listing_review_available=True)

    missing_section = missing.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]
    empty_section = empty.split("## Listing Review Needed", 1)[1].split("## Recommendation Review", 1)[0]

    assert "No active listing-side review is needed for this run." in missing_section
    assert "No active listing-side review is needed for this run." in empty_section


def test_listing_review_needed_does_not_change_recommendation_review() -> None:
    without_review = build_markdown("2026-05-08", sample_rows())
    with_review = build_markdown(
        "2026-05-08",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
    )

    without_recommendations = without_review.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    with_recommendations = with_review.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    assert with_recommendations == without_recommendations


def test_listing_review_evidence_reference_does_not_change_recommendation_review() -> None:
    without_reference = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        listing_review_markdown_available=False,
    )
    with_reference = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_review_rows=[listing_review_row()],
        listing_review_available=True,
        listing_review_markdown_available=True,
        listing_snapshot_available=True,
        listing_visual_baseline_available=True,
        competitor_list_available=True,
        competitor_calendar_rows=competitor_calendar_rows(),
        competitor_calendar_available=True,
    )

    without_recommendations = without_reference.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    with_recommendations = with_reference.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    assert with_recommendations == without_recommendations


def test_active_listing_tests_section_appears_when_active_change_exists() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_change_rows=[listing_change_row()],
        listing_change_log_available=True,
    )
    section = markdown.split("## Active Listing Tests", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Active test: cover_photo_test." in section
    assert "Related issue: airbnb_visibility_up_conversion_down." in section
    assert "Change date: 2026-05-26." in section
    assert "Expected effect: Improve search-to-listing and listing-to-booking conversion." in section
    assert "Review after: 2026-06-01." in section
    assert "Review due this run: No." in section
    assert "Do not make additional listing or pricing changes until this test has at least one full Airbnb diagnostic cycle" in section


def test_active_listing_tests_section_shows_review_due_this_run() -> None:
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        listing_change_rows=[listing_change_row(review_after_run_date="2026-06-01")],
        listing_change_log_available=True,
    )
    section = markdown.split("## Active Listing Tests", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Review due this run: Yes." in section


def test_active_listing_tests_section_notes_visual_baseline_when_available() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_change_rows=[listing_change_row()],
        listing_change_log_available=True,
        listing_visual_baseline_available=True,
    )
    section = markdown.split("## Active Listing Tests", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Current visual baseline files are included in the evidence bundle." in section


def test_active_listing_tests_section_omits_visual_note_when_missing() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_change_rows=[listing_change_row()],
        listing_change_log_available=True,
        listing_visual_baseline_available=False,
    )
    section = markdown.split("## Active Listing Tests", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Current visual baseline files are included" not in section


def test_active_listing_tests_omits_inactive_and_resolved_changes() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_change_rows=[
            listing_change_row(status="open"),
            listing_change_row(status="monitoring"),
            listing_change_row(status="resolved"),
            listing_change_row(status="inactive"),
            listing_change_row(status="closed"),
        ],
        listing_change_log_available=True,
    )

    assert "## Active Listing Tests" not in markdown


def test_missing_listing_change_log_does_not_render_active_tests() -> None:
    markdown = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_change_rows=[listing_change_row()],
        listing_change_log_available=False,
    )

    assert "## Active Listing Tests" not in markdown


def test_active_listing_tests_do_not_change_recommendation_review() -> None:
    without_change = build_markdown("2026-05-25", sample_rows())
    with_change = build_markdown(
        "2026-05-25",
        sample_rows(),
        listing_change_rows=[listing_change_row()],
        listing_change_log_available=True,
    )

    without_recommendations = without_change.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    with_recommendations = with_change.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    assert with_recommendations == without_recommendations


def test_airbnb_search_visibility_section_appears_when_diagnostic_exists() -> None:
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        airbnb_search_visibility_rows=airbnb_search_visibility_rows(),
        airbnb_search_visibility_available=True,
    )
    section = markdown.split("## Airbnb Search Visibility Diagnostic", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Broad no-filter status: not_found after 15 pages checked." in section
    assert "High-intent filter status: found on page 4, position 3." in section
    assert "Best filtered scenario found: broad_high_intent_filters." in section
    assert "Cover photo status: current_cover." in section
    assert "Airbnb search visibility is diagnostic only and does not create a PriceLabs rule recommendation." in section


def test_airbnb_search_visibility_section_omitted_when_missing() -> None:
    markdown = build_markdown("2026-06-01", sample_rows(), airbnb_search_visibility_available=False)

    assert "## Airbnb Search Visibility Diagnostic" not in markdown


def test_airbnb_search_visibility_does_not_change_recommendation_review() -> None:
    without_visibility = build_markdown("2026-06-01", sample_rows())
    with_visibility = build_markdown(
        "2026-06-01",
        sample_rows(),
        airbnb_search_visibility_rows=airbnb_search_visibility_rows(),
        airbnb_search_visibility_available=True,
    )

    without_recommendations = without_visibility.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    with_recommendations = with_visibility.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    assert with_recommendations == without_recommendations


def test_stayfi_anniversary_email_section_appears_when_summary_exists() -> None:
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        stayfi_anniversary_summary_rows=[stayfi_anniversary_summary_row()],
        stayfi_anniversary_summary_available=True,
    )
    section = markdown.split("## StayFi Anniversary Email Drafts", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Anniversary audience window: 2025-06-01 to 2025-06-07." in section
    assert "Date column used: First Seen. Email column used: Contact Email." in section
    assert "Total StayFi rows checked: 42." in section
    assert "Rows in audience window: 15." in section
    assert "Eligible guests: 3." in section
    assert "Draft-ready CSV records prepared: 3." in section
    assert "Gmail drafts created: 0." in section
    assert "Gmail draft failures: 1." in section
    assert "Excluded invalid emails: 2." in section
    assert "Excluded missing email: 1." in section
    assert "Excluded wrong property: 2." in section
    assert "Excluded no opt-in: 5." in section
    assert "Excluded bad rating 1-3 stars: 1." in section
    assert "Skipped duplicates from permanent log: 4." in section
    assert "Date parse failures: 3." in section
    assert "Draft-only workflow; no emails were sent automatically." in section


def test_stayfi_anniversary_email_section_shows_send_results_when_available() -> None:
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        stayfi_anniversary_summary_rows=[stayfi_anniversary_summary_row()],
        stayfi_anniversary_summary_available=True,
        stayfi_anniversary_send_result_rows=stayfi_anniversary_send_result_rows(),
        stayfi_anniversary_send_results_available=True,
    )
    section = markdown.split("## StayFi Anniversary Email Drafts", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Emails sent: 1." in section
    assert "Dry-run would send: 1." in section
    assert "Send failures: 1." in section
    assert "Send skipped duplicates from permanent log: 1." in section
    assert "Manual send workflow; no emails were sent automatically by the weekly pipeline." in section


def test_stayfi_anniversary_email_section_omitted_when_missing() -> None:
    markdown = build_markdown("2026-06-01", sample_rows(), stayfi_anniversary_summary_available=False)

    assert "## StayFi Anniversary Email Drafts" not in markdown


def test_stayfi_anniversary_email_section_warns_when_source_missing() -> None:
    summary = stayfi_anniversary_summary_row()
    summary["source_file_status"] = "missing"
    summary["stayfi_input_file"] = "data/source/stayfi/stayfi_guests_2026.csv"
    summary["total_stayfi_rows_checked"] = "0"
    summary["eligible_guests"] = "0"
    summary["drafts_created"] = "0"
    summary["drafts_prepared_csv"] = "0"
    summary["gmail_drafts_created"] = "0"
    summary["gmail_draft_failures"] = "0"
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        stayfi_anniversary_summary_rows=[summary],
        stayfi_anniversary_summary_available=True,
    )
    section = markdown.split("## StayFi Anniversary Email Drafts", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Warning: StayFi source file missing: data/source/stayfi/stayfi_guests_2026.csv." in section
    assert "Draft-ready CSV records prepared: 0." in section
    assert "Gmail drafts created: 0." in section
    assert "Gmail draft failures: 0." in section


def test_stayfi_anniversary_email_section_warns_when_columns_missing() -> None:
    summary = stayfi_anniversary_summary_row()
    summary["source_file_status"] = "available_but_missing_columns"
    summary["missing_required_columns"] = "first_sign_in | property"
    markdown = build_markdown(
        "2026-06-01",
        sample_rows(),
        stayfi_anniversary_summary_rows=[summary],
        stayfi_anniversary_summary_available=True,
    )
    section = markdown.split("## StayFi Anniversary Email Drafts", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Warning: StayFi source file is missing required columns: first_sign_in | property." in section


def test_stayfi_anniversary_section_does_not_change_recommendation_review() -> None:
    without_stayfi = build_markdown("2026-06-01", sample_rows())
    with_stayfi = build_markdown(
        "2026-06-01",
        sample_rows(),
        stayfi_anniversary_summary_rows=[stayfi_anniversary_summary_row()],
        stayfi_anniversary_summary_available=True,
    )

    without_recommendations = without_stayfi.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    with_recommendations = with_stayfi.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]
    assert with_recommendations == without_recommendations


def test_email_includes_market_vs_listing_signal_when_combined_csv_exists() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), combined_signal_rows=[combined_signal_row()])

    assert "## Market vs Listing Signal" in markdown
    assert (
        "Market/listing signal: Outperformance / pricing-efficiency review. "
        "Airbnb diagnostics are above similar listings, but PriceLabs core metrics show weak revenue pace, "
        "behind-market occupancy, and inefficient cleaning performance. This should be treated as a high-priority "
        "pricing-efficiency review, not an automatic discount signal. Protect premium positioning and avoid filling "
        "gaps with low-value turnovers unless PriceLabs revenue pace and booking-window data justify it."
    ) in markdown
    assert "Investigation priority: medium." in markdown
    assert "Data quality status: complete." in markdown
    assert "Average overall conversion rate: 1.65%." in markdown
    assert "First-page search impression rate: 55.6%." in markdown
    assert "Search-to-listing conversion rate: 35.99%." in markdown
    assert "Listing-to-booking conversion rate: 3.98%." in markdown


def test_email_handles_missing_combined_signal_gracefully() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), combined_signal_rows=[])

    assert "## Market vs Listing Signal" in markdown
    assert "Combined market/listing signal unavailable for this run." in markdown


def test_airbnb_only_signal_does_not_create_pricelabs_recommendation() -> None:
    signal = combined_signal_row(category="insufficient_data", market="unknown", listing="down")
    signal.update(
        {
            "allowed_recommendation_scope": "none",
            "explanation": "PriceLabs market/revenue context is missing.",
            "data_quality_status": "missing_pricelabs_context",
        }
    )
    markdown = build_markdown("2026-05-08", sample_rows(), combined_signal_rows=[signal])

    assert "PriceLabs market/revenue context is missing." in markdown
    assert "Airbnb diagnostics can raise investigation priority" in markdown
    assert "Airbnb rule" not in markdown
    assert "automatic discount signal" not in markdown
    assert "Pricing efficiency risk:" not in markdown


def test_market_vs_listing_section_does_not_add_forbidden_airbnb_truth_fields() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), combined_signal_rows=[combined_signal_row()])
    section = markdown.split("## Market vs Listing Signal", 1)[1].split("## Recommendation Review", 1)[0]
    forbidden = (
        "lower price",
        "raise price",
        "manual override",
        "airbnb booked nights",
        "airbnb booking totals",
        "airbnb cleaning count",
        "airbnb monthly revenue pace",
        "manual calendar",
    )

    for phrase in forbidden:
        assert phrase not in section.lower()


def test_recommendation_review_includes_pricing_efficiency_risk_context() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), combined_signal_rows=[combined_signal_row()])
    recommendation_section = markdown.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]

    assert (
        "Pricing efficiency risk: PriceLabs core metrics show weak revenue pace, behind-market occupancy, and inefficient cleaning performance. "
        "Treat this as investigation context only; no rule change is recommended unless existing PriceLabs recommendation logic supports it."
    ) in recommendation_section
    assert recommendation_section.index("Pricing efficiency risk:") < recommendation_section.index("- 2026-06:")
    assert "- 2026-06: Monitor" in recommendation_section
    forbidden = (
        "lower prices",
        "discount",
        "reduce base price",
        "change pricelabs rule",
        "adjust minimum price",
    )
    for phrase in forbidden:
        assert phrase not in recommendation_section.lower()


def test_recommendation_review_omits_pricing_efficiency_risk_for_incomplete_core_data() -> None:
    signal = combined_signal_row()
    signal["data_quality_status"] = "partial"
    markdown = build_markdown("2026-05-08", sample_rows(), combined_signal_rows=[signal])
    recommendation_section = markdown.split("## Recommendation Review", 1)[1].split("## Booking Source Notes", 1)[0]

    assert "Pricing efficiency risk:" not in recommendation_section


def test_email_reason_review_is_concise_and_gated() -> None:
    markdown = build_markdown(
        "2026-05-08",
        sample_rows(),
        [
            reason_row(
                "days_16_45",
                "weak_pickup",
                "listing_or_conversion_issue",
                recommendation_type="investigate_listing",
            ),
            reason_row(
                "days_46_90",
                "weak_pickup",
                "price_or_rule_issue",
                recommendation_allowed="true",
                recommendation_type="consider_pricelabs_rule_change",
            ),
        ],
    )

    assert "## Reason Review" in markdown
    assert (
        "Days 16-45 show weak pickup. Likely reason: listing/conversion issue. "
        "Recommendation gate: closed; investigate listing/conversion before changing PriceLabs. "
        "Next action: investigate listing/conversion before changing PriceLabs."
    ) in markdown
    assert (
        "Days 46-90 show weak pickup. Likely reason: price/rule issue. "
        "Recommendation gate: open; a PriceLabs rule change may be considered. "
        "Next action: review the relevant PriceLabs rule area."
    ) in markdown
    assert "PriceLabs rule change justified now" not in markdown


def test_email_recommendation_review_respects_closed_reason_gate() -> None:
    markdown = build_markdown(
        "2026-05-08",
        sample_rows(),
        [
            reason_row(
                "days_16_45",
                "weak_pickup",
                "listing_or_conversion_issue",
                recommendation_allowed="false",
                recommendation_type="investigate_listing",
            )
        ],
    )

    assert "## Reason Review" in markdown
    assert "## Recommendation Review" in markdown
    assert "- 2026-06: Investigate listing/conversion before changing PriceLabs rules." in markdown
    assert (
        "- 2026-06: Monitor next-month conversion risk while protecting premium positioning. "
        "Rule areas to review:"
    ) not in markdown


def test_email_revenue_report_cli_writes_file(tmp_path, monkeypatch) -> None:
    rolling_file = tmp_path / "rolling_13_month_revenue_view_2026-05-08.csv"
    summary_file = tmp_path / "monthly_revenue_summary_2026-05-08.md"
    output_file = tmp_path / "email_revenue_report_2026-05-08.md"

    with rolling_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=sample_rows()[0].keys())
        writer.writeheader()
        writer.writerows(sample_rows())
    summary_file.write_text("# Monthly Revenue Summary - 2026-05-08\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_revenue_report",
            "--run-date",
            "2026-05-08",
            "--rolling-file",
            str(rolling_file),
            "--summary-file",
            str(summary_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0
    assert output_file.exists()
    assert "Aloha Poconos Weekly Revenue Snapshot" in output_file.read_text(encoding="utf-8")


def test_email_revenue_report_cli_defaults_to_per_run_analysis_paths(tmp_path, monkeypatch) -> None:
    run_date = "2026-05-08"
    monkeypatch.chdir(tmp_path)
    analysis_dir = tmp_path / "data" / "runs" / run_date / "analysis"
    rolling_file = analysis_dir / f"rolling_13_month_revenue_view_{run_date}.csv"
    summary_file = analysis_dir / f"monthly_revenue_summary_{run_date}.md"
    reason_file = analysis_dir / f"performance_reason_review_{run_date}.csv"
    combined_file = analysis_dir / f"combined_market_listing_signal_{run_date}.csv"
    output_file = analysis_dir / f"email_revenue_report_{run_date}.md"

    analysis_dir.mkdir(parents=True)
    with rolling_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=sample_rows()[0].keys())
        writer.writeheader()
        writer.writerows(sample_rows())
    summary_file.write_text("# Monthly Revenue Summary - 2026-05-08\n", encoding="utf-8")
    with reason_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=reason_row("days_0_15", "none", "no_issue").keys())
        writer.writeheader()
        writer.writerow(reason_row("days_0_15", "none", "no_issue"))
    with combined_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=combined_signal_row().keys())
        writer.writeheader()
        writer.writerow(combined_signal_row())

    monkeypatch.setattr(sys, "argv", ["email_revenue_report", "--run-date", run_date])

    assert run() == 0
    markdown = output_file.read_text(encoding="utf-8")
    assert "## Reason Review" in markdown
    assert "## Market vs Listing Signal" in markdown
    assert "## Recommendation Review" in markdown
    assert markdown.index("## Reason Review") < markdown.index("## Market vs Listing Signal") < markdown.index("## Recommendation Review")
    assert "Outperformance / pricing-efficiency review" in markdown


def test_email_revenue_report_cli_reads_combined_signal_from_output_analysis_dir(tmp_path, monkeypatch) -> None:
    run_date = "2026-05-08"
    analysis_dir = tmp_path / "data" / "runs" / run_date / "analysis"
    rolling_file = analysis_dir / f"rolling_13_month_revenue_view_{run_date}.csv"
    summary_file = analysis_dir / f"monthly_revenue_summary_{run_date}.md"
    output_file = analysis_dir / f"email_revenue_report_{run_date}.md"
    combined_file = analysis_dir / f"combined_market_listing_signal_{run_date}.csv"

    analysis_dir.mkdir(parents=True)
    with rolling_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=sample_rows()[0].keys())
        writer.writeheader()
        writer.writerows(sample_rows())
    summary_file.write_text("# Monthly Revenue Summary - 2026-05-08\n", encoding="utf-8")
    with combined_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=combined_signal_row().keys())
        writer.writeheader()
        writer.writerow(combined_signal_row())

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_revenue_report",
            "--run-date",
            run_date,
            "--rolling-file",
            str(rolling_file),
            "--summary-file",
            str(summary_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0
    markdown = output_file.read_text(encoding="utf-8")
    assert "## Market vs Listing Signal" in markdown
    assert markdown.index("## Market vs Listing Signal") < markdown.index("## Recommendation Review")
    assert "Outperformance / pricing-efficiency review" in markdown


def test_email_revenue_report_cli_combined_signal_override_and_missing_default(tmp_path, monkeypatch) -> None:
    run_date = "2026-05-08"
    rolling_file = tmp_path / f"rolling_13_month_revenue_view_{run_date}.csv"
    summary_file = tmp_path / f"monthly_revenue_summary_{run_date}.md"
    output_file = tmp_path / f"email_revenue_report_{run_date}.md"
    override_file = tmp_path / "override_combined_signal.csv"

    with rolling_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=sample_rows()[0].keys())
        writer.writeheader()
        writer.writerows(sample_rows())
    summary_file.write_text("# Monthly Revenue Summary - 2026-05-08\n", encoding="utf-8")
    with override_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=combined_signal_row().keys())
        writer.writeheader()
        writer.writerow(combined_signal_row(category="market_softness", market="down", listing="down"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_revenue_report",
            "--run-date",
            run_date,
            "--rolling-file",
            str(rolling_file),
            "--summary-file",
            str(summary_file),
            "--output-file",
            str(output_file),
            "--combined-signal-file",
            str(override_file),
        ],
    )

    assert run() == 0
    markdown = output_file.read_text(encoding="utf-8")
    assert "Market/listing signal: Market softness." in markdown

    output_file.unlink()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "email_revenue_report",
            "--run-date",
            run_date,
            "--rolling-file",
            str(rolling_file),
            "--summary-file",
            str(summary_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0
    markdown = output_file.read_text(encoding="utf-8")
    assert "## Market vs Listing Signal" in markdown
    assert "Combined market/listing signal unavailable for this run." in markdown
    assert "## Recommendation Review" in markdown
    assert "- 2026-06: Monitor" in markdown
    assert "Pricing efficiency risk:" not in markdown
