from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, SessionDep
from app.models.item import Location
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.services import items as items_service

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(data: ItemCreate, user: CurrentUserDep, session: SessionDep) -> ItemRead:
    item = items_service.create_item(session, user.id, data)
    return ItemRead.model_validate(item)


@router.get("", response_model=list[ItemRead])
def list_items(
    user: CurrentUserDep, session: SessionDep, location: Location | None = None
) -> list[ItemRead]:
    items = items_service.list_items(session, user.id, location)
    return [ItemRead.model_validate(item) for item in items]


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: UUID, user: CurrentUserDep, session: SessionDep) -> ItemRead:
    return ItemRead.model_validate(items_service.get_item(session, user.id, item_id))


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(
    item_id: UUID, data: ItemUpdate, user: CurrentUserDep, session: SessionDep
) -> ItemRead:
    item = items_service.update_item(session, user.id, item_id, data)
    return ItemRead.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, user: CurrentUserDep, session: SessionDep) -> None:
    items_service.delete_item(session, user.id, item_id)
