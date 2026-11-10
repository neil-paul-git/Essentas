"""Interface for product databases (Open Food Facts now, USDA FoodData Central later)."""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class ProductData:
    barcode: str
    name: str | None = None
    brand: str | None = None
    quantity_text: str | None = None
    categories: list[str] = field(default_factory=list)
    image_url: str | None = None


class FoodDataUnavailableError(Exception):
    """The provider couldn't answer: network error, timeout, rate limit or server error."""


class FoodDataProvider(Protocol):
    source: str  # stored with each cached product, e.g. "open_food_facts"

    def lookup(self, barcode: str) -> ProductData | None:
        """Return the product, or None if the provider has no such barcode.
        Raise FoodDataUnavailableError if it can't answer right now."""
        ...


@lru_cache
def get_food_data_provider() -> FoodDataProvider:
    """One provider per process, so its HTTP connection pool and rate limiter are shared.
    Overridden in tests."""
    from app.providers.open_food_facts import OpenFoodFactsProvider

    settings = get_settings()
    return OpenFoodFactsProvider(
        base_url=settings.off_base_url,
        user_agent=f"Essentas/{settings.app_version} ({settings.off_contact})",
        timeout_seconds=settings.off_timeout_seconds,
    )
