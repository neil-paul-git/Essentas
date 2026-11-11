"""Map external category names onto our own short list (app.models.item.Category)."""

from collections.abc import Sequence

from app.models.item import Category

# Every category string in app/data/foodkeeper.json. test_categories.py checks none
# are missing, so a FoodKeeper data update can't silently drop foods into "other".
_FOODKEEPER = {
    "Baked Goods / Bakery": Category.BAKERY,
    "Baked Goods / Baking and Cooking": Category.PANTRY_BAKING,
    "Baked Goods / Refrigerated Dough": Category.BAKERY,
    "Beverages": Category.DRINKS,
    "Condiments, Sauces & Canned Goods": Category.CONDIMENTS_CANNED,
    "Dairy Products & Eggs": Category.DAIRY_EGGS,
    "Deli & Prepared Foods": Category.PREPARED,
    "Food Purchased Frozen": Category.FROZEN,
    "Grains, Beans & Pasta": Category.GRAINS_PASTA,
    "Meat / Fresh": Category.MEAT_POULTRY,
    "Meat / Shelf Stable Foods": Category.PANTRY_BAKING,
    "Meat / Smoked or Processed": Category.MEAT_POULTRY,
    "Meat / Stuffed or Assembled": Category.MEAT_POULTRY,
    "Poultry / Cooked or Processed": Category.MEAT_POULTRY,
    "Poultry / Fresh": Category.MEAT_POULTRY,
    "Poultry / Shelf Stable Foods": Category.PANTRY_BAKING,
    "Poultry / Stuffed or Assembled": Category.MEAT_POULTRY,
    "Produce / Fresh Fruits": Category.FRUIT,
    "Produce / Fresh Vegetables": Category.VEGETABLES,
    "Seafood / Fresh": Category.SEAFOOD,
    "Seafood / Shellfish": Category.SEAFOOD,
    "Seafood / Smoked": Category.SEAFOOD,
    "Shelf Stable Foods": Category.PANTRY_BAKING,
    "Vegetarian Proteins": Category.PLANT_PROTEIN,
}


def from_foodkeeper(category: str | None) -> Category:
    return _FOODKEEPER.get(category, Category.OTHER) if category else Category.OTHER


# Broad Open Food Facts category tags, for products FoodKeeper has no food for (crisps,
# sweets, fizzy drinks...). Only a fallback, so it covers the common groups, not every tag.
_OFF_TAGS = {
    "en:dairies": Category.DAIRY_EGGS,
    "en:cheeses": Category.DAIRY_EGGS,
    "en:yogurts": Category.DAIRY_EGGS,
    "en:eggs": Category.DAIRY_EGGS,
    "en:meats": Category.MEAT_POULTRY,
    "en:poultries": Category.MEAT_POULTRY,
    "en:seafood": Category.SEAFOOD,
    "en:fishes": Category.SEAFOOD,
    "en:fruits": Category.FRUIT,
    "en:vegetables": Category.VEGETABLES,
    "en:breads": Category.BAKERY,
    "en:pastries": Category.BAKERY,
    "en:pastas": Category.GRAINS_PASTA,
    "en:rices": Category.GRAINS_PASTA,
    "en:legumes": Category.GRAINS_PASTA,
    "en:breakfast-cereals": Category.GRAINS_PASTA,
    "en:meat-alternatives": Category.PLANT_PROTEIN,
    "en:condiments": Category.CONDIMENTS_CANNED,
    "en:sauces": Category.CONDIMENTS_CANNED,
    "en:canned-foods": Category.CONDIMENTS_CANNED,
    "en:beverages": Category.DRINKS,
    "en:meals": Category.PREPARED,
    "en:frozen-foods": Category.FROZEN,
    "en:snacks": Category.SNACKS,
    "en:confectioneries": Category.SNACKS,
    "en:chocolates": Category.SNACKS,
    "en:biscuits-and-cakes": Category.SNACKS,
    "en:flours": Category.PANTRY_BAKING,
    "en:sugars": Category.PANTRY_BAKING,
}


def from_off_tags(tags: Sequence[str]) -> Category:
    """OFF lists tags general -> specific ("en:snacks", "en:sweet-snacks", ...), so check
    the most specific first."""
    for tag in reversed(tags):
        if (category := _OFF_TAGS.get(tag)) is not None:
            return category
    return Category.OTHER
