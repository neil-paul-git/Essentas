"""Does an inventory item fit a user's strict diet and allergies? Rules only, never the LLM.

Used only to choose which inventory items go into a recipe prompt, and how they are
tagged. It never limits what a user can add, scan or keep in their inventory.

Each rule answers allowed, blocked or unknown. Open Food Facts tags decide first; our
item category is only a fallback for obvious cases (meat isn't vegan, fruit is), used
when the tags say nothing. OFF data is crowd-sourced and often missing, so "no data"
is unknown, never allowed. Loose preferences (keto, dislikes) are left to the LLM.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from app.models.dietary_profile import Allergen, DietaryProfile, DietaryRestriction
from app.models.item import Category, Item


class Verdict(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"  # sent to the LLM tagged as such


@dataclass(frozen=True)
class DietCheck:
    status: Verdict
    reasons: list[str] = field(default_factory=list)  # why blocked/unknown; empty if allowed
    # The user's allergens listed as traces ("may contain"). Never changes status: the
    # recipe page shows a small disclaimer instead (docs/frontend-notes.md).
    may_contain: list[Allergen] = field(default_factory=list)


@dataclass(frozen=True)
class _Facts:
    category: Category
    tags: frozenset[str]  # OFF ingredients_analysis + labels, e.g. "en:vegan", "en:halal"
    allergens: frozenset[str]  # empty = not recorded, not "none"
    traces: frozenset[str]


@dataclass(frozen=True)
class _Rule:
    block_tags: frozenset[str] = frozenset()
    block_allergens: frozenset[str] = frozenset()
    block_categories: frozenset[Category] = frozenset()
    allow_tags: frozenset[str] = frozenset()
    allow_categories: frozenset[Category] = frozenset()
    # Allowed if the product has an allergen list without any block_allergens in it.
    allow_if_allergens_recorded: bool = False

    def decide(self, facts: _Facts) -> Verdict:
        # 1. OFF tags. If they conflict, blocked wins.
        if facts.tags & self.block_tags or facts.allergens & self.block_allergens:
            return Verdict.BLOCKED
        if facts.tags & self.allow_tags or (self.allow_if_allergens_recorded and facts.allergens):
            return Verdict.ALLOWED
        # 2. Category, only when the tags didn't decide. So a "vegan" label beats a
        # dairy_eggs category (oat milk), and gluten in the allergens beats meat (nuggets).
        if facts.category in self.block_categories:
            return Verdict.BLOCKED
        if facts.category in self.allow_categories:
            return Verdict.ALLOWED
        return Verdict.UNKNOWN


C = Category
_PRODUCE = frozenset({C.FRUIT, C.VEGETABLES})
# Fresh produce, meat and fish contain no gluten or dairy. Processed ones (breaded,
# marinated in butter) list it in their allergens, and tags are checked first.
_FRESH = _PRODUCE | {C.MEAT_POULTRY, C.SEAFOOD}
_SEA_ANIMALS = frozenset({"en:fish", "en:crustaceans", "en:molluscs"})

_RULES: dict[DietaryRestriction, _Rule] = {
    DietaryRestriction.VEGAN: _Rule(
        block_tags=frozenset({"en:non-vegan"}),
        block_allergens=_SEA_ANIMALS | {"en:milk", "en:eggs"},
        block_categories=frozenset({C.MEAT_POULTRY, C.SEAFOOD, C.DAIRY_EGGS}),
        allow_tags=frozenset({"en:vegan"}),
        allow_categories=_PRODUCE,
    ),
    DietaryRestriction.VEGETARIAN: _Rule(
        block_tags=frozenset({"en:non-vegetarian"}),
        block_allergens=_SEA_ANIMALS,
        block_categories=frozenset({C.MEAT_POULTRY, C.SEAFOOD}),
        # Not dairy_eggs: cheese can use animal rennet, yogurt can contain gelatine.
        allow_tags=frozenset({"en:vegetarian", "en:vegan"}),
        allow_categories=_PRODUCE,
    ),
    DietaryRestriction.GLUTEN_FREE: _Rule(
        block_allergens=frozenset({"en:gluten"}),
        allow_tags=frozenset({"en:no-gluten", "en:gluten-free"}),
        allow_if_allergens_recorded=True,
        allow_categories=_FRESH,
    ),
    DietaryRestriction.DAIRY_FREE: _Rule(
        block_allergens=frozenset({"en:milk"}),
        # dairy_eggs is neither blocked nor allowed: eggs aren't dairy.
        allow_tags=frozenset({"en:vegan"}),
        allow_if_allergens_recorded=True,
        allow_categories=_FRESH,
    ),
    # We can't prove something isn't halal, so these never block on missing labels.
    DietaryRestriction.HALAL: _Rule(allow_tags=frozenset({"en:halal"}), allow_categories=_PRODUCE),
    DietaryRestriction.KOSHER: _Rule(
        block_allergens=frozenset({"en:crustaceans", "en:molluscs"}),  # shellfish
        allow_tags=frozenset({"en:kosher"}),
        allow_categories=_PRODUCE,
    ),
    DietaryRestriction.CARNIVORE: _Rule(
        block_tags=frozenset({"en:vegan"}),
        block_categories=_PRODUCE | {C.BAKERY, C.GRAINS_PASTA, C.PLANT_PROTEIN},
        allow_categories=frozenset({C.MEAT_POULTRY, C.SEAFOOD, C.DAIRY_EGGS}),
    ),
}


def check_item(item: Item, profile: DietaryProfile | None) -> DietCheck:
    if profile is None:
        return DietCheck(Verdict.ALLOWED)
    facts = _facts(item)
    results: list[tuple[Verdict, str]] = []

    for value in profile.restrictions:
        restriction = DietaryRestriction(value)
        name = restriction.value.replace("_", "-")
        verdict = _RULES[restriction].decide(facts)
        results.append((verdict, f"not {name}" if verdict is Verdict.BLOCKED else f"{name}?"))

    may_contain: list[Allergen] = []
    for value in profile.allergens:
        allergen = Allergen(value)
        name = allergen.value.replace("_", " ")
        if allergen.off_tag in facts.allergens:
            results.append((Verdict.BLOCKED, f"contains {name}"))
        elif facts.allergens:
            results.append((Verdict.ALLOWED, ""))
        else:
            results.append((Verdict.UNKNOWN, f"{name}?"))
        if allergen.off_tag in facts.traces and allergen.off_tag not in facts.allergens:
            may_contain.append(allergen)

    for status in (Verdict.BLOCKED, Verdict.UNKNOWN):
        reasons = [reason for verdict, reason in results if verdict is status]
        if reasons:
            return DietCheck(status, reasons, may_contain)
    return DietCheck(Verdict.ALLOWED, [], may_contain)


def _facts(item: Item) -> _Facts:
    product = item.product if item.product is not None and item.product.found else None
    category = Category(item.category)
    if product is None:  # typed in by hand, or a barcode OFF doesn't know
        return _Facts(category, frozenset(), frozenset(), frozenset())
    return _Facts(
        category,
        tags=frozenset(product.ingredients_analysis) | frozenset(product.labels),
        allergens=frozenset(product.allergens),
        traces=frozenset(product.traces),
    )
