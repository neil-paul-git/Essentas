"""Item categories: the FoodKeeper mapping, auto-fill on create, and PATCH rules."""

import json
from importlib.resources import files

import pytest

from app.models.item import Category
from app.providers.food_data import ProductData
from app.services.categories import _FOODKEEPER, from_foodkeeper

# --- The mapping ---------------------------------------------------------------------


def test_every_foodkeeper_category_is_mapped() -> None:
    """Fails if a FoodKeeper data update adds or renames a category."""
    raw = json.loads((files("app") / "data" / "foodkeeper.json").read_text(encoding="utf-8"))
    in_data = {food["category"] for food in raw["foods"] if food["category"]}

    assert in_data == set(_FOODKEEPER)


@pytest.mark.parametrize("category", [None, "", "Something new"])
def test_unknown_foodkeeper_category_is_other(category) -> None:
    assert from_foodkeeper(category) is Category.OTHER


# --- POST /api/v1/items ----------------------------------------------------------------


def _create(client, headers, **body) -> dict:
    response = client.post("/api/v1/items", json={"location": "fridge", **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("name", "location", "category"),
    [
        ("Butter", "fridge", "dairy_eggs"),
        ("Free range eggs x12", "fridge", "dairy_eggs"),
        ("Chicken thighs", "fridge", "meat_poultry"),
        ("Basmati rice", "pantry", "grains_pasta"),
        # FoodKeeper's rice in the fridge is cooked rice, under Deli & Prepared Foods
        ("Basmati rice", "fridge", "prepared"),
        ("Mystery jar", "pantry", "other"),
    ],
)
def test_create_fills_category(client, auth_headers, name, location, category) -> None:
    item = _create(client, auth_headers(), name=name, location=location)

    assert item["category"] == category


def test_create_keeps_category_sent_by_client(client, auth_headers) -> None:
    assert _create(client, auth_headers(), name="Butter", category="snacks")["category"] == "snacks"


def test_create_fills_category_even_without_estimate(client, auth_headers) -> None:
    """A confirmed date, or a "Not Recommended" location, still gets a category."""
    headers = auth_headers()
    confirmed = _create(client, headers, name="Butter", expires_on="2026-12-01")
    frozen = _create(client, headers, name="Artichokes", location="freezer")

    assert confirmed["category"] == "dairy_eggs"
    assert frozen["expires_on"] is None
    assert frozen["category"] == "vegetables"


def test_create_category_from_cached_product(client, auth_headers, food_provider) -> None:
    """An unrecognised name falls back to the product's Open Food Facts categories."""
    food_provider.products["3017620422003"] = ProductData(
        barcode="3017620422003", name="Lait", categories=["en:dairies", "en:milks"]
    )

    item = _create(client, auth_headers(), name="Lait", barcode="3017620422003")

    assert item["category"] == "dairy_eggs"


# --- PATCH /api/v1/items/{id} ----------------------------------------------------------


def _patch(client, headers, item_id, **body) -> dict:
    response = client.patch(f"/api/v1/items/{item_id}", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_rename_recategorizes(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, name="Buttr")
    assert created["category"] == "other"

    assert _patch(client, headers, created["id"], name="Butter")["category"] == "dairy_eggs"


def test_rename_recategorizes_even_with_confirmed_expiry(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, name="Buttr", expires_on="2026-12-01")

    updated = _patch(client, headers, created["id"], name="Butter")

    assert updated["category"] == "dairy_eggs"
    assert updated["expires_on"] == "2026-12-01"


def test_category_sent_with_rename_wins(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, name="Buttr")

    updated = _patch(client, headers, created["id"], name="Butter", category="snacks")

    assert updated["category"] == "snacks"


def test_move_keeps_manual_category(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, name="Butter", category="snacks")

    assert _patch(client, headers, created["id"], location="freezer")["category"] == "snacks"


@pytest.mark.parametrize("category", [None, "candy"])
def test_patch_rejects_bad_category(client, auth_headers, category) -> None:
    headers = auth_headers()
    created = _create(client, headers, name="Butter")

    response = client.patch(
        f"/api/v1/items/{created['id']}", json={"category": category}, headers=headers
    )

    assert response.status_code == 422
