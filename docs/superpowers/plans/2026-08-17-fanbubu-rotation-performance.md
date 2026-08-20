# Fanbubu Rotation and Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the mini program as 饭卜卜, guarantee meaningful cook/eat-out rotation, and reduce warm recommendation latency without weakening dietary safety.

**Architecture:** Keep FastAPI + CloudBase Cloud Run + callContainer. Add bounded client exclusion hints that are merged with authoritative server history, collapse the recommendation catalog to one joined query, remove the frontend's redundant today-log request, and emit stage timings. The CloudBase MySQL HTTP Repository migration remains a separately gated second milestone because its real OpenAPI and server API Key must be verified before production code is written.

**Tech Stack:** FastAPI, SQLModel, Pydantic v2, pytest, uni-app, Vue 3, Pinia, TypeScript, Vitest, CloudBase Cloud Run.

---

### Task 1: Lock brand copy and rotation API contracts

**Files:**
- Modify: `backend/app/schemas/daily.py`
- Modify: `backend/app/schemas/dining.py`
- Test: `backend/tests/test_daily_context_contract.py`
- Test: `backend/tests/test_api_v1/test_dining.py`
- Modify: `miniapp/src/types/api.ts`

- [ ] **Step 1: Write failing backend contract tests**

Add tests proving camel/snake-compatible request models accept up to 12 unique exclusion identifiers, reject oversized input, and default to empty lists:

```python
def test_recommend_request_defaults_to_no_client_exclusions() -> None:
    request = RecommendRequest()
    assert request.exclude_food_ids == []


def test_external_request_rejects_more_than_twelve_exclusion_keys() -> None:
    with pytest.raises(ValidationError):
        ExternalDiningRequest(exclude_keys=[f"rule-{index}" for index in range(13)])
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd /root/miniapp-trellis/backend
.venv/bin/pytest -q tests/test_daily_context_contract.py tests/test_api_v1/test_dining.py
```

Expected: FAIL because `exclude_food_ids` and `exclude_keys` do not exist.

- [ ] **Step 3: Add bounded normalized fields**

Implement the public contract:

```python
exclude_food_ids: list[int] = Field(default_factory=list, max_length=12)
exclude_keys: list[str] = Field(default_factory=list, max_length=12)
```

Use validators to remove duplicates while preserving order and reject non-positive food IDs or blank keys.

- [ ] **Step 4: Add matching TypeScript fields**

```ts
export interface RecommendRequest {
  // existing fields
  excludeFoodIds?: number[]
  weatherSnapshot?: WeatherData
}

export interface ExternalDiningRequest {
  // existing fields
  excludeKeys?: string[]
}
```

- [ ] **Step 5: Run focused tests and type-check**

```bash
cd /root/miniapp-trellis/backend
.venv/bin/pytest -q tests/test_daily_context_contract.py tests/test_api_v1/test_dining.py
cd /root/miniapp-trellis/miniapp
npm run type-check
```

Expected: PASS.

### Task 2: Make external dining rotate instead of replaying a fixed top three

**Files:**
- Modify: `backend/app/services/external_dining.py`
- Modify: `backend/app/schemas/dining.py`
- Test: `backend/tests/services/test_external_dining.py`
- Test: `backend/tests/test_api_v1/test_dining.py`

- [ ] **Step 1: Write failing rotation tests**

Cover adjacent batch overlap and exhausted-pool fallback:

```python
def test_external_second_batch_changes_at_least_two_items(session, user) -> None:
    first = recommend_external(session, user.id, ExternalDiningRequest())
    second = recommend_external(
        session,
        user.id,
        ExternalDiningRequest(exclude_keys=[item.key for item in first.suggestions]),
    )
    assert len({item.key for item in first.suggestions} & {item.key for item in second.suggestions}) <= 1


def test_external_safety_filters_are_not_relaxed_by_exclusions(...) -> None:
    ...
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd /root/miniapp-trellis/backend
.venv/bin/pytest -q tests/services/test_external_dining.py tests/test_api_v1/test_dining.py
```

