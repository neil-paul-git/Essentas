from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from app.models.item import Item, Location


def list_for_user(session: Session, user_id: UUID, location: Location | None = None) -> list[Item]:
    # selectinload fetches all the linked products in one extra query. Without it,
    # reading item.product would run one query per item (the "N+1" problem).
    statement = (
        select(Item).where(Item.user_id == user_id).options(selectinload(Item.product))  # type: ignore[arg-type]
    )
    if location is not None:
        statement = statement.where(Item.location == location)
    statement = statement.order_by(col(Item.created_at).desc())
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
