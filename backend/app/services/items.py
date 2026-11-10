from uuid import UUID

from sqlmodel import Session

from app.models.item import Item, Location, utcnow
from app.repositories import items as items_repo
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.errors import NotFoundError


def create_item(session: Session, user_id: UUID, data: ItemCreate) -> Item:
    # user_id comes from the verified token, never from the request body.
    return items_repo.save(session, Item(**data.model_dump(), user_id=user_id))


def list_items(session: Session, user_id: UUID, location: Location | None = None) -> list[Item]:
    return items_repo.list_for_user(session, user_id, location)


def get_item(session: Session, user_id: UUID, item_id: UUID) -> Item:
    item = items_repo.get_for_user(session, user_id, item_id)
    if item is None:
        raise NotFoundError("Item")
    return item


def update_item(session: Session, user_id: UUID, item_id: UUID, data: ItemUpdate) -> Item:
    item = get_item(session, user_id, item_id)
    item.sqlmodel_update(data.model_dump(exclude_unset=True))
    item.updated_at = utcnow()
    return items_repo.save(session, item)


def delete_item(session: Session, user_id: UUID, item_id: UUID) -> None:
    items_repo.delete(session, get_item(session, user_id, item_id))
