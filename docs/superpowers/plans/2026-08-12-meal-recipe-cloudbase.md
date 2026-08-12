# Meal Recipe CloudBase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Deliver an end-to-end WeChat miniapp that logs in through CloudBase, recommends one three-slot meal with safe substitutions, exposes 60 lightweight recipes with per-serving estimated nutrition, and persists choices, favorites, and history in CloudBase MySQL.

**Architecture:** Keep FastAPI and the current rule engine, add a transport boundary so H5 uses HTTP while mp-weixin uses wx.cloud.callContainer, then extend the SQLModel domain with Recipe and immutable meal snapshots. Build meals only from the 60 validated recipe-ready foods and deploy the same application to CloudBase Cloud Run with Alembic-managed MySQL.

**Tech Stack:** Python 3.10, FastAPI, SQLModel, Alembic, SQLite, CloudBase MySQL, pytest, Docker, uni-app, Vue 3, Pinia, TypeScript, Vitest, wx.cloud.callContainer

---

## Execution constraints

- Canonical repository: /root/miniapp-trellis
- Branch: feat/recommendation-diversity
- Do not edit C:\Users\Estevan\Documents\devlop\Eat-What.
- Do not edit miniapp/dist directly.
- Preserve the pre-existing dirty worktree.
- Never stage project.config.json, project.private.config.json, backend/.env, secrets, or build output.
- Every behavior change uses red, green, refactor.
- Each commit stages only the files named in that task.
- The AppSecret previously pasted into chat is compromised and must be rotated before code2session is enabled.

## Recorded baseline

- [x] Backend:

~~~bash
cd /root/miniapp-trellis/backend
.venv/bin/pytest -q
~~~

Observed: 237 passed; one pre-existing short-test-key warning.

- [x] Frontend:

~~~bash
cd /root/miniapp-trellis/miniapp
npm test -- --run
npm run type-check
npm run lint:check
~~~

Observed: 9 tests passed, type-check passed, one pre-existing no-console warning in src/App.vue.

## File map

- Runtime/auth: backend/app/core/config.py, backend/app/core/cloud_context.py, backend/app/api/v1/auth.py, backend/app/main.py.
- Transports: miniapp/src/api/transport.ts, http-transport.ts, cloud-transport.ts, response.ts, request.ts.
- Persistence: backend/app/db.py, backend/alembic, backend/Dockerfile.
- Recipe domain: backend/app/models/recipe.py, backend/data/recipe_seed.json, recipe seed/service/validator.
- Meal domain: backend/app/schemas/meal.py, backend/app/services/meal_builder.py, recommender.py, daily_service.py.
- Miniapp product: meal types/store/domain, plate components, today, recipe, favorite, and history pages.
- Delivery: CloudBase deployment, WSL DevTools, and acceptance guides.

---

### Task 1: CloudBase settings and trusted-header login

**Files:**
- Modify: backend/app/core/config.py
- Create: backend/app/core/cloud_context.py
- Modify: backend/app/api/v1/auth.py
- Create: backend/tests/test_config.py
- Create: backend/tests/test_api_v1/test_cloud_login.py
- Modify: backend/tests/conftest.py

- [ ] **Step 1: Write failing settings tests**

~~~python
from app.core.config import Settings


def test_cloud_mode_does_not_require_wx_secret():
    settings = Settings(
        environment="production",
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=False,
        wx_secret="",
    )
    assert settings.validate_required() == []


def test_code2session_requires_secret():
    settings = Settings(
        jwt_secret="x" * 32,
        wx_appid="wx-test",
        cloudbase_env_id="cloud-test",
        enable_code2session=True,
        wx_secret="",
    )
    assert "WX_SECRET" in settings.validate_required()
~~~

- [ ] **Step 2: Verify red**

~~~bash
cd /root/miniapp-trellis/backend
.venv/bin/pytest tests/test_config.py -q
~~~

Expected: FAIL because the CloudBase settings are not defined.

- [ ] **Step 3: Implement settings**

Add:

~~~python
cloudbase_env_id: str = ""
enable_code2session: bool = False
port: int = 8080
~~~

validate_required requires a 32-character JWT secret, WX_APPID, and CLOUDBASE_ENV_ID. WX_SECRET is required only when enable_code2session is true.

- [ ] **Step 4: Write failing login tests**

