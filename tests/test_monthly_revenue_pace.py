from decimal import Decimal
import calendar
import csv
import sys

from pricelabs.transform.monthly_revenue_pace import summarize_monthly, run


def enriched_row(
    stay_date: str,
    status: str,
    booked_revenue_proxy: str,
    open_revenue_ask: str,
    booked_stay_start_proxy: str,
) -> dict[str, str]:
    return {
        "run_date": "2026-05-08",
        "listing_id": "650255___717243",
        "stay_date": stay_date,
        "status": status,
        "booked_revenue_proxy": booked_revenue_proxy,
        "open_revenue_ask": open_revenue_ask,
        "booked_stay_start_proxy": booked_stay_start_proxy,
    }


def by_month(rows: list[dict[str, str]], month: str) -> dict[str, str]:
    return next(row for row in rows if row["stay_month"] == month)


def full_month_rows(year: int, month: int, special_rows: dict[int, dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        rows.append(
            special_rows.get(
                day,
                enriched_row(f"{year}-{month:02d}-{day:02d}", "available", "0", "0", "0"),
            )
        )
    return rows


def test_monthly_revenue_pace_aggregation() -> None:
    rows = summarize_monthly(
        [
            enriched_row("2026-05-10", "booked", "350", "0", "1"),
            enriched_row("2026-05-11", "booked", "350", "0", "0"),
            enriched_row("2026-05-12", "booked", "500", "0", "1"),
            enriched_row("2026-05-13", "available", "0", "475", "0"),
            enriched_row("2026-05-14", "blocked", "0", "0", "0"),
            enriched_row("2026-06-01", "booked", "600", "0", "1"),
            enriched_row("2026-06-02", "available", "0", "700", "0"),
        ]
    )

    may = by_month(rows, "2026-05")
    june = by_month(rows, "2026-06")

    assert may["booked_nights"] == "3"
    assert may["month_time_bucket"] == "current_month"
    assert may["days_in_scope"] == "5"
    assert may["days_in_month"] == "31"
    assert may["month_scope_status"] == "partial_month"
    assert may["available_nights"] == "1"
    assert may["unavailable_nights"] == "1"
    assert Decimal(may["booked_revenue_proxy"]) == Decimal("1200")
    assert Decimal(may["open_revenue_ask"]) == Decimal("475")
    assert Decimal(may["total_future_revenue_proxy"]) == Decimal("1675")
    assert Decimal(may["monthly_target"]) == Decimal("10000")
    assert Decimal(may["booked_gap_to_target"]) == Decimal("8800")
    assert Decimal(may["total_gap_to_target"]) == Decimal("8325")
    assert may["booked_cleanings_proxy"] == "2"
    assert Decimal(may["avg_stay_length_proxy"]) == Decimal("1.50")
    assert Decimal(may["revenue_per_cleaning_proxy"]) == Decimal("600")
    assert Decimal(may["booked_revenue_pct_of_target"]) == Decimal("0.1200")
    assert Decimal(may["total_future_revenue_pct_of_target"]) == Decimal("0.1675")
    assert may["revenue_pace_status"] == "urgent"
    assert may["cleaning_efficiency_status"] == "watch"
    assert may["month_action_level"] == "critical_now"

    assert june["booked_nights"] == "1"
    assert june["available_nights"] == "1"
    assert june["unavailable_nights"] == "0"
    assert Decimal(june["booked_revenue_proxy"]) == Decimal("600")
    assert Decimal(june["open_revenue_ask"]) == Decimal("700")
    assert Decimal(june["total_future_revenue_proxy"]) == Decimal("1300")
    assert june["booked_cleanings_proxy"] == "1"


def test_monthly_revenue_pace_cli_writes_output(tmp_path, monkeypatch) -> None:
    enriched_file = tmp_path / "future_daily_pricing_enriched_2026-05-08.csv"
    output_file = tmp_path / "monthly_revenue_pace_2026-05-08.csv"

    with enriched_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=(
                "run_date",
                "listing_id",
                "stay_date",
                "status",
                "booked_revenue_proxy",
                "open_revenue_ask",
                "booked_stay_start_proxy",
            ),
        )
        writer.writeheader()
        writer.writerow(enriched_row("2026-05-10", "booked", "350", "0", "1"))
        writer.writerow(enriched_row("2026-05-11", "available", "0", "475", "0"))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "monthly_revenue_pace",
            "--run-date",
            "2026-05-08",
            "--enriched-file",
            str(enriched_file),
            "--output-file",
            str(output_file),
        ],
    )

    assert run() == 0

    with output_file.open("r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        assert reader.fieldnames == list(
            (
                "run_date",
                "listing_id",
                "stay_month",
                "month_time_bucket",
                "days_in_scope",
                "days_in_month",
                "month_scope_status",
                "booked_nights",
                "available_nights",
                "unavailable_nights",
                "booked_revenue_proxy",
                "open_revenue_ask",
                "total_future_revenue_proxy",
                "monthly_target",
                "booked_gap_to_target",
                "total_gap_to_target",
                "booked_cleanings_proxy",
                "avg_stay_length_proxy",
                "revenue_per_cleaning_proxy",
                "booked_revenue_pct_of_target",
                "total_future_revenue_pct_of_target",
                "revenue_pace_status",
                "cleaning_efficiency_status",
                "month_action_level",
            )
        )
        row = next(reader)

    assert row["stay_month"] == "2026-05"
    assert row["booked_nights"] == "1"
    assert row["available_nights"] == "1"


