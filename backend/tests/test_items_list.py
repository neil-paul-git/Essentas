"""GET /api/v1/items: search, filtering and sorting, including the "use it soon" view."""

from datetime import date, timedelta

import pytest

from app.providers.food_data import ProductData

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


def _day(offset: int) -> str:
    return (TODAY + timedelta(days=offset)).isoformat()


def _create(client, headers, name, location="pantry", **body) -> None:
    response = client.post(
        "/api/v1/items", json={"name": name, "location": location, **body}, headers=headers
    )
    assert response.status_code == 201, response.text


def _names(client, headers, **params) -> list[str]:
    response = client.get("/api/v1/items", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()]


def test_use_it_soon_includes_expired_and_sorts_soonest_first(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Tomorrow", expires_on=_day(1))
    _create(client, headers, "Next week", expires_on=_day(7))
    _create(client, headers, "Expired", expires_on=_day(-3))
    _create(client, headers, "Today", expires_on=_day(0))
    _create(client, headers, "Mystery jar")  # no expiry: never "use it soon"

    names = _names(client, headers, expires_by=TOMORROW.isoformat(), sort="expiring")

    assert names == ["Expired", "Today", "Tomorrow"]


def test_use_it_soon_uses_early_end_of_estimate(client, auth_headers) -> None:
    """Butter keeps 1-2 months in the fridge; added 29 days ago it has 1-31 days left."""
    headers = auth_headers()
    _create(client, headers, "Butter", location="fridge", added_on=_day(-29))

    assert _names(client, headers, expires_by=TOMORROW.isoformat()) == ["Butter"]


def test_filters_combine(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Fridge soon", location="fridge", expires_on=_day(0))
    _create(client, headers, "Freezer soon", location="freezer", expires_on=_day(0))
    _create(client, headers, "Fridge later", location="fridge", expires_on=_day(9))

    names = _names(client, headers, location="fridge", expires_by=TOMORROW.isoformat())

    assert names == ["Fridge soon"]


def test_sort_expiring_puts_no_expiry_last(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Mystery jar")
    _create(client, headers, "Later", expires_on=_day(9))
    _create(client, headers, "Sooner", expires_on=_day(2))

    assert _names(client, headers, sort="expiring") == ["Sooner", "Later", "Mystery jar"]


def test_sort_by_name_ignores_case(client, auth_headers) -> None:
    headers = auth_headers()
    for name in ("cherry jam", "Apple juice", "banana chips"):
        _create(client, headers, name)

    assert _names(client, headers, sort="name") == ["Apple juice", "banana chips", "cherry jam"]


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("newest", ["Recent", "Middle", "Old"]),
        ("oldest", ["Old", "Middle", "Recent"]),
    ],
)
def test_sort_by_date_added(client, auth_headers, sort, expected) -> None:
    headers = auth_headers()
    _create(client, headers, "Middle", added_on=_day(-5))
    _create(client, headers, "Recent", added_on=_day(0))
    _create(client, headers, "Old", added_on=_day(-30))

    assert _names(client, headers, sort=sort) == expected


def test_default_sort_is_newest(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Old", added_on=_day(-30))
    _create(client, headers, "Recent", added_on=_day(0))

    assert _names(client, headers) == ["Recent", "Old"]


# --- Search (?q=) ---------------------------------------------------------------------


def test_search_matches_part_of_name_ignoring_case(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Semi-skimmed Milk")
    _create(client, headers, "Oat milk")
    _create(client, headers, "Bread")

    assert sorted(_names(client, headers, q="MILK")) == ["Oat milk", "Semi-skimmed Milk"]


def test_search_needs_every_word_in_any_order(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Whole milk")
    _create(client, headers, "Whole wheat bread")

    assert _names(client, headers, q="milk whole") == ["Whole milk"]


def test_search_matches_linked_product_name_and_brand(client, auth_headers, food_provider) -> None:
    headers = auth_headers()
    food_provider.products["3017620422003"] = ProductData(
        barcode="3017620422003", name="Nutella", brand="Ferrero"
    )
    _create(client, headers, "Chocolate spread", barcode="3017620422003")
    _create(client, headers, "Jam")

    assert _names(client, headers, q="ferrero") == ["Chocolate spread"]
    assert _names(client, headers, q="nutella") == ["Chocolate spread"]


def test_search_treats_wildcards_literally(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Chocolate 70% cocoa")
    _create(client, headers, "Chocolate 70 cocoa")

    assert _names(client, headers, q="70%") == ["Chocolate 70% cocoa"]
    assert _names(client, headers, q="_") == []


def test_blank_search_lists_everything(client, auth_headers) -> None:
    headers = auth_headers()
    _create(client, headers, "Milk")
    _create(client, headers, "Bread")

    assert len(_names(client, headers, q="   ")) == 2


def test_search_combines_with_filters_and_other_users_hidden(client, auth_headers) -> None:
    alice, bob = auth_headers(), auth_headers()
    _create(client, alice, "Milk", location="fridge")
    _create(client, alice, "Powdered milk", location="pantry")
    _create(client, bob, "Milk", location="fridge")

    assert _names(client, alice, q="milk", location="fridge") == ["Milk"]


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"q": "x" * 101}, id="search-too-long"),
        pytest.param({"sort": "price"}, id="unknown-sort"),
        pytest.param({"expires_by": "tomorrow"}, id="bad-date"),
        pytest.param({"sortt": "name"}, id="unknown-parameter"),
    ],
)
def test_bad_list_params_are_422(client, auth_headers, params) -> None:
    response = client.get("/api/v1/items", params=params, headers=auth_headers())

    assert response.status_code == 422
