from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from app.models.item import Item
from app.schemas.item import ItemListParams, ItemSort

# Each sort ends with a tie-break, so items with equal values come back in a stable order.
_ORDER_BY = {
    ItemSort.NEWEST: (col(Item.added_on).desc(), col(Item.created_at).desc()),
    ItemSort.OLDEST: (col(Item.added_on).asc(), col(Item.created_at).asc()),
    ItemSort.NAME: (func.lower(Item.name), col(Item.created_at).desc()),
    ItemSort.EXPIRING: (col(Item.expires_on).asc().nulls_last(), func.lower(Item.name)),
}


def list_for_user(session: Session, user_id: UUID, params: ItemListParams) -> list[Item]:
    # selectinload fetches all the linked products in one extra query. Without it,
    # reading item.product would run one query per item (the "N+1" problem).
    statement = (
        select(Item).where(Item.user_id == user_id).options(selectinload(Item.product))  # type: ignore[arg-type]
    )
    if params.location is not None:
        statement = statement.where(Item.location == params.location)
    if params.expires_by is not None:
        # In SQL, NULL <= date is not true, so items with no expiry are left out.
        statement = statement.where(col(Item.expires_on) <= params.expires_by)
    statement = statement.order_by(*_ORDER_BY[params.sort])
    return list(session.exec(statement))


def get_for_user(session: Session, user_id: UUID, item_id: UUID) -> Item | None:
    # Filtering on user_id here (not checking afterwards) means another user's item
    # is simply "not found".
    statement = select(Item).where(Item.id == item_id, Item.user_id == user_id)
    return session.exec(statement).first()


def save(session: Session, item: Item) -> Item:
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete(session: Session, item: Item) -> None:
    session.delete(item)
    session.commit()