def test_monthly_diagnostics_statuses() -> None:
    diagnostic_rows = []
    diagnostic_rows.extend(
        full_month_rows(
            2026,
            5,
            {
                1: enriched_row("2026-05-01", "booked", "9000", "0", "1"),
            },
        )
    )
    diagnostic_rows.extend(
        full_month_rows(
            2026,
            6,
            {
                1: enriched_row("2026-06-01", "booked", "3000", "0", "1"),
                2: enriched_row("2026-06-02", "available", "0", "8000", "0"),
            },
        )
    )
    diagnostic_rows.extend(
        full_month_rows(
            2026,
            7,
            {
                1: enriched_row("2026-07-01", "booked", "3000", "0", "1"),
                2: enriched_row("2026-07-02", "available", "0", "7000", "0"),
            },
        )
    )
    diagnostic_rows.extend(
        full_month_rows(
            2026,
            8,
            {
                1: enriched_row("2026-08-01", "available", "0", "1000", "0"),
            },
        )
    )
    diagnostic_rows.extend(
        full_month_rows(
            2026,
            9,
            {
                1: enriched_row("2026-09-01", "booked", "400", "0", "1"),
            },
        )
    )
    diagnostic_rows.extend(
        full_month_rows(
            2026,
            10,
            {
                1: enriched_row("2026-10-01", "available", "0", "10000", "0"),
            },
        )
    )
    rows = summarize_monthly(
        diagnostic_rows
    )

    may = by_month(rows, "2026-05")
    june = by_month(rows, "2026-06")
    july = by_month(rows, "2026-07")
    august = by_month(rows, "2026-08")
    september = by_month(rows, "2026-09")
    october = by_month(rows, "2026-10")

    assert may["month_time_bucket"] == "current_month"
    assert may["month_scope_status"] == "full_month"
    assert may["revenue_pace_status"] == "on_track"
    assert may["cleaning_efficiency_status"] == "strong"
    assert may["month_action_level"] == "protect"

    assert june["month_time_bucket"] == "next_month"
    assert june["revenue_pace_status"] == "conversion_risk"
    assert june["month_action_level"] == "advisory"

    assert july["month_time_bucket"] == "future_month"
    assert july["revenue_pace_status"] == "protect_open_value"
    assert july["month_action_level"] == "protect"

    assert august["cleaning_efficiency_status"] == "no_booked_cleanings"
    assert august["revenue_pace_status"] == "behind"

    assert september["cleaning_efficiency_status"] == "inefficient"
    assert september["month_time_bucket"] == "far_future_month"

    assert october["month_time_bucket"] == "far_future_month"
    assert october["revenue_pace_status"] == "protect_open_value"
    assert october["month_action_level"] == "protect"


def test_current_month_urgent_status() -> None:
    urgent_rows = full_month_rows(
        2026,
        5,
        {
            1: enriched_row("2026-05-01", "booked", "1000", "0", "1"),
            2: enriched_row("2026-05-02", "available", "0", "2000", "0"),
        },
    )
    rows = summarize_monthly(
        urgent_rows
    )

    may = by_month(rows, "2026-05")

    assert may["month_time_bucket"] == "current_month"
    assert may["month_scope_status"] == "full_month"
    assert may["revenue_pace_status"] == "urgent"
    assert may["month_action_level"] == "critical_now"


def test_current_month_partial_scope_still_uses_current_month_status_logic() -> None:
    rows = summarize_monthly(
        [
            enriched_row("2026-05-08", "booked", "2834", "0", "1"),
            enriched_row("2026-05-09", "available", "0", "7425", "0"),
        ]
    )

    may = by_month(rows, "2026-05")

    assert may["month_scope_status"] == "partial_month"
    assert may["month_time_bucket"] == "current_month"
    assert may["revenue_pace_status"] == "conversion_risk"
    assert may["month_action_level"] == "advisory"


def test_far_future_partial_month_gets_partial_horizon_status() -> None:
    rows = summarize_monthly(
        [
            enriched_row("2026-11-01", "available", "0", "988", "0"),
        ]
    )

    november = by_month(rows, "2026-11")

    assert november["days_in_scope"] == "1"
    assert november["days_in_month"] == "30"
    assert november["month_scope_status"] == "partial_month"
    assert november["revenue_pace_status"] == "partial_horizon"
    assert november["month_action_level"] == "monitor"
