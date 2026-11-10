from datetime import date

from pydantic import BaseModel

from app.models.item import Location


class FoodKeeperFood(BaseModel):
    id: int
    name: str
    subtitle: str | None
    category: str | None


class StorageRange(BaseModel):
    min: float
    max: float
    unit: str  # hours, days, weeks, months, years


class SpoilageEstimateRead(BaseModel):
    food: FoodKeeperFood
    location: Location
    storage: StorageRange | None  # None when FoodKeeper only has a note, or no data
    note: str | None  # e.g. "Not Recommended", "When Ripe", "Indefinitely"
    expires_on: date | None
    matched_text: str  # which text matched: the item name, or product name/category
