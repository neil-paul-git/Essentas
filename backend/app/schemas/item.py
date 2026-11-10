from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.item import Location

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Unit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
# float, not Decimal: Pydantic serializes Decimal as a JSON *string* ("1.5"), which is
# awkward for the mobile app, and kitchen quantities don't need exact decimal maths.
Quantity = Annotated[float, Field(gt=0, le=100_000)]


class ItemCreate(BaseModel):
    # Reject unknown fields, so a typo like "expiry" fails loudly and a client can't
    # smuggle in fields such as user_id.
    model_config = ConfigDict(extra="forbid")

    name: Name
    location: Location
    quantity: Quantity = 1
    unit: Unit | None = None
    added_on: date = Field(default_factory=date.today)
    expires_on: date | None = None


class ItemUpdate(BaseModel):
    """PATCH body. Only fields present in the request are changed."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    location: Location | None = None
    quantity: Quantity | None = None
    unit: Unit | None = None
    added_on: date | None = None
    expires_on: date | None = None

    @model_validator(mode="after")
    def _required_fields_not_null(self) -> Self:
        # "Field omitted" means "leave it alone"; an explicit null is only allowed for
        # columns that may be empty (unit, expires_on).
        for field in ("name", "location", "quantity", "added_on"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    location: Location
    quantity: float
    unit: str | None
    added_on: date
    expires_on: date | None
    created_at: datetime
    updated_at: datetime