Expected: the second response repeats all three existing suggestions.

- [ ] **Step 3: Implement a three-pass selector**

Create a pure helper with this order:

```python
def select_rotating_suggestions(
    ordered: Sequence[ExternalDiningSuggestion],
    excluded_keys: set[str],
    *,
    size: int = 3,
) -> tuple[list[ExternalDiningSuggestion], bool]:
    # pass 1: unseen keys with unique categories
    # pass 2: unseen keys regardless of category
    # pass 3: excluded keys as bounded fallback
```

Return `rotation_restarted=True` only when excluded items had to be reused. Never reintroduce a candidate removed by forbidden tags or exact avoided memory.

- [ ] **Step 4: Run tests and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 3: Merge client exclusions into cook recommendation history

**Files:**
- Modify: `backend/app/services/recommendation_ranking.py`
- Modify: `backend/app/services/recommender.py`
- Test: `backend/tests/services/test_recommendation_ranking.py`
- Test: `backend/tests/services/test_recommender.py`

- [ ] **Step 1: Write failing ranking tests**

```python
def test_client_exclusions_join_seen_today_without_changing_chosen_history() -> None:
    merged = with_client_exclusions(history, [4, 5, 5])
    assert merged.seen_today == history.seen_today | {4, 5}
    assert merged.chosen_days_ago == history.chosen_days_ago


@pytest.mark.asyncio
async def test_adjacent_cook_batches_share_at_most_one_item_when_pool_allows(...):
    first = await recommender.recommend(session, user, RecommendRequest())
    second = await recommender.recommend(
        session,
        user,
        RecommendRequest(exclude_food_ids=[item.id for item in first.foods]),
    )
    assert len({item.id for item in first.foods} & {item.id for item in second.foods}) <= 1
```

- [ ] **Step 2: Run and verify RED**

```bash
cd /root/miniapp-trellis/backend
.venv/bin/pytest -q tests/services/test_recommendation_ranking.py tests/services/test_recommender.py
```

- [ ] **Step 3: Implement immutable history merge**

```python
def with_client_exclusions(
    history: RecommendationHistory,
    food_ids: Sequence[int],
) -> RecommendationHistory:
    return replace(
        history,
        seen_today=history.seen_today | frozenset(food_ids),
    )
```

Apply it after database history construction and before meal building.

- [ ] **Step 4: Run and verify GREEN**

Run the Step 2 command. Expected: PASS, including existing hard-filter tests.

### Task 4: Persist two recent batches in Pinia and remove the redundant request

**Files:**
- Modify: `miniapp/src/stores/daily.ts`
- Modify: `miniapp/src/stores/dining.ts`
- Modify: `miniapp/src/stores/daily.test.ts`
- Modify: `miniapp/src/stores/dining.test.ts`
- Modify: `miniapp/src/pages/today/today.vue`

- [ ] **Step 1: Write failing store tests**

Tests must prove:

```ts
it('sends the previous two cook batches and does not refetch today after success', async () => {
  // seed two batches, execute a third request
  expect(recommend).toHaveBeenCalledWith(expect.objectContaining({
    excludeFoodIds: [/* six prior unique IDs */],
  }))
  expect(getTodayLog).not.toHaveBeenCalled()
})

it('sends recent external keys and caps history at six', async () => {
  // execute three external requests and inspect the third request
})
```

- [ ] **Step 2: Run and verify RED**

```bash
cd /root/miniapp-trellis/miniapp
npx vitest run src/stores/daily.test.ts src/stores/dining.test.ts
```

- [ ] **Step 3: Implement capped storage histories**

Use existing technical storage prefixes:

```ts
const RECENT_COOK_IDS_KEY = 'eat_what_recent_cook_ids_v1'
const RECENT_DINING_KEYS_KEY = 'eat_what_recent_dining_keys_v1'
const MAX_RECENT_RESULT_IDS = 6
```

Send the previous list before appending the successful response. Deduplicate while keeping newest entries and cap at six. Remove `await fetchTodayLog()` from `fetchRecommend()`.

