from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.item import Category, Location
from app.schemas.product import BARCODE_PATTERN

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Barcode = Annotated[str, StringConstraints(pattern=BARCODE_PATTERN)]
# float, not Decimal: Pydantic serializes Decimal as a JSON *string* ("1.5"), which is
# awkward for the mobile app, and kitchen quantities don't need exact decimal maths.
Quantity = Annotated[float, Field(gt=0, le=100_000)]


class ItemCreate(BaseModel):
    # Reject unknown fields, so a typo like "expiry" fails loudly and a client can't
    # smuggle in fields such as user_id.
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None  # filled from the product when a barcode is given
    location: Location
    category: Category | None = None  # worked out from the name/product when omitted
    quantity: Quantity = 1
    unit: Unit | None = None
    added_on: date = Field(default_factory=date.today)
    expires_on: date | None = None
    barcode: Barcode | None = None

    @model_validator(mode="after")
    def _name_or_barcode(self) -> Self:
        if self.name is None and self.barcode is None:
            raise ValueError("name is required unless a barcode is given")
        return self


class ItemUpdate(BaseModel):
    """PATCH body. Only fields present in the request are changed."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    location: Location | None = None
    category: Category | None = None
    quantity: Quantity | None = None
    unit: Unit | None = None
    added_on: date | None = None
    expires_on: date | None = None
    barcode: Barcode | None = None  # null unlinks the product

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> Self:
        # "Field omitted" means "leave it alone"; an explicit null is only allowed for
        # columns that may be empty (unit, expires_on, barcode).
        for field in ("name", "location", "category", "quantity", "added_on"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ItemSort(StrEnum):
    NEWEST = "newest"  # most recently added first
    OLDEST = "oldest"
    NAME = "name"  # A-Z, ignoring case
    EXPIRING = "expiring"  # soonest expiry first, items with no expiry last


class ItemListParams(BaseModel):
    """Query parameters for GET /items. Filters are optional and combine with AND, so the
    app can mix them freely: ?location=fridge&expires_by=2026-11-11&sort=name"""

    # Reject unknown parameters, so a typo like ?sortt=name fails instead of being ignored.
    model_config = ConfigDict(extra="forbid")

    # Words to find in the item's name or its product's name/brand; every word must match.
    q: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = None
    location: Location | None = None
    # On or before this date, so already-expired items are included. The app sends a date
    # (e.g. its local tomorrow for "use it soon") rather than a day count, because the
    # server's "today" in UTC can differ from the user's.
    expires_by: date | None = None
    sort: ItemSort = ItemSort.NEWEST


class ProductSummary(BaseModel):
    """The bits of a product the inventory screen needs."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None
    brand: str | None
    image_url: str | None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    location: Location
    category: Category
    quantity: float
    unit: str | None
    added_on: date
    stored_since: date | None  # set by the server when the item changes location
    expires_on: date | None  # for an estimate, the early end of the range
    expiry_estimated: bool  # set by the server; clients can't send it
    expires_on_latest: date | None  # late end of an estimate; None for confirmed dates
    created_at: datetime
    updated_at: datetime
    barcode: str | None
    product: ProductSummary | None

    @field_validator("product", mode="before")
    @classmethod
    def _hide_cached_misses(cls, value: Any) -> Any:
        # A linked products row with found=False only records "OFF doesn't know this";
        # there's nothing useful to show.
        if value is not None and getattr(value, "found", True) is False:
            return None
        return value