~~~python
def _headers(**overrides: str) -> dict[str, str]:
    values = {
        "X-WX-OPENID": "openid-cloud-user",
        "X-WX-APPID": "wx-test",
        "X-WX-ENV": "cloud-test",
        "X-WX-REQUEST-ID": "request-123",
    }
    values.update(overrides)
    return values


def test_cloud_login_creates_and_reuses_user(client):
    first = client.post("/api/v1/auth/cloud-login", headers=_headers())
    second = client.post("/api/v1/auth/cloud-login", headers=_headers())
    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]


def test_cloud_login_rejects_invalid_identity(client):
    missing = _headers()
    missing.pop("X-WX-OPENID")
    assert client.post("/api/v1/auth/cloud-login", headers=missing).status_code == 401
    assert client.post(
        "/api/v1/auth/cloud-login",
        headers=_headers(**{"X-WX-APPID": "wrong"}),
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/cloud-login",
        headers=_headers(**{"X-WX-ENV": "wrong"}),
    ).status_code == 401


def test_wx_login_is_disabled_by_default(client):
    response = client.post("/api/v1/auth/wx-login", json={"code": "code"})
    assert response.status_code == 404
    assert response.json()["code"] == "CODE2SESSION_DISABLED"
~~~

- [ ] **Step 5: Verify red**

~~~bash
.venv/bin/pytest tests/test_api_v1/test_cloud_login.py -q
~~~

Expected: FAIL because cloud-login does not exist.

- [ ] **Step 6: Implement identity parsing**

backend/app/core/cloud_context.py:

~~~python
@dataclass(frozen=True)
class CloudIdentity:
    openid: str
    appid: str
    environment: str
    request_id: str | None


def read_cloud_identity(request: Request, settings: Settings) -> CloudIdentity:
    openid = request.headers.get("X-WX-OPENID", "").strip()
    appid = request.headers.get("X-WX-APPID", "").strip()
    environment = request.headers.get("X-WX-ENV", "").strip()
    if not openid or appid != settings.wx_appid or environment != settings.cloudbase_env_id:
        raise AppError(
            code="CLOUD_IDENTITY_INVALID",
            message="CloudBase 身份校验失败",
            status_code=401,
        )
    return CloudIdentity(
        openid=openid,
        appid=appid,
        environment=environment,
        request_id=request.headers.get("X-WX-REQUEST-ID"),
    )
~~~

- [ ] **Step 7: Implement routes and pass regression**

cloud-login calls read_cloud_identity, upsert_by_openid, create_access_token, and returns the same LoginResponse shape as guest-login. wx-login raises CODE2SESSION_DISABLED unless the flag is true. Tests set CLOUDBASE_ENV_ID=cloud-test and ENABLE_CODE2SESSION=false.

~~~bash
.venv/bin/pytest tests/test_config.py tests/test_api_v1/test_cloud_login.py \
  tests/test_api_v1/test_auth.py tests/test_api_v1/test_guest_login.py -q
.venv/bin/pytest -q
~~~

- [ ] **Step 8: Commit**

~~~bash
git add backend/app/core/config.py backend/app/core/cloud_context.py \
  backend/app/api/v1/auth.py backend/tests/test_config.py \
  backend/tests/test_api_v1/test_cloud_login.py backend/tests/conftest.py
git commit -m "feat(auth): add CloudBase trusted-header login"
~~~

---

### Task 2: Dual HTTP and CloudBase transports

**Files:**
- Create: miniapp/src/api/transport.ts
- Create: miniapp/src/api/http-transport.ts
- Create: miniapp/src/api/cloud-transport.ts
- Create: miniapp/src/api/response.ts
- Modify: miniapp/src/api/request.ts
- Modify: miniapp/src/config/env.ts
- Modify: miniapp/src/env.d.ts
- Modify: miniapp/src/App.vue
- Modify: miniapp/src/api/auth.ts
- Modify: miniapp/src/stores/user.ts
- Add focused Vitest files beside the modules.

- [ ] **Step 1: Write failing environment and response tests**

~~~typescript
expect(resolveCloudConfig(' cloud-test ', ' api-service ')).toEqual({
  environmentId: 'cloud-test',
  serviceName: 'api-service',
})
expect(() => resolveCloudConfig('', 'api-service')).toThrow('CloudBase')

