# rules_v6 排序审计与研究依据

审计日期：2026-08-28

## 结论先行

当前代码不是等待被拯救的 `rules_v1`，而是已经上线若干轮后的 `rules_v5`。它已有正确的安全边界、事件历史、轻量偏好和质量带探索。`rules_v6` 应做的是收拢和校正，而不是再套一层“新版排序器”：

1. 把对所有候选恒定的 `diversity=10` 从基础分中移出，落实成 slate 动态 7 分；
2. 把 meal intent、Agent delta 等散落加减项收回明确预算，锁定 85 + 15；
3. 把 7 天历史扩成“14 天惩罚 + 30 天画像/探索资格”；
4. 用最终分、曝光距离、稳定 seed、id 的严格序替代 `selection_order` 抢跑；
5. 节气从“节气当天/下一节气”升级为完整周期分档；
6. 在现有 category/method/ingredient 偏好上补 tag/nature，并诚实处理曝光偏差。

## 1. 本地代码基线

### 1.1 评分与版本名

证据：`backend/app/services/recommendation_ranking.py`

- 常量仍名为 `RULE_V4_WEIGHTS`，值为 nutrition 22、seasonal_wellness 18、personal_family 20、preference_history 15、feasibility 15、diversity 10，总计 100。
- `ScoreBreakdown.total` 直接累加上述六项。
- `recommender.recommend()` 在 identity reranker 下把运行引擎名映射成 `rules_v5`。也就是说代码类型名、权重名和事件版本已经错开一代，继续沿用只会让日志像族谱一样难读。
- `RankedCandidate.final_raw_score` 还会额外叠加 `rerank_adjustment`、`meal_intent_adjustment` 和 `novelty_penalty`；基础 100 分与外加项并非清晰的固定预算。

结论：v6 必须先改分数账本，再谈排序体验。否则“85+15”只会成为文档里的数学，代码继续自由发挥。

### 1.2 多样性

证据：`backend/app/services/recommendation_ranking.py` 与 `backend/app/services/meal_builder.py`

- `ScoreBreakdown.diversity` 当前对所有候选固定为 10，对候选间排序没有任何影响。
- `select_diverse()` 能按 category/method 三阶段放宽，但当前完整餐主链路没有调用它。
- 主链路实际由 `meal_builder._choose_primary()` 选择，优先避免重复 cooking_method，不检查 category。
- 替换项另行排序，存在主餐与替换项使用不同多样性语义的风险。

结论：保留两个选择器不是“解耦”，是让同一道菜在两套宇宙观里参加选秀。v6 应只保留一次动态 slate 重排。

### 1.3 新鲜度与探索

证据：`backend/app/services/recommendation_ranking.py`

- 选择与曝光惩罚均为 7 个元素，窗口是 7 天。
- 当天已曝光的惩罚为 `-30`；如果未曝光候选足够，`apply_novelty()` 会直接删除当天候选，否则才回补并扣分。
- 重复曝光会额外扣分，封顶 12；选择与曝光不重复扣分，这部分机制可以保留。
- `apply_bounded_exploration()` 已有 5 分质量带和 SHA-256 稳定随机，且 seed 包含 user/date/request/role/engine/food。
- 但它把质量带内候选直接生成 `selection_order`；`meal_builder._selection_key()` 先比较 `selection_order`，再比较最终分、id。于是 seed 顺序能早于最终分决胜，不符合 v6 锁定顺序。
- 质量带外仍只按 final score + id，缺少曝光距离 tie-break。

结论：质量带、稳定 SHA-256、事件历史都能复用；需要替换的是资格和排序键，不需要再发明一台随机数机器。

### 1.4 偏好画像

证据：`backend/app/services/recommendation_ranking.py`、`recommender.py`、`favorite_service.py`

- `PreferenceSnapshot` 已有 category、cooking_method、ingredient 三个 affinity map。
- 当前 `recommend()` 只取近 7 天 `DailyLog`，收藏则调用 `list_favorited_ids()` 读取全部仍在收藏的 id，不带时间。
- 收藏固定权重 2，选择固定权重 1；没有时间衰减，也没有曝光次数阻尼。
- 偏好分为 7.5 中性基准 + category 3 + method 2 + ingredient 2.5，最大 15。
- 当前没有负反馈模型或 API；客户端 `exclude_food_ids` 仅用于换餐软排除，不能把它偷换成“不喜欢”。

结论：category/method/ingredient 已存在，v6 不应重复实现。新增 tag/nature、30 天窗口、时间衰减和显式负反馈 seam 即可。

### 1.5 节气

证据：`backend/app/services/solar_terms.py` 与 `recommender._score_solar_term()`

