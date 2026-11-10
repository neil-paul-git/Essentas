from datetime import date, timedelta

import pytest

from app.models.item import Location
from app.models.product import Product
from app.services.spoilage import (
    StorageInfo,
    _parse_food,
    estimate,
    expiry_from,
    load_foods,
    match_food,
    words,
)

ADDED = date(2026, 11, 10)


def _food(id_: int, name: str, keywords: list[str], fridge=None, **extra):
    return _parse_food(
        {
            "id": id_,
            "name": name,
            "subtitle": None,
            "category": None,
            "keywords": keywords,
            "storage": {"pantry": None, "fridge": fridge, "freezer": None, **extra},
        }
    )


WEEK = {"min": 1, "max": 2, "unit": "weeks"}
FOODS = [
    _food(1, "Cheese", ["cheese"], fridge=WEEK),
    _food(2, "Cream cheese", ["cream cheese", "cheese", "cream"], fridge=WEEK),
    _food(3, "Butter", ["butter"], fridge=WEEK),
    _food(4, "Peanut butter", ["peanut butter", "butter", "peanut"], fridge=WEEK),
    _food(5, "Artichokes, whole", ["artichokes", "artichoke", "whole"], fridge=WEEK),
]


def _match_id(text: str) -> int | None:
    match = match_food([text], Location.FRIDGE, FOODS)
    return match[0].id if match else None


# --- Matching rules (small fixture dataset) ------------------------------------------


def test_words_normalises_case_punctuation_and_plurals() -> None:
    assert words("Semi-skimmed MILKS, 2L") == ("semi", "skimmed", "milk", "2l")
    assert words("Berries tomatoes peaches") == ("berry", "tomato", "peach")


def test_longest_phrase_wins() -> None:
    assert _match_id("Philadelphia cream cheese") == 2


def test_fewer_unexplained_name_words_wins() -> None:
    assert _match_id("Butter") == 3
    assert _match_id("Crunchy peanut butter") == 4


def test_plural_and_singular_match() -> None:
    assert _match_id("artichoke") == 5


def test_generic_words_alone_do_not_match() -> None:
    assert _match_id("whole") is None


def test_unknown_food_does_not_match() -> None:
    assert _match_id("Ferrero Rocher") is None


def test_real_data_packaging_and_meal_words_do_not_match() -> None:
    """FoodKeeper lists "jar" (garlic) and "breakfast" (frozen entrees) as keywords."""
    assert match_food(["Mystery jar"], Location.PANTRY) is None
    assert match_food(["Breakfast stuff"], Location.PANTRY) is None


def test_later_texts_are_fallbacks() -> None:
    match = match_food(["Breakfast stuff", "Salted butter"], Location.FRIDGE, FOODS)

    assert match is not None
    assert (match[0].id, match[1]) == (3, "Salted butter")


@pytest.mark.parametrize(
    ("storage", "expected"),
    [
        (StorageInfo(min=3, max=5, unit="days"), ADDED + timedelta(days=3)),
        (StorageInfo(min=2, max=3, unit="weeks"), ADDED + timedelta(days=14)),
        (StorageInfo(min=6, max=9, unit="months"), ADDED + timedelta(days=180)),
        (StorageInfo(min=1.5, max=2, unit="years"), ADDED + timedelta(days=547)),
        (StorageInfo(min=2, max=2, unit="hours"), ADDED),  # rounds down: eat today
        (StorageInfo(note="Not Recommended"), None),
        (None, None),
    ],
)
def test_expiry_uses_low_end_of_range(storage, expected) -> None:
    assert expiry_from(ADDED, storage) == expected


# --- The real FoodKeeper file --------------------------------------------------------


def test_real_data_loads() -> None:
    foods = load_foods()

    assert len(foods) > 600
    assert all(food.keywords for food in foods)


@pytest.mark.parametrize(
    ("name", "location", "food_name", "days"),
    [
        ("Butter", Location.FREEZER, "Butter", 180),
        ("Free range eggs x12", Location.FRIDGE, "Eggs", 21),
        ("Cream cheese", Location.FRIDGE, "Cream cheese", 14),
        ("Greek yogurt", Location.FRIDGE, "Yogurt", 7),
        ("Basmati rice", Location.PANTRY, "Rice", 730),
    ],
)
def test_real_data_common_foods(name, location, food_name, days) -> None:
    result = estimate([name], location, ADDED)

    assert result is not None
    assert result.food.name == food_name
    assert result.expires_on == ADDED + timedelta(days=days)


def test_real_data_note_instead_of_time() -> None:
    result = estimate(["Artichokes"], Location.FREEZER, ADDED)

    assert result is not None
    assert result.storage == StorageInfo(note="Not Recommended")
    assert result.expires_on is None


# --- GET /api/v1/spoilage/estimate ---------------------------------------------------


def test_endpoint_requires_auth(client) -> None:
    params = {"name": "Butter", "location": "fridge"}
    assert client.get("/api/v1/spoilage/estimate", params=params).status_code == 401


def test_endpoint_returns_estimate(client, auth_headers) -> None:
    response = client.get(
        "/api/v1/spoilage/estimate",
        params={"name": "Butter", "location": "freezer", "added_on": "2026-11-10"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["food"]["name"] == "Butter"
    assert body["storage"] == {"min": 6, "max": 9, "unit": "months"}
    assert body["note"] is None
    assert body["expires_on"] == "2027-05-09"
    assert body["matched_text"] == "Butter"


def test_endpoint_unknown_food_is_404(client, auth_headers) -> None:
    response = client.get(
        "/api/v1/spoilage/estimate",
        params={"name": "Ferrero Rocher", "location": "pantry"},
        headers=auth_headers(),
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("product_name", "expected_match"),
    [
        pytest.param("Nutella", "Nutella", id="product-name"),
        # Product name matches nothing, so the most specific category is tried next.
        pytest.param("Ferrero Rocher", "hazelnut-spreads", id="product-category"),
    ],
)
def test_endpoint_falls_back_to_cached_product(
    client, auth_headers, session, food_provider, product_name, expected_match
) -> None:
    session.add(
        Product(
            barcode="3017620422003",
            found=True,
            name=product_name,
            categories=["en:spreads", "en:sweet-spreads", "en:hazelnut-spreads"],
            source="fake",
        )
    )
    session.commit()

    response = client.get(
        "/api/v1/spoilage/estimate",
        params={"name": "Mystery jar", "location": "pantry", "barcode": "3017620422003"},
        headers=auth_headers(),
    )

    assert response.status_code == 200, response.text
    assert response.json()["matched_text"] == expected_match
    assert food_provider.calls == []  # only reads our cache, never calls Open Food Facts
