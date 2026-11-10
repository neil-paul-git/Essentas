"""Database tables (SQLModel classes with table=True).

Import every model module here. Alembic's env.py imports this package so that
autogenerate can see all tables on SQLModel.metadata.
"""

from app.models.item import Item, Location
from app.models.product import Product

__all__ = ["Item", "Location", "Product"]