- [ ] **Step 4: Clear cross-mode stale results**

Expose `clearMealRecommendation()` from the daily store. In `selectMode()`, clear the inactive result store after changing mode.

- [ ] **Step 5: Run and verify GREEN**

Run Vitest and `npm run type-check`. Expected: PASS.

### Task 5: Collapse the static recommendation catalog to one database query

**Files:**
- Modify: `backend/app/services/food_service.py`
- Modify: `backend/app/services/recommender.py`
- Modify: `backend/app/services/profile_service.py`
- Modify: `backend/app/services/daily_service.py`
- Test: `backend/tests/services/test_recommender.py`
- Test: `backend/tests/services/test_daily_service.py`

- [ ] **Step 1: Write failing query-budget and persistence tests**

Add a SQLAlchemy query counter around one recommendation and assert the hot path does not issue a separate food count, a duplicate profile SELECT, or recipe refresh SELECTs. Add a daily-service assertion that returned event/log IDs remain available without post-commit refresh.

- [ ] **Step 2: Run and verify RED**

```bash
cd /root/miniapp-trellis/backend
.venv/bin/pytest -q tests/services/test_recommender.py tests/services/test_daily_service.py
```

- [ ] **Step 3: Add a joined catalog query**

```python
def get_recommendation_catalog(
    session: Session,
) -> tuple[list[Food], dict[int, Recipe]]:
    rows = session.exec(
        select(Food, Recipe)
        .join(Recipe, Recipe.food_id == Food.id)
        .where(Food.recipe_ready.is_(True))
    ).all()
    foods = [food for food, _ in rows]
    recipes = {recipe.food_id: recipe for _, recipe in rows}
    return foods, recipes
```

Pass `recipes_by_food_id` into `_build_complete_meal()` instead of querying all recipes there.

- [ ] **Step 4: Remove duplicate profile read and ORM refreshes**

Add `profile_service.get_profile_record()` returning the ORM model and use it once. In `record_recommendation()`, rely on flush/commit populated identifiers and return the already populated objects without two refresh queries.

- [ ] **Step 5: Run and verify GREEN**

Run the Step 2 command and the focused API tests. Expected: PASS with a lower SELECT count.

### Task 6: Reuse a fresh weather snapshot

**Files:**
- Modify: `backend/app/schemas/daily.py`
- Modify: `backend/app/services/recommender.py`
- Modify: `miniapp/src/stores/daily.ts`
- Test: `backend/tests/services/test_recommender.py`
- Test: `miniapp/src/stores/daily.test.ts`

- [ ] **Step 1: Write failing backend and frontend tests**

Assert a supplied valid `WeatherData` snapshot prevents `weather_client.get_current()` from being called. Assert the store includes its cached weather in a recommendation request.

- [ ] **Step 2: Run and verify RED**

Run the two focused test files.

- [ ] **Step 3: Implement bounded trust**

Add `weather_snapshot: WeatherData | None` to `RecommendRequest`. `_resolve_weather()` uses it only when its `fetched_at` is no more than two hours old; otherwise it follows the current coordinates/timeout/fallback path. This is a soft ±3 point input and cannot bypass hard dietary filters.

- [ ] **Step 4: Run and verify GREEN**

Run backend and frontend focused tests. Expected: PASS.

### Task 7: Add safe timing observability

**Files:**
- Create: `backend/app/core/timing.py`
- Modify: `backend/app/api/v1/daily.py`
- Modify: `backend/app/services/recommender.py`
- Test: `backend/tests/test_api_v1/test_daily.py`

- [ ] **Step 1: Write a failing response-header test**

```python
def test_recommend_exposes_safe_server_timing(client, auth_headers) -> None:
    response = client.post('/api/v1/daily/recommend', headers=auth_headers, json={})
    assert response.status_code == 200
    assert 'total;dur=' in response.headers['Server-Timing']
    assert 'profile;dur=' in response.headers['Server-Timing']
    assert 'database_url' not in response.headers['Server-Timing'].lower()
```

