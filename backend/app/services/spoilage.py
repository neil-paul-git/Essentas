"""Spoilage estimates from USDA FoodKeeper storage times. Rules only, no LLM.

Matching is keyword-based: normalise the item's name (and, if it has one, its product's
name and categories) into words, then find FoodKeeper keywords that appear in them.
"""

import json
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from importlib.resources import files
from typing import Any

from sqlmodel import Session

from app.models.item import Location
from app.repositories import products as products_repo

# Words that appear as FoodKeeper keywords but don't identify a food on their own.
_GENERIC_WORDS = frozenset(
    "whole fresh dried dry raw cooked canned frozen homemade commercial commercially "
    "opened unopened prepared plain flavored store bought package packaged mix mixes "
    "refrigerated leftover leftovers other such as etc and or with without of in "
    # packaging, preparation and meal words: FoodKeeper lists e.g. "jar" for chopped
    # garlic and "breakfast" for frozen entrees, which would hijack "Mystery jar"
    "jar bottle bottled can box bag bagged tub chopped sliced diced "
    "breakfast lunch dinner meal".split()
)
_DAYS_PER_UNIT = {"hours": 1 / 24, "days": 1, "weeks": 7, "months": 30, "years": 365}


@dataclass(frozen=True)
class StorageInfo:
    """How long a food keeps in one location: a range, or a note such as "Not Recommended"."""

    min: float | None = None
    max: float | None = None
    unit: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class Food:
    id: int
    name: str
    subtitle: str | None
    category: str | None
    keywords: tuple[tuple[str, ...], ...]  # each keyword phrase as normalised words
    name_words: frozenset[str]
    storage: dict[Location, StorageInfo | None]


@dataclass(frozen=True)
class SpoilageEstimate:
    food: Food
    location: Location
    storage: StorageInfo | None
    expires_on: date | None
    matched_text: str


# --- Text normalisation -------------------------------------------------------------


def _singular(word: str) -> str:
    """Rough English singular. It only needs to be consistent: both the query and the
    keywords go through it, so "hummus" -> "hummu" still matches itself."""
    if len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("oes", "ches", "shes", "sses", "xes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def words(text: str) -> tuple[str, ...]:
    """'Semi-skimmed MILKS, 1L' -> ('semi', 'skimmed', 'milk', '1l')"""
    return tuple(_singular(w) for w in re.findall(r"[a-z0-9]+", text.lower()))


def _contains(haystack: tuple[str, ...], phrase: tuple[str, ...]) -> bool:
    n = len(phrase)
    return any(haystack[i : i + n] == phrase for i in range(len(haystack) - n + 1))


# --- Loading the data ---------------------------------------------------------------


def _parse_food(raw: dict[str, Any]) -> Food:
    phrases = {words(k) for k in raw["keywords"]}
    meaningful = tuple(
        sorted(p for p in phrases if p and not (len(p) == 1 and p[0] in _GENERIC_WORDS))
    )
    storage = {
        Location(location): StorageInfo(**info) if info else None
        for location, info in raw["storage"].items()
    }
    return Food(
        id=raw["id"],
        name=raw["name"],
        subtitle=raw["subtitle"],
        category=raw["category"],
        keywords=meaningful,
        name_words=frozenset(words(raw["name"])) - _GENERIC_WORDS,
        storage=storage,
    )


@lru_cache
def load_foods() -> tuple[Food, ...]:
    """Parse app/data/foodkeeper.json once per process (~650 foods, a few ms)."""
    raw = json.loads((files("app") / "data" / "foodkeeper.json").read_text(encoding="utf-8"))
    return tuple(_parse_food(food) for food in raw["foods"])


# --- Matching and estimating --------------------------------------------------------


def _score(food: Food, query: tuple[str, ...], location: Location) -> tuple | None:
    matched = [p for p in food.keywords if _contains(query, p)]
    if not matched:
        return None
    return (
        max(len(p) for p in matched),  # longest phrase wins: "cream cheese" > "cheese"
        -len(food.name_words - set(query)),  # fewer unexplained words: Butter > Peanut butter
        food.storage.get(location) is not None,  # prefer foods we can actually estimate
        sum(len(p) for p in matched),
        -food.id,  # deterministic final tie-break
    )


def match_food(
    texts: Iterable[str], location: Location, foods: Sequence[Food] | None = None
) -> tuple[Food, str] | None:
    """Best FoodKeeper food for the first text that matches anything, else None.
    Texts are tried in order of trust: the user's name first, then product data."""
    foods = load_foods() if foods is None else foods
    for text in texts:
        query = words(text)
        scored = [(s, f) for f in foods if (s := _score(f, query, location)) is not None]
        if scored:
            return max(scored, key=lambda pair: pair[0])[1], text
    return None


def expiry_from(added_on: date, storage: StorageInfo | None) -> date | None:
    """Conservative: the low end of the range. Months/years are approximated as 30/365
    days, which is plenty precise for "roughly when will this go off"."""
    if storage is None or storage.min is None or storage.unit not in _DAYS_PER_UNIT:
        return None
    return added_on + timedelta(days=math.floor(storage.min * _DAYS_PER_UNIT[storage.unit]))


def estimate(
    texts: Sequence[str],
    location: Location,
    added_on: date,
    foods: Sequence[Food] | None = None,
) -> SpoilageEstimate | None:
    match = match_food(texts, location, foods)
    if match is None:
        return None
    food, matched_text = match
    storage = food.storage.get(location)
    return SpoilageEstimate(
        food=food,
        location=location,
        storage=storage,
        expires_on=expiry_from(added_on, storage),
        matched_text=matched_text,
    )


def estimate_for(
    session: Session,
    name: str,
    location: Location,
    added_on: date,
    barcode: str | None = None,
) -> SpoilageEstimate | None:
    """Estimate from an item's name, falling back to its cached product's name and
    categories. Only reads our products table: never calls Open Food Facts."""
    texts = [name]
    product = products_repo.get(session, barcode) if barcode else None
    if product is not None and product.found:
        if product.name:
            texts.append(product.name)
        # OFF tags run general -> specific ("en:dairies", ..., "en:semi-skimmed-milks"),
        # so try the most specific first.
        texts.extend(tag.split(":", 1)[-1] for tag in reversed(product.categories))
    return estimate(texts, location, added_on)
