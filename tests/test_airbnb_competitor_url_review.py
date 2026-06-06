import csv
from pathlib import Path

from airbnb import airbnb_competitor_url_review as review


RUN_DATE = "2026-06-03"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_input_columns_contract() -> None:
    assert review.INPUT_COLUMNS == ["rank_group", "source_note", "listing_url"]


def test_listing_id_and_visible_signal_parsers() -> None:
    text = "Guest favorite\n4.91\n128 reviews\n10 guests · 4 bedrooms · 6 beds · 3 baths\n$1,978 total"

    assert review.listing_id_from_url("https://www.airbnb.com/rooms/123456?adults=8") == "123456"
    assert review.parse_rating(text) == "4.91"
    assert review.parse_review_count(text) == "128"
    assert review.parse_number_before("guests?", text) == "10"
    assert review.parse_number_before("bedrooms?", text) == "4"
    assert review.parse_visible_price(text) == "$1,978"


def test_amenity_and_hook_classification() -> None:
    text = "Luxury family cabin with hot tub, sauna, game room, theater, lake access, fire pit, EV charger"

    assert review.contains_any(text, ("hot tub",))
    assert review.classify_primary_guest_value_hook(text) == "spa"
    assert review.classify_cover_photo_hook(text, ["Hot tub under string lights"]) == "hot_tub"
    assert review.title_signal_strength("Hot Tub Sauna Game Room Lake Cabin") == "high"


def test_summary_rows_aggregate_competitor_patterns() -> None:
    rows = [
        {
            "rank_group": "tier_1_direct_comp",
            "match_reason": "direct_location_hot_tub_sauna",
            "scrape_status": "success",
            "guest_favorite_badge": "true",
            "superhost_badge": "false",
            "rating": "4.9",
            "review_count": "100",
            "hot_tub_visible": "true",
            "sauna_visible": "true",
            "pool_visible": "false",
            "game_room_visible": "true",
            "theater_visible": "false",
            "arcade_visible": "false",
            "lake_access_visible": "true",
            "fire_pit_visible": "true",
            "fireplace_visible": "true",
            "cover_photo_hook_guess": "hot_tub",
            "primary_guest_value_hook": "spa",
            "self_check_in_visible": "true",
            "pets_allowed_visible": "false",
        },
        {
            "rank_group": "tier_2_market_pattern",
            "scrape_status": "failed",
            "guest_favorite_badge": "false",
            "superhost_badge": "false",
        },
    ]

    summary = review.summary_rows(RUN_DATE, rows, total_cards_inspected=100)[0]

    assert summary["total_cards_inspected"] == "100"
    assert summary["total_urls_collected"] == "2"
    assert summary["total_listings_reviewed"] == "2"
    assert summary["successful_scrapes"] == "1"
    assert summary["failed_scrapes"] == "1"
    assert summary["guest_favorite_count"] == "1"
    assert summary["average_rating"] == "4.9"
    assert summary["median_review_count"] == "100"
    assert summary["hot_tub_count"] == "1"
    assert summary["tier_1_direct_comp_count"] == "1"
    assert summary["tier_2_market_pattern_count"] == "1"
    assert summary["spa_hook_count"] == "1"
    assert summary["fireplace_count"] == "1"
    assert summary["listings_with_clear_self_check_in"] == "1"


def test_write_outputs_creates_review_summary_and_gaps(tmp_path: Path) -> None:
    run_dir = tmp_path / "data" / "runs" / RUN_DATE
    rows = [{column: "" for column in review.REVIEW_COLUMNS}]
    rows[0].update(
        {
            "run_date": RUN_DATE,
            "rank_group": "tier_1",
            "source_note": "Manual competitor",
            "match_reason": "direct_location_hot_tub_sauna",
            "absolute_position": "12",
            "listing_url": "https://www.airbnb.com/rooms/123",
            "listing_id": "123",
            "listing_title": "Lake Cabin Hot Tub",
            "scrape_status": "success",
            "guest_favorite_badge": "true",
            "rating": "4.9",
            "review_count": "100",
            "hot_tub_visible": "true",
            "primary_guest_value_hook": "spa",
        }
    )

    review_path, summary_path, gaps_path = review.write_outputs(RUN_DATE, rows, run_dir, total_cards_inspected=100)

    assert review_path.name == f"airbnb_competitor_url_review_{RUN_DATE}.csv"
    assert summary_path.name == f"airbnb_competitor_pattern_summary_{RUN_DATE}.csv"
    assert gaps_path.name == f"airbnb_competitor_actionable_gaps_{RUN_DATE}.md"
    assert read_csv(review_path)[0]["listing_id"] == "123"
    assert read_csv(review_path)[0]["match_reason"] == "direct_location_hot_tub_sauna"
    assert read_csv(summary_path)[0]["total_listings_reviewed"] == "1"
    assert read_csv(summary_path)[0]["total_cards_inspected"] == "100"
    assert "No PriceLabs rule changes" in gaps_path.read_text(encoding="utf-8")
    assert "Top Direct Competitors Discovered" in gaps_path.read_text(encoding="utf-8")


def test_wrapper_does_not_use_pricelabs_preflight_or_weekly_pipeline() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_airbnb_competitor_url_review.ps1").read_text(encoding="utf-8")

    assert "airbnb.airbnb_competitor_url_review" in script
    assert "No PriceLabs preflight is run" in script
    assert "priceLabs_future_export.csv" not in script
    assert "price_occ.csv" not in script
    assert "run_weekly_pipeline.ps1" not in script
