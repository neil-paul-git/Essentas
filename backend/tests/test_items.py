from datetime import date
from uuid import uuid4

import pytest

MILK = {
    "name": "Milk",
    "location": "fridge",
    "quantity": 1,
    "unit": "L",
    "expires_on": "2026-11-20",
}


def _create(client, headers, **overrides) -> dict:
    response = client.post("/api/v1/items", json={**MILK, **overrides}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_items_require_auth(client) -> None:
    assert client.get("/api/v1/items").status_code == 401
    assert client.post("/api/v1/items", json=MILK).status_code == 401


def test_create_item(client, auth_headers) -> None:
    item = _create(client, auth_headers(), name="  Milk  ")

    assert item["name"] == "Milk"  # whitespace stripped
    assert item["location"] == "fridge"
    assert item["quantity"] == 1
    assert item["added_on"] == date.today().isoformat()  # defaulted
    assert item["expires_on"] == "2026-11-20"
    assert "user_id" not in item


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"quantity": 0}, id="zero-quantity"),
        pytest.param({"name": "   "}, id="blank-name"),
        pytest.param({"location": "garage"}, id="unknown-location"),
        pytest.param({"user_id": str(uuid4())}, id="client-sets-user-id"),
        pytest.param({"expiry": "2026-11-20"}, id="unknown-field"),
    ],
)
def test_create_item_rejects_bad_input(client, auth_headers, overrides) -> None:
    response = client.post("/api/v1/items", json={**MILK, **overrides}, headers=auth_headers())

    assert response.status_code == 422


def test_list_returns_only_callers_items(client, auth_headers) -> None:
    alice, bob = auth_headers(uuid4()), auth_headers(uuid4())
    _create(client, alice, name="Milk")
    _create(client, alice, name="Peas", location="freezer")
    _create(client, bob, name="Eggs")

    names = sorted(i["name"] for i in client.get("/api/v1/items", headers=alice).json())

    assert names == ["Milk", "Peas"]


def test_list_filters_by_location(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, name="Milk")
    _create(client, headers, name="Peas", location="freezer")

    response = client.get("/api/v1/items", params={"location": "freezer"}, headers=headers)

    assert [i["name"] for i in response.json()] == ["Peas"]


def test_get_item(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers)

    response = client.get(f"/api/v1/items/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == created


def test_unknown_item_is_404(client, auth_headers) -> None:
    response = client.get(f"/api/v1/items/{uuid4()}", headers=auth_headers())

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


@pytest.mark.parametrize(
    ("method", "body"), [("get", None), ("patch", {"quantity": 5}), ("delete", None)]
)
def test_other_users_item_is_404(client, auth_headers, method, body) -> None:
    """404, not 403: don't even reveal that the item exists."""
    owner_item = _create(client, auth_headers())

    response = client.request(
        method, f"/api/v1/items/{owner_item['id']}", json=body, headers=auth_headers()
    )

    assert response.status_code == 404


def test_patch_changes_only_sent_fields(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers)

    response = client.patch(
        f"/api/v1/items/{created['id']}", json={"quantity": 0.5}, headers=headers
    )

    updated = response.json()
    assert response.status_code == 200
    assert updated["quantity"] == 0.5
    assert updated["name"] == created["name"]
    assert updated["expires_on"] == created["expires_on"]
    assert updated["updated_at"] >= created["updated_at"]


def test_patch_can_clear_optional_field(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers)

    response = client.patch(
        f"/api/v1/items/{created['id']}", json={"expires_on": None}, headers=headers
    )

    assert response.json()["expires_on"] is None


def test_patch_rejects_null_for_required_field(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers)

    response = client.patch(f"/api/v1/items/{created['id']}", json={"name": None}, headers=headers)

    assert response.status_code == 422


def test_delete_item(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers)

    assert client.delete(f"/api/v1/items/{created['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/v1/items/{created['id']}", headers=headers).status_code == 404
