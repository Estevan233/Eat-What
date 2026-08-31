# rules_v6 推荐排序与 30 天偏好画像 Implementation Plan

> **For agentic workers:** 实施前必须先由用户审阅本任务 `prd.md`、`design.md` 与本计划，并显式启动 Trellis 任务。执行时逐项使用 TDD；本规划阶段不启动任务、不改生产代码、不提交。

**Goal:** 在现有推荐管线上完成 85 分基础评分、15 分受约束重排、14 天新鲜度和 30 天轻量偏好画像，并保持硬过滤、完整餐、幂等和 API 主契约。

**Architecture:** 保留 `recommender.py` 编排和 `meal_builder.py` 组餐，集中在 `recommendation_ranking.py` 实现历史、画像、探索、多样性与 tie-break 纯函数；`solar_terms.py` 提供内部节气周期。所有数据库读取继续走现有 service/repository 双路径，不新增表。

**Tech Stack:** Python 3.10+、FastAPI、SQLModel、CloudBase HTTP Repository、Pydantic v2、lunar-python、pytest/pytest-asyncio、ruff、mypy。

---

## 0. 执行前门禁

- [ ] 用户确认 `prd.md`、`design.md` 和本计划可以进入实现。
- [ ] 主线程执行 `python3 ./.trellis/scripts/task.py start 08-28-recommendation-v6`；当前规划代理不得代执行。
- [ ] 确认工作树只包含预期变更；若 Git 指针仍为跨系统 `/root/...`，在创建该 worktree 的 WSL 环境执行 Git 与测试，不修改 `.git` 文件。
- [ ] 激活已安装 backend dev dependencies 的环境。以下命令均从仓库根目录在 WSL/bash 执行，测试密钥只存在于单次进程：

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py -q
```

预期：实现前基线通过；新增 RED 测试加入后按各任务描述失败。

## 1. RED：锁定 85 + 15 分数账本

**Files:**

- Modify: `backend/tests/services/test_recommendation_ranking.py`
- Modify: `backend/tests/services/test_recommender.py`
- Modify: `backend/app/services/recommendation_ranking.py`
- Modify: `backend/app/services/recommender.py`
- Modify: `backend/app/schemas/daily.py`
- Modify: `backend/tests/test_api_v1/test_daily.py`

- [ ] **Step 1.1：先写权重与边界失败测试**

新增并只测试一个行为/函数：

```python
def test_rule_v6_weights_split_eighty_five_base_and_fifteen_rerank() -> None:
    assert RULE_V6_BASE_WEIGHTS == {
        "nutrition": 12,
        "constitution": 14,
        "solar_term": 16,
        "weather": 4,
        "preference": 15,
        "feasibility": 14,
        "mood": 5,
        "activity": 3,
        "zodiac": 2,
    }
    assert RULE_V6_RERANK_WEIGHTS == {"diversity": 7, "exploration": 8}
    assert sum(RULE_V6_BASE_WEIGHTS.values()) == 85
    assert sum(RULE_V6_RERANK_WEIGHTS.values()) == 15
```

同时新增：

- `test_score_breakdown_total_is_capped_at_eighty_five`
- `test_final_score_is_clamped_to_zero_and_one_hundred`
- `test_meal_intent_is_inside_feasibility_budget`
- `test_weight_profile_keeps_legacy_aggregates_and_adds_v6_details`

- [ ] **Step 1.2：运行 RED 并确认失败原因正确**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py::test_rule_v6_weights_split_eighty_five_base_and_fifteen_rerank tests/services/test_recommender.py::test_score_food_uses_exact_v6_caps tests/services/test_recommender.py::test_meal_intent_is_inside_feasibility_budget tests/test_api_v1/test_daily.py::test_recommend_returns_rules_v6_weight_profile -q
```

预期：FAIL，原因是 v6 常量/字段不存在或仍返回 v5 权重；不得是 import typo、fixture 错误或数据库错误。

- [ ] **Step 1.3：实现最小分数结构**

按 `design.md §4/§5`：

- 把 `ScoreBreakdown` 改为九个基础字段，`total` 最大 85；
- `RankedCandidate.final_raw_score` 只由 base、novelty、exploration、diversity组成；
- 把 meal intent 收进 14 分 feasibility；
- 增加 v6 权重常量；
- 兼容扩展 `RecommendationWeightProfile`，不删旧聚合键。

