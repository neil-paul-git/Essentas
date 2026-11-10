"""Estimated vs confirmed expiry dates on items. Uses the real FoodKeeper file (no network)."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.item import Item, Location

ADDED = date(2026, 11, 10)
# FoodKeeper: butter keeps 6-9 months in the freezer.
BUTTER = {"name": "Butter", "location": "freezer", "added_on": ADDED.isoformat()}


def _create(client, headers, **body) -> dict:
    response = client.post("/api/v1/items", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_without_expiry_fills_estimate(client, auth_headers) -> None:
    item = _create(client, auth_headers(), **BUTTER)

    assert item["expiry_estimated"] is True
    assert item["expires_on"] == (ADDED + timedelta(days=180)).isoformat()
    assert item["expires_on_latest"] == (ADDED + timedelta(days=270)).isoformat()


def test_create_with_expiry_is_confirmed(client, auth_headers) -> None:
    item = _create(client, auth_headers(), **BUTTER, expires_on="2026-12-01")

    assert item["expiry_estimated"] is False
    assert item["expires_on"] == "2026-12-01"
    assert item["expires_on_latest"] is None


def test_create_unknown_food_has_no_expiry(client, auth_headers) -> None:
    item = _create(client, auth_headers(), name="Mystery jar", location="pantry")

    assert item["expiry_estimated"] is False
    assert item["expires_on"] is None
    assert item["expires_on_latest"] is None


def test_create_note_only_food_has_no_expiry(client, auth_headers) -> None:
    """FoodKeeper says freezing artichokes is "Not Recommended": no date to estimate."""
    item = _create(client, auth_headers(), name="Artichokes", location="freezer")

    assert item["expiry_estimated"] is False
    assert item["expires_on"] is None


def test_client_cannot_set_estimated_flag(client, auth_headers) -> None:
    response = client.post(
        "/api/v1/items", json={**BUTTER, "expiry_estimated": False}, headers=auth_headers()
    )

    assert response.status_code == 422


def test_patch_expiry_confirms_estimate(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER)

    response = client.patch(
        f"/api/v1/items/{created['id']}", json={"expires_on": "2027-01-15"}, headers=headers
    )

    updated = response.json()
    assert updated["expires_on"] == "2027-01-15"
    assert updated["expiry_estimated"] is False
    assert updated["expires_on_latest"] is None


def test_patch_null_expiry_clears_estimate(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER)

    response = client.patch(
        f"/api/v1/items/{created['id']}", json={"expires_on": None}, headers=headers
    )

    updated = response.json()
    assert updated["expires_on"] is None
    assert updated["expiry_estimated"] is False
    assert updated["expires_on_latest"] is None


def test_patch_other_fields_keeps_estimate(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER)

    response = client.patch(f"/api/v1/items/{created['id']}", json={"quantity": 2}, headers=headers)

    updated = response.json()
    assert updated["expiry_estimated"] is True
    assert updated["expires_on"] == created["expires_on"]
    assert updated["expires_on_latest"] == created["expires_on_latest"]


def test_db_rejects_range_on_confirmed_expiry(session) -> None:
    """The check constraint backs up the service: a confirmed date can't carry a range."""
    session.add(
        Item(
            user_id=uuid4(),
            name="Butter",
            location=Location.FRIDGE,
            quantity=1,
            expires_on=ADDED,
            expiry_estimated=False,
            expires_on_latest=ADDED + timedelta(days=5),
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
