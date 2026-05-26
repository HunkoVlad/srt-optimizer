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
        "parsed_metric_pages": "booking_conversion;page_views;wishlist_additions",
        "missing_metric_pages": "",
        "diagnostic_summary": "Airbnb conversion signals are available for the selected week.",
        "notes": "Airbnb diagnostic only.",
    }


def diagnostic_issue_row(status: str = "open") -> dict[str, str]:
    return {
        "issue_id": "airbnb_visibility_up_conversion_down",
        "issue_title": "Airbnb visibility up, conversion down",
        "first_seen_run_date": "2026-05-25",
        "last_seen_run_date": "2026-05-25",
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
        "resolution_rule": "Keep open until conversion improves for 2 consecutive runs; V1 does not auto-resolve.",
        "notes": "Diagnostic issue only; no recommendation action is created.",
    }


def test_email_revenue_report_content() -> None:
    markdown = build_markdown("2026-05-08", sample_rows())

    assert "Subject: Aloha Poconos Weekly Revenue Snapshot — 2026-05-08" in markdown
    assert "## Executive Snapshot" in markdown
    assert "## What Needs Attention" in markdown
    assert "## What To Protect" in markdown
    assert "## Market vs Listing Signal" in markdown
    assert "## Airbnb Funnel Signals" in markdown
    assert "## Open Diagnostic Issues" in markdown
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
    assert "- First-page search impression rate: 60.9%." in section
    assert "- Average overall conversion rate: 0.14%." in section
    assert "- Search-to-listing conversion rate: 9.48%." in section
    assert "- Listing-to-booking conversion rate: 1.49%." in section
    assert "First-page search impressions: 3535%." not in section


def test_airbnb_funnel_section_handles_missing_summary() -> None:
    markdown = build_markdown("2026-05-08", sample_rows(), airbnb_summary_rows=[])
    section = markdown.split("## Airbnb Funnel Signals", 1)[1].split("## Recommendation Review", 1)[0]

    assert "Airbnb funnel diagnostics unavailable for this run." in section
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
        "2026-05-08",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row()],
        diagnostic_issue_tracker_available=True,
    )
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "High: Airbnb visibility up, conversion down." in section
    assert "First seen: 2026-05-25. Weeks open: 1." in section
    assert "Evidence: First-page search impressions increased sharply: 3535 vs 489. Conversion weakened / remained weak." in section
    assert "Investigation: Review listing against competitors before changing PriceLabs rules." in section
    assert "Guardrail: Airbnb diagnostic signal alone cannot create PriceLabs rule recommendation." in section
    assert "Diagnostic issues are informational only." in section


def test_open_diagnostic_issues_section_handles_missing_tracker() -> None:
    markdown = build_markdown("2026-05-08", sample_rows())
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "No diagnostic issue tracker available for this run." in section


def test_open_diagnostic_issues_section_omits_resolved_only_tracker() -> None:
    markdown = build_markdown(
        "2026-05-08",
        sample_rows(),
        diagnostic_issue_rows=[diagnostic_issue_row(status="resolved")],
        diagnostic_issue_tracker_available=True,
    )
    section = markdown.split("## Open Diagnostic Issues", 1)[1].split("## Recommendation Review", 1)[0]

    assert "No active diagnostic issues." in section
    assert "Airbnb visibility up, conversion down" not in section


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
