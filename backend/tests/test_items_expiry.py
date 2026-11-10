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


# --- Re-estimating on PATCH -----------------------------------------------------------

# Bought three months ago, so "counts from today" and "counts from added_on" differ.
LONG_AGO = date.today() - timedelta(days=90)


def _patch(client, headers, item_id, **body) -> dict:
    response = client.patch(f"/api/v1/items/{item_id}", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_fixing_misspelt_name_gives_first_estimate(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **{**BUTTER, "name": "Buttr"})
    assert created["expires_on"] is None

    updated = _patch(client, headers, created["id"], name="Butter")

    assert updated["expiry_estimated"] is True
    assert updated["expires_on"] == (ADDED + timedelta(days=180)).isoformat()


def test_renaming_to_unknown_food_clears_estimate(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER)

    updated = _patch(client, headers, created["id"], name="Mystery jar")

    assert updated["expiry_estimated"] is False
    assert updated["expires_on"] is None
    assert updated["expires_on_latest"] is None


def test_changing_added_on_shifts_estimate(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER)

    updated = _patch(client, headers, created["id"], added_on="2026-11-01")

    assert updated["expires_on"] == (date(2026, 11, 1) + timedelta(days=180)).isoformat()


def test_move_counts_from_today_not_added_on(client, auth_headers) -> None:
    """Butter frozen three months ago, moved to the fridge today: 1-2 fridge months from now."""
    headers = auth_headers()
    created = _create(client, headers, **{**BUTTER, "added_on": LONG_AGO.isoformat()})

    updated = _patch(client, headers, created["id"], location="fridge")

    today = date.today()
    assert updated["stored_since"] == today.isoformat()
    assert updated["added_on"] == LONG_AGO.isoformat()  # still when it was bought
    assert updated["expires_on"] == (today + timedelta(days=30)).isoformat()
    assert updated["expires_on_latest"] == (today + timedelta(days=60)).isoformat()


def test_rename_after_move_still_counts_from_move(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(
        client, headers, **{**BUTTER, "name": "Buttr", "added_on": LONG_AGO.isoformat()}
    )
    _patch(client, headers, created["id"], location="fridge")

    updated = _patch(client, headers, created["id"], name="Butter")

    assert updated["expires_on"] == (date.today() + timedelta(days=30)).isoformat()


def test_move_to_not_recommended_location_clears_estimate(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, name="Artichokes", location="fridge")
    assert created["expiry_estimated"] is True

    updated = _patch(client, headers, created["id"], location="freezer")

    assert updated["expiry_estimated"] is False
    assert updated["expires_on"] is None


def test_move_keeps_confirmed_expiry(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER, expires_on="2026-12-01")

    updated = _patch(client, headers, created["id"], location="fridge", name="Salted butter")

    assert updated["expires_on"] == "2026-12-01"
    assert updated["expiry_estimated"] is False
    assert updated["stored_since"] == date.today().isoformat()  # the move is still recorded


def test_expiry_sent_with_move_is_confirmed(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER)

    updated = _patch(client, headers, created["id"], location="fridge", expires_on="2026-12-24")

    assert updated["expires_on"] == "2026-12-24"
    assert updated["expiry_estimated"] is False


def test_resending_same_location_is_not_a_move(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **{**BUTTER, "added_on": LONG_AGO.isoformat()})

    updated = _patch(client, headers, created["id"], location="freezer")

    assert updated["stored_since"] is None
    assert updated["expires_on"] == created["expires_on"]


def test_client_cannot_set_stored_since(client, auth_headers) -> None:
    headers = auth_headers()
    created = _create(client, headers, **BUTTER)

    response = client.patch(
        f"/api/v1/items/{created['id']}", json={"stored_since": "2026-01-01"}, headers=headers
    )

    assert response.status_code == 422
