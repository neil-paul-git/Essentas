from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.core.time import utcnow


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
    source: str = Field(max_length=40)
    fetched_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
