# Meal Modes and CloudBase MySQL Delivery Plan

> Canonical repository: `/root/miniapp-trellis`. Execute with TDD and do not stage user-owned WeChat project files.

**Goal:** Make the existing FastAPI + CloudBase stack genuinely MySQL-ready, then add a backward-compatible first vertical slice for cook/eat-out and personal/family decisions with private shop+dish memories.

**Architecture:** Keep the current cook recommendation path intact. Add explicit request context (`dining_mode`, `audience`, `party_size`) and a separate external dining response instead of pretending restaurants are recipes. Store user dining memories in their own table and apply exact shop+dish avoid rules before external candidates are returned.

**Tech Stack:** FastAPI, SQLModel, Alembic, PyMySQL, pytest, uni-app, Vue 3, Pinia, TypeScript, Vitest, CloudBase Cloud Run/MySQL.

---

## Task 1: Make the schema compile and fail closed for production MySQL

**Files:**
- Modify: `backend/app/models/food.py`
- Modify: `backend/alembic/versions/20260812_01_cloudbase_foundation.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_config.py`
- Test: `backend/tests/test_mysql_migrations.py`

- [x] Add a failing MySQL-dialect migration compile test proving every revision emits valid MySQL DDL.
- [x] Add failing production settings tests for SQLite fallback, debug mode, code2session, and unsupported JWT algorithms.
- [x] Replace unbounded `VARCHAR` description with `Text` in model and foundation migration.
- [x] Add production validation requiring `mysql+pymysql://`, `DEBUG=false`, `ENABLE_CODE2SESSION=false`, and `HS256`.
- [x] Add conservative MySQL pool and connect timeout options.
- [x] Run focused tests, then the full backend suite.

## Task 2: Separate deploy-time migration/seed from app startup

**Files:**
- Modify: `backend/Dockerfile`
- Create: `backend/scripts/release.sh`
- Modify: `backend/scripts/container_health_smoke.sh`
- Modify: `backend/.env.example`
- Modify: `docs/guides/cloudbase-cloudrun-deploy.md`
- Modify: `.trellis/spec/backend/database-guidelines.md`

- [x] Make the application container start only Uvicorn.
- [x] Provide an explicit idempotent release command for Alembic + seed.
- [x] Document CloudBase private network/VPC, least-privilege account, internal DSN, URL-encoded password, and closing external DB access.
- [x] Make the SQLite container smoke explicitly use a dev/test environment; document a separate real-MySQL smoke command.
- [x] Verify Dockerfile structure, shell syntax, and backend tests.

## Task 3: Define backward-compatible decision context

**Files:**
- Modify: `backend/app/schemas/daily.py`
- Modify: `backend/app/models/daily_log.py`
- Modify: `backend/app/models/recommendation_event.py`
- Create: `backend/alembic/versions/20260817_04_decision_context.py`
- Modify: `backend/app/services/daily_service.py`
- Modify: `backend/app/services/recommender.py`
- Test: `backend/tests/test_api_v1/test_daily.py`
- Test: `backend/tests/services/test_daily_service.py`

- [x] Add failing contract tests for defaults: `cook`, `personal`, party size 1.
- [x] Add validation: personal forces 1; family accepts 2-8.
- [x] Persist mode/audience/party size in recommendation event and daily snapshots.
- [x] Preserve old clients and existing cook response.

## Task 4: Add private shop+dish memories

**Files:**
- Create: `backend/app/models/dining_memory.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/dining.py`
- Create: `backend/app/services/dining_memory_service.py`
- Create: `backend/app/api/v1/dining.py`
- Modify: `backend/app/api/v1/__init__.py`
- Create: `backend/alembic/versions/20260817_05_dining_memories.py`
- Test: `backend/tests/test_api_v1/test_dining.py`

- [x] Test idempotent upsert and user isolation first.
- [x] Model exact normalized `shop_name + dish_name` identity; verdict is `liked | neutral | avoided`; note is optional and private.
- [x] Avoid only the exact pair. Do not block the whole shop or the dish globally.
- [x] Add list/upsert/delete APIs with stable pagination and validation.

## Task 5: Add deterministic external dining recommendations

**Files:**
- Create: `backend/app/services/external_dining.py`
- Extend: `backend/app/schemas/dining.py`
- Extend: `backend/app/api/v1/dining.py`
- Test: `backend/tests/services/test_external_dining.py`
- Test: `backend/tests/test_api_v1/test_dining.py`

- [x] Test that external results contain a dish/category, search keywords, order tips, estimated energy range, and seasonal/nutrition explanation.
- [x] Test that exact avoided pairs never return and liked memories can be recalled without dominating diversity.
- [x] Keep location optional and never persist coordinates.
- [x] Return deterministic rule-based suggestions; no LLM, merchant API, price promise, or ordering integration.

## Task 6: Rebalance the recommendation explanation model

**Files:**
- Modify: `backend/app/services/recommendation_ranking.py`
- Modify: `backend/app/services/recommender.py`
- Test: `backend/tests/services/test_recommendation_ranking.py`
- Test: `backend/tests/services/test_recommender.py`

- [x] Add failing exact-weight tests for nutrition 22, seasonal wellness 18, personal/family 20, preference/history 15, feasibility 15, diversity 10.
- [x] Make weather a bounded modifier inside seasonal wellness, with absolute impact no greater than 3 points.
- [x] Keep allergies/forbidden tags as hard filters and keep all wellness copy non-medical.
- [x] Expose an explanation breakdown suitable for the miniapp without leaking raw health data.

## Task 7: Add mode controls and external result UI

**Files:**
- Modify: `miniapp/src/types/api.ts`
- Modify: `miniapp/src/api/daily.ts`
- Create: `miniapp/src/api/dining.ts`
- Modify: `miniapp/src/stores/daily.ts`
- Create: `miniapp/src/stores/dining.ts`
- Modify: `miniapp/src/pages/today/today.vue`
- Create: `miniapp/src/components/ExternalDiningCard.vue`
- Test: focused Vitest files beside store/domain modules.

- [x] Test persisted `cook/eatOut`, `personal/family`, and party size; invalidate v1 cache on context changes.
- [x] Show segmented controls before mood/activity; show party-size picker only for family.
- [x] Cook continues to render `MealPlateCard`; eat-out renders dish/category, energy estimate, keywords, tips, and a memory action.
- [x] A location denial must not block either mode.

## Task 8: Add dining-memory UI and complete verification

**Files:**
- Modify: `miniapp/src/pages/mine/mine.vue`
- Create: `miniapp/src/pages/dining-memory/dining-memory.vue`
- Modify: `miniapp/src/pages.json`
- Add focused Vitest tests.

- [x] Support private note editing and `liked/neutral/avoided` for exact shop+dish pairs.
- [x] Make avoided styling explicit; never present it as a favorite.
- [x] Run backend Ruff, mypy, pytest, Alembic SQLite and MySQL compile checks.
- [x] Run frontend lint, type-check, Vitest, H5 build, and mp-weixin build.
- [x] Produce WeChat DevTools verification steps; do not claim cloud verification until the user deploys the new image and MySQL.
