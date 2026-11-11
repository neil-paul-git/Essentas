"""Barcode lookup: our products table first, the external provider only on a miss."""

import logging
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.time import as_utc, utcnow
from app.models.product import Product
from app.providers.food_data import FoodDataProvider, FoodDataUnavailableError, ProductData
from app.repositories import products as products_repo
from app.services.errors import NotFoundError, ServiceUnavailableError

logger = logging.getLogger(__name__)

# Product data rarely changes; "not found" may change sooner as people add products to OFF.
FOUND_TTL = timedelta(days=30)
NOT_FOUND_TTL = timedelta(days=7)


def lookup_product(
    session: Session,
    provider: FoodDataProvider,
    barcode: str,
    now: datetime | None = None,
) -> Product:
    """Return the product for a barcode, or raise NotFoundError / ServiceUnavailableError."""
    return _found_or_raise(get_or_fetch(session, provider, barcode, now))


def get_or_fetch(
    session: Session,
    provider: FoodDataProvider,
    barcode: str,
    now: datetime | None = None,
) -> Product:
    """Return the products row for a barcode, fetching it if missing or stale.

    The row may have found=False (a cached miss). Raises ServiceUnavailableError only
    when the provider is down and we have nothing cached at all.
    """
    now = now or utcnow()
    cached = products_repo.get(session, barcode)

    if cached is not None and _is_fresh(cached, now):
        return cached

    try:
        data = provider.lookup(barcode)
    except FoodDataUnavailableError:
        if cached is not None:
            # An old answer beats no answer while the provider is down or rate-limited.
            logger.info("Serving stale product %s: provider unavailable", barcode)
            return cached
        logger.warning("Product lookup failed for %s", barcode, exc_info=True)
        raise ServiceUnavailableError("Product lookup is temporarily unavailable") from None

    product = cached or Product(barcode=barcode, found=False, source=provider.source)
    _apply(product, data, provider.source, now)
    try:
        return products_repo.save(session, product)
    except IntegrityError:
        # Two requests for the same new barcode raced; the other one saved it first.
        session.rollback()
        return products_repo.get(session, barcode) or product


def _is_fresh(product: Product, now: datetime) -> bool:
    ttl = FOUND_TTL if product.found else NOT_FOUND_TTL
    return now - as_utc(product.fetched_at) < ttl


def _found_or_raise(product: Product) -> Product:
    if not product.found:
        raise NotFoundError("Product")
    return product


def _apply(product: Product, data: ProductData | None, source: str, now: datetime) -> None:
    product.found = data is not None
    product.name = data.name if data else None
    product.brand = data.brand if data else None
    product.quantity_text = data.quantity_text if data else None
    product.categories = list(data.categories) if data else []
    product.image_url = data.image_url if data else None
    product.allergens = list(data.allergens) if data else []
    product.traces = list(data.traces) if data else []
    product.ingredients_analysis = list(data.ingredients_analysis) if data else []
    product.labels = list(data.labels) if data else []
    product.source = source
    product.fetched_at = now