const normalized = normalizeTransportResponse({
  statusCode: 200,
  body: JSON.stringify({ ok: true, data: { user_id: 7 } }),
  requestId: 'request-7',
})
expect(normalized.data).toEqual({ user_id: 7 })
expect(normalized.requestId).toBe('request-7')
~~~

- [ ] **Step 2: Verify red**

~~~bash
cd /root/miniapp-trellis/miniapp
npm test -- src/config/env.test.ts src/api/response.test.ts
~~~

- [ ] **Step 3: Define transport contracts**

~~~typescript
export type TransportRequest = {
  path: string
  method: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: unknown
  headers: Record<string, string>
  timeout: number
}

export type TransportResponse = {
  statusCode: number
  body: unknown
  requestId?: string
}

export interface Transport {
  execute(request: TransportRequest): Promise<TransportResponse>
}
~~~

response.ts parses string JSON, validates the ApiResult envelope, maps non-2xx and ok=false to ApiError, keeps requestId, and maps missing CloudBase service/environment to SERVICE_CONFIG_ERROR.

- [ ] **Step 4: Write failing CloudTransport tests**

Mock wx.cloud.callContainer and assert:

~~~typescript
expect(call.config.env).toBe('cloud-test')
expect(call.header['X-WX-SERVICE']).toBe('api-service')
expect(call.path).toBe('/api/v1/auth/cloud-login')
expect(call.method).toBe('POST')
~~~

Also verify network failure and request ID extraction.

- [ ] **Step 5: Implement adapters**

HttpTransport wraps uni.request with API_BASE_URL. CloudTransport wraps:

~~~typescript
wx.cloud.callContainer({
  config: { env: config.environmentId },
  path: input.path,
  method: input.method,
  data: input.data,
  header: { ...input.headers, 'X-WX-SERVICE': config.serviceName },
  timeout: input.timeout,
  success: resolveResponse,
  fail: rejectResponse,
})
~~~

Use uni-app platform compilation so mp-weixin selects CloudTransport and H5 selects HttpTransport.

- [ ] **Step 6: Refactor request.ts**

Keep request generic. Add a loading reference counter, one shared 401 redirect gate, guest-ID preservation, camel/snake conversion, 10-second default timeout, caller override, and no retry for POST.

- [ ] **Step 7: Initialize cloud and switch login**

App.vue initializes wx.cloud once with VITE_CLOUDBASE_ENV_ID. auth.ts adds cloudLogin for POST /api/v1/auth/cloud-login. userStore.login uses cloudLogin on mp-weixin; H5 uses guest login for local development. Existing wx.login/code2session remains compatibility-only.

- [ ] **Step 8: Verify**

~~~bash
npm test -- --run
npm run type-check
npm run lint:check
npm run build:h5
npm run build:mp-weixin
~~~

- [ ] **Step 9: Commit**

~~~bash
git add miniapp/src/api miniapp/src/config/env.ts miniapp/src/config/env.test.ts \
  miniapp/src/env.d.ts miniapp/src/App.vue miniapp/src/stores/user.ts miniapp/.env.example
git commit -m "feat(miniapp): route WeChat requests through CloudBase"
~~~

---

### Task 3: Alembic, MySQL, Docker, and health

**Files:**
- Modify: backend/pyproject.toml
- Modify: backend/app/db.py
- Modify: backend/app/main.py
- Create: backend/alembic.ini
- Create: backend/alembic/env.py
- Create: backend/alembic/script.py.mako
- Create: backend/alembic/versions/20260812_01_cloudbase_foundation.py
- Create: backend/Dockerfile
- Create: backend/.dockerignore
- Create: backend/scripts/container_health_smoke.sh
- Create: backend/tests/test_db_config.py
- Modify: backend/tests/test_health.py

- [ ] **Step 1: Write failing engine tests**

~~~python
def test_sqlite_options():
    options = build_engine_options("sqlite:///./dev.db", debug=False)
    assert options["connect_args"] == {"check_same_thread": False}


def test_mysql_options():
    options = build_engine_options("mysql+pymysql://u:p@db/eat", debug=False)
    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] == 300
~~~

- [ ] **Step 2: Verify red**

~~~bash
.venv/bin/pytest tests/test_db_config.py -q
~~~

- [ ] **Step 3: Implement runtime**

Add alembic and pymysql dependencies. build_engine_options returns SQLite thread options or MySQL health-check options. init_db may use create_all only in dev/test; production relies on Alembic.