- [ ] **Step 1.4：运行 GREEN 与局部回归**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py tests/services/test_recommender.py tests/test_api_v1/test_daily.py -q
```

预期：本任务新增权重测试 PASS；既有硬过滤、天气、meal intent 与 API 测试无回归。

## 2. RED：节气周期前中后三档

**Files:**

- Modify: `backend/tests/services/test_solar_terms.py`
- Modify: `backend/tests/services/test_recommender.py`
- Modify: `backend/app/services/solar_terms.py`
- Modify: `backend/app/services/recommender.py`

- [ ] **Step 2.1：写周期 helper 失败测试**

测试必须固定日期，不依赖真实今天：

- `test_solar_term_cycle_switches_on_term_day`
- `test_solar_term_cycle_has_previous_and_next_boundaries`
- `test_solar_term_score_active_term_uses_16_12_8_tiers`
- `test_solar_term_score_next_term_uses_0_4_8_tiers`
- `test_solar_term_score_does_not_sum_active_and_next`
- `test_today_context_existing_current_term_semantics_are_unchanged`

周期测试直接构造 `SolarTermCycle` 覆盖 phase 0/1/2；另用 2026 年固定日期验证 lunar-python 边界对象。

- [ ] **Step 2.2：运行 RED**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_solar_terms.py::test_solar_term_cycle_switches_on_term_day tests/services/test_recommender.py::test_solar_term_score_active_term_uses_16_12_8_tiers tests/services/test_recommender.py::test_solar_term_score_next_term_uses_0_4_8_tiers -q
```

预期：FAIL，原因是 `SolarTermCycle`/周期评分尚不存在。

- [ ] **Step 2.3：实现最小周期计算与缓存**

- 使用 `getPrevJieQi(whole_day=True)`、`getNextJieQi(whole_day=True)`；
- 节气当天显式把当天作为 active，并从次日获取真正 next；
- `phase_index = min(2, floor(3 * elapsed / cycle_days))`；
- 只新增内部上下文，不篡改 `TodayContext` 对外字段。

- [ ] **Step 2.4：运行 GREEN**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_solar_terms.py tests/services/test_recommender.py -q
```

预期：周期边界全 PASS，既有星座/节气固定日期测试继续 PASS。

## 3. RED：30 天查询与画像证据

**Files:**

- Modify: `backend/tests/services/test_daily_service.py`
- Modify: `backend/tests/services/test_recommendation_ranking.py`
- Create or modify: `backend/tests/services/test_favorite_service.py`
- Modify: `backend/app/services/daily_service.py`
- Modify: `backend/app/services/favorite_service.py`
- Modify: `backend/app/services/recommendation_ranking.py`

- [ ] **Step 3.1：写查询窗口失败测试**

- `test_get_recent_uses_inclusive_thirty_day_window_with_as_of`
- `test_get_recent_recommendation_events_uses_inclusive_thirty_day_window`
- `test_list_recent_favorites_matches_sqlmodel_and_cloudbase_boundaries`

边界数据必须含 `days_ago=0/29/30`，断言 0 与 29 纳入、30 排除。CloudBase 使用 repository fake 断言 `created_at gte/lt` 过滤，不 mock service 自己。

- [ ] **Step 3.2：运行 RED**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_daily_service.py::test_get_recent_uses_inclusive_thirty_day_window_with_as_of tests/services/test_favorite_service.py::test_list_recent_favorites_matches_sqlmodel_and_cloudbase_boundaries -q
```

预期：FAIL，原因是 `get_recent(as_of=...)` 或 `list_recent_favorites` 尚不存在。

- [ ] **Step 3.3：实现查询最小改动**

- `daily_service.get_recent` 增加 keyword-only `as_of: date | None = None`；
- 复用已有 `get_recent_recommendation_events(days, as_of)`；
- `favorite_service.list_recent_favorites` 返回 `Favorite` 行并保证 SQLModel/CloudBase 同窗口；
- 不新增 query，不在 Python 全表拉取后过滤。

- [ ] **Step 3.4：写画像失败测试**

新增：

- `test_preference_snapshot_uses_only_last_thirty_days`
- `test_preference_snapshot_contains_tag_category_nature_method_and_ingredient`
- `test_favorite_signal_outweighs_chosen_signal`
- `test_chosen_signal_decays_by_recency_bucket`
- `test_chosen_signal_is_damped_by_exposure_count`
- `test_exposed_but_not_chosen_is_not_negative_feedback`
- `test_explicit_negative_signal_requires_explicit_input`
- `test_empty_preference_snapshot_returns_neutral_seven_point_five`