- `TodayContext.solar_term_current` 来自 `lunar.getJieQi()`，只在节气当天非空。
- 排序当前节气命中 15，下一节气命中 8，否则 0。
- 普通日期无法知道正处于哪个节气周期，因此一条立秋标签可能只在立秋当天满分，第二天就突然归零；这不是分档，是断电。
- lunar-python 提供上一/下一节气对象和日期，足以在本地构建周期，无需联网或新依赖。

结论：新增内部 `SolarTermCycle`，不要更改现有 `TodayContext` 字段语义，避免前端展示被连带改变。

### 1.6 数据访问与性能

证据：`daily_service.py`、`favorite_service.py`、`recommender.py` 及现有性能测试

- `daily_service.get_recent(days=N)` 和 `get_recent_recommendation_events(days=N, as_of=...)` 已能按窗口查询；前者缺少可注入 `as_of`。
- 推荐热路径当前依次读取 profile、logs、events、catalog、favorites，已有测试限制最多 5 次 select。
- 30 天画像不要求新表，只需把同样五次查询的窗口和返回形态改正确。
- 已有 200 候选 `<500 ms` 测试可作为 v6 回归基线。

## 2. 数据字段覆盖审计

对 `backend/data/food_seed.json` 的只读统计：

| 指标 | 结果 |
|---|---:|
| Food 记录 | 205 |
| category 枚举数 | 10 |
| cooking_method 枚举数 | 9 |
| 缺少 seasonal_solar_terms | 102 |
| 缺少 tags | 4 |
| nature 枚举 | `cool, neutral, warm` |

头部分布：category 中 `stir_fry=78`，cooking_method 中 `stir_fry=83`。这意味着：

- 7 分动态多样性有实际价值，否则炒菜会凭基数优势长期霸榜；
- 102/205 没有节气标签，16 分节气项的区分度会被数据覆盖率限制；
- `nature` 目前只有三档，画像先支持现有值，并由相邻候选库任务补 `cold/hot/unknown`，排序器不能凭空猜性味。

`recipe_ready` 是运行时由 Food/Recipe 目录关联决定的安全资格，不应仅凭 food seed 是否出现同名字段判断可推荐数量。

## 3. 外部一手依据

### 3.1 候选、评分、重排的职责

