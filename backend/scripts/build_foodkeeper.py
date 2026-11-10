"""Convert USDA FSIS FoodKeeper data into the compact file the app loads.

Usage (from backend/):  python scripts/build_foodkeeper.py

Input:  data/foodkeeper/foodkeeper_raw.json   (downloaded by hand; see docs/data-sources.md)
Output: app/data/foodkeeper.json              (committed; loaded by app.services.spoilage)

The raw file stores every row as a list of one-key objects, e.g.
[{"ID": 1.0}, {"Name": "Butter"}, {"DOP_Refrigerate_Min": 1.0}, ...], and rows omit
empty fields. We flatten that and keep only what spoilage estimates need.
"""

import json
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
RAW_PATH = BACKEND_DIR / "data" / "foodkeeper" / "foodkeeper_raw.json"
OUT_PATH = BACKEND_DIR / "app" / "data" / "foodkeeper.json"

# Our location names -> FoodKeeper column prefixes.
LOCATIONS = {"pantry": "Pantry", "fridge": "Refrigerate", "freezer": "Freeze"}
UNITS = {
    "Hours": "hours",
    "Days": "days",
    "Weeks": "weeks",
    "Months": "months",
    "Years": "years",
    "Year": "years",  # the source has both spellings
}


def _rows(raw: dict[str, Any], sheet: str) -> list[dict[str, Any]]:
    (data,) = [s["data"] for s in raw["sheets"] if s["name"] == sheet]
    return [{key: value for cell in row for key, value in cell.items()} for row in data]


def _number(value: Any) -> float | int | None:
    if isinstance(value, int | float):
        return int(value) if float(value).is_integer() else float(value)
    return None


def _storage(product: dict[str, Any], prefix: str) -> dict[str, Any] | None:
    """Storage time for one location. "DOP_" columns count from the date of purchase;
    a food uses either those or the plain columns, so prefer DOP_ and fall back."""
    for columns in (f"DOP_{prefix}", prefix):
        metric = product.get(f"{columns}_Metric")
        if metric is None:
            continue
        if metric not in UNITS:
            # "Not Recommended", "Indefinitely", "When Ripe", "Package use-by date"
            return {"note": metric}
        low = _number(product.get(f"{columns}_Min"))
        high = _number(product.get(f"{columns}_Max"))
        if low is None and high is None:
            continue
        return {"min": low if low is not None else high, "max": high or low, "unit": UNITS[metric]}
    return None


def _keywords(product: dict[str, Any]) -> list[str]:
    candidates = [product.get("Name") or "", *(product.get("Keywords") or "").split(",")]
    seen: dict[str, None] = {}  # dict keeps insertion order, unlike set
    for keyword in candidates:
        if keyword := keyword.strip().lower():
            seen[keyword] = None
    return list(seen)


def build(raw: dict[str, Any]) -> dict[str, Any]:
    categories = {
        int(c["ID"]): " / ".join(filter(None, (c.get("Category_Name"), c.get("Subcategory_Name"))))
        for c in _rows(raw, "Category")
    }
    version = next(v for v in reversed(_rows(raw, "Version")) if v.get("Current_Version"))

    foods = []
    for product in _rows(raw, "Product"):
        storage = {ours: _storage(product, theirs) for ours, theirs in LOCATIONS.items()}
        if not any(storage.values()):
            continue  # nothing to estimate from
        foods.append(
            {
                "id": int(product["ID"]),
                "name": product["Name"].strip(),
                "subtitle": (product.get("Name_subtitle") or "").strip() or None,
                "category": categories.get(int(product.get("Category_ID") or 0)),
                "keywords": _keywords(product),
                "storage": storage,
            }
        )

    return {
        "source": "USDA FSIS FoodKeeper (public domain)",
        "version": _number(version.get("Data_Version_Number")),
        "modified": version.get("Modified_Date"),
        "foods": foods,
    }


def main() -> None:
    result = build(json.loads(RAW_PATH.read_text(encoding="utf-8")))
    foods = result.pop("foods")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # One food per line: small file, readable diffs when the data is updated.
    lines = ",\n".join("    " + json.dumps(food, ensure_ascii=False) for food in foods)
    header = json.dumps(result, ensure_ascii=False)[1:-1]
    OUT_PATH.write_text(f'{{{header}, "foods": [\n{lines}\n]}}\n', encoding="utf-8")
    print(f"Wrote {len(foods)} foods to {OUT_PATH.relative_to(BACKEND_DIR)}")


if __name__ == "__main__":
    main()
