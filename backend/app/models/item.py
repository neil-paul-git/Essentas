from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

from app.core.time import utcnow
from app.models.product import Product


class Location(StrEnum):
    FRIDGE = "fridge"
    FREEZER = "freezer"
    PANTRY = "pantry"


class Item(SQLModel, table=True):
    """One thing in a user's kitchen. Input is validated by app.schemas.item, not here:
    SQLModel table classes skip validation when constructed."""

    __tablename__ = "items"
    __table_args__ = (
        sa.CheckConstraint("quantity > 0", name="ck_items_quantity_positive"),
        sa.CheckConstraint(
            "expiry_estimated OR expires_on_latest IS NULL",
            name="ck_items_range_only_when_estimated",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Supabase Auth user id (the JWT "sub" claim). Supabase owns the users table.
    user_id: UUID = Field(index=True)
    name: str = Field(max_length=200)
    # Stored as plain VARCHAR holding "fridge"/"freezer"/"pantry", not a native Postgres
    # ENUM type, so adding a location later doesn't need an ALTER TYPE migration.
    location: Location = Field(
        sa_type=sa.Enum(
            Location,
            native_enum=False,
            length=20,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    quantity: float
    unit: str | None = Field(default=None, max_length=20)
    added_on: date = Field(default_factory=date.today)
    # When the item went into its current location; None means "since added_on".
    # Storage times restart on a move: thawed meat keeps 1-2 days from going into the fridge.
    stored_since: date | None = None
    # Either a date the user confirmed (e.g. printed on the pack), or a FoodKeeper estimate.
    # For an estimate, expires_on is the early end of the range and expires_on_latest the
    # late end, so sorting by expires_on is always the cautious order.
    expires_on: date | None = None
    expiry_estimated: bool = Field(default=False, sa_column_kwargs={"server_default": sa.false()})
    expires_on_latest: date | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=sa.DateTime(timezone=True))

    # Optional link to the cached product. The foreign key makes the database guarantee
    # the barcode exists in products; SET NULL means pruning the cache only unlinks items.
    barcode: str | None = Field(
        default=None,
        max_length=14,
        foreign_key="products.barcode",
        ondelete="SET NULL",
        index=True,
    )
    product: Product | None = Relationship()
