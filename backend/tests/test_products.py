"""GET /products/{barcode}: caching behaviour, using the fake provider from conftest."""

from datetime import timedelta

import pytest

from app.core.time import utcnow
from app.models.product import Product
from app.providers.food_data import ProductData

BARCODE = "3017620422003"
NUTELLA = ProductData(barcode=BARCODE, name="Nutella", brand="Ferrero", categories=["en:spreads"])


def test_requires_auth(client) -> None:
    assert client.get(f"/api/v1/products/{BARCODE}").status_code == 401


@pytest.mark.parametrize("barcode", ["abc12345", "1234567", "123456789012345"])
def test_rejects_malformed_barcode(client, auth_headers, food_provider, barcode) -> None:
    response = client.get(f"/api/v1/products/{barcode}", headers=auth_headers())

    assert response.status_code == 422
    assert food_provider.calls == []


def test_first_lookup_hits_provider_then_cache(client, auth_headers, food_provider) -> None:
    food_provider.products[BARCODE] = NUTELLA
    headers = auth_headers()

    first = client.get(f"/api/v1/products/{BARCODE}", headers=headers)
    second = client.get(f"/api/v1/products/{BARCODE}", headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json()["name"] == "Nutella"
    assert first.json()["source"] == "fake"
    assert second.json() == first.json()
    assert food_provider.calls == [BARCODE]  # second request served from our DB


def test_dietary_tags_are_cached(client, auth_headers, food_provider, session) -> None:
    food_provider.products[BARCODE] = ProductData(
        barcode=BARCODE, name="Nutella", allergens=["en:milk", "en:nuts"], traces=["en:gluten"],
        ingredients_analysis=["en:non-vegan"], labels=["en:no-gluten"],
    )  # fmt: skip

    client.get(f"/api/v1/products/{BARCODE}", headers=auth_headers())

    session.expire_all()  # read what was committed, not the request's in-memory object
    cached = session.get(Product, BARCODE)
    assert cached is not None
    assert cached.allergens == ["en:milk", "en:nuts"]
    assert cached.traces == ["en:gluten"]
    assert cached.ingredients_analysis == ["en:non-vegan"]
    assert cached.labels == ["en:no-gluten"]


def test_unknown_barcode_is_404_and_miss_is_cached(client, auth_headers, food_provider) -> None:
    headers = auth_headers()

    first = client.get(f"/api/v1/products/{BARCODE}", headers=headers)
    second = client.get(f"/api/v1/products/{BARCODE}", headers=headers)

    assert first.status_code == second.status_code == 404
    assert first.json() == {"detail": "Product not found"}
    assert food_provider.calls == [BARCODE]


def test_stale_cache_entry_is_refetched(client, auth_headers, food_provider, session) -> None:
    session.add(
        Product(barcode=BARCODE, found=True, name="Old name", source="fake",
                fetched_at=utcnow() - timedelta(days=31))
    )  # fmt: skip
    session.commit()
    food_provider.products[BARCODE] = NUTELLA

    response = client.get(f"/api/v1/products/{BARCODE}", headers=auth_headers())

    assert response.json()["name"] == "Nutella"
    assert food_provider.calls == [BARCODE]


def test_stale_entry_served_when_provider_down(client, auth_headers, food_provider, session):
    session.add(
        Product(barcode=BARCODE, found=True, name="Old name", source="fake",
                fetched_at=utcnow() - timedelta(days=31))
    )  # fmt: skip
    session.commit()
    food_provider.unavailable = True

    response = client.get(f"/api/v1/products/{BARCODE}", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["name"] == "Old name"


def test_provider_down_and_nothing_cached_is_503(client, auth_headers, food_provider) -> None:
    food_provider.unavailable = True

    response = client.get(f"/api/v1/products/{BARCODE}", headers=auth_headers())

    assert response.status_code == 503
    assert response.headers["retry-after"] == "60"
