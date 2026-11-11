# Frontend notes

Product decisions for the Expo app, recorded before the app exists so the backend can
support them. Not a spec: details can change when the screens are built.

## Expiry labels

The app works these out from the phone's local date and the item's dates. The backend
stores no "expired" flag. `expires_on` is the early end of an estimate and
`expires_on_latest` is the late end; confirmed dates have no late end.

| Label | When | Look |
|---|---|---|
| Expired | Confirmed date before today, or an estimate's late end before today | Red "danger" |
| Use it soon | Expires today or tomorrow, **or** an estimate is between its early and late end | Orange / light red "caution" |
| Fine | Anything else | No warning |

An estimate is a guess, so an item stays "use it soon" while it sits inside the
estimated range, and is only called expired once the whole range has passed.

## Disclaimer

Small print on the inventory page footer and/or in Settings / About: estimates are rough,
food can spoil early (storage, moisture, appliance faults, a bad batch), so inspect food
and use your own judgement before eating it. The app helps people waste less; it
should never push anyone to eat food that has gone off.

## Inventory page

- Search bar, separate from the sort/filter control: `GET /api/v1/items?q=…`
- Sort/filter control: `sort`, `location`, `expires_by` (combine freely, like a shop's
  product filters). "Use it soon" = `expires_by=<local tomorrow>&sort=expiring`,
  which already includes expired items.
- Grid and list layouts (frontend only).
- Categories: `?category=dairy_eggs`, repeatable for several. Either an option in the
  sort/filter control, or a category mode (icon grid of the 15 values in
  `app.models.item.Category`, tap one to list its items). Users can change an item's
  category with PATCH.

## Adding items (far future)

A single "+" button offering: barcode scan, search, photo, receipt scan.

- Barcode: done on the backend (`GET /api/v1/products/{barcode}`).
- Search: Open Food Facts has a text search API, but it has a stricter rate limit than
  barcode reads, so it would need debouncing and caching. Check the current limits
  before building it.
- Photo and receipt: the LLM vision feature (MVP item 7). `expo-camera` and
  `expo-image-picker` both work in Expo Go.
