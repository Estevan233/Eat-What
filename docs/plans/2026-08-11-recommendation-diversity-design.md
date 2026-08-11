# 推荐多样性与 Agent 扩展边界设计

日期：2026-08-11

状态：待规格审查

范围：后端推荐算法、推荐事件与测试；不接入实际 Agent

## 1. 背景与问题

当前推荐器存在三个互相放大的问题：

1. 天气最高 30 分。雨天汤粥得到 30 分、其他菜只有 8 分，单个维度即可拉开 22 分。
2. 排序后只保留 Top 6，再从这 6 道里做多样性选择。候选池若已被天气筛成同一种菜，多样性函数无牌可打。
3. 推荐结果按分数与 `food.id` 确定性排序，没有记录同一天的多次曝光，也没有近期重复惩罚。

目标不是随手加入随机数。随机只能把重复问题从“稳定地重复”改成“随机地重复”，看上去热闹，底层仍旧没治。

## 2. 目标与非目标

### 2.1 目标

- 天气保留影响，但不再支配结果。
- 同一天每次刷新尽量给出未出现过的菜。
- 近 7 天选择过的菜强降权，曝光过但未选择的菜轻降权。
- 候选足够时，一批 3 道菜的品类与烹饪方式均不同。
- 保持现有 HTTP 请求与响应结构兼容。
- 为未来 Agent 候选重排预留类型化边界和可靠回退。

### 2.2 非目标

- 不接入 LLM，不增加 API Key、SDK、网络请求和调用费用。
- 不让 Agent 或任何软评分绕过忌口、过敏和体质禁忌。
- 不在本任务实现菜谱详情、份量换算或整道菜热量。
- 不引入 Alembic；MVP 仍使用 `create_all`，正式生产迁移另行处理。

## 3. 推荐管线

```text
用户/环境上下文
    ↓
硬过滤（忌口、体质禁忌）
    ↓
规则评分（天气、节气、心情、营养、体质、活动量、星座）
    ↓
可选候选重排器（当前直通；未来 Agent）
    ↓
近期曝光/选择降权
    ↓
多样性选择
    ↓
生成理由、持久化、返回 3 道菜
```

关键约束：硬过滤位于最前端，新鲜度与多样性位于 Agent 之后。即使未来模型输出发疯，最终安全约束仍由后端兜底。

## 4. 规则评分 V2

所有维度先计算基础原始分，基础原始分上限为 75。经过可选重排调整和新鲜度惩罚后得到 `final_raw`，最终按 `clamp(final_raw, 0, 75) / 75 * 100` 归一化；返回 API 的 `score` 始终保持 0～100。

| 维度 | 上限 | 规则摘要 |
|---|---:|---|
| 天气 | 15 | 高匹配 15、普通适配 6～8、明显相反 3 |
| 节气 | 15 | 当前节气 15、下一节气 8、无匹配 0 |
| 心情 | 12 | 疲惫高蛋白、压力时暖胃、焦虑时匹配食材，命中 12 |
| 营养 | 15 | 无有效历史基础 8；与近期明显偏差互补时 15 |
| 体质适配 | 10 | 命中 `suitable_constitutions` 10；无明确标签 5；不匹配 0 |
| 活动量 | 5 | 高活动量匹配高蛋白 5；轻活动量匹配低脂 3；否则 0 |
| 星座彩蛋 | 3 | 命中偏好 3，否则 0 |

### 4.1 天气分值

| 天气 | 高匹配 | 普通/中性 | 明显相反 |
|---|---:|---:|---:|
| rainy | 汤粥 15 | 其他 8 | 无单独反向惩罚 |
| snowy | 汤粥或温热性 15 | 其他 6 | 无单独反向惩罚 |
| dry | 命中润燥食材 15 | 其他 8 | 无单独反向惩罚 |
| cold | 温热性 15 | 中性 8 | 寒凉性 3 |
| hot | 寒凉性 15 | 中性 8 | 温热性 3 |
| mild/any | 全部 8 | — | — |

天气造成的最大候选差距由当前 22 分降到 12 分。天气仍然是建议，不再扮演手握生杀大权的暴君。

### 4.2 评分内部结构

引入仅在 service 内使用的类型：

```python
@dataclass(frozen=True)
class ScoreBreakdown:
    weather: float
    solar_term: float
    mood: float
    nutrition: float
    constitution: float
    activity: float
    zodiac: float

@dataclass(frozen=True)
class RankedCandidate:
    food: Food
    base_score: float
    rerank_adjustment: float
    novelty_penalty: float
    breakdown: ScoreBreakdown
    reason_phrases: Mapping[str, str]

    @property
    def final_score(self) -> float: ...
```

分项结构便于测试权重，也让未来 Agent 能读取可解释特征，而不必重新解析一段自然语言理由。

## 5. 新鲜度策略

### 5.1 当天曝光

- 查询当天全部 `RecommendationEvent`，合并出 `seen_today_food_ids`。
- 未曝光候选不少于 3 道时，已曝光菜直接从最终候选中排除。
- 未曝光候选不足 3 道时，已曝光菜以 `-30` 原始分回补，保证结果数量。

这使每次成功推荐都会改变后续推荐状态。旧测试“同输入连续请求结果完全相同”应改为：同一数据库状态下纯评分稳定，但成功推荐后下一次请求应轮换。

### 5.2 近 7 天选择惩罚

按距今天数 0～6 使用以下原始分惩罚：

```text
-30, -24, -18, -12, -8, -5, -3
```

候选足够时，近期选过的菜不会进入 Top 3；菜库不足时仍可随时间逐步恢复。

### 5.3 近 7 天曝光惩罚

对之前推荐但未选择的菜使用较轻的原始分惩罚：

