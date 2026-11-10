from datetime import datetime

from pydantic import BaseModel, ConfigDict

# EAN-8, UPC-A (12), EAN-13 or GTIN-14: digits only.
BARCODE_PATTERN = r"^\d{8,14}$"


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    barcode: str
    name: str | None
    brand: str | None
    quantity_text: str | None
    categories: list[str]
    image_url: str | None
    source: str
    fetched_at: datetime