Alembic env imports app.models, uses SQLModel.metadata, compares types, and uses SQLite batch mode. The foundation migration creates current tables without destructive drops.

- [ ] **Step 4: Make health database-aware**

GET /health executes SELECT 1. Success returns status=healthy and database=ready. A database exception returns 503 with status=degraded and database=unavailable, never a connection string.

- [ ] **Step 5: Add container**

~~~dockerfile
FROM python:3.10-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY data ./data
COPY scripts ./scripts
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
~~~

.dockerignore excludes .env, dev.db, tests, caches, virtualenvs, and Git.

- [ ] **Step 6: Verify migration and container**

~~~bash
.venv/bin/alembic upgrade head
.venv/bin/pytest tests/test_db_config.py tests/test_health.py -q
docker build -t eat-what-api:test .
./scripts/container_health_smoke.sh eat-what-api:test
~~~

- [ ] **Step 7: Commit**

~~~bash
git add backend/pyproject.toml backend/app/db.py backend/app/main.py \
  backend/alembic.ini backend/alembic backend/Dockerfile backend/.dockerignore \
  backend/scripts/container_health_smoke.sh backend/tests/test_db_config.py \
  backend/tests/test_health.py
git commit -m "build(backend): add CloudBase MySQL container runtime"
~~~

---

### Task 4: Recipe model and 60-recipe quality gate

**Files:**
- Modify: backend/app/models/food.py
- Create: backend/app/models/recipe.py
- Modify: backend/app/models/__init__.py
- Create: backend/app/schemas/recipe.py
- Create: backend/app/services/recipe_seed.py
- Create: backend/app/services/recipe_service.py
- Modify: backend/app/services/food_seed.py
- Create: backend/data/recipe_seed.json
- Create: backend/scripts/validate_recipe_seed.py
- Modify: backend/scripts/validate_food_seed.py
- Create: backend/alembic/versions/20260812_02_recipes.py
- Add recipe seed and service tests.

- [ ] **Step 1: Write failing seed tests**

~~~python
recipes = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))
assert len(recipes) == 60
assert len({item["food_name"] for item in recipes}) == 60
assert sum(item["meal_role"] == "main" for item in recipes) >= 20
assert sum(item["meal_role"] == "vegetable" for item in recipes) >= 20
assert sum(item["meal_role"] == "staple" for item in recipes) >= 10
for item in recipes:
    assert 4 <= len(item["steps"]) <= 6
    assert item["nutrition_per_serving"]["energy_kcal"] > 0
~~~

An idempotency test imports twice, proves all original 204 Food names still exist,
allows the approved 冬瓜香菜汤 addition, and has exactly 60 Recipe rows.

- [ ] **Step 2: Verify red**

~~~bash
.venv/bin/pytest tests/services/test_recipe_seed.py -q
~~~

- [ ] **Step 3: Add models**

Food gains meal_role, recipe_ready, and visual_key. Recipe has unique food_id, servings, ingredient JSON, step JSON, prep/cook time, per-serving nutrition JSON, difficulty, optional source, nutrition basis, version, and timestamps.

- [ ] **Step 4: Create the exact seed**

recipe_seed.json contains exactly 60 food names. Fifty-nine or more resolve to the
existing seed; the approved 冬瓜香菜汤 example is added to food_seed.json when absent.
Each record has role, visual key, servings, quantified ingredients, 4-6 executable
steps, times, per-serving energy/protein/fat/carbohydrate, nutrition basis,
difficulty, and version.

The approved example is encoded as:

~~~json
{
  "food_name": "冬瓜香菜汤",
  "meal_role": "vegetable",
  "servings": 2,
  "ingredients": [
    {"name": "冬瓜", "amount": 400, "unit": "g", "optional": false},
    {"name": "香菜", "amount": 20, "unit": "g", "optional": false},
    {"name": "食用油", "amount": 5, "unit": "ml", "optional": false},
    {"name": "盐", "amount": null, "unit": "适量", "optional": true}
  ],
  "steps": [
    "冬瓜去皮去瓤切片，香菜洗净切段。",
    "锅中放油，小火将冬瓜两面煎至微黄。",
    "加入 700 毫升清水煮开，中小火煮 8 至 10 分钟。",
    "冬瓜变软后少量加盐，关火放入香菜。"
  ],
  "prep_time_min": 8,
  "cook_time_min": 15,
  "nutrition_per_serving": {
    "energy_kcal": 78,
    "protein_g": 2.0,
    "fat_g": 2.8,
    "carb_g": 11.5
  },
  "difficulty": "easy",
  "nutrition_basis": "按主要食材、用油和 2 人份估算；盐为适量。",
  "version": 1
}
~~~