[Google Recommendation Systems Overview](https://developers.google.com/machine-learning/recommendation/overview/types) 将常见推荐架构分为 candidate generation、scoring、re-ranking，并明确把显式 dislike、freshness 与 diversity 放在最终重排考虑。该页面当前标注更新于 2025-08-25。

对本项目的含义：硬过滤/候选资格、85 分单候选相关性、15 分 slate 重排应该保持分层。把 diversity 当所有候选的常量基础分，形式上有数字，行为上等于没有。

### 3.2 多样性与新鲜度

[Google Re-ranking](https://developers.google.com/machine-learning/recommendation/dnn/re-ranking) 建议通过 metadata（如 genre）在重排阶段确保多样性，并把内容年龄/最近数据用于 freshness。

对本项目的含义：使用 category 与 cooking_method 做 7 分动态 bonus、使用曝光时间做历史修正，符合重排职责；不需要为了“高级”引入模型。

### 3.3 探索的价值与边界

[Values of Exploration in Recommender Systems](https://research.google/pubs/values-of-exploration-in-recommender-systems/)（Google Research, RecSys 2021）讨论探索对 accuracy、diversity、novelty、serendipity 的影响，也指出探索存在短期用户体验成本。

对本项目的含义：探索不是全体长期未曝光菜固定加分的通行证。先设 5 分质量带，再给 30 天未曝光候选 8 分资格，可以把探索成本限制在相关性相近的区域。

### 3.4 曝光/位置偏差

[Google Scoring](https://developers.google.com/machine-learning/recommendation/dnn/scoring) 明确提醒低位置内容天然更少被点击，直接使用行为会混入 position bias。

[Recommendations as Treatments: Debiasing Learning and Evaluation](https://proceedings.mlr.press/v48/schnabel16.html)（ICML 2016）进一步说明推荐数据同时受用户自选择和推荐策略本身影响，并用 propensity 方法处理选择偏差。

对本项目的含义：当前事件只记录一批 food ids，没有展示位置和当次选择概率，无法严谨做 IPS。v6 只能采取三项诚实措施：

1. 不把未曝光或曝光未选当负反馈；
2. 对 chosen 隐式正反馈按 30 天曝光次数做平方根阻尼，降低自我强化；
3. 为未来事件位置/探索概率和显式负反馈留接口，但不宣称已经因果无偏。

如果没有 propensity 却在报告里写“已去偏”，那不叫推荐科学，叫统计学 cosplay。

### 3.5 节气 API 能力

[6tail/lunar-python 官方仓库](https://github.com/6tail/lunar-python) 是项目当前依赖的一手源码与版本来源；其 `Lunar` API 提供 `getPrevJieQi()` / `getNextJieQi()` 及对应公历日期对象。

对本项目的含义：节气周期可以纯本地计算，不增加网络依赖。边界日仍需固定日期测试，因为 prev/next 对“当天是否算近邻”的语义最容易藏一只小妖怪。

## 4. 曝光偏差与负反馈的具体判断

### 可以在 v6 做

- 正反馈只来自近 30 天收藏和实际选择；
- 收藏按创建时间衰减，选择按日志日期衰减；
- chosen 贡献除以 `sqrt(max(1, exposure_count))`；
- exposure-only 贡献 0；
- 领域函数接受显式 `not_interested/hide` 信号，默认空；
- 未来负反馈接口必须验证事件归属与 food membership。

### 不能在 v6 假装做完

- 不知道某菜展示在第几位，无法估计 position propensity；
- 不知道用户是否真正看见整批结果；
- 收藏取消当前是物理删除，无法恢复“取消收藏发生在何时”的负反馈历史；
- `DailyLog` 一天一行，只代表最终确认餐单，不等于每次曝光逐项判断；
- 没有随机策略概率，不能做可靠 off-policy evaluation。

因此本任务的“曝光偏差处理”是保守防自强化，不是无偏学习。未来若进入在线学习，应扩展 RecommendationEvent item-level exposure 位置和 exploration probability，并单独开数据迁移/隐私审查任务。

## 5. 方案比较

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| A. 新建独立 rules_v6 模块，与 v5 并存 | 回滚直观 | 复制硬过滤、历史、组餐与事件写入；两套规则必然漂移 | 拒绝 |
| B. 在现有 final score 上继续堆 +8/+7 | 改动小 | 质量带、预算和 tie-break 仍混乱；全体未曝光会被固定抬升 | 拒绝 |
| C. 原地演进类型与纯函数，统一一次重排 | 复用成熟机制；预算清晰；测试边界明确 | 需要同步更新较多既有测试 | 采用 |

## 6. 设计参数的理由

- **5 分质量带**：沿用 rules_v5 已验证阈值，避免同时改阈值和探索语义，减少变量。
- **14 天惩罚**：比现有 7 天覆盖两个完整星期，仍保持有限记忆；day 14 归零边界可精确测试。
- **当天 -45**：替代 hard exclude + fallback 双路径；在 85 分基础尺度上足够强，但安全候选不足时仍可回补。
- **30 天画像/探索**：能积累比 7 天更稳定的偏好证据，又不会把半年前一次选择当终身誓言。
- **favorite=2、chosen=1**：复用现有显式收藏高于隐式选择的关系，只新增时间与曝光修正。
- **偏好中性 7.5**：保留现有冷启动语义；画像缺失不应让新用户平白少 15 分。
- **多样性 3.5 + 3.5**：直接对应 category/method 两个已存在结构化字段，解释和测试都比模糊 MMR 系数更稳。
- **严格 tie-break**：先尊重最终质量和新鲜度，再使用 seed 提供变化，id 只兜底；这才叫可复现探索，不是按主键装命运。

## 7. 风险与依赖

- 102 道菜缺节气标签会降低 16 分节气项覆盖率；候选库任务需补标，v6 不杜撰。
- nature 只有 cool/neutral/warm，画像需容忍后续新增 cold/hot/unknown。
- SQLite 与 CloudBase 对 datetime/date 过滤类型不同，近 30 天收藏必须有双路径测试。
- 家庭多人套餐含重复 meal role，动态多样性必须按槽位逐步算，不能假设每个角色只出现一次。
- 同一 request id 的幂等重放必须排除自身历史事件并复用相同 seed，否则会出现“数据库说是旧事件，响应却是新餐单”的幽灵结果。
- Future Agent seam 仍在，但本期不得让 Agent delta 形成第 101 分或绕出质量带。

## 8. 审计后锁定项

- 采用 85 基础：营养12、体质14、节气16、天气4、偏好15、场景14、心情5、活动3、星座2。
- 采用 15 重排：多样性7、探索8。
- 14 天新鲜度；当天统一 `-45`；第 14 天归零；只取最强惩罚。
- 30 天未曝光只获得“进入 5 分质量带探索池”的资格，不对全体固定加 8。
- tie-break 固定为 final score → exposure distance → user/date/request seed → id。
- 节气采用当前周期前/中/后三档，active 16/12/8，next 0/4/8。
- 30 天画像复用 category/method/ingredient，新增 tag/nature；收藏与选择分档衰减。
- 曝光未选不是负反馈；显式负反馈只预留领域接口，持久化/API/UI 另开任务。
