"""The strict diet and allergy rules. Pure functions: no DB, no HTTP."""

from uuid import uuid4

import pytest

from app.models.dietary_profile import Allergen, DietaryProfile, DietaryRestriction
from app.models.item import Category, Item, Location
from app.models.product import Product
from app.services.dietary_rules import Verdict, check_item

R = DietaryRestriction
C = Category


def _item(category: Category = C.OTHER, **product_tags: list[str]) -> Item:
    """An item; pass any product tag list (allergens=..., labels=...) to link a product."""
    product = Product(barcode="1", found=True, source="test", **product_tags)
    return Item(
        user_id=uuid4(),
        name="thing",
        location=Location.PANTRY,
        category=category,
        product=product if product_tags else None,
    )


def _profile(restrictions=(), allergens=()) -> DietaryProfile:
    return DietaryProfile(
        user_id=uuid4(), restrictions=list(restrictions), allergens=list(allergens)
    )


def test_no_profile_or_empty_profile_allows_everything() -> None:
    item = _item(C.MEAT_POULTRY)
    assert check_item(item, None).status is Verdict.ALLOWED
    assert check_item(item, _profile()).status is Verdict.ALLOWED


@pytest.mark.parametrize(
    ("restriction", "item", "expected"),
    [
        # vegan
        (R.VEGAN, _item(ingredients_analysis=["en:non-vegan"]), Verdict.BLOCKED),
        (R.VEGAN, _item(ingredients_analysis=["en:vegan"]), Verdict.ALLOWED),
        (R.VEGAN, _item(labels=["en:vegan"]), Verdict.ALLOWED),
        (R.VEGAN, _item(ingredients_analysis=["en:maybe-vegan"]), Verdict.UNKNOWN),
        (R.VEGAN, _item(allergens=["en:milk"]), Verdict.BLOCKED),
        (R.VEGAN, _item(C.MEAT_POULTRY), Verdict.BLOCKED),
        (R.VEGAN, _item(C.FRUIT), Verdict.ALLOWED),
        (R.VEGAN, _item(C.SNACKS), Verdict.UNKNOWN),
        (R.VEGAN, _item(C.FRUIT, ingredients_analysis=["en:non-vegan"]), Verdict.BLOCKED),
        # tags beat the category: oat milk filed under dairy_eggs
        (R.VEGAN, _item(C.DAIRY_EGGS, labels=["en:vegan"]), Verdict.ALLOWED),
        # vegetarian
        (R.VEGETARIAN, _item(ingredients_analysis=["en:vegan"]), Verdict.ALLOWED),
        (R.VEGETARIAN, _item(C.SEAFOOD), Verdict.BLOCKED),
        (R.VEGETARIAN, _item(allergens=["en:fish"]), Verdict.BLOCKED),
        (R.VEGETARIAN, _item(C.DAIRY_EGGS), Verdict.UNKNOWN),  # rennet, gelatine
        # gluten-free
        (R.GLUTEN_FREE, _item(labels=["en:no-gluten"]), Verdict.ALLOWED),
        (R.GLUTEN_FREE, _item(allergens=["en:gluten"]), Verdict.BLOCKED),
        (R.GLUTEN_FREE, _item(allergens=["en:milk"]), Verdict.ALLOWED),  # list has no gluten
        (R.GLUTEN_FREE, _item(labels=["en:organic"]), Verdict.UNKNOWN),  # no allergen list
        (R.GLUTEN_FREE, _item(C.BAKERY), Verdict.UNKNOWN),
        (R.GLUTEN_FREE, _item(C.MEAT_POULTRY), Verdict.ALLOWED),
        (R.GLUTEN_FREE, _item(C.SEAFOOD, labels=["en:organic"]), Verdict.ALLOWED),
        (R.GLUTEN_FREE, _item(C.MEAT_POULTRY, allergens=["en:gluten"]), Verdict.BLOCKED),
        # dairy-free
        (R.DAIRY_FREE, _item(allergens=["en:nuts"]), Verdict.ALLOWED),
        (R.DAIRY_FREE, _item(allergens=["en:milk"]), Verdict.BLOCKED),
        (R.DAIRY_FREE, _item(C.DAIRY_EGGS), Verdict.UNKNOWN),  # eggs aren't dairy
        (R.DAIRY_FREE, _item(C.MEAT_POULTRY), Verdict.ALLOWED),
        (R.DAIRY_FREE, _item(C.SEAFOOD, allergens=["en:milk"]), Verdict.BLOCKED),
        # halal / kosher
        (R.HALAL, _item(labels=["en:halal"]), Verdict.ALLOWED),
        (R.HALAL, _item(C.MEAT_POULTRY), Verdict.UNKNOWN),
        (R.HALAL, _item(C.VEGETABLES), Verdict.ALLOWED),
        (R.KOSHER, _item(labels=["en:kosher"]), Verdict.ALLOWED),
        (R.KOSHER, _item(allergens=["en:crustaceans"]), Verdict.BLOCKED),
        # carnivore (seafood counts)
        (R.CARNIVORE, _item(C.MEAT_POULTRY), Verdict.ALLOWED),
        (R.CARNIVORE, _item(C.SEAFOOD), Verdict.ALLOWED),
        (R.CARNIVORE, _item(C.PLANT_PROTEIN), Verdict.BLOCKED),
        (R.CARNIVORE, _item(C.SNACKS, labels=["en:vegan"]), Verdict.BLOCKED),
        (R.CARNIVORE, _item(C.SNACKS), Verdict.UNKNOWN),
    ],
)
def test_restriction_rules(restriction, item, expected) -> None:
    assert check_item(item, _profile([restriction])).status is expected


