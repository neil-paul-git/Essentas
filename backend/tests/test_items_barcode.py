"""Items linked to products by barcode. Uses the fake provider from conftest."""

from sqlalchemy import text

from app.providers.food_data import ProductData

BARCODE = "3017620422003"
NUTELLA = ProductData(
    barcode=BARCODE,
    name="Nutella",
    brand="Ferrero",
    image_url="https://images.example/nutella.jpg",
)
NUTELLA_SUMMARY = {
    "name": "Nutella",
    "brand": "Ferrero",
    "image_url": "https://images.example/nutella.jpg",
}


def _post(client, headers, **body):
    return client.post("/api/v1/items", json={"location": "pantry", **body}, headers=headers)


def test_barcode_alone_creates_linked_item_named_after_product(
    client, auth_headers, food_provider
) -> None:
    food_provider.products[BARCODE] = NUTELLA

    response = _post(client, auth_headers(), barcode=BARCODE)

    assert response.status_code == 201, response.text
    item = response.json()
    assert item["name"] == "Nutella"
    assert item["barcode"] == BARCODE
    assert item["product"] == NUTELLA_SUMMARY


def test_explicit_name_wins_over_product_name(client, auth_headers, food_provider) -> None:
    food_provider.products[BARCODE] = NUTELLA

    item = _post(client, auth_headers(), barcode=BARCODE, name="Choc spread").json()

    assert item["name"] == "Choc spread"
    assert item["product"]["name"] == "Nutella"


def test_scan_then_add_uses_cache(client, auth_headers, food_provider) -> None:
    """The app's normal flow: GET /products after scanning, then POST /items."""
    food_provider.products[BARCODE] = NUTELLA
    headers = auth_headers()

    client.get(f"/api/v1/products/{BARCODE}", headers=headers)
    _post(client, headers, barcode=BARCODE)

    assert food_provider.calls == [BARCODE]


def test_unknown_barcode_with_name_is_linked_without_product_details(client, auth_headers) -> None:
    item = _post(client, auth_headers(), barcode=BARCODE, name="Mystery jam").json()

    assert item["barcode"] == BARCODE
    assert item["product"] is None  # cached miss: nothing to show yet


def test_unknown_barcode_without_name_is_422(client, auth_headers) -> None:
    response = _post(client, auth_headers(), barcode=BARCODE)

    assert response.status_code == 422
    assert "name is required" in response.json()["detail"]


def test_neither_name_nor_barcode_is_422(client, auth_headers) -> None:
    assert _post(client, auth_headers()).status_code == 422


def test_malformed_barcode_is_422(client, auth_headers, food_provider) -> None:
    response = _post(client, auth_headers(), barcode="12-34", name="Jam")

    assert response.status_code == 422
    assert food_provider.calls == []


def test_provider_down_and_not_cached_is_503(client, auth_headers, food_provider) -> None:
    food_provider.unavailable = True

    response = _post(client, auth_headers(), barcode=BARCODE, name="Jam")

    assert response.status_code == 503


def test_patch_links_and_unlinks_product(client, auth_headers, food_provider) -> None:
    food_provider.products[BARCODE] = NUTELLA
    headers = auth_headers()
    item = _post(client, headers, name="Spread").json()
    url = f"/api/v1/items/{item['id']}"

    linked = client.patch(url, json={"barcode": BARCODE}, headers=headers).json()
    unlinked = client.patch(url, json={"barcode": None}, headers=headers).json()

    assert linked["product"] == NUTELLA_SUMMARY
    assert linked["name"] == "Spread"  # linking doesn't rename
    assert unlinked["barcode"] is None
    assert unlinked["product"] is None


def test_list_includes_product_summary(client, auth_headers, food_provider) -> None:
    food_provider.products[BARCODE] = NUTELLA
    headers = auth_headers()
    _post(client, headers, barcode=BARCODE)
    _post(client, headers, name="Apples")

    items = {i["name"]: i for i in client.get("/api/v1/items", headers=headers).json()}

    assert items["Nutella"]["product"] == NUTELLA_SUMMARY
    assert items["Apples"]["product"] is None


def test_deleting_cached_product_unlinks_items(
    client, auth_headers, food_provider, session
) -> None:
    """ON DELETE SET NULL: pruning the products cache must not delete anyone's items."""
    food_provider.products[BARCODE] = NUTELLA
    headers = auth_headers()
    item = _post(client, headers, barcode=BARCODE).json()

    session.execute(text("DELETE FROM products"))
    session.commit()
    session.expire_all()

    after = client.get(f"/api/v1/items/{item['id']}", headers=headers).json()
    assert after["name"] == "Nutella"
    assert after["barcode"] is None