- [ ] **Step 3.5：运行画像 RED**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py -k 'preference_snapshot or preference_score or explicit_negative' -q
```

预期：FAIL，原因是快照仍只接受 ids/7 天数据且没有 tag/nature/negative seam。

- [ ] **Step 3.6：实现画像公式并跑 GREEN**

严格实现 `design.md §6` 的 30 天分档、favorite/chosen 权重、平方根曝光阻尼、标签均分和各轴 cap。显式负反馈默认空；不得从未选择推断。

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_daily_service.py tests/services/test_favorite_service.py tests/services/test_recommendation_ranking.py -q
```

预期：全部 PASS。

## 4. RED：14 天惩罚与曝光距离

**Files:**

- Modify: `backend/tests/services/test_recommendation_ranking.py`
- Modify: `backend/app/services/recommendation_ranking.py`

- [ ] **Step 4.1：写边界参数化测试**

```python
@pytest.mark.parametrize("days_ago", range(1, 14))
def test_chosen_penalty_is_stronger_than_exposure_and_monotonic(days_ago: int) -> None:
    ...
```

另加：

- `test_same_day_exposure_penalty_is_minus_forty_five`
- `test_day_fourteen_has_no_novelty_penalty`
- `test_novelty_uses_strongest_signal_without_stacking`
- `test_repeated_exposure_extra_is_bounded`
- `test_unexposed_distance_is_thirty_day_sentinel`
- `test_client_exclusion_becomes_today_soft_history_only`

- [ ] **Step 4.2：运行 RED**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py -k 'penalty or novelty or exposure_distance or client_exclusion' -q
```

预期：旧 7 天数组、`SEEN_TODAY_PENALTY=-30` 或当天硬删除导致 FAIL。

- [ ] **Step 4.3：实现公式与单一路径**

- 窗口判断为 `0..13`；
- 当天 `-45`；
- 第 1～13 天使用 design 中线性公式；
- 重复曝光额外扣分封顶 12；
- 只取最强 penalty；
- 删除“候选足够时排除 seen_today”的分支。

- [ ] **Step 4.4：运行 GREEN**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py -q
```

预期：所有 14 天边界与既有 idempotency history 测试 PASS。

## 5. RED：质量带探索、动态多样性与严格 tie-break

**Files:**

- Modify: `backend/tests/services/test_recommendation_ranking.py`
- Modify: `backend/tests/services/test_meal_builder.py`
- Modify: `backend/app/services/recommendation_ranking.py`
- Modify: `backend/app/services/meal_builder.py`

- [ ] **Step 5.1：写探索资格失败测试**

- `test_unexposed_candidate_outside_quality_band_gets_no_exploration_bonus`
- `test_unexposed_candidate_inside_quality_band_gets_eight`
- `test_request_seed_does_not_change_quality_band_membership`
- `test_no_unexposed_in_band_does_not_expand_quality_band`

- [ ] **Step 5.2：写动态多样性失败测试**

- `test_first_slot_gives_equal_seven_diversity_points`
- `test_next_slot_splits_category_and_method_bonus_three_point_five_each`
- `test_diversity_bonus_does_not_drop_required_role_when_pool_is_sparse`
- `test_primary_and_substitution_use_same_rules_v6_key`

- [ ] **Step 5.3：写 tie-break 失败测试**

- `test_tie_break_prefers_final_score_before_exposure_distance`
- `test_tie_break_prefers_longer_exposure_distance_before_seed`
- `test_tie_break_uses_user_date_request_seed_before_food_id`
- `test_tie_break_uses_food_id_only_as_last_resort`
- `test_same_user_date_request_is_reproducible`

- [ ] **Step 5.4：运行 RED**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py tests/services/test_meal_builder.py -k 'quality_band or exploration or diversity_bonus or tie_break or rules_v6_key' -q
```

预期：FAIL，原因是旧 `selection_order` 优先或旧 `food.id` tie-break。

- [ ] **Step 5.5：实现统一 slate rerank**

- 每个待填角色先算 `quality_score` 与固定 5 分 band；
- 仅 band 内 30 天未曝光候选得 8；
- 按已选 category/method 算 0/3.5/7；
- 统一使用 `(-final, -distance, sha256-seed, id)`；
- 主餐与替换项复用同一 key；
- 删除/收口不再进入主链路的第二套 `select_diverse` 与旧 explorer 逻辑，避免双重重排。

- [ ] **Step 5.6：运行 GREEN**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py tests/services/test_meal_builder.py -q
```

预期：统一重排测试全 PASS，完整餐角色与替换项既有测试无回归。

## 6. RED：接入 recommend 主链路与版本契约

**Files:**

