"""Database tables (SQLModel classes with table=True).

Import every model module here. Alembic's env.py imports this package so that
autogenerate can see all tables on SQLModel.metadata.
"""

from sqlmodel import SQLModel

# Give constraints predictable names, so migrations can later drop or alter them by
# name. (Unnamed ones get database-chosen names that Alembic can't know in advance.)
# Must be set before the model modules below define their tables.
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",  # SQLAlchemy's default, kept so existing names match
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}

from app.models.item import Item, Location  # noqa: E402
from app.models.product import Product  # noqa: E402

__all__ = ["Item", "Location", "Product"]
