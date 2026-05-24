"""Combine PriceLabs market context with Airbnb diagnostic signals."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path


COLUMNS = [
    "run_date",
    "window_name",
    "window_start",
    "window_end",
    "market_health_signal",
    "listing_airbnb_signal",
    "revenue_pace_signal",
    "occupancy_gap_signal",
    "cleaning_efficiency_signal",
    "combined_signal_category",
    "investigation_priority",
    "explanation",
    "allowed_recommendation_scope",
    "data_quality_status",
    "notes",
]

UP_SIGNALS = {"up", "improving", "strong", "market_up", "listing_up", "ahead", "positive"}
DOWN_SIGNALS = {"down", "soft", "weak", "weakening", "market_down", "listing_down", "behind", "negative"}
STABLE_SIGNALS = {"stable", "normal", "flat"}


@dataclass
class PriceLabsSignal:
    has_data: bool
    market_trend: str = "unknown"
    listing_trend: str = "unknown"
    revenue_pace_signal: str = "unknown"
    occupancy_gap_signal: str = "unknown"
    cleaning_efficiency_signal: str = "unknown"
    pricing_efficiency_signal: str = "unknown"
    window_name: str = "weekly"
    window_start: str = ""
    window_end: str = ""


@dataclass
class AirbnbSignal:
    has_data: bool
    listing_trend: str = "unknown"
    similar_listing_signal: str = "unknown"
    window_start: str = ""
    window_end: str = ""
    notes: str = ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create combined PriceLabs + Airbnb market/listing signal CSV.")
    parser.add_argument("--run-date", required=True, help="Run date in YYYY-MM-DD format.")
    parser.add_argument("--run-dir", help="Run directory. Defaults to data/runs/<run-date>.")
    parser.add_argument("--output-file", help="Combined signal output CSV.")
    parser.add_argument("--future-file", help="Future daily pricing enriched CSV.")
    parser.add_argument("--rolling-file", help="Rolling 13-month revenue view CSV.")
    parser.add_argument("--future-window-signals-file", help="Future window signals CSV.")
    parser.add_argument("--airbnb-history-file", help="Airbnb retained-history comparison CSV.")
    parser.add_argument("--airbnb-similar-file", help="Airbnb similar-listing summary CSV.")
    return parser.parse_args(argv)


def read_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as csv_file:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(csv_file)]


def parse_number(value: str) -> float | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    try:
        return float(stripped.replace("$", "").replace(",", "").rstrip("%"))
    except ValueError:
        return None


def normalized_signal(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def trend_from_value(value: str) -> str:
    signal = normalized_signal(value)
    if signal in UP_SIGNALS or any(token in signal for token in ("improv", "strong", "up")):
        return "up"
    if signal in DOWN_SIGNALS or any(token in signal for token in ("weak", "soft", "down", "behind")):
        return "down"
    if signal in STABLE_SIGNALS:
        return "stable"
    return "unknown"


def first_present(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(name, "")
        if value:
            return value
    return ""


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def numeric_average(rows: list[dict[str, str]], names: tuple[str, ...]) -> float | None:
    values: list[float] = []
    for row in rows:
        value = parse_number(first_present(row, names))
        if value is not None:
            values.append(value)
    return average(values)


def run_month(run_date: str) -> str:
    return run_date[:7]


def current_future_rows(rows: list[dict[str, str]], run_date: str) -> list[dict[str, str]]:
    month = run_month(run_date)
    return [row for row in rows if row.get("stay_month", "") >= month]


def worst_signal(signals: list[str], severity: tuple[str, ...]) -> str:
    for signal in severity:
        if signal in signals:
            return signal
    return "unknown"


def normalize_revenue_pace(value: str) -> str:
    mapping = {
        "conversion_risk": "weak",
        "watch": "soft",
        "protect_open_value": "on_track",
        "partial_horizon": "unknown",
        "data_not_available": "unknown",
        "historical_actuals": "unknown",
    }
    return mapping.get(normalized_signal(value), "unknown")


def revenue_pace_from_rolling(rows: list[dict[str, str]], run_date: str) -> str:
    signals = [
        normalize_revenue_pace(row.get("revenue_pace_status", ""))
        for row in current_future_rows(rows, run_date)
        if normalized_signal(row.get("revenue_pace_status", "")) != "historical_actuals"
    ]
    return worst_signal(signals, ("weak", "soft", "on_track", "strong"))


def normalize_occupancy_gap(value: str) -> str:
    mapping = {
        "behind_market": "behind",
        "near_market": "aligned",
        "ahead_market": "ahead",
    }
    return mapping.get(normalized_signal(value), "unknown")


def occupancy_gap_from_window_signals(rows: list[dict[str, str]]) -> str:
    near_windows = [row for row in rows if row.get("window_name", "") in {"days_0_15", "days_16_45"}]
    fallback_windows = [row for row in rows if row.get("window_name", "") == "days_46_90"]
    candidates = near_windows or fallback_windows
    signals = [normalize_occupancy_gap(row.get("pace_status", "")) for row in candidates]
    known = [signal for signal in signals if signal != "unknown"]
    if "behind" in known:
        return "behind"
    if known and all(signal == "aligned" for signal in known):
        return "aligned"
    if "ahead" in known:
        return "ahead"
    return "unknown"


def normalize_cleaning_efficiency(value: str) -> str:
    mapping = {
        "inefficient": "inefficient",
        "watch": "acceptable",
        "no_booked_cleanings": "unknown",
        "partial_horizon": "unknown",
        "data_not_available": "unknown",
        "historical_actuals": "unknown",
    }
    return mapping.get(normalized_signal(value), "unknown")


def cleaning_efficiency_from_rolling(rows: list[dict[str, str]], run_date: str) -> str:
    signals = [
        normalize_cleaning_efficiency(row.get("cleaning_efficiency_status", ""))
        for row in current_future_rows(rows, run_date)
        if normalized_signal(row.get("cleaning_efficiency_status", "")) != "historical_actuals"
    ]
    return worst_signal(signals, ("inefficient", "acceptable", "efficient"))


def core_data_quality(pricelabs: PriceLabsSignal) -> str:
    known = [
        signal
        for signal in (
            pricelabs.revenue_pace_signal,
            pricelabs.occupancy_gap_signal,
            pricelabs.cleaning_efficiency_signal,
        )
        if signal != "unknown"
    ]
    if len(known) == 3:
        return "complete"
    if known:
        return "partial"
    return "missing_core"


def infer_pricelabs_signal(
    future_rows: list[dict[str, str]],
    *,
    run_date: str,
    rolling_rows: list[dict[str, str]] | None = None,
    window_signal_rows: list[dict[str, str]] | None = None,
    has_report_text: bool = False,
) -> PriceLabsSignal:
    rolling_rows = rolling_rows or []
    window_signal_rows = window_signal_rows or []
    if not future_rows and not rolling_rows and not window_signal_rows and not has_report_text:
        return PriceLabsSignal(has_data=False)
    first = future_rows[0] if future_rows else {}
    market_trend = trend_from_value(first_present(first, ("market_trend", "market_health_signal", "market_pace_signal")))
    listing_trend = trend_from_value(first_present(first, ("listing_trend", "listing_revenue_trend", "revenue_trend")))
    direct_revenue_signal = first_present(first, ("revenue_pace_signal", "revenue_pace_status", "pace_status")) or "unknown"
    direct_cleaning_signal = first_present(first, ("cleaning_efficiency_signal", "cleaning_efficiency_status")) or "unknown"
    pricing_signal = trend_from_value(first_present(first, ("pricing_efficiency_signal", "adr_signal", "open_ask_signal")))

    market_occ = numeric_average(future_rows, ("market_occupancy", "market_occupancy_pct", "market_occupancy_avg"))
    booked_occ = numeric_average(
        future_rows,
        ("booked_occupancy", "booked_occupancy_pct", "listing_booked_occupancy", "your_booked_occupancy"),
    )
    occupancy_gap_signal = "unknown"
    if market_occ is not None and booked_occ is not None:
        occupancy_gap_signal = "urgent_gap" if booked_occ <= market_occ else "above_market"
    core_revenue_signal = revenue_pace_from_rolling(rolling_rows, run_date)
    core_occupancy_signal = occupancy_gap_from_window_signals(window_signal_rows)
    core_cleaning_signal = cleaning_efficiency_from_rolling(rolling_rows, run_date)

    revenue_pace_signal = core_revenue_signal if core_revenue_signal != "unknown" else direct_revenue_signal
    if core_occupancy_signal != "unknown":
        occupancy_gap_signal = core_occupancy_signal
    cleaning_signal = core_cleaning_signal if core_cleaning_signal != "unknown" else direct_cleaning_signal

    if market_trend == "unknown" and market_occ is not None:
        if market_occ < 40:
            market_trend = "down"
        elif market_occ >= 70:
            market_trend = "up"
        else:
            market_trend = "stable"
    if listing_trend == "unknown":
        listing_trend = trend_from_value(revenue_pace_signal)

    return PriceLabsSignal(
        has_data=True,
        market_trend=market_trend,
        listing_trend=listing_trend,
        revenue_pace_signal=revenue_pace_signal,
        occupancy_gap_signal=occupancy_gap_signal,
        cleaning_efficiency_signal=cleaning_signal,
        pricing_efficiency_signal=pricing_signal,
        window_name=first_present(first, ("window_name", "stay_month")) or "weekly",
        window_start=first_present(first, ("window_start", "metric_window_start", "stay_date")),
        window_end=first_present(first, ("window_end", "metric_window_end", "stay_date")),
    )


def infer_airbnb_signal(history_rows: list[dict[str, str]], similar_rows: list[dict[str, str]]) -> AirbnbSignal:
    if not history_rows and not similar_rows:
        return AirbnbSignal(has_data=False, notes="Airbnb diagnostics missing.")
    window_start = first_present(history_rows[0], ("metric_window_start", "window_start")) if history_rows else ""
    window_end = first_present(history_rows[0], ("metric_window_end", "window_end")) if history_rows else ""
    if not window_start and similar_rows:
        window_start = first_present(similar_rows[0], ("metric_window_start", "window_start"))
    if not window_end and similar_rows:
        window_end = first_present(similar_rows[0], ("metric_window_end", "window_end"))
    changes = [parse_number(row.get("change_vs_previous_week", "")) for row in history_rows]
    clean_changes = [value for value in changes if value is not None]
    listing_trend = "unknown"
    if clean_changes:
        avg_change = sum(clean_changes) / len(clean_changes)
        if avg_change > 0:
            listing_trend = "up"
        elif avg_change < 0:
            listing_trend = "down"
        else:
            listing_trend = "stable"
    similar_diffs = [parse_number(row.get("difference_vs_similar_listings", "")) for row in similar_rows]
    clean_diffs = [value for value in similar_diffs if value is not None and row_status_is_usable(value)]
    similar_signal = "unknown"
    if clean_diffs:
        avg_diff = sum(clean_diffs) / len(clean_diffs)
        if avg_diff > 0:
            similar_signal = "above_similar_listings"
        elif avg_diff < 0:
            similar_signal = "below_similar_listings"
        else:
            similar_signal = "near_similar_listings"
    return AirbnbSignal(
        has_data=True,
        listing_trend=listing_trend,
        similar_listing_signal=similar_signal,
        window_start=window_start,
        window_end=window_end,
        notes="Airbnb diagnostics are visibility/conversion context only.",
    )


def row_status_is_usable(_value: float) -> bool:
    return True


def pricing_efficiency_concern(pricelabs: PriceLabsSignal) -> bool:
    revenue = normalized_signal(pricelabs.revenue_pace_signal)
    cleaning = normalized_signal(pricelabs.cleaning_efficiency_signal)
    return (
        pricelabs.pricing_efficiency_signal == "down"
        or any(token in revenue for token in ("ahead", "strong", "selling_too_easily", "protect"))
        or any(token in cleaning for token in ("high", "inefficient"))
    )


def combined_listing_signal(pricelabs: PriceLabsSignal, airbnb: AirbnbSignal) -> str:
    if airbnb.similar_listing_signal == "above_similar_listings":
        return "above_similar"
    if airbnb.listing_trend in {"up", "down", "stable"}:
        return airbnb.listing_trend
    if pricelabs.listing_trend in {"up", "down", "stable"}:
        return pricelabs.listing_trend
    return "unknown"


def classify_combined_signal(pricelabs: PriceLabsSignal, airbnb: AirbnbSignal) -> tuple[str, str, str, str, str]:
    if not pricelabs.has_data:
        return (
            "insufficient_data",
            "none",
            "PriceLabs market/revenue context is missing, so combined signal classification is not trusted.",
            "none",
            "missing_pricelabs_context",
        )
    if pricelabs.occupancy_gap_signal == "urgent_gap":
        return (
            "urgent_revenue_occupancy_gap",
            "urgent",
            "Booked occupancy is less than or equal to market occupancy; urgent PriceLabs-context review is required.",
            "pricelabs_diagnostic_review_only",
            "occupancy_gap_detected",
        )

    market = pricelabs.market_trend
    listing = combined_listing_signal(pricelabs, airbnb)
    listing_down = listing == "down"
    listing_up = listing in {"up", "strong", "above_market", "above_similar"}
    market_up_or_stable = market in {"up", "stable"}
    market_down = market == "down"

    if market_up_or_stable and listing_down:
        return (
            "listing_specific_investigation",
            "high",
            "Market context is stable or improving while listing/Airbnb signals are down; investigate listing visibility and conversion.",
            "investigate_listing_and_pricelabs_context",
            "airbnb_diagnostic_only",
        )
    if market_down and listing_up:
        priority = "high" if pricing_efficiency_concern(pricelabs) else "medium"
        return (
            "outperformance_pricing_efficiency_investigation",
            priority,
            "Listing signals are stronger than a soft market; investigate pricing efficiency before any rule change.",
            "pricelabs_rule_review_only_if_core_metrics_support_it",
            "airbnb_can_raise_investigation_priority_not_recommend_changes",
        )
    if market_down and listing_down:
        return (
            "market_softness",
            "medium",
            "Market and listing diagnostic signals are both soft; investigate broader market softness before assigning listing or pricing cause.",
            "monitor",
            "market_softness_context",
        )
    if market_up_or_stable and listing_up:
        return (
            "healthy_alignment",
            "low",
            "Market and listing signals are aligned positively; no Airbnb-driven action is justified.",
            "no_change",
            "healthy_alignment",
        )
    return (
        "insufficient_data",
        "low",
        "Available signals are not comparable enough to assign a combined category.",
        "none",
        "incomplete_or_mixed_signals",
    )


def output_row(run_date: str, pricelabs: PriceLabsSignal, airbnb: AirbnbSignal) -> dict[str, str]:
    category, priority, explanation, scope, notes = classify_combined_signal(pricelabs, airbnb)
    data_quality = core_data_quality(pricelabs)
    if data_quality == "missing_core":
        notes = f"{notes}; PriceLabs core signals unavailable or not parsed."
    window_start = airbnb.window_start or pricelabs.window_start
    window_end = airbnb.window_end or pricelabs.window_end
    return {
        "run_date": run_date,
        "window_name": pricelabs.window_name,
        "window_start": window_start,
        "window_end": window_end,
        "market_health_signal": pricelabs.market_trend,
        "listing_airbnb_signal": combined_listing_signal(pricelabs, airbnb) if airbnb.has_data else "missing",
        "revenue_pace_signal": pricelabs.revenue_pace_signal,
        "occupancy_gap_signal": pricelabs.occupancy_gap_signal,
        "cleaning_efficiency_signal": pricelabs.cleaning_efficiency_signal,
        "combined_signal_category": category,
        "investigation_priority": priority,
        "explanation": explanation,
        "allowed_recommendation_scope": scope,
        "data_quality_status": data_quality,
        "notes": notes,
    }


def default_run_dir(run_date: str) -> Path:
    return Path("data") / "runs" / run_date


def default_paths(run_date: str, run_dir: Path) -> dict[str, Path]:
    analysis_dir = run_dir / "analysis"
    return {
        "future": analysis_dir / f"future_daily_pricing_enriched_{run_date}.csv",
        "rolling": analysis_dir / f"rolling_13_month_revenue_view_{run_date}.csv",
        "window_signals": analysis_dir / f"future_window_signals_{run_date}.csv",
        "monthly_summary": analysis_dir / f"monthly_revenue_summary_{run_date}.md",
        "email_report": analysis_dir / f"email_revenue_report_{run_date}.md",
        "airbnb_history": analysis_dir / f"airbnb_weekly_history_comparison_{run_date}.csv",
        "airbnb_similar": analysis_dir / f"airbnb_similar_listing_summary_{run_date}.csv",
        "output": analysis_dir / f"combined_market_listing_signal_{run_date}.csv",
    }


def write_output(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def run(
    run_date: str,
    *,
    run_dir: Path | None = None,
    output_file: Path | None = None,
    future_file: Path | None = None,
    rolling_file: Path | None = None,
    future_window_signals_file: Path | None = None,
    airbnb_history_file: Path | None = None,
    airbnb_similar_file: Path | None = None,
) -> Path:
    resolved_run_dir = run_dir or default_run_dir(run_date)
    paths = default_paths(run_date, resolved_run_dir)
    resolved_future = future_file or paths["future"]
    resolved_rolling = rolling_file or paths["rolling"]
    resolved_window_signals = future_window_signals_file or paths["window_signals"]
    resolved_history = airbnb_history_file or paths["airbnb_history"]
    resolved_similar = airbnb_similar_file or paths["airbnb_similar"]
    resolved_output = output_file or paths["output"]

    future_rows = read_csv_rows(resolved_future)
    has_report_text = paths["monthly_summary"].exists() or paths["email_report"].exists()
    pricelabs = infer_pricelabs_signal(
        future_rows,
        run_date=run_date,
        rolling_rows=read_csv_rows(resolved_rolling),
        window_signal_rows=read_csv_rows(resolved_window_signals),
        has_report_text=has_report_text,
    )
    airbnb = infer_airbnb_signal(read_csv_rows(resolved_history), read_csv_rows(resolved_similar))
    write_output(resolved_output, [output_row(run_date, pricelabs, airbnb)])
    return resolved_output


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = run(
        args.run_date,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        output_file=Path(args.output_file) if args.output_file else None,
        future_file=Path(args.future_file) if args.future_file else None,
        rolling_file=Path(args.rolling_file) if args.rolling_file else None,
        future_window_signals_file=Path(args.future_window_signals_file) if args.future_window_signals_file else None,
        airbnb_history_file=Path(args.airbnb_history_file) if args.airbnb_history_file else None,
        airbnb_similar_file=Path(args.airbnb_similar_file) if args.airbnb_similar_file else None,
    )
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