@pytest.mark.parametrize(
    ("item", "expected", "reasons"),
    [
        (_item(allergens=["en:milk", "en:peanuts"]), Verdict.BLOCKED, ["contains peanuts"]),
        (_item(allergens=["en:milk"]), Verdict.ALLOWED, []),  # recorded, no peanuts
        (_item(labels=["en:organic"]), Verdict.UNKNOWN, ["peanuts?"]),  # list not recorded
        (_item(C.FRUIT), Verdict.UNKNOWN, ["peanuts?"]),  # no product at all
    ],
)
def test_allergen_rules(item, expected, reasons) -> None:
    result = check_item(item, _profile(allergens=[Allergen.PEANUTS]))

    assert (result.status, result.reasons) == (expected, reasons)


def test_unfound_product_is_treated_as_no_data() -> None:
    item = _item(allergens=["en:milk"])
    assert item.product is not None
    item.product.found = False

    assert check_item(item, _profile(allergens=[Allergen.MILK])).status is Verdict.UNKNOWN


def test_traces_add_a_disclaimer_without_blocking() -> None:
    item = _item(allergens=["en:milk"], traces=["en:nuts", "en:sesame-seeds"])

    result = check_item(item, _profile(allergens=[Allergen.NUTS]))

    assert result.status is Verdict.ALLOWED
    assert result.may_contain == [Allergen.NUTS]  # sesame isn't one of the user's allergens


def test_trace_of_an_allergen_already_present_is_not_repeated() -> None:
    item = _item(allergens=["en:nuts"], traces=["en:nuts"])

    result = check_item(item, _profile(allergens=[Allergen.NUTS]))

    assert (result.status, result.may_contain) == (Verdict.BLOCKED, [])


def test_blocked_wins_and_lists_only_blocking_reasons() -> None:
    item = _item(allergens=["en:milk"])  # no vegan tags, no halal label

    result = check_item(item, _profile([R.HALAL, R.VEGAN, R.DAIRY_FREE], [Allergen.MILK]))

    assert result.status is Verdict.BLOCKED
    assert result.reasons == ["not vegan", "not dairy-free", "contains milk"]


def test_unknown_lists_every_open_question() -> None:
    result = check_item(_item(C.SNACKS), _profile([R.HALAL, R.VEGAN], [Allergen.EGGS]))

    assert (result.status, result.reasons) == (Verdict.UNKNOWN, ["halal?", "vegan?", "eggs?"])


def test_profile_values_loaded_from_db_as_plain_strings_work() -> None:
    profile = _profile(["vegan"], ["sesame_seeds"])  # JSON columns hand back strings

    result = check_item(_item(allergens=["en:sesame-seeds"]), profile)

    assert result.reasons == ["contains sesame seeds"]