- [ ] **Step 2: Run and verify RED**

Run the focused daily API test. Expected: missing header.

- [ ] **Step 3: Implement a monotonic timing collector**

`TimingTrace` records only whitelisted stage names and millisecond durations, emits a standards-compatible header, and supplies the same numeric fields to the existing structured `recommend_ok` log. Never include coordinates, JWT, database URL, profile values, or API keys.

- [ ] **Step 4: Run and verify GREEN**

Run the focused daily API test. Expected: PASS.

### Task 8: Apply the 饭卜卜 brand without changing technical identifiers

**Files:**
- Modify: `miniapp/src/manifest.json`
- Modify: `miniapp/src/pages.json`
- Modify: `miniapp/src/pages/auth/auth.vue`
- Modify: `miniapp/src/pages/today/today.vue`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_main.py`

- [ ] **Step 1: Add a failing backend metadata assertion**

```python
def test_openapi_uses_fanbubu_product_name() -> None:
    assert app.title == '饭卜卜 API'
```

- [ ] **Step 2: Run and verify RED**

Run `pytest -q tests/test_main.py`. Expected: old title.

- [ ] **Step 3: Replace only user-visible copy**

Use:

```text
饭卜卜
今天吃啥嘞
Eat-What，卜一卜 → 补一补
```

Do not rename AppID, CloudRun service, API paths, imports, package names or local-storage keys.

- [ ] **Step 4: Run metadata test and frontend build checks**

Expected: backend test, JSON parsing, type-check and build pass.

### Task 9: Full local verification and deployment artifact

**Files:**
- Modify: `docs/guides/cloudbase-cloudrun-deploy.md`
- Create: `backend-cloudbase-20260817-v3.zip`

- [ ] **Step 1: Run backend quality gates**

```bash
cd /root/miniapp-trellis/backend
.venv/bin/ruff check app tests
.venv/bin/mypy app
.venv/bin/pytest -q
```

- [ ] **Step 2: Run miniapp quality gates**

```bash
cd /root/miniapp-trellis/miniapp
npm run lint
npm run type-check
npx vitest run
npm run build:h5
npm run build:mp-weixin
```

- [ ] **Step 3: Build and inspect the CloudBase package**

Package the `backend/` build context with Dockerfile at archive root. Verify the archive includes `app/`, `alembic/`, `data/`, `scripts/`, `pyproject.toml`, `README.md`, and excludes `.env`, `.venv`, caches and local databases.

- [ ] **Step 4: Document cloud acceptance**

Record how to deploy v3, observe `Server-Timing` and request IDs, run four adjacent recommendation checks, and compare warm versus cold requests. Explicitly state that public MySQL remains temporary until the separately gated HTTP Repository milestone is cloud-verified.

### Task 10: Gate the CloudBase HTTP Repository milestone

**Files:**
- Create after live verification: `docs/superpowers/plans/2026-08-17-cloudbase-http-repository.md`

- [ ] **Step 1: Obtain real prerequisites without exposing secrets**

Create a server API Key in CloudBase and store it only as `CLOUDBASE_DB_API_KEY` in CloudRun. Retrieve the official `mysqldb` OpenAPI through CloudBase tooling and verify one authenticated read against a non-sensitive table.

- [ ] **Step 2: Verify required semantics before implementation**

Confirm exact filter encoding, upsert conflict keys, response headers, error envelope, rate limits and whether a supported transaction/RPC endpoint exists. If transaction/RPC is absent, retain the design's idempotent event-first write model.

- [ ] **Step 3: Write the separate migration plan**

The plan must cover every current SQLAlchemy-backed module, shadow reads, per-user scoping tests, migration execution, rollback, and the final closure of public MySQL. No runtime code is written before Steps 1-2 produce cloud evidence.

## Execution note

The canonical worktree already contains substantial uncommitted user-owned changes from earlier milestones. Implementation must use the current `/root/miniapp-trellis` worktree, patch only named files, and avoid commits/staging until the user explicitly asks to package or publish the combined dirty state.