- Modify: `backend/tests/services/test_recommender.py`
- Modify: `backend/tests/test_api_v1/test_daily.py`
- Modify: `backend/app/services/recommender.py`

- [ ] **Step 6.1：写主链路失败测试**

- `test_recommend_reads_thirty_day_logs_events_and_favorites_once`
- `test_recommend_persists_rules_v6_engine_and_scorer_version`
- `test_same_request_id_replays_identical_rules_v6_meal`
- `test_different_request_seed_only_changes_tied_quality_candidates`
- `test_hard_filter_still_precedes_exploration_and_diversity`
- `test_rules_v6_reason_uses_only_true_base_matches`

- [ ] **Step 6.2：运行 RED**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommender.py -k 'rules_v6 or thirty_day or same_request_id or hard_filter' -q
```

预期：FAIL，原因是主链路仍读取 7 天、调用旧 explorer 或写 `rules_v5`。

- [ ] **Step 6.3：最小接线**

- 一次读取 logs30/events30/favorites30；营养分从 logs30 内切最近 3 天，不另查；
- 构建偏好与历史快照；
- 每个角色走统一 v6 重排；
- 写 `engine/scorer_version=rules_v6`；
- API 顶层字段不变，weight profile 兼容扩展。

- [ ] **Step 6.4：运行 service + API GREEN**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommender.py tests/services/test_daily_service.py tests/test_api_v1/test_daily.py -q
```

预期：全部 PASS。

## 7. 完整验证与验收指标

- [ ] **Step 7.1：目标测试与覆盖率**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommendation_ranking.py tests/services/test_recommender.py tests/services/test_solar_terms.py tests/services/test_daily_service.py tests/services/test_favorite_service.py tests/services/test_meal_builder.py --cov=app.services.recommendation_ranking --cov=app.services.recommender --cov=app.services.solar_terms --cov-report=term-missing --cov-fail-under=80 -q
```

预期：PASS；目标服务合并覆盖率 ≥80%，没有测试警告新增。

- [ ] **Step 7.2：性能与查询预算**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/services/test_recommender.py::test_two_hundred_food_recommendation_finishes_under_half_second tests/services/test_recommender.py::test_recommendation_hot_path_uses_at_most_five_selects -q
```

预期：200 候选纯规则完整推荐 <500 ms；热路径 select ≤5。

- [ ] **Step 7.3：lint 与类型检查**

```bash
cd backend && python -m ruff check app/ tests/
```

```bash
cd backend && python -m mypy app/
```

预期：两条命令退出码 0，无新增 ignore 或裸 `Any`。

- [ ] **Step 7.4：完整后端回归**

```bash
cd backend && JWT_SECRET='rules-v6-test-secret-at-least-32-bytes' python -m pytest tests/ -q
```

预期：全部 PASS；既有 346-test 基线不得减少，新增测试计数应上升。

- [ ] **Step 7.5：需求逐条核对**

| 指标 | 必须结果 |
|---|---|
| 基础/重排预算 | 85 / 15，最终 0..100 |
| 当天/历史 | today=-45；days 1..13 单调；day 14=0 |
| 探索 | 仅 5 分质量带内且 30 天未曝光得 8 |
| tie-break | final → distance → stable seed → id |
| 节气 | active 16/12/8；next 0/4/8 |
| 偏好 | 30 天；tag/category/nature/method + 兼容 ingredient |
| 曝光偏差 | 曝光未选=0；chosen 按曝光次数阻尼 |
| 负反馈 | 仅显式注入生效；无表/路由/UI |
| 安全 | 忌口、体质、recipe-ready 永不放宽 |
| 性能 | 200 候选 <500 ms；select ≤5 |

## 8. 审查与回滚点

- [ ] 若新增评分字段导致 API equality test 变化，只允许“保留旧键 + 新增明细键”；不得删除旧键图省事。
- [ ] 若 30 天查询使 select >5，先合并/复用已取数据，不加缓存掩盖 N+1。
- [ ] 若节气边界日测试暴露 lunar-python prev/next 同日行为，修周期 helper，不改 `TodayContext` 既有语义。
- [ ] 若统一重排导致角色不足，回滚到最后 GREEN，检查角色内候选与动态 bonus；不得恢复当天硬删除或放宽硬过滤。
- [ ] 若完整回归失败，先保留 RED 复现，再修最小实现；禁止把断言改回 rules_v5 值假装通过。
- [ ] 本任务实现完成后由主线程按 Trellis Phase 2.2 做全范围检查；提交分组需另获用户确认，本计划不授权当前代理提交。
