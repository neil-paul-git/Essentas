from datetime import date
from uuid import UUID

from sqlmodel import Session

from app.core.time import utcnow
from app.models.item import Item
from app.providers.food_data import FoodDataProvider
from app.repositories import items as items_repo
from app.schemas.item import ItemCreate, ItemListParams, ItemUpdate
from app.services import categories
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
    fill_expiry, fill_category = item.expires_on is None, data.category is None
    if fill_expiry or fill_category:
        match = _match_food(session, item)
        if fill_expiry:
            _set_estimated_expiry(item, match)
        if fill_category:
            _set_category(item, match)
    return items_repo.save(session, item)


# Fields the FoodKeeper estimate depends on: changing one makes an old estimate stale.
_ESTIMATE_INPUTS = frozenset({"name", "location", "added_on", "barcode"})
# The category only depends on what the food is, not where or since when it's stored.
_CATEGORY_INPUTS = frozenset({"name", "barcode"})


def _match_food(session: Session, item: Item) -> spoilage_service.SpoilageEstimate | None:
    """One FoodKeeper match feeds both the expiry estimate and the category."""
    return spoilage_service.estimate_for(
        session, item.name, item.location, item.stored_since or item.added_on, item.barcode
    )


def _set_estimated_expiry(item: Item, result: spoilage_service.SpoilageEstimate | None) -> None:
    """Set (or replace) a FoodKeeper estimate. Clears the expiry if no food matches or
    FoodKeeper only has a note for this location (e.g. "Not Recommended")."""
    found = result is not None and result.expires_on is not None
    item.expires_on = result.expires_on if found else None
    item.expires_on_latest = result.expires_on_latest if found else None
    item.expiry_estimated = found


def _set_category(item: Item, result: spoilage_service.SpoilageEstimate | None) -> None:
    item.category = categories.from_foodkeeper(result.food.category if result else None)


def list_items(session: Session, user_id: UUID, params: ItemListParams) -> list[Item]:
    return items_repo.list_for_user(session, user_id, params)


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
    changed = {field for field in changes if changes[field] != getattr(item, field)}
    if "location" in changed:
        changes["stored_since"] = date.today()

    if "expires_on" in changes:
        # A date from the client is confirmed; null clears the expiry. Either way any
        # earlier estimate no longer applies.
        changes["expiry_estimated"] = False
        changes["expires_on_latest"] = None

    # Never overwrite a confirmed date. An empty expiry counts as re-estimable, so fixing
    # a misspelt name can produce a first estimate.
    is_confirmed = item.expires_on is not None and not item.expiry_estimated
    reestimate = (
        bool(changed & _ESTIMATE_INPUTS) and "expires_on" not in changes and not is_confirmed
    )
    # A category the client sends wins; otherwise a new name or barcode re-derives it.
    recategorize = bool(changed & _CATEGORY_INPUTS) and "category" not in changes

    item.sqlmodel_update(changes)
    if reestimate or recategorize:
        match = _match_food(session, item)
        if reestimate:
            _set_estimated_expiry(item, match)
        if recategorize:
            _set_category(item, match)
    item.updated_at = utcnow()
    return items_repo.save(session, item)


def delete_item(session: Session, user_id: UUID, item_id: UUID) -> None:
    items_repo.delete(session, get_item(session, user_id, item_id))