- [ ] **Step 5: Implement non-destructive upserts and validator**

food seed upserts by name and never deletes production rows. It adds a structured
冬瓜香菜汤 Food row without changing or deleting any of the original 204 names.
Recipe seed resolves food names, sets recipe_ready, and upserts by food_id in one
transaction.

The validator rejects wrong count, duplicates, absent foods, invalid roles, insufficient role counts, steps outside 4-6, missing nutrition, negative macros, unquantified nutrition-driving ingredients, non-HTTPS source links, or missing nutrition basis.

- [ ] **Step 6: Add recipe read service and migration**

RecipeRead returns ingredients, ordered steps, per-serving nutrition, times, difficulty, source, basis, and version. Migration adds Food fields and recipes table with unique food_id.

- [ ] **Step 7: Verify**

~~~bash
.venv/bin/alembic upgrade head
.venv/bin/python scripts/validate_food_seed.py
.venv/bin/python scripts/validate_recipe_seed.py
.venv/bin/pytest tests/services/test_food_seed.py \
  tests/services/test_recipe_seed.py tests/services/test_recipe_service.py -q
~~~

- [ ] **Step 8: Commit**

~~~bash
git add backend/app/models backend/app/schemas/recipe.py \
  backend/app/services/food_seed.py backend/app/services/recipe_seed.py \
  backend/app/services/recipe_service.py backend/data/recipe_seed.json \
  backend/scripts/validate_food_seed.py backend/scripts/validate_recipe_seed.py \
  backend/alembic/versions/20260812_02_recipes.py backend/tests/services
git commit -m "feat(recipes): add sixty validated per-serving recipes"
~~~

---

### Task 5: Rule engine v3 and complete meal builder

**Files:**
- Modify: backend/app/services/recommendation_ranking.py
- Modify: backend/app/services/recommender.py
- Create: backend/app/services/meal_builder.py
- Create: backend/app/schemas/meal.py
- Modify: backend/app/schemas/daily.py
- Add focused recommendation and meal builder tests.

- [ ] **Step 1: Write failing weight tests**

~~~python
assert RULE_V3_WEIGHTS == {
    "nutrition": 20,
    "constitution": 12,
    "mood": 10,
    "activity": 8,
    "method_time": 13,
    "weather": 6,
    "solar_term": 5,
    "zodiac": 1,
}
assert sum(RULE_V3_WEIGHTS.values()) == 75
assert hard_filter([recipe_food, non_recipe_food], profile) == [recipe_food]
~~~

- [ ] **Step 2: Verify red**

~~~bash
.venv/bin/pytest tests/services/test_recommender.py -q
~~~

- [ ] **Step 3: Implement v3 scoring**

Scale every dimension to its exact cap. method_time covers method variety and cooking time, not freshness. Seven-day choice/exposure penalties remain only in apply_novelty. Fallback weather creates no specific weather reason. Zodiac is never the main reason. Future reranker deltas are bounded to -10 through 10 and invalid output falls back to rules_v3.

- [ ] **Step 4: Write failing builder tests**

~~~python
result = build_meal(candidates)
assert [item.meal_role for item in result.primary_meal.items] == [
    "main", "vegetable", "staple"
]
assert len({item.food_id for item in result.primary_meal.items}) == 3
assert result.primary_meal.total_nutrition.energy_kcal == sum(
    item.nutrition_per_serving.energy_kcal
    for item in result.primary_meal.items
)
assert result.primary_meal.estimated_time_min == (
    sum(item.prep_time_min for item in result.primary_meal.items)
    + max(item.cook_time_min for item in result.primary_meal.items)
)
assert len(result.substitutions) == 2
~~~

A sparse safe-candidate fixture returns 0-1 substitutions plus substitution_notice, never an unsafe result.

- [ ] **Step 5: Define and implement meal contract**

MealRole is main, vegetable, or staple. MealItem includes food, role, method, visual, recipe times, per-serving nutrition, reason, and score. MealSnapshot has three items, summed nutrition, estimated time, and reason. Substitution has target role, replacement, resulting total, and reason. MealRecommendation has recommendation ID, primary meal, substitutions, notice, context, and engine.

