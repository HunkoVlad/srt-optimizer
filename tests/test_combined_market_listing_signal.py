import csv
from pathlib import Path

from analysis import combined_market_listing_signal


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else ["placeholder"]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_output(path: Path) -> dict[str, str]:
    rows = list(csv.DictReader(path.open("r", encoding="utf-8")))
    assert len(rows) == 1
    return rows[0]


def run_with_inputs(
    tmp_path: Path,
    *,
    future_rows: list[dict[str, str]] | None = None,
    rolling_rows: list[dict[str, str]] | None = None,
    window_signal_rows: list[dict[str, str]] | None = None,
    airbnb_history_rows: list[dict[str, str]] | None = None,
    similar_rows: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    run_date = "2026-05-20"
    run_dir = tmp_path / "data" / "runs" / run_date
    analysis_dir = run_dir / "analysis"
    if future_rows is not None:
        write_csv(analysis_dir / f"future_daily_pricing_enriched_{run_date}.csv", future_rows)
    if rolling_rows is not None:
        write_csv(analysis_dir / f"rolling_13_month_revenue_view_{run_date}.csv", rolling_rows)
    if window_signal_rows is not None:
        write_csv(analysis_dir / f"future_window_signals_{run_date}.csv", window_signal_rows)
    if airbnb_history_rows is not None:
        write_csv(analysis_dir / f"airbnb_weekly_history_comparison_{run_date}.csv", airbnb_history_rows)
    if similar_rows is not None:
        write_csv(analysis_dir / f"airbnb_similar_listing_summary_{run_date}.csv", similar_rows)

    output = combined_market_listing_signal.run(run_date, run_dir=run_dir)
    return read_output(output)


def test_booked_occupancy_at_or_below_market_creates_urgent_gap(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[
            {
                "window_name": "days_0_15",
                "market_trend": "stable",
                "listing_trend": "up",
                "market_occupancy": "55",
                "booked_occupancy": "55",
            }
        ],
    )

    assert row["combined_signal_category"] == "urgent_revenue_occupancy_gap"
    assert row["investigation_priority"] == "urgent"
    assert row["occupancy_gap_signal"] == "urgent_gap"


def test_market_up_and_listing_down_creates_listing_specific_investigation(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[{"market_trend": "up", "listing_trend": "down", "revenue_pace_signal": "behind"}],
        airbnb_history_rows=[{"metric_name": "page_views", "change_vs_previous_week": "-100"}],
    )

    assert row["combined_signal_category"] == "listing_specific_investigation"
    assert row["investigation_priority"] == "high"


def test_market_down_and_listing_up_creates_pricing_efficiency_investigation(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[
            {
                "market_trend": "down",
                "listing_trend": "up",
                "revenue_pace_signal": "ahead",
                "cleaning_efficiency_signal": "ok",
            }
        ],
    )

    assert row["combined_signal_category"] == "outperformance_pricing_efficiency_investigation"
    assert row["investigation_priority"] == "high"
    assert "rule" in row["allowed_recommendation_scope"]


def test_market_down_and_listing_down_creates_market_softness_not_outperformance(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[{"market_trend": "down", "listing_trend": "down", "revenue_pace_signal": "behind"}],
        airbnb_history_rows=[{"metric_name": "page_views", "change_vs_previous_week": "-100"}],
    )

    assert row["market_health_signal"] == "down"
    assert row["listing_airbnb_signal"] == "down"
    assert row["combined_signal_category"] == "market_softness"
    assert row["investigation_priority"] == "medium"
    assert row["explanation"] == (
        "Market and listing diagnostic signals are both soft; investigate broader market softness before assigning listing or pricing cause."
    )


def test_airbnb_metric_window_is_preferred_over_run_date_window(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[{"market_trend": "stable", "listing_trend": "up", "window_start": "2026-05-20", "window_end": "2026-05-20"}],
        airbnb_history_rows=[
            {
                "metric_name": "page_views",
                "metric_window_start": "2026-05-10",
                "metric_window_end": "2026-05-17",
                "change_vs_previous_week": "10",
            }
        ],
    )

    assert row["window_start"] == "2026-05-10"
    assert row["window_end"] == "2026-05-17"


def test_unknown_core_pricelabs_signals_make_data_quality_partial(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[{"market_trend": "stable", "listing_trend": "up"}],
        airbnb_history_rows=[{"metric_name": "page_views", "change_vs_previous_week": "10"}],
    )

    assert row["data_quality_status"] == "missing_core"
    assert "PriceLabs core signals unavailable or not parsed" in row["notes"]


def test_airbnb_only_data_cannot_create_pricelabs_recommendation(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        airbnb_history_rows=[{"metric_name": "page_views", "change_vs_previous_week": "-100"}],
        similar_rows=[{"metric_name": "page_views", "difference_vs_similar_listings": "-10"}],
    )

    assert row["combined_signal_category"] == "insufficient_data"
    assert row["allowed_recommendation_scope"] == "none"
    assert row["data_quality_status"] == "missing_core"


def test_missing_data_creates_insufficient_data(tmp_path: Path) -> None:
    row = run_with_inputs(tmp_path)

    assert row["combined_signal_category"] == "insufficient_data"
    assert row["investigation_priority"] == "none"


def test_output_csv_is_created_with_required_columns(tmp_path: Path) -> None:
    run_date = "2026-05-20"
    run_dir = tmp_path / "data" / "runs" / run_date
    output = combined_market_listing_signal.run(run_date, run_dir=run_dir)
    rows = list(csv.DictReader(output.open("r", encoding="utf-8")))

    assert output == run_dir / "analysis" / f"combined_market_listing_signal_{run_date}.csv"
    assert rows
    assert set(combined_market_listing_signal.COLUMNS).issubset(rows[0].keys())


def test_pricelabs_core_mapping_populates_all_core_signals(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[{"market_trend": "stable", "listing_trend": "up"}],
        rolling_rows=[
            {
                "stay_month": "2026-05",
                "revenue_pace_status": "conversion_risk",
                "cleaning_efficiency_status": "inefficient",
            }
        ],
        window_signal_rows=[
            {"window_name": "days_0_15", "pace_status": "near_market"},
            {"window_name": "days_16_45", "pace_status": "behind_market"},
        ],
    )

    assert row["revenue_pace_signal"] == "weak"
    assert row["occupancy_gap_signal"] == "behind"
    assert row["cleaning_efficiency_signal"] == "inefficient"
    assert row["data_quality_status"] == "complete"


def test_partial_core_mapping_from_future_window_signals_only(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[{"market_trend": "stable", "listing_trend": "up"}],
        rolling_rows=[
            {
                "stay_month": "2026-05",
                "revenue_pace_status": "data_not_available",
                "cleaning_efficiency_status": "no_booked_cleanings",
            }
        ],
        window_signal_rows=[
            {"window_name": "days_0_15", "pace_status": "near_market"},
            {"window_name": "days_16_45", "pace_status": "near_market"},
        ],
    )

    assert row["revenue_pace_signal"] == "unknown"
    assert row["occupancy_gap_signal"] == "aligned"
    assert row["cleaning_efficiency_signal"] == "unknown"
    assert row["data_quality_status"] == "partial"


def test_airbnb_with_missing_pricelabs_core_files_keeps_core_signals_unknown(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        airbnb_history_rows=[{"metric_name": "page_views", "change_vs_previous_week": "10"}],
        similar_rows=[{"metric_name": "page_views", "difference_vs_similar_listings": "5"}],
    )

    assert row["revenue_pace_signal"] == "unknown"
    assert row["occupancy_gap_signal"] == "unknown"
    assert row["cleaning_efficiency_signal"] == "unknown"
    assert row["data_quality_status"] == "missing_core"


def test_historical_actuals_rows_do_not_drive_current_future_core_signals(tmp_path: Path) -> None:
    row = run_with_inputs(
        tmp_path,
        future_rows=[{"market_trend": "stable", "listing_trend": "up"}],
        rolling_rows=[
            {
                "stay_month": "2026-02",
                "revenue_pace_status": "historical_actuals",
                "cleaning_efficiency_status": "historical_actuals",
            },
            {
                "stay_month": "2026-05",
                "revenue_pace_status": "data_not_available",
                "cleaning_efficiency_status": "no_booked_cleanings",
            },
        ],
    )

    assert row["revenue_pace_signal"] == "unknown"
    assert row["cleaning_efficiency_signal"] == "unknown"
    assert row["data_quality_status"] == "missing_core"
