from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, FoodDataProviderDep, SessionDep
from app.schemas.item import ItemCreate, ItemListParams, ItemRead, ItemUpdate
from app.services import items as items_service

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    data: ItemCreate, user: CurrentUserDep, session: SessionDep, provider: FoodDataProviderDep
) -> ItemRead:
    item = items_service.create_item(session, provider, user.id, data)
    return ItemRead.model_validate(item)


@router.get("", response_model=list[ItemRead])
def list_items(
    params: Annotated[ItemListParams, Query()], user: CurrentUserDep, session: SessionDep
) -> list[ItemRead]:
    """List the caller's items. For "use it soon", the app sends its local tomorrow:
    ?expires_by=<tomorrow>&sort=expiring (already-expired items are included)."""
    items = items_service.list_items(session, user.id, params)
    return [ItemRead.model_validate(item) for item in items]


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: UUID, user: CurrentUserDep, session: SessionDep) -> ItemRead:
    return ItemRead.model_validate(items_service.get_item(session, user.id, item_id))


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(
    item_id: UUID,
    data: ItemUpdate,
    user: CurrentUserDep,
    session: SessionDep,
    provider: FoodDataProviderDep,
) -> ItemRead:
    item = items_service.update_item(session, provider, user.id, item_id, data)
    return ItemRead.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, user: CurrentUserDep, session: SessionDep) -> None:
    items_service.delete_item(session, user.id, item_id)
