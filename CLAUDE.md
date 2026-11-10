# CLAUDE.md — Essentas

Solo portfolio project by Neil Paul. Licensed PolyForm Noncommercial 1.0.0.
Keep this file short. Long design notes go in `docs/` and get linked from here.

## What the app does
Essentas reduces home food waste. Users log what's in their fridge, freezer and pantry,
see when items are likely to spoil, and get recipes built from what they already have.

**MVP features (build in this order):**
1. Accounts and auth
2. Inventory CRUD: item, location (fridge/freezer/pantry), quantity, added date, expiry date
3. Barcode scan → product lookup (Open Food Facts, cached in our DB)
4. Spoilage estimate from the USDA FoodKeeper table (rules, not the LLM)
5. "Use it soon" list, sorted by expiry
6. LLM recipe suggestions from current inventory
7. Photo upload → LLM vision identifies items or reads expiry dates/receipts

**Not in scope for now:** remote push notifications, payments, social features, web app,
on-device ML, anything needing a paid Apple Developer account or a custom native build.

Frontend product decisions (expiry labels, disclaimer, inventory page, "+" button):
[docs/frontend-notes.md](docs/frontend-notes.md).

## Stack
- **Mobile:** Expo (React Native, TypeScript), Expo Router. **Expo Go compatible only.**
  Do not add libraries that need a development build or custom native code.
  Barcode scanning uses `expo-camera`.
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLModel/SQLAlchemy, Alembic migrations.
- **Database/Auth:** PostgreSQL on Supabase (free tier) + Supabase Auth. FastAPI verifies the JWT.
- **External services:** Open Food Facts (primary), USDA FoodData Central (fallback),
  LLM = Claude Haiku 5.5 (`claude-haiku-5-5`), no extended thinking, structured JSON output.
- **Hosting (later):** Cloud Run or Render free tier.
- **Dev machine:** Windows. Give commands that work in PowerShell.

## Architecture rules
- The mobile app talks **only** to our REST API. It never calls Open Food Facts or the LLM directly,
  and no API keys ever ship in the app.
- REST, JSON, versioned under `/api/v1`. Plural nouns (`/items`, `/products/{barcode}`).
  Pydantic schemas for every request and response.
- Each external service sits behind an interface in `backend/app/providers/`
  (e.g. `FoodDataProvider`, `LLMProvider`). Routes depend on the interface, not the vendor,
  so providers can be swapped by config.
- **Open Food Facts:** limit is 15 product reads/min per IP. Always check our `products` table
  first, cache every result, and send `User-Agent: Essentas/<version> (<contact>)`.
- **LLM cost control:** short prompts, cap `max_tokens`, per-user rate limit,
  log token usage per request. Never send more than the needed inventory fields.
- Layers: `api/` (routes) → `services/` (logic) → `repositories/` or models (DB). Keep routes thin.
- Config and secrets come from environment variables via a settings class. `.env` is gitignored;
  keep `.env.example` up to date.

## Planned layout
```
backend/   FastAPI app (app/api, app/services, app/providers, app/models, tests/)
mobile/    Expo app
docs/      design notes, API notes, decisions
```

## Commands
Fill these in as they are set up. Don't invent commands that don't exist yet.
Backend commands run from `backend/` with the venv active.
- Backend setup: `python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -e ".[dev]"`
- Backend dev server: `uvicorn app.main:app --reload`
- Backend tests: `pytest`
- Lint/format: `ruff check .` / `ruff format .`
- Apply migrations: `alembic upgrade head` (targets `DATABASE_URL`, i.e. Supabase)
- New migration: `alembic revision --autogenerate -m "add items table"` (review the file before applying)
- Rebuild FoodKeeper data: `python scripts/build_foodkeeper.py` (see [docs/data-sources.md](docs/data-sources.md))
- Mobile: `npx expo start`

## How to work with me (important)
I'm new to Claude Code and want **small, reviewable steps**.
- **One task per session.** A task is one endpoint, one model plus migration, one screen, or one provider.
  If a request is bigger, propose a split and do only the first part.
- **Plan first** for anything touching more than 2–3 files. Show the plan and wait for my OK.
- **Keep diffs small:** aim for under ~200 changed lines per commit, not counting lockfiles
  or generated migrations. Stop and check in rather than exceed that.
- **Commits:** one logical change each, Conventional Commits style
  (`feat(backend): add item CRUD endpoints`). Don't commit until I approve. Never push
  unless I ask. Never commit `.env`, keys, or large data files.
- **Ask before** adding a dependency, changing the stack, changing the DB schema,
  or deleting files.
- **Tests:** add or update pytest tests with each backend change. Mock every external API
  (Open Food Facts, USDA, LLM). **Tests must never make paid LLM calls.**
- **Explain briefly** what you changed and why at the end of each task. I need to be able to
  explain this code in interviews. Point out anything non-obvious.
- When done, suggest the next small task, but don't start it.
- Do not append co-author attibutions or AI generated code disclosures.

## Keeping context and token use low
- Don't read or search `node_modules/`, `.venv/`, lockfiles, build output, or data dumps.
- Read only the files the task needs. Don't scan the whole repo to "get familiar".
- Don't paste large files or full command output back to me; summarize.
- Don't run long-running or networked commands (servers, installs, real API calls) without asking.

## Status
- [x] Repo, README, license
- [x] Backend skeleton: settings, health check, DB connection, first migration
- [x] Backend auth: Supabase JWT verification (`get_current_user`, `GET /me`)
- [x] Inventory models + CRUD
- [x] Barcode lookup with product cache (Open Food Facts; USDA fallback still to do)
- [x] Spoilage estimates (FoodKeeper): estimate endpoint, auto-fill + re-estimate on items, "use it soon" via `GET /items?expires_by=&sort=expiring`
- [ ] Expo app skeleton + auth
- [ ] Recipe suggestions (LLM)
- [ ] Photo recognition (LLM vision)

Update this checklist when a milestone is done.
