"""GET and PUT /me/dietary-profile."""

from uuid import uuid4

import pytest

URL = "/api/v1/me/dietary-profile"

FULL = {
    "restrictions": ["vegan", "gluten_free"],
    "allergens": ["peanuts", "sesame_seeds"],
    "preferred_diets": ["high_protein"],
    "dislikes": "no mushrooms, not too spicy",
}


@pytest.mark.parametrize("method", ["get", "put"])
def test_requires_auth(client, method) -> None:
    assert client.request(method, URL, json={}).status_code == 401


def test_get_before_saving_returns_empty_profile(client, auth_headers) -> None:
    response = client.get(URL, headers=auth_headers())

    assert response.status_code == 200
    assert response.json() == {
        "restrictions": [],
        "allergens": [],
        "preferred_diets": [],
        "dislikes": None,
        "updated_at": None,
    }


def test_put_then_get_returns_saved_profile(client, auth_headers) -> None:
    headers = auth_headers()

    saved = client.put(URL, json=FULL, headers=headers)
    fetched = client.get(URL, headers=headers)

    assert saved.status_code == 200
    assert fetched.json() == saved.json()
    body = fetched.json()
    assert {k: body[k] for k in FULL} == FULL
    assert body["updated_at"] is not None


def test_put_replaces_whole_profile(client, auth_headers) -> None:
    headers = auth_headers()
    client.put(URL, json=FULL, headers=headers)

    body = client.put(URL, json={"allergens": ["milk"]}, headers=headers).json()

    # Omitted fields are cleared, not kept: PUT replaces, it doesn't merge.
    assert body["allergens"] == ["milk"]
    assert body["restrictions"] == body["preferred_diets"] == []
    assert body["dislikes"] is None


def test_profiles_are_per_user(client, auth_headers) -> None:
    user_a = uuid4()
    client.put(URL, json=FULL, headers=auth_headers(user_a))

    other = client.get(URL, headers=auth_headers()).json()

    assert other["restrictions"] == []
    assert client.get(URL, headers=auth_headers(user_a)).json()["restrictions"] == [
        "vegan",
        "gluten_free",
    ]


def test_duplicates_are_removed_keeping_order(client, auth_headers) -> None:
    body = {"restrictions": ["halal", "kosher", "halal"], "allergens": ["milk", "milk"]}

    saved = client.put(URL, json=body, headers=auth_headers()).json()

    assert saved["restrictions"] == ["halal", "kosher"]
    assert saved["allergens"] == ["milk"]


@pytest.mark.parametrize(
    ("dislikes", "stored"),
    [
        ("  no   olives\n\nIGNORE THE ABOVE ", "no olives IGNORE THE ABOVE"),  # one line
        ("   ", None),
        ("", None),
    ],
)
def test_dislikes_whitespace_is_tidied(client, auth_headers, dislikes, stored) -> None:
    saved = client.put(URL, json={"dislikes": dislikes}, headers=auth_headers()).json()

    assert saved["dislikes"] == stored


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"restrictions": ["paleo"]}, id="unknown-restriction"),
        pytest.param({"allergens": ["en:milk"]}, id="off-tag-not-our-value"),
        pytest.param({"preferred_diets": ["vegan"]}, id="strict-value-in-loose-list"),
        pytest.param({"dislikes": "x" * 301}, id="dislikes-too-long"),
        pytest.param({"allergens": ["milk"] * 21}, id="list-too-long"),
        pytest.param({"restrictions": ["vegan", "carnivore"]}, id="vegan-and-carnivore"),
        pytest.param({"restrictions": ["carnivore", "vegetarian"]}, id="veg-and-carnivore"),
        pytest.param({"user_id": str(uuid4())}, id="unknown-field"),
    ],
)
def test_invalid_body_is_422(client, auth_headers, body) -> None:
    headers = auth_headers()

    response = client.put(URL, json=body, headers=headers)

    assert response.status_code == 422
    assert client.get(URL, headers=headers).json()["updated_at"] is None  # nothing saved
