from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, get_current_user
from app.models.item import Location
from app.schemas.product import BARCODE_PATTERN
from app.schemas.spoilage import FoodKeeperFood, SpoilageEstimateRead, StorageRange
from app.services import spoilage as spoilage_service
from app.services.errors import NotFoundError

router = APIRouter(prefix="/spoilage", tags=["spoilage"], dependencies=[Depends(get_current_user)])


@router.get(
    "/estimate",
    response_model=SpoilageEstimateRead,
    responses={404: {"description": "No FoodKeeper food matches this name"}},
)
def estimate_spoilage(
    session: SessionDep,
    name: Annotated[str, Query(min_length=1, max_length=200)],
    location: Location,
    added_on: date | None = None,
    barcode: Annotated[str | None, Query(pattern=BARCODE_PATTERN)] = None,
) -> SpoilageEstimateRead:
    """Estimate when food stored in `location` since `added_on` (default today) goes off."""
    result = spoilage_service.estimate_for(
        session, name, location, added_on or date.today(), barcode
    )
    if result is None:
        raise NotFoundError("Matching food")

    storage = result.storage
    has_range = storage is not None and storage.min is not None
    return SpoilageEstimateRead(
        food=FoodKeeperFood(
            id=result.food.id,
            name=result.food.name,
            subtitle=result.food.subtitle,
            category=result.food.category,
        ),
        location=result.location,
        storage=StorageRange(min=storage.min, max=storage.max, unit=storage.unit)
        if has_range
        else None,
        note=storage.note if storage else None,
        expires_on=result.expires_on,
        matched_text=result.matched_text,
    )