```text
-12, -10, -8, -6, -4, -3, -2
```

同一道菜若同时属于已选择和已曝光，只应用选择惩罚，避免双重扣分。

## 6. 多样性重排

不再截取 Top 6。对所有经过硬过滤和新鲜度调整的候选按以下稳定顺序选择：

1. 按调整后分数降序、`food.id` 升序排序。
2. 第一轮只选品类和烹饪方式都未出现过的菜。
3. 不足 3 道时，第二轮放宽烹饪方式，但仍要求品类不同。
4. 仍不足时，第三轮只保证 food ID 不重复。

在数据允许的情况下，最终 3 道菜同时满足品类和做法互异；极小菜库则优雅降级，不因为“追求多样”反而一盘菜都端不上来。

## 7. 推荐事件模型

新增表 `recommendation_events`，不修改现有 `daily_logs`：

```python
class RecommendationEvent(SQLModel, table=True):
    id: int | None
    user_id: int
    event_date: date
    recommended_food_ids_json: list[int]
    mood: str
    activity_level: str
    weather_tag: str | None
    engine: str              # 当前为 rules_v2
    created_at: datetime
```

数据库约束：

- 为 `(user_id, event_date)` 建联合索引。
- 不设日期唯一约束，因为同一天允许多次刷新。
- 不保存经纬度、生日、身高、体重、完整体质问卷或完整候选列表。

`daily_service.record_recommendation()` 在同一次事务中：

1. upsert 当天 `DailyLog` 的最新推荐；
2. insert 一条 `RecommendationEvent`；
3. commit 并 refresh。

这样当前 UI 仍从 `DailyLog` 读取最新结果，新鲜度逻辑则从事件表读取完整曝光历史。

MVP 使用 `SQLModel.metadata.create_all`，新增独立表可以在保留现有 `dev.db` 数据的情况下创建。生产数据库启用前需改用正式迁移。

## 8. API 兼容性

本任务不修改以下外部契约：

- `POST /api/v1/daily/recommend` 请求体；
- `RecommendResponse` JSON 结构；
- `POST /api/v1/daily/choose`；
- `GET /api/v1/daily/today`；
- `GET /api/v1/daily/history`。

因此 `miniapp` 无需同步改动。用户再次点击现有“看看今天吃啥”按钮，即自然产生下一批推荐。

## 9. Agent 扩展边界

预留内部 `CandidateReranker` 协议。它不直接返回最终排序，而是返回有边界的候选调整值，避免后续新鲜度排序把 Agent 结果洗掉，也避免 Agent 用任意大分数绕开后端规则：

```python
class CandidateReranker(Protocol):
    async def rerank(
        self,
        candidates: Sequence[RankedCandidate],
        context: RecommendationRankingContext,
    ) -> Mapping[int, RerankAdjustment]: ...

class RerankAdjustment(BaseModel):
    food_id: int
    score_delta: float  # 后端强制截断到 [-15, 15]
    reason: str | None = None
```

当前使用 `IdentityReranker`，不发起外部请求。未来的 `AgentReranker` 必须遵守：

- 输入仅包含通过硬过滤的候选 ID、菜品特征和最小化用户上下文。
- 输出仅允许候选集合内的唯一 food ID、`[-15, 15]` 调整值与可选理由。
- 后端校验未知 ID、重复 ID、空结果和结构错误。
- 设置短超时与熔断；任何异常自动回退 `IdentityReranker`。
- Agent 重排后仍执行近期惩罚和多样性约束。

当前不添加 Agent SDK。协议基于 Python 类型定义，与具体模型供应商解耦。

## 10. 可观测性

成功日志新增以下非敏感字段：

- `engine=rules_v2`
- `event_id`
- `seen_today_count`
- `history_chosen_count`
- `recommended_food_ids`

不把经纬度、完整 profile 或模型提示词写入日志。

## 11. 测试策略

### 11.1 单元测试

- 各天气分支分值与上限。
- 分项总分归一化到 0～100。
- 当天曝光排除与候选不足回补。
- 7 天选择/曝光惩罚及衰减。
- 同一道菜不重复应用两种历史惩罚。
- 三阶段多样性降级。
- 硬过滤结果不被重排重新引入。
- IdentityReranker 保持顺序。

### 11.2 服务与 API 测试

- 连续两次推荐在候选充足时无交集。
- 连续四批在至少 12 道合格菜时产生 12 道不同菜。
- 每次推荐新增事件，但 `DailyLog` 始终保存最新一批。
- choose/today/history 兼容性不变。
- 现有全量测试及新增测试全部通过。

### 11.3 质量门槛

```bash
cd backend
ruff check app/ tests/
mypy app/
pytest tests/
```

若前端没有源代码变更，只执行现有前端 type-check/build 作为接口兼容抽查，不要求新增前端测试。

## 12. 发布与回滚

### 发布

1. 在开发数据库自动创建 `recommendation_events`。
2. 运行完整测试。
3. H5 连续刷新验证轮换效果。
4. 微信小程序构建后验证同一接口行为。

### 回滚

- 回退推荐器和持久化代码即可恢复旧行为。
- 新增事件表可暂时保留，旧代码不会读取它；无需为回滚删除用户数据。
- HTTP 接口无结构变化，因此前端无需配套回滚。

## 13. 关键风险

- 菜库标签质量决定多样性和体质适配上限；算法不能凭空修复错误标签。
- 当前营养字段是每 100 克数据，历史营养互补仍是启发式判断，不应宣传为医疗建议。
- `date.today()` 沿用现有服务器日期语义；跨时区部署需另设用户时区方案。
- 事件表会持续增长。MVP 仅查询最近 7 天；规模扩大后再增加保留策略或归档。
