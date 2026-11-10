from datetime import date
from uuid import UUID

from sqlmodel import Session

from app.core.time import utcnow
from app.models.item import Item, Location
from app.providers.food_data import FoodDataProvider
from app.repositories import items as items_repo
from app.schemas.item import ItemCreate, ItemUpdate
from app.services import products as products_service
from app.services import spoilage as spoilage_service
from app.services.errors import InvalidInputError, NotFoundError


def create_item(
    session: Session, provider: FoodDataProvider, user_id: UUID, data: ItemCreate
) -> Item:
    values = data.model_dump()

    if data.barcode is not None:
        # The foreign key needs a products row first. Usually a cache hit, because the
        # app looked the barcode up right after scanning it.
        product = products_service.get_or_fetch(session, provider, data.barcode)
        if values["name"] is None and product.found:
            values["name"] = product.name

    if values["name"] is None:
        raise InvalidInputError("name is required: the product has no name on record")

    # user_id comes from the verified token, never from the request body.
    item = Item(**values, user_id=user_id)
    if item.expires_on is None:
        _estimate_expiry(session, item)
    return items_repo.save(session, item)


# Fields the FoodKeeper estimate depends on: changing one makes an old estimate stale.
_ESTIMATE_INPUTS = ("name", "location", "added_on", "barcode")


def _estimate_expiry(session: Session, item: Item) -> None:
    """Set (or replace) a FoodKeeper estimate. Clears the expiry if no food matches or
    FoodKeeper only has a note for this location (e.g. "Not Recommended")."""
    result = spoilage_service.estimate_for(
        session, item.name, item.location, item.stored_since or item.added_on, item.barcode
    )
    found = result is not None and result.expires_on is not None
    item.expires_on = result.expires_on if found else None
    item.expires_on_latest = result.expires_on_latest if found else None
    item.expiry_estimated = found


def list_items(session: Session, user_id: UUID, location: Location | None = None) -> list[Item]:
    return items_repo.list_for_user(session, user_id, location)


def get_item(session: Session, user_id: UUID, item_id: UUID) -> Item:
    item = items_repo.get_for_user(session, user_id, item_id)
    if item is None:
        raise NotFoundError("Item")
    return item


def update_item(
    session: Session,
    provider: FoodDataProvider,
    user_id: UUID,
    item_id: UUID,
    data: ItemUpdate,
) -> Item:
    item = get_item(session, user_id, item_id)
    changes = data.model_dump(exclude_unset=True)

    if changes.get("barcode") is not None:
        products_service.get_or_fetch(session, provider, changes["barcode"])

    # Compare against the stored values, so re-sending an unchanged field is a no-op.
    inputs_changed = any(
        field in changes and changes[field] != getattr(item, field) for field in _ESTIMATE_INPUTS
    )
    if "location" in changes and changes["location"] != item.location:
        changes["stored_since"] = date.today()

    if "expires_on" in changes:
        # A date from the client is confirmed; null clears the expiry. Either way any
        # earlier estimate no longer applies.
        changes["expiry_estimated"] = False
        changes["expires_on_latest"] = None

    # Never overwrite a confirmed date. An empty expiry counts as re-estimable, so fixing
    # a misspelt name can produce a first estimate.
    is_confirmed = item.expires_on is not None and not item.expiry_estimated
    reestimate = inputs_changed and "expires_on" not in changes and not is_confirmed

    item.sqlmodel_update(changes)
    if reestimate:
        _estimate_expiry(session, item)
    item.updated_at = utcnow()
    return items_repo.save(session, item)


def delete_item(session: Session, user_id: UUID, item_id: UUID) -> None:
    items_repo.delete(session, get_item(session, user_id, item_id))
