"""Map external category names onto our own short list (app.models.item.Category)."""

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