Builder partitions by role, chooses distinct IDs, prefers category/method diversity, sums nutrition once, computes sum-prep plus max-cook time, and proposes main/vegetable replacements within 25 percent energy. It expands to 35 percent only when needed and never relaxes hard filters.

- [ ] **Step 6: Integrate and verify**

recommender builds the meal before persisting the event. Event data and response IDs must match.

~~~bash
.venv/bin/pytest tests/services/test_recommendation_ranking.py \
  tests/services/test_recommender.py tests/services/test_meal_builder.py -q
.venv/bin/pytest -q
~~~

- [ ] **Step 7: Commit**

~~~bash
git add backend/app/services/recommendation_ranking.py \
  backend/app/services/recommender.py backend/app/services/meal_builder.py \
  backend/app/schemas/meal.py backend/app/schemas/daily.py \
  backend/tests/services/test_recommendation_ranking.py \
  backend/tests/services/test_recommender.py backend/tests/services/test_meal_builder.py
git commit -m "feat(recommendation): build balanced three-slot meals"
~~~

---

### Task 6: Immutable snapshots, idempotent choice, and recipe API

**Files:**
- Modify: backend/app/models/daily_log.py
- Modify: backend/app/models/recommendation_event.py
- Modify: backend/app/services/daily_service.py
- Modify: backend/app/api/v1/daily.py
- Modify: backend/app/api/v1/food.py
- Create: backend/alembic/versions/20260812_03_meal_snapshots.py
- Modify daily service/API and food API tests.

- [ ] **Step 1: Write failing choice tests**

~~~python
body = {
    "recommendation_id": recommendation["recommendation_id"],
    "selected_food_ids": [
        item["food_id"] for item in recommendation["primary_meal"]["items"]
    ],
    "substitutions": [],
}
first = client.post("/api/v1/daily/choose", json=body, headers=auth_headers)
second = client.post("/api/v1/daily/choose", json=body, headers=auth_headers)
assert first.status_code == second.status_code == 200
assert first.json()["data"] == second.json()["data"]
assert len(first.json()["data"]["chosen_meal"]["items"]) == 3
~~~

Unknown IDs must return 422 with INVALID_MEAL_CHOICE.

- [ ] **Step 2: Verify red**

~~~bash
.venv/bin/pytest tests/test_api_v1/test_daily.py -q
~~~

- [ ] **Step 3: Extend persistence**

DailyLog gains recommendation_event_id, recommended_meal_json, chosen_meal_json, and chosen_total_nutrition_json while keeping legacy arrays. RecommendationEvent gains primary IDs, substitution role/IDs, scorer version, builder version, optional agent name, and summary.

- [ ] **Step 4: Implement strict idempotent save**

Load the current user's event, allow only primary/replacement IDs for their roles, require exactly one item per role, build a snapshot, return an identical prior choice unchanged, reject a conflicting second choice, and commit once.

today/history serialize stored snapshots rather than querying current Recipe rows.

- [ ] **Step 5: Add recipe route**

~~~python
response = client.get(f"/api/v1/food/{seeded_recipe.food_id}/recipe")
assert response.status_code == 200
assert 4 <= len(response.json()["data"]["steps"]) <= 6
assert response.json()["data"]["nutrition_per_serving"]["energy_kcal"] > 0
~~~

A non-recipe food returns 404.

- [ ] **Step 6: Verify**

~~~bash
.venv/bin/alembic upgrade head
.venv/bin/pytest tests/services/test_daily_service.py \
  tests/test_api_v1/test_daily.py tests/test_api_v1/test_food.py -q
.venv/bin/pytest -q
~~~

- [ ] **Step 7: Commit**

~~~bash
git add backend/app/models/daily_log.py backend/app/models/recommendation_event.py \
  backend/app/services/daily_service.py backend/app/api/v1/daily.py \
  backend/app/api/v1/food.py \
  backend/alembic/versions/20260812_03_meal_snapshots.py \
  backend/tests/services/test_daily_service.py \
  backend/tests/test_api_v1/test_daily.py backend/tests/test_api_v1/test_food.py
git commit -m "feat(daily): persist idempotent meal snapshots"
~~~

---

### Task 7: Miniapp meal domain, cache, and offline state

