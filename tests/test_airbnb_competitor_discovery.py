import csv
from pathlib import Path

from airbnb import airbnb_competitor_discovery as discovery


RUN_DATE = "2026-06-03"


class FakeLink:
    def __init__(self, href: str, text: str = "") -> None:
        self.href = href
        self.text = text

    def get_attribute(self, name: str, timeout: int = 1000) -> str:
        if name == "href":
            return self.href
        return ""

    def inner_text(self, timeout: int = 1500) -> str:
        return self.text

    def evaluate(self, script: str) -> str:
        return self.text


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def test_competitor_eligibility_classifies_direct_location_and_amenity() -> None:
    eligibility = discovery.classify_competitor(
        "Guest favorite cabin in Long Pond with hot tub, sauna, game room, 4.91, 128 reviews",
        absolute_position=12,
    )

    assert eligibility.include
    assert eligibility.rank_group == "tier_1_direct_comp"
    assert eligibility.match_reason == "direct_location_hot_tub_sauna"
    assert "direct location" in eligibility.source_note


def test_rank_group_assignment_for_market_pattern() -> None:
    eligibility = discovery.classify_competitor(
        "Lake Harmony chalet with theater, arcade, lake access, and hot tub",
        absolute_position=44,
    )

    assert eligibility.include
    assert eligibility.rank_group == "tier_2_market_pattern"


def test_rank_group_assignment_for_high_rank_outlier_pattern() -> None:
    eligibility = discovery.classify_competitor(
        "Guest favorite luxury spa retreat with pool and fire pit",
        absolute_position=8,
    )

    assert eligibility.include
    assert eligibility.rank_group == "tier_3_outlier_pattern"


def test_excludes_weak_non_comparable_card() -> None:
    eligibility = discovery.classify_competitor("Tiny city studio for two guests", absolute_position=22)

    assert not eligibility.include


def test_match_reason_assignment_examples() -> None:
    assert discovery.match_reason_for("New modern cabin with fire pit", 3) == "new_listing_high_rank"
    assert discovery.match_reason_for("Guest favorite game room arcade", 20) == "guest_favorite_game_room"
    assert discovery.match_reason_for("Lakefront cabin with dock", 30) == "lakefront_high_rank"
    assert discovery.match_reason_for("Spa chalet with sauna", 80) == "luxury_spa_pattern"


def test_duplicate_url_handling() -> None:
    rows = [
        {"listing_id": "1", "listing_url": "https://www.airbnb.com/rooms/1"},
        {"listing_id": "1", "listing_url": "https://www.airbnb.com/rooms/1?adults=8"},
        {"listing_id": "2", "listing_url": "https://www.airbnb.com/rooms/2"},
    ]

    unique = discovery.dedupe_rows(rows)

    assert [row["listing_id"] for row in unique] == ["1", "2"]


def test_listing_id_extraction_and_url_cleaning() -> None:
    url = "https://www.airbnb.com/rooms/1313377469848413047?adults=8&foo=bar"

    assert discovery.clean_listing_url(url) == "https://www.airbnb.com/rooms/1313377469848413047"
    assert discovery.listing_id_from_url(url) == "1313377469848413047"


def test_write_discovery_csv_uses_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "airbnb_competitor_urls.csv"
    row = {column: "" for column in discovery.DISCOVERY_COLUMNS}
    row.update(
        {
            "run_date": RUN_DATE,
            "absolute_position": "7",
            "rank_group": "tier_1_direct_comp",
            "listing_url": "https://www.airbnb.com/rooms/123",
        }
    )

    discovery.write_discovery_csv(path, [row])

    rows = read_csv(path)
    assert list(rows[0].keys()) == discovery.DISCOVERY_COLUMNS
    assert rows[0]["absolute_position"] == "7"


def test_debug_rows_are_written_before_filtering(tmp_path: Path) -> None:
    path = tmp_path / "debug_cards.csv"
    link = FakeLink("", "Tiny city studio for two guests")
    debug_row = discovery.debug_row_from_card(
        run_date=RUN_DATE,
        link=link,
        page_number=1,
        position_on_page=1,
        cards_seen_before_page=0,
    )

    discovery.write_debug_cards_csv(path, [debug_row])

    rows = read_csv(path)
    assert list(rows[0].keys()) == discovery.DEBUG_COLUMNS
    assert rows[0]["would_collect"] == "false"
    assert rows[0]["rejection_reason"] == "missing_valid_room_url"


def test_valid_room_url_causes_card_to_be_collectible_even_when_criteria_are_weak() -> None:
    link = FakeLink("https://www.airbnb.com/rooms/123456?adults=8", "Tiny city studio for two guests")

    row, rejection = discovery.discovery_row_from_card(
        run_date=RUN_DATE,
        link=link,
        page_number=1,
        position_on_page=2,
        cards_seen_before_page=0,
    )

    assert rejection == ""
    assert row is not None
    assert row["listing_id"] == "123456"
    assert row["rank_group"] == "tier_3_outlier_pattern"
    assert row["match_reason"] == "valid_url_broad_search"
    assert row["rejection_reason"]


def test_rejection_reason_is_populated_for_non_collected_cards() -> None:
    link = FakeLink("", "Guest favorite Long Pond hot tub")

    row, rejection = discovery.discovery_row_from_card(
        run_date=RUN_DATE,
        link=link,
        page_number=1,
        position_on_page=3,
        cards_seen_before_page=0,
    )

    assert row is None
    assert rejection == "Rejected: missing valid Airbnb /rooms/<id> URL."


def test_discovery_counts_summarize_debug_and_collection_rows() -> None:
    debug_rows = [
        {
            "raw_card_text": "Guest favorite Long Pond hot tub",
            "listing_url": "https://www.airbnb.com/rooms/1",
            "listing_id": "1",
            "eligibility_reasons": "direct_location; amenity; trust",
            "absolute_position": "1",
        },
        {
            "raw_card_text": "",
            "listing_url": "",
            "listing_id": "",
            "eligibility_reasons": "",
            "absolute_position": "2",
        },
    ]
    collected_rows = [{"listing_id": "1"}]

    counts = discovery.discovery_counts(debug_rows, collected_rows)

    assert counts["cards_inspected"] == 2
    assert counts["cards_with_non_empty_raw_card_text"] == 1
    assert counts["cards_with_listing_url"] == 1
    assert counts["cards_with_listing_id"] == 1
    assert counts["cards_passing_location_criteria"] == 1
    assert counts["cards_passing_amenity_criteria"] == 1
    assert counts["cards_passing_trust_criteria"] == 1
    assert counts["cards_passing_final_eligibility"] == 1
    assert counts["urls_collected"] == 1


def test_sort_collection_rows_prioritizes_score_then_absolute_position() -> None:
    rows = [
        {"listing_id": "1", "eligibility_score": "10", "absolute_position": "1"},
        {"listing_id": "2", "eligibility_score": "16", "absolute_position": "20"},
        {"listing_id": "3", "eligibility_score": "16", "absolute_position": "5"},
    ]

    sorted_rows = discovery.sort_collection_rows(rows)

    assert [row["listing_id"] for row in sorted_rows] == ["3", "2", "1"]


def test_wrapper_does_not_use_pricelabs_preflight_or_weekly_pipeline() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "run_airbnb_competitor_discovery.ps1").read_text(encoding="utf-8")

    assert "airbnb.airbnb_competitor_discovery" in script
    assert "No PriceLabs preflight is run" in script
    assert "priceLabs_future_export.csv" not in script
    assert "price_occ.csv" not in script
    assert "run_weekly_pipeline.ps1" not in script
