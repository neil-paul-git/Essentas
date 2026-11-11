"""Open Food Facts product lookups. API docs: https://openfoodfacts.github.io/openfoodfacts-server/api/"""

import logging
from typing import Any

import httpx

from app.core.rate_limit import SlidingWindowRateLimiter
from app.providers.food_data import FoodDataUnavailableError, ProductData

logger = logging.getLogger(__name__)

# Ask only for what we store: smaller, faster responses.
_FIELDS = (
    "code,product_name,brands,quantity,categories_tags,image_front_small_url,"
    "allergens_tags,traces_tags,ingredients_analysis_tags,labels_tags"
)
# OFF's published limit for product reads is 15/min per IP.
_MAX_READS_PER_MINUTE = 15


class OpenFoodFactsProvider:
    source = "open_food_facts"

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        timeout_seconds: float = 5.0,
        rate_limiter: SlidingWindowRateLimiter | None = None,
        transport: httpx.BaseTransport | None = None,  # tests pass httpx.MockTransport
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            transport=transport,
        )
        self._rate_limiter = rate_limiter or SlidingWindowRateLimiter(_MAX_READS_PER_MINUTE, 60)

    def lookup(self, barcode: str) -> ProductData | None:
        if not self._rate_limiter.try_acquire():
            raise FoodDataUnavailableError("Open Food Facts rate limit reached")

        try:
            response = self._client.get(f"/api/v2/product/{barcode}", params={"fields": _FIELDS})
        except httpx.HTTPError as exc:  # timeouts, DNS, connection refused...
            raise FoodDataUnavailableError(f"Open Food Facts unreachable: {exc!r}") from exc

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise FoodDataUnavailableError(f"Open Food Facts returned HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise FoodDataUnavailableError("Open Food Facts returned invalid JSON") from exc

        product = body.get("product")
        if body.get("status") != 1 or not isinstance(product, dict):
            return None
        return _to_product_data(barcode, product)


def _text(value: Any) -> str | None:
    """OFF fields are user-contributed: often missing, empty or not even strings."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _tags(value: Any) -> list[str]:
    """A *_tags field: should be a list of strings, but anything else becomes []."""
    return [t for t in value if isinstance(t, str)] if isinstance(value, list) else []


def _to_product_data(barcode: str, product: dict[str, Any]) -> ProductData:
    brands = _text(product.get("brands"))
    return ProductData(
        barcode=barcode,
        name=_text(product.get("product_name")),
        # "Ferrero, Nutella" -> "Ferrero"
        brand=_text(brands.split(",")[0]) if brands else None,
        quantity_text=_text(product.get("quantity")),
        categories=_tags(product.get("categories_tags")),
        image_url=_text(product.get("image_front_small_url")),
        allergens=_tags(product.get("allergens_tags")),
        traces=_tags(product.get("traces_tags")),
        ingredients_analysis=_tags(product.get("ingredients_analysis_tags")),
        labels=_tags(product.get("labels_tags")),
    )