**Files:**
- Modify: miniapp/src/types/api.ts
- Modify: miniapp/src/api/daily.ts
- Create: miniapp/src/api/recipe.ts
- Create: miniapp/src/domain/meal.ts
- Create: miniapp/src/domain/meal.test.ts
- Modify: miniapp/src/stores/daily.ts
- Create: miniapp/src/stores/daily.test.ts

- [ ] **Step 1: Write failing pure-domain tests**

~~~typescript
const updated = applySubstitution(primaryMeal, substitution)
expect(updated.items.find((item) => item.mealRole === substitution.targetRole)?.foodId)
  .toBe(substitution.replacement.foodId)
expect(updated.totalNutrition).toEqual(sumNutrition(updated.items))
expect(JSON.stringify(primaryMeal)).toBe(before)
~~~

- [ ] **Step 2: Define frontend contracts**

Add camelCase NutritionTotal, MealItem, MealSnapshot, MealSubstitution, MealRecommendation, RecipeRead, and expanded DailyLogRead. RecommendResponse becomes recommendationId, primaryMeal, substitutions, notice, context, and engine.

- [ ] **Step 3: Implement pure operations**

meal.ts exports sumNutrition, estimateMealTime, and applySubstitution. It returns new objects, preserves one item per role, and rounds display values once.

- [ ] **Step 4: Update APIs and store tests**

choose sends recommendationId, all three current food IDs, and applied substitutions. Recipe API calls GET /food/{id}/recipe.

Store tests assert versioned cache save/restore, stale cached state, offline read-only fallback, successful refresh recovery, substitution recalculation, and whole-meal choice.

- [ ] **Step 5: Refactor store**

Use serverRecommendation, currentMeal, appliedSubstitutions, stale, offline, and lastRequestId. Degrade to cache only for network, timeout, or 5xx. Do not swallow auth or service configuration errors. Disable writes when stale/offline.

- [ ] **Step 6: Verify**

~~~bash
npm test -- src/domain/meal.test.ts src/stores/daily.test.ts
npm test -- --run
npm run type-check
~~~

- [ ] **Step 7: Commit**

~~~bash
git add miniapp/src/types/api.ts miniapp/src/api/daily.ts \
  miniapp/src/api/recipe.ts miniapp/src/domain/meal.ts \
  miniapp/src/domain/meal.test.ts miniapp/src/stores/daily.ts \
  miniapp/src/stores/daily.test.ts
git commit -m "feat(miniapp): manage complete meal recommendations"
~~~

---

### Task 8: Plate-list UI, recipe page, favorites, and history

**Files:**
- Create: miniapp/src/components/MealPlateCard.vue
- Create: miniapp/src/components/MealSlotRow.vue
- Create: miniapp/src/components/MealSubstitution.vue
- Create: miniapp/src/components/NutritionSummary.vue
- Modify: miniapp/src/pages/today/today.vue
- Create: miniapp/src/pages/recipe/recipe.vue
- Modify: miniapp/src/pages.json
- Modify: miniapp/src/pages/favorite/favorite.vue
- Modify: miniapp/src/pages/history/history.vue

- [ ] **Step 1: Build components**

MealPlateCard renders main, vegetable, and staple in order, deterministic role fallback visuals, 约 N kcal/份, protein, 约 N 分钟, reason, and one 就吃这套 button. Rows emit openRecipe. NutritionSummary labels all values estimated. Substitution emits the complete object.

- [ ] **Step 2: Replace loose-food homepage**

~~~vue
<MealPlateCard
  v-if="dailyStore.currentMeal"
  :meal="dailyStore.currentMeal"
  :readonly="dailyStore.stale || dailyStore.offline"
  @open-recipe="openRecipe"
  @choose="chooseCurrentMeal"
/>
<MealSubstitution
  v-for="item in dailyStore.availableSubstitutions"
  :key="item.targetRole + '-' + item.replacement.foodId"
  :substitution="item"
  @apply="dailyStore.applySubstitution(item)"
/>
~~~

Denied location continues with fallback. Cold start shows a retry message. Cached state says 上次推荐 and disables writes. Configuration errors include request ID. Chosen banner lists all three foods.

- [ ] **Step 3: Add recipe page**

Register pages/recipe/recipe. Display name, role, per-serving estimated nutrition, servings, times, difficulty, quantified ingredients, 4-6 steps, basis disclosure, optional HTTPS source, and favorite toggle. No third-party WebView is required.

- [ ] **Step 4: Upgrade favorite and history pages**

