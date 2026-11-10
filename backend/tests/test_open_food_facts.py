"""The real OFF provider, with HTTP intercepted by httpx.MockTransport (no network)."""

import httpx
import pytest

from app.core.rate_limit import SlidingWindowRateLimiter
from app.providers.food_data import FoodDataUnavailableError, ProductData
from app.providers.open_food_facts import OpenFoodFactsProvider

BARCODE = "3017620422003"

# Trimmed real-world response shape from GET /api/v2/product/{barcode}
FOUND_BODY = {
    "code": BARCODE,
    "status": 1,
    "status_verbose": "product found",
    "product": {
        "code": BARCODE,
        "product_name": "Nutella",
        "brands": "Ferrero, Nutella",
        "quantity": "400 g",
        "categories_tags": ["en:spreads", "en:sweet-spreads", 42],
        "image_front_small_url": "https://images.openfoodfacts.org/nutella.jpg",
    },
}


def _provider(handler, rate_limiter=None) -> OpenFoodFactsProvider:
    return OpenFoodFactsProvider(
        base_url="https://off.test",
        user_agent="Essentas/0.1.0 (https://github.com/example/essentas)",
        rate_limiter=rate_limiter,
        transport=httpx.MockTransport(handler),
    )


def test_found_product_is_parsed() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FOUND_BODY)

    result = _provider(handler).lookup(BARCODE)

    assert result == ProductData(
        barcode=BARCODE,
        name="Nutella",
        brand="Ferrero",
        quantity_text="400 g",
        categories=["en:spreads", "en:sweet-spreads"],  # non-strings dropped
        image_url="https://images.openfoodfacts.org/nutella.jpg",
    )
    (request,) = requests
    assert request.url.path == f"/api/v2/product/{BARCODE}"
    assert "product_name" in request.url.params["fields"]
    assert request.headers["User-Agent"] == "Essentas/0.1.0 (https://github.com/example/essentas)"


def test_blank_and_missing_fields_become_none() -> None:
    body = {"status": 1, "product": {"product_name": "  ", "brands": ""}}

    result = _provider(lambda r: httpx.Response(200, json=body)).lookup(BARCODE)

    assert result == ProductData(barcode=BARCODE)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(httpx.Response(404, json={"status": 0}), id="http-404"),
        pytest.param(httpx.Response(200, json={"status": 0}), id="status-0"),
    ],
)
def test_unknown_barcode_returns_none(response: httpx.Response) -> None:
    assert _provider(lambda r: response).lookup(BARCODE) is None


@pytest.mark.parametrize(
    "handler",
    [
        pytest.param(lambda r: httpx.Response(429), id="rate-limited-by-off"),
        pytest.param(lambda r: httpx.Response(503), id="server-error"),
        pytest.param(lambda r: httpx.Response(200, text="<html>oops"), id="not-json"),
    ],
)
def test_bad_responses_raise_unavailable(handler) -> None:
    with pytest.raises(FoodDataUnavailableError):
        _provider(handler).lookup(BARCODE)


def test_timeout_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(FoodDataUnavailableError):
        _provider(handler).lookup(BARCODE)


def test_own_rate_limit_stops_request_before_it_is_sent() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=FOUND_BODY)

    provider = _provider(handler, rate_limiter=SlidingWindowRateLimiter(1, 60))
    provider.lookup(BARCODE)

    with pytest.raises(FoodDataUnavailableError):
        provider.lookup(BARCODE)
    assert len(requests) == 1
