# Data sources

## USDA FSIS FoodKeeper

Storage times for ~650 foods in the pantry, fridge and freezer. Used for spoilage
estimates (`backend/app/services/spoilage.py`). Rules only: no LLM, no network calls.

- **Publisher:** USDA Food Safety and Inspection Service (FSIS)
- **Where:** FSIS "FoodKeeper Data" page
  (https://www.fsis.usda.gov/science-data/data-sets-visualizations/foodkeeper-data),
  also listed on catalog.data.gov. The site blocks scripted downloads, so get the
  JSON in a browser.
- **Licence:** US federal government work, so public domain in the US.
- **Version in repo:** data version 128, modified 2018-09-06 (as recorded in the file).
- **Downloaded:** 2026-11-10

### Files

| File | What | Committed |
|---|---|---|
| `backend/data/foodkeeper/foodkeeper_raw.json` | The download, unmodified (~617 KB) | Yes, so the build can be redone if the source moves |
| `backend/scripts/build_foodkeeper.py` | Converts raw -> compact | Yes |
| `backend/app/data/foodkeeper.json` | What the app loads (~190 KB, one food per line) | Yes |

Both JSON files are committed on purpose (small, static, public domain), as an
exception to the "no large data files" rule.

### Updating

1. Download the new JSON and replace `foodkeeper_raw.json`.
2. From `backend/`: `python scripts/build_foodkeeper.py`
3. Run `pytest`. `test_spoilage.py` checks some well-known foods against the real file.

### Known quirks

- Each food has times counted either from the **date of purchase** (`DOP_*` columns)
  or generically (plain columns), almost never both. The build prefers `DOP_*`.
- Some "times" are notes instead: `Not Recommended`, `Indefinitely`, `When Ripe`,
  `Package use-by date`. These give no estimated date.
- Keywords are noisy: single words like "jar", "breakfast" or "whole" appear as
  keywords. The matcher ignores a list of such generic words on their own.
