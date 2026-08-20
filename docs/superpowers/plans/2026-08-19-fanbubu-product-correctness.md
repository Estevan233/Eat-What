# Fanbubu Product Correctness Implementation Plan

> For agentic workers: use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make personal external dining return three rotating choices, scale home-cooked meals by party size, fix clipped profile inputs, and treat a missing constitution result as a normal first-use state.

**Architecture:** Keep the current FastAPI + SQLModel + CloudBase Cloud Run architecture. Extend pure recommendation selectors and snapshot validation without changing database tables, then make narrow frontend contract and styling fixes. Defer the HTTPS Repository migration until the product paths are stable.

**Tech Stack:** Python 3.10, FastAPI, SQLModel, Pydantic v2, pytest, uni-app, Vue 3, Pinia, TypeScript, Vitest, Docker.

---

### Task 1: Repair personal external dining cardinality and rotation

**Files:**
- Create: backend/tests/services/test_external_dining.py
- Modify: backend/app/services/external_dining.py

- [ ] Write failing tests proving a personal request returns three suggestions with three distinct keys and meal formats, and two adjacent batches produce six distinct keys when exclusions are supplied.
- [ ] Run backend/.venv/bin/pytest -q backend/tests/services/test_external_dining.py and confirm the current implementation returns one item.
- [ ] Give every existing personal candidate a distinct stable meal format and expand the personal rule pool to at least twelve safe, nutritionally described directions.
- [ ] Keep forbidden-tag filtering before rotation and do not duplicate results when fewer than three safe candidates exist.
- [ ] Rerun the focused tests and the dining API tests.

### Task 2: Add party-size meal templates and multi-slot meal building

**Files:**
- Modify: backend/app/services/meal_builder.py
- Modify: backend/app/services/recommender.py
- Modify: backend/app/services/daily_service.py
- Test: backend/tests/services/test_meal_builder.py
- Test: backend/tests/services/test_recommender.py
- Test: backend/tests/services/test_daily_service.py
- Test: backend/tests/test_api_v1/test_daily.py

- [ ] Add failing parameterized tests for the 1/2/3–4/5–6/7–8 role-count matrix.
- [ ] Add failing tests proving repeated roles select distinct foods and avoid duplicate cooking methods when candidates allow.
- [ ] Add failing tests proving a family snapshot with repeated roles can be confirmed only with exactly the IDs from that recommendation.
- [ ] Implement a pure meal_role_targets helper and pass its counts through novelty selection and meal construction.
- [ ] Disable ambiguous role-only substitutions for templates containing repeated roles while preserving the current personal substitution contract.
- [ ] Add a family confirmation branch that validates the submitted ID set against the primary snapshot and preserves snapshot order.
- [ ] Run all focused backend tests until green.

### Task 3: Strengthen adjacent-batch and seven-day freshness

**Files:**
- Modify: backend/app/services/recommendation_ranking.py
- Modify: miniapp/src/stores/daily.ts
- Test: backend/tests/services/test_recommendation_ranking.py
- Test: backend/tests/services/test_recommender.py
- Test: miniapp/src/stores/daily.test.ts

- [ ] Write a failing ranking test showing repeated exposure within seven days receives a stronger penalty than one exposure at the same age.
- [ ] Write failing store tests proving the client retains at most twelve unique recent cook IDs and sends them before appending the new batch.
- [ ] Add exposure counts to RecommendationHistory and apply a bounded repeat penalty without weakening hard filters.
- [ ] Increase the client recent-cook cap from six to twelve.
- [ ] Add a family recommendation test asserting adjacent batches replace at least the upward-rounded N×60% items when the pool is sufficient.
- [ ] Run backend ranking/recommender tests and frontend daily-store tests.

### Task 4: Render dynamic family meal cards safely

**Files:**
- Modify: miniapp/src/components/MealPlateCard.vue
- Modify: miniapp/src/pages/today/today.vue
- Test: miniapp/src/components/meal-plate-contract.test.ts

- [ ] Write a failing source contract test proving the card no longer contains the hard-coded “一主菜 · 一蔬菜 · 一主食” headline and list keys are not based on role alone.
- [ ] Compute role counts from meal.items, render a Chinese count headline, and key rows by foodId.
- [ ] Pass partySize from the Today page and show per-person plus whole-table energy for family meals.
- [ ] Run the component contract test, type-check, and the mp-weixin build.

### Task 5: Fix profile numeric input clipping

**Files:**
- Modify: miniapp/src/pages/profile/profile.vue
- Test: miniapp/src/pages/profile/profile-layout.test.ts

- [ ] Write a failing source regression test requiring an explicit input height, matching line-height, zero vertical padding, full width, and border-box sizing.
- [ ] Replace vertical padding with a fixed native-input box while preserving horizontal spacing and current validation ranges.
- [ ] Run the focused layout test, type-check, and mp-weixin build.

### Task 6: Make missing constitution data a silent empty state

**Files:**
- Modify: miniapp/src/api/request.ts
- Modify: miniapp/src/api/constitution.ts
- Modify: miniapp/src/stores/user.ts
- Modify: miniapp/src/pages/constitution/constitution.vue
- Test: miniapp/src/api/request.test.ts
- Test: miniapp/src/stores/user.test.ts

- [ ] Write a failing request test proving a configured silent 404 still rejects but does not call uni.showToast.
- [ ] Write failing store tests proving 404 returns null and clears stale constitution cache, while network/5xx failures still reject and preserve an existing result.
- [ ] Add silentErrorStatuses to request options and use status 404 only for constitution result GET.
- [ ] Narrow the Store catch to ApiError statusCode 404; update the page to select result/form view from the nullable return value.
- [ ] Run request, user-store, type-check, and the full frontend suite.

### Task 7: Full verification and deployment artifacts

**Files:**
- Modify only when a verification exposes an in-scope regression.

- [ ] Run the complete backend pytest suite.
- [ ] Run frontend Vitest, ESLint check, and Vue type-check.
- [ ] Build miniapp/dist/build/mp-weixin and verify app.json plus project.config.json are present in the imported project root.
- [ ] Build the backend Docker image and run its health smoke test.
- [ ] Record exact pass counts, artifact paths, remaining manual WeChat DevTools checks, and do not commit or push without explicit user authorization.