Favorites open recipe and prefer per-serving energy; kcal/100g is a labeled fallback. History renders stored three-food snapshots and nutrition; legacy rows retain their count fallback.

- [ ] **Step 5: Verify responsive UI and builds**

Check 320, 375, and 414 CSS-pixel widths for overflow, 88rpx primary targets, readable units, and missing-image fallback.

~~~bash
npm test -- --run
npm run type-check
npm run lint:check
npm run build:h5
npm run build:mp-weixin
test -f dist/build/mp-weixin/app.json
grep -R "localhost:8000" dist/build/mp-weixin && exit 1 || true
~~~

- [ ] **Step 6: Commit**

~~~bash
git add miniapp/src/components/MealPlateCard.vue \
  miniapp/src/components/MealSlotRow.vue miniapp/src/components/MealSubstitution.vue \
  miniapp/src/components/NutritionSummary.vue miniapp/src/pages/today/today.vue \
  miniapp/src/pages/recipe/recipe.vue miniapp/src/pages.json \
  miniapp/src/pages/favorite/favorite.vue miniapp/src/pages/history/history.vue
git commit -m "feat(miniapp): add meal plate and lightweight recipes"
~~~

---

### Task 9: Automated quality gates and delivery guides

**Files:**
- Create: docs/guides/cloudbase-cloudrun-deploy.md
- Modify: docs/guides/wechat-devtools-wsl.md
- Create: docs/guides/meal-recipe-acceptance.md

- [ ] **Step 1: Backend gate**

~~~bash
cd /root/miniapp-trellis/backend
.venv/bin/ruff check .
.venv/bin/mypy app
.venv/bin/python scripts/validate_food_seed.py
.venv/bin/python scripts/validate_recipe_seed.py
.venv/bin/alembic upgrade head
.venv/bin/pytest
docker build -t eat-what-api:acceptance .
./scripts/container_health_smoke.sh eat-what-api:acceptance
~~~

- [ ] **Step 2: Frontend gate**

~~~bash
cd /root/miniapp-trellis/miniapp
npm run lint:check
npm run type-check
npm test -- --run
npm run build:h5
npm run build:mp-weixin
~~~

- [ ] **Step 3: Write deployment runbook**

Record environment cloud1-d8gz4jm8vb964a1c9, service eat-what-api, port 8080, minimum instances 0, maximum 1, and initial 0.25 vCPU/0.5 GB. List secret variable names without values. Require migration before traffic, authenticated console/tcb deployment, health smoke, private-link smoke, then public-access shutdown and budget alerts.

- [ ] **Step 4: Write DevTools runbook**

Development import:

~~~text
\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\dev\mp-weixin
~~~

Production import:

~~~text
\\wsl.localhost\Ubuntu-22.04\root\miniapp-trellis\miniapp\dist\build\mp-weixin
~~~

Verify app.json, AppID wx59c5620b7a894f8e, callContainer, X-WX-SERVICE=eat-what-api, and no localhost request.

- [ ] **Step 5: Record real acceptance**

The acceptance guide records date, result, screenshot, and request ID for cloud login, guest login, profile, complete meal, three recipes, substitution, choice, favorite, history after restart, denied location, offline cache, cold start, simulator, QR preview, and one real phone.

- [ ] **Step 6: Commit guides**

~~~bash
git add docs/guides/cloudbase-cloudrun-deploy.md \
  docs/guides/wechat-devtools-wsl.md docs/guides/meal-recipe-acceptance.md
git commit -m "docs: add CloudBase deployment and acceptance runbooks"
~~~

---

## Completion checks

- [ ] git diff --check passes.
- [ ] All backend tests, frontend tests, static checks, validators, migrations, dual builds, and Docker health pass.
- [ ] mp-weixin production output has app.json and no localhost API endpoint.
- [ ] Standard profile returns three roles and two substitutions; extreme safe-filter fixtures may return fewer with a reason.
- [ ] All 60 recipes have 4-6 steps, quantified core ingredients, and per-serving estimated nutrition.
- [ ] All original 204 Food names remain, total Food rows are at least 205 after adding 冬瓜香菜汤, and production seed performs no table wipe.
- [ ] Secrets, openid values, tokens, private project config, and build output are absent from staged changes.
- [ ] Automated evidence is reported separately from manual CloudBase, simulator, QR, and real-device evidence.
- [ ] Remote push occurs only after explicit user authorization.
