from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.core.time import utcnow

_EMPTY = {"server_default": "[]"}


class Product(SQLModel, table=True):
    """Cache of external product lookups, keyed by barcode.

    found=False rows are cached misses ("Open Food Facts doesn't know this barcode"),
    so repeat scans of unknown products don't spend our rate limit.
    """

    __tablename__ = "products"

    barcode: str = Field(primary_key=True, max_length=14)
    found: bool
    name: str | None = None
    brand: str | None = None
    quantity_text: str | None = None  # free text from the package, e.g. "400 g"
    categories: list[str] = Field(default_factory=list, sa_type=sa.JSON)
    image_url: str | None = None
    # Dietary tags from the provider (see ProductData). The server default fills rows
    # cached before these columns existed; the 30-day cache TTL refetches them anyway.
    allergens: list[str] = Field(default_factory=list, sa_type=sa.JSON, sa_column_kwargs=_EMPTY)
    traces: list[str] = Field(default_factory=list, sa_type=sa.JSON, sa_column_kwargs=_EMPTY)
    ingredients_analysis: list[str] = Field(
        default_factory=list, sa_type=sa.JSON, sa_column_kwargs=_EMPTY
    )
    labels: list[str] = Field(default_factory=list, sa_type=sa.JSON, sa_column_kwargs=_EMPTY)
    source: str = Field(max_length=40)
    fetched_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
