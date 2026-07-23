# T10 推荐算法核心

## Goal

实现「规则筛选 + 加权打分 + 理由生成」的推荐算法，输出 3 道菜 + 自然语言解释。这是整个产品的核心价值。

## Requirements

### 算法规范

#### 输入

```python
class RecommendRequest(BaseModel):
    mood: str          # happy | neutral | tired | stressed | anxious
    lat: Optional[float]  # 用户实时位置；未提供时天气用 fallback
    lng: Optional[float]
    activity_level: str = "normal"  # light | normal | heavy
```

#### 算法步骤

1. **硬筛（剔除）**
   - 忌口冲突（用户的 `forbidden_tags` 与菜的 `tags` 交集）→ 直接剔除
   - 体质禁忌（用户的 `constitution_type` 主+兼夹 ∈ 菜的 `forbidden_for`）→ 直接剔除

2. **软筛（降权 0.5×）**
   - 体质非禁忌但与菜的 `suitable_constitutions` 不匹配
   - 油炸 / 重辣对湿热/痰湿体质

3. **加权打分（满分 100）**
   - 天气适配（30 分）
     - `weather_tag == 'cold'` → 温热性 (warm/hot) 加分，寒凉性 (cold/cool) 扣分
     - `weather_tag == 'hot'` → 反向
     - `rainy` → 暖胃汤粥加分
     - `dry` → 润燥（银耳/梨/百合）加分
     - `mild` → 中性菜不加分不扣分
   - 节气适配（20 分）
     - 当前节气 ∈ `seasonal_solar_terms` → +20
     - 下一节气 ∈ → +10
     - 不匹配 → 0
   - 星座趣味（10 分）
     - 按 zodiac 与菜的某种「星座友好」映射（火象 → 辛辣、土象 → 务实家常、风象 → 多样、水象 → 滋补），仅彩蛋，不强烈影响
   - 心情适配（20 分）
     - `tired` → 高蛋白 + B 族加分
     - `stressed` → 暖胃 + 易消化加分
     - `anxious` → 富含色氨酸（鸡蛋、牛奶、燕麦）加分
     - `happy` → 不加不减
   - 营养均衡（20 分）
     - 取用户最近 3 天 `DailyLog.chosen_food_ids` → 看营养偏差 → 给互补的菜加分（如近 3 天高脂 → 给低脂加分）
     - 历史不足 3 天 → 默认 10 分

4. **去重与多样性**
   - 取 Top 6 候选 → 保证不同 `category`（不能 3 个都是汤）
   - 同 `cooking_method` 不超过 2 道
   - 最终取 Top 3

5. **理由生成**
   - 对每道入选菜，根据其得分项组合自然语言：
     - 例：「适合今日的【冷天 + 暖胃】场景，含高蛋白可缓解你的疲惫感，与你近三天偏油腻的饮食互补。」

### Backend

#### `app/services/recommender.py`

```python
async def recommend(session, user: User, req: RecommendRequest) -> RecommendResponse:
    profile = profile_service.get_profile(session, user.id)
    weather = await weather_client.get_current(req.lat or 0, req.lng or 0)
    today = solar_terms.get_today_context()
    history = daily_service.get_recent(session, user.id, days=3)
    foods = food_service.get_all(session)  # MVP 全量；后续可缓存

    candidates = filter_forbidden(foods, profile)
    candidates = soft_demote(candidates, profile)
    scored = [
        (food, score(food, weather, today, profile, history, req.mood, req.activity_level))
        for food in candidates
    ]
    top6 = sorted(scored, key=lambda x: -x[1])[:6]
    top3 = ensure_diversity(top6)
    return RecommendResponse(
        foods=[FoodWithReason.from_food(f, reason=f, score=s) for f, s, reason in top3],
        context=RecommendContext(weather=weather, today=today),
    )
```

#### `app/schemas/daily.py`

- `RecommendRequest`、`RecommendResponse`、`FoodWithReason`、`RecommendContext`

#### 路由 `app/api/v1/daily.py`

- `POST /daily/recommend` → 登录依赖，调 `recommender.recommend`
- 不写 `DailyLog`（用户选了才写，T11）

#### 测试 `tests/services/test_recommender.py`（必须充分）

- **测试用例覆盖**：
  - 用户忌口 `pork` → 红烧肉被剔除
  - 体质湿热 → 油炸菜分数 ≤ 50
  - 天气 cold + 体质阳虚 → 温热性菜排名靠前
  - 节气立秋 + 银耳羹 → 排名靠前
  - 心情 tired + 鸡蛋菜 → 排名靠前
  - 历史 3 天高脂 → 低脂菜加分
  - 多样性：Top 3 不同 category
  - 理由文本含关键词
- mock `weather_client`、`solar_terms`、`food_service`、`profile_service`、`daily_service`，专注于 recommender 本身

### Frontend

本任务**不**做前端 UI（留给 T11），仅确保 `npm run gen:api` 后接口类型可用。

## Acceptance Criteria

- [ ] `POST /daily/recommend` 返回 3 道菜 + 每道菜理由 + 上下文（天气、节气、星座）
- [ ] 忌口冲突的菜绝不出现
- [ ] 单测 ≥ 8 个用例，覆盖主要分支
- [ ] 推荐结果稳定（相同输入多次调用一致，缓存除外）
- [ ] 推荐耗时 < 500ms（200 道菜全量打分）
- [ ] pytest 全绿，覆盖率 ≥ 80%

## Dependencies

- T05（用户 profile，含忌口与体质）
- T06（体质判定结果）
- T07（食物库冷启动）
- T08（节气与星座）
- T09（天气数据）

## Notes

- 推荐是「规则 + 打分」，不引入机器学习
- 理由文本要自然，避免机械堆砌关键词
- `weather_tag` 由后端在 weather_client 里映射，不暴露和风原文给算法
- 不实现 A/B 测试、不实现用户反馈学习（P2）
- 当食物库 < 100 道时，算法仍可工作（T07 保证 ≥ 200）
