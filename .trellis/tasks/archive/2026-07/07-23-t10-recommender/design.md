# T10 Design — 推荐算法核心

## 1. 偏离 PRD 的几个小决策

| 项 | PRD 原文 | 实际选择 | 理由 |
|---|---|---|---|
| activity_level 枚举 | `light \| normal \| heavy` | 与前端 `ActivityLevel='light'\|'normal'\|'high'` 统一 | T01-T05 已在 `types/api.ts` 定义 'high'，统一避免双套常量；扣字段语义没差别 |

## 2. 新增 DailyLog 表

PRD 算法第 4 步要读近 3 天 `chosen_food_ids` 给营养互补加分，但 PRD 说 T11 才写入。决策现在建表+history 为空时 default 10 分，让 T10 完整逻辑可跑、T11 只需加写入端点。

```python
class DailyLog(SQLModel, table=True):
    __tablename__ = "daily_logs"
    id: int | None = Field(primary_key, default=None)
    user_id: int = Field(foreign_key="users.id", index=True)
    log_date: date = Field(index=True)               # 当天日期
    chosen_food_ids_json: list[int] = Field(default=[], sa_column=Column(JSON))
    recommended_food_ids_json: list[int] = Field(default=[], sa_column=Column(JSON))
    mood: str = Field(default="neutral", max_length=16)
    activity_level: str = Field(default="normal", max_length=8)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

`chosen_food_ids` 是用户最终从 3 道推荐里挑了哪些（T11 写入）。`recommended_food_ids` 是这次推荐的 3 道菜的 id（T10 写入便于反馈学习）。`mood/activity_level` 用户当时的输入（用作反馈分析）。

**唯一约束**：(user_id, log_date) 联合 unique（一个用户每天一行，重选覆盖）。

## 3. Weather fallback

PRD notes："拒绝授权时用默认 fallback（北京或上海）→ weather_tag = 'mild'"。实际实现：

```python
def _fallback_weather() -> WeatherData:
    return WeatherData(
        location_name="未知位置 · fallback",
        temp_c=22.0, feels_like_c=22.0, text="温和",
        wind_dir="无", wind_scale="0级 无风",
        humidity=50, precipitation_mm=0,
        weather_tag="mild",
        fetched_at=datetime.now(timezone.utc),
    )
```

`RecommendRequest.lat/lng is None` 时调此 fallback，不打外部 HTTP。

## 4. 评分项详细规则（满分 100）

| 维度 | 满分 | 触发加分 / 扣分 |
|---|---|---|
| 天气适配 | 30 | rainy→暖胃汤粥 +30；hot→凉性菜 +30；cold→温热性 +30；dry→润燥 +30；mild→ 0；snowy→ 暖性汤 +30；任一不匹配 →0 分，反向扣 10 分（轻度惩罚）|
| 节气适配 | 20 | 当前节气 ∈→+20；下一节气 ∈→+10；无→0 |
| 星座趣味 | 10 | 火象(白羊/狮子/射手)→辛辣/spicy flavor；土象(金牛/处女/摩羯)→家常/平性；风象(双子/天秤/水瓶)→多样/quick tag；水象(巨蟹/天蝎/双鱼)→滋补 mild。命中 +10；不匹配不扣 |
| 心情适配 | 20 | tired→高蛋白(protein_g≥8)+8；stressed→暖胃/易消化 +8；anxious→色氨酸(egg/oats/milk tag)+8；happy/neutral+0；命中累加≤20 |
| 营养均衡 | 20 | history 不足 3 天 → default 10；近 3 天高脂(>40g 总) → 给低脂菜 +20；高蛋白 → 给低脂菜 +10；不足 → 基础 10 |

每项综合到 score：0-100 纯分数。**算法稳定性**：相同输入必返相同输出（无随机）。

## 5. 推荐流程代码骨架

```python
async def recommend(session, user, req) -> RecommendResponse:
    profile = profile_service.get_profile(session, user.id)
    if profile is None:
        raise NotFoundError("user_profile", user.id)  # 未建档不能推荐

    weather = await _get_weather(req.lat, req.lng)
    today = get_today_context_cached()
    history = daily_service.get_recent(session, user.id, days=3)
    foods, _ = food_service.get_all(session, page=1, size=500)  # 全量

    # 硬筛
    kept = [f for f in foods if not _is_forbidden(f, profile, req)]
    # 软筛（不剔除，打 0.5 权重标签先不写，T11 视情况加，先简单）
    # 打分
    scored = [
        (f, _score(f, weather, today, profile, history, req.mood),
         _make_reason(f, ..., profile, weather, today, req.mood, history))
        for f in kept
    ]
    # Top 6 后保证多样
    scored.sort(key=lambda x: -x[1])
    top6 = scored[:6]
    top3 = _ensure_diversity(top6)
    # 写 DailyLog（推荐日志）
    _write_daily_log(session, user.id, top3, req)
    return RecommendResponse(
        foods=[FoodWithReason(...)],
        context=RecommendContext(weather=weather, today=today),
    )
```

## 6. 多样性算法

Top 6 里挑 3 道：
1. category 不得全相同（最多 2 道 category 重复）
2. cooking_method 不得全相同
3. 同分按 food.id 升序（确定性 tie-break）
4. 占位法：依次选 score 最高的、未违反多样性约束的；直到 3 道

## 7. 理由生成（避免堆砌）

模板：`适合今日【{天气描述}】场景，{体质维度}，{心情维度}，{营养维度}。`
- 仅列出**实际命中**的维度，每项出现一次，避免关键词堆砌
- 维度短语示例：
  - 天气rainy："雨天暖胃"
  - 节气立秋："正值立秋"
  - 心情tired："可缓解你的疲惫"
  - 营养互补："与你近三天偏油腻饮食互补"
- 维度都未命中："今天品尝舒适"（兜底）

## 8. 性能保证

200 道菜全量打分：纯 Python，每条 5-8 个 dict 字段查询 + 数字比较 → O(1500 字段查找 × 200) << 1ms 单条；总耗时 < 50ms。无需特殊缓存。

## 9. 路由

`POST /daily/recommend`：登录依赖。
- Body: `RecommendRequest` （mood 必填，activity_level 默认 normal，lat/lng 可空）
- Response: `RecommendResponse.foods: list[FoodWithReason]` + `context: RecommendContext`

## 10. 测试覆盖（≥ 8 例）

| 测试 | 覆盖分支 |
|---|---|
| test_recommender_returns_three_foods | 返回 3 道 |
| test_forbidden_tag_filters_pork | 红烧肉不出现 |
| test_constitution_forbidden_filters | 体差禁忌菜不出现 |
| test_weather_cold_promotes_warm | cold + 阳虚 → 温性菜 feedforward_top1 |
| test_weather_rainy_promotes_soup | rainy → 汤类上榜 |
| test_solar_term_promotes_in_season | 节气立秋 + 银耳羹 → 上榜 |
| test_mood_tired_promotes_high_protein | tired → 高蛋白菜入选 |
| test_history_high_fat_promotes_low_fat | 高脂 history → 低脂菜加分 |
| test_diversity_no_three_same_category | Top 3 不全相同 category |
| test_no_profile_raises | 未建档 → error |
| test_reason_contains_keywords | 理由文本含"立秋/暖胃"等关键词 |
| test_stable_result_for_same_input | 同输入两次结果一致 |