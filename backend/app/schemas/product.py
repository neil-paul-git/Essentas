from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
