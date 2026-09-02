# 候选目录现状审计

## 1. 审计范围与结论

审计日期：2026-08-28（Asia/Shanghai）

本次只做只读审计与方案研究，未修改生产代码、数据库迁移、`food_seed.json`、`recipe_seed.json` 或外食规则。

已检查：

- `.trellis/spec/backend/index.md`
- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `backend/app/models/food.py`
- `backend/app/models/recipe.py`
- `backend/app/services/food_seed.py`
- `backend/app/services/recipe_seed.py`
- `backend/app/services/external_dining.py`
- `backend/data/food_seed.json`
- `backend/data/recipe_seed.json`
- `backend/data/recipe_review_manifest.json`
- `backend/scripts/validate_food_seed.py`
- `backend/scripts/validate_recipe_seed.py`
- `backend/scripts/build_recipe_seed.py`
- 相关 seed、外食、Recipe service、迁移与 API 测试。

一句话结论：**家庭候选的数量已经到位，外食数量和全目录的数据治理没有到位。** 当前有 205 个家庭候选、120 份完整菜谱、57 个外食方向。距离 500+ 的主要工作是把外食扩到约 300，并为两类候选补齐可用于推荐的结构字段、来源、审核、稳定身份与去重机制，而不是再造 295 份假装完整的菜谱。

## 2. 自动化审计摘要

### 2.1 当前 validator 结果

| 命令 | 结果 | 说明 |
|---|---|---|
| `python backend/scripts/validate_food_seed.py` | exit 0 | 205 条；体质、四项营养 100%；节气 103/205（50%） |
| `python backend/scripts/validate_recipe_seed.py` | exit 0 | 120 条；结构、角色、营养、熟制、食材量化通过旧门槛 |

两个脚本都通过，但这不是“数据已经可信”的证明。它们只证明数据满足当前脚本写下的门槛，而当前门槛没有检查候选公共分类、来源覆盖、审核状态、语义重复，也把节气完整率停在 50%。交通灯是绿的，因为传感器只接了半根线。

### 2.2 总量

| 数据集 | 总数 | 唯一名称 | 当前目标差距 |
|---|---:|---:|---:|
| 家庭 Food seed | 205 | 205 | 已达到 205–250 下限 |
| Recipe seed | 120 | 120 | 保留；未来渐进扩到 180–240 |
| 外食规则候选 | 57 | 57 | 距 300 还差 243 |
| 当前候选方向合计 | 262 | 两类 exact-name 交集为 0 | 距 500 至少差 238 |

注意：家庭与外食 exact-name 交集为 0，并不说明没有语义重复。外食大量使用“某菜 + 米饭/青菜/套餐”的组合名，必须做结构化近重复审查。

## 3. 家庭候选审计

### 3.1 基础分布

`food_seed.json` 顶层为 205 条记录，名称全部唯一。现有字段为：

`name, category, ingredients, calories_kcal_per_100g, nutrition, nature, flavor, organ_meridians, suitable_constitutions, suitable_weathers, forbidden_for, tags, cooking_method, cooking_time_min, seasonal_solar_terms, description`

`category` 分布：

| category | 数量 | 占比 |
|---|---:|---:|
| stir_fry | 78 | 38.0% |
| soup | 30 | 14.6% |
| staple | 27 | 13.2% |
| stew | 26 | 12.7% |
| cold_dish | 19 | 9.3% |
| steam | 12 | 5.9% |
| congee | 8 | 3.9% |
| deep_fry | 2 | 1.0% |
| other | 2 | 1.0% |
| cold | 1 | 0.5% |

`cooking_method` 分布：

| cooking_method | 数量 |
|---|---:|
| stir_fry | 83 |
| soup | 30 |
| stew | 27 |
| steam | 18 |
| boil | 16 |
| cold | 13 |
| congee | 8 |
| other | 8 |
| deep_fry | 2 |

结论：`category` 同时混入了烹饪方式、菜品角色和产品类型，例如 `cold` 与 `cold_dish` 并存。它能支撑旧代码，却不适合作为 500+ 目录的唯一分类层。新增 `meal_family/sub_family` 必须受控，旧字段只做兼容。

### 3.2 营养完整不等于营养可信

- 205/205 有 `calories_kcal_per_100g`；
- 205/205 的 `nutrition` 都有 `protein_g/fat_g/carb_g/fiber_g`；
- 205/205 有非空描述；
- 0/205 有 `source_url` 或 `nutrition_source_url`；
- Food 模型没有 `nutrition_basis` 字段。

这意味着当前营养的**结构完整率为 100%，证据可追溯率为 0%**。USDA FoodData Central 明确区分分析值、研究文献、膳食调查编制值、制造商标签和历史数据库等数据类型；来源类型本身就是营养数据含义的一部分，不能只存一个数字就假装上下文不存在。[USDA FoodData Central 数据文档](https://fdc.nal.usda.gov/data-documentation/)

建议：数字营养值发布前必须同时具备 `nutrition_source_url` 和 `nutrition_basis`，并标注来源类型/估算方式。

### 3.3 节气完整率不达新要求

- 103/205 有具体节气；
- 102/205 是空列表；
- 24 个节气键在全体数据中均有出现；
- 当前 validator 仅要求 >=50%，所以 103/205 刚好通过。

新要求是 100% 非空，但必须允许 `[all_season]`。对于无可靠季节依据的 102 条，正确做法是先标 `all_season`，不是让脚本随机撒上节气粉末。

UNESCO 对二十四节气的权威描述是基于太阳周年运动和季节、天文、自然现象观察形成的知识与社会实践，并用于农业和日常生活安排；该来源并没有把每一道菜映射为医疗功效。因此目录可把节气作为文化/季节性轻量信号，但不能把它升级成治疗推断。[UNESCO 二十四节气非遗条目](https://ich.unesco.org/en/RL/the-twenty-four-solar-terms-knowledge-in-china-of-time-and-practices-developed-through-observation-of-the-suns-annual-motion-00647)

### 3.4 性味、体质与功效表述风险

`nature` 分布：

| nature | 数量 |
|---|---:|
| neutral | 107 |
| cool | 52 |
| warm | 46 |
| cold | 0 |
| hot | 0 |
| unknown | 0（当前枚举不允许） |

同时：

- 205/205 有非空 `suitable_constitutions`；
- 205/205 有非空 `organ_meridians`；
- 57/205 有 `forbidden_for`；
- 38/205 的 `description` 命中“清热、解毒、祛湿、润肺、补气、养胃、滋阴、健脾、补血、安神、降火、利尿、活血、温补、驱寒”等功效性词组；
- 当前 Food validator 不扫描这些描述，Recipe validator 也只扫描 Recipe 步骤和营养依据。

样例包括：

- “养胃安神，适合脾胃虚弱者”；
- “清热解暑利尿，夏季首选凉菜”；
- “润肺养阴安神，秋燥时节最佳甜羹”；
- “温补气血暖身”；
- “清热解毒消暑”。

这些文案不一定全部错误，但当前数据没有来源字段，系统却会把 `nature`、`suitable_constitutions` 和 `forbidden_for` 用于推荐加权甚至硬过滤。风险不是“传统文化不能出现”，而是**没有证据、没有 unknown、没有语义边界，却把文化标签装成了个体安全结论**。

建议：

1. `nature` 增加 `unknown`，不设 unknown 比例惩罚；
2. `unknown` 在评分中走中性基准；
3. 无依据的归经/体质数组留空，不自动补齐；
4. 过敏、宗教/伦理忌口、明确食材排除与体质标签分开；
5. 公开描述删改无依据的治疗/预防式断言，传统文化信息若保留需明确语境且不参与医疗判断。

WHO 2026 年健康饮食事实页将充分、平衡、适度、多样与安全列为核心原则，并强调健康饮食构成取决于个体特征、文化语境、当地食物和饮食习惯；这支持目录用结构字段提供多样性与情境匹配，但不支持按一条未经来源的“性味”标签给出万能健康结论。[WHO Healthy diet](https://www.who.int/news-room/fact-sheets/detail/healthy-diet)

### 3.5 新目录字段覆盖为零

以下字段在 `food_seed.json` 中均为 0/205：

| 字段 | 当前覆盖 |
|---|---:|
| `meal_family` | 0% |
| `sub_family` | 0% |
| `cuisine_region` | 0% |
| `staple_type` | 0% |
| `protein_types` | 0% |
| `serving_style` | 0% |
| `meal_periods` | 0% |
| `delivery_fit` | 0% |
| `price_band` | 0% |
| `source_url` | 0% |
| `review_status` | 0% |

当前 tag 也不足以可靠反推这些字段：`pork=55`、`beef=19`、`egg=17`、`seafood=16`、`fish=13`，没有 poultry，且 fish/seafood 粒度重叠；`easy/quick` 又和蛋白、菜系混在同一数组。迁移必须人工/规则辅助复核，不能直接把 tag 批量改名后宣布完成。

### 3.6 静态 seed 与运行时状态不一致

`food_seed.json` 本身没有 `meal_role`、`recipe_ready`、`visual_key`。这三个字段由 `import_recipe_seed()` 在数据库运行时回写 Food：

- 静态审计看到 205 条 `meal_role` 全空、`recipe_ready` 全 false；
- 导入 Recipe 后应有 120 条 ready，并写入 50/50/20 角色。

因此后续 validator 必须支持**跨文件联检**，不能只看一个 seed 就判断 recipe readiness。数据库导入测试仍需验证 Recipe importer 的回写结果。

## 4. Recipe 审计

### 4.1 结构与数量

- 120 条、120 个唯一 `food_name`；
- 50 main、50 vegetable、20 staple；
- 83 easy、36 medium、1 hard；
- 全部 `version=2`；
- 全部有 4–6 步、量化食材、熟制提示、每份营养和 `nutrition_basis`；
- 每份能量范围 67–785 kcal；
- 120 个 `visual_key` 全部唯一。

这 120 条是应保护的高价值基线，不能在 500+ 口径里被稀释成“只是 120 个名字”。

### 4.2 来源与审核清单缺口

- 120/120 都有 `source_url` 属性，但值全部为 null；
- `nutrition_basis` 只有 4 个不同模板，分别按约 220g、240g、250g、350g 成品从 Food 的每 100g 值等比例估算；
- Recipe 的营养最终追溯到 Food，而 Food 没有营养来源，所以链条仍止于无来源数字；
- `recipe_review_manifest.json` 记录 dataset v2 的新增 60 条，60/60 status=reviewed，另有 20 条人工样本；
- 其余 60 条不在该 manifest 中。

用户已确认现有 120 份均作为审核菜谱保留；实施时仍需把 manifest 扩成覆盖全量 120 的审计格式，并如实记录历史审核依据。不能把缺失的 reviewer/time/source 用脚本自动编出来——机器很勤快，伪证也会造得很整齐。

### 4.3 validator 扩容阻塞

当前 `validate_recipe_seed.py` 硬编码：

- 总数必须恰好 120；
- role 必须恰好 50/50/20。

因此它能很好地守住当前基线，却会把第 121 条合格 Recipe 视为错误。后续应拆成：

1. 现有 120 基线集合不可丢失；
2. 全量 Recipe 满足结构/安全规则；
3. 新增 batch <=30 且有批次 manifest；
4. 全量目标范围 180–240 可配置；
5. 角色分布用下限/比例或版本化目标，不再永久锁死 50/50/20。

Schema.org 的 Recipe 类型将烹饪方法、营养、类别、菜系、结构化食材、步骤与产量作为不同属性，说明分类、菜系、食材/步骤和营养本来就是不同维度；现有 Recipe 已覆盖其中多数执行字段，新目录字段不应反向塞进步骤文本。[Schema.org Recipe](https://schema.org/Recipe)

## 5. 外食候选审计

### 5.1 数量与结构

`RULE_CANDIDATES` 共 57 条：

- 36 `individual`；
- 21 `shared`；
- 57 个唯一 dish name；
- 57 个 `meal_format` 值，但唯一值 56 个；`steamed_set` 在个人与共享各出现一次；
- 与家庭 Food exact-name 重合 0 条。

当前每条包含：

`dish_name, category, energy_min/max, forbidden_tags, nutrition_note, warming, cooling, high_protein, meal_format, serving_style`

缺少：

- 稳定业务 key（现有 key 是 `sha1(category:dish_name)`，改名/改分类就变）；
- `meal_family/sub_family/cuisine_region/staple_type/protein_types/meal_periods/delivery_fit/price_band`；
- `source_url/source_type/review_status/reviewer/version`；
- 可审计的季节标签与 `nature=unknown`；
- 独立 seed/importer/validator。

### 5.2 category 伪多样性

57 个候选恰好有 57 个中文 category，每个 category 只出现一次，例如“家常盖饭、砂锅简餐、均衡套餐、粥品套餐、汤面、蒸菜套餐……”

这在 UI 文案上很花哨，在统计上几乎不可用：每类样本数都是 1，无法衡量覆盖、约束单类占比或学习偏好。应保留 `category` 作为展示文本，另建立受控的 `meal_family/sub_family`。

### 5.3 当前轮换优势与迁移约束

现有外食逻辑有几个必须保留的正确边界：

- 忌口在排序/轮换前硬过滤；
- audience 决定 individual/shared；
- 每批优先不同 `meal_format`；
- 七日曝光历史避免重复；
- request id 可重放；
- 高质量带内做稳定探索；
- 用户喜欢的真实店+菜只进入个人推荐，且仍受历史约束；
- 事件不会持久化城市或搜索关键词。

迁移到数据库不能把这些好东西顺手扔掉。新目录只替换候选来源，响应结构与轮换/隐私边界保持不变。

### 5.4 来源与营养边界

当前 `source="rules"` 只表示推荐来源是规则，不是内容证据。57 条都没有来源 URL 或审核状态。能量使用宽区间，营养文案通常也主动声明少油、少盐或商户差异，这比伪精确热量稳妥，应保留该风格。

Schema.org 的 MenuItem 把 `nutrition`、`offers`（价格/可售）和 `suitableForDiet` 分成不同属性；它提醒我们“餐型是什么”“价格如何”“适合何种饮食限制”是不同事实来源。目录的 `price_band` 不能被当成实时报价，营养也不能从一个泛化餐型名凭空推导。[Schema.org MenuItem](https://schema.org/MenuItem)

## 6. 数据质量缺口优先级

### P0 — 发布前必须解决

1. 500+ 的 approved 口径、稳定 key 和审核状态尚不存在；
2. Food 数字营养来源覆盖 0%，Recipe 来源 URL 覆盖 0%；
3. 所有 Food 都被强制分配 nature，没有 `unknown`；
4. 38 条描述存在未经来源支撑的功效性文案，当前 validator 不扫描；
5. 体质标签会影响硬过滤，但来源/审核字段缺失；
6. 外食只有 57 条，距离 300 约差 243。

### P1 — 扩容时必须同步解决

1. 11 个公共分类/来源/审核字段在家庭数据覆盖均为 0%；
2. 节气只有 103/205，旧门槛为 50%；
3. 外食 57 个 category 全部只出现一次，无法做覆盖度统计；
4. Food 按 name upsert，外食 key 随 category/name 改变，身份不稳定；
5. Recipe validator 写死 120 与 50/50/20，阻断合格扩容；
6. Recipe review manifest 只覆盖后 60 条。

### P2 — 可在兼容迁移后优化

1. Food seed 静态字段与 Recipe import 后运行时 `recipe_ready/meal_role` 有差异；
2. 205 个 Food 的 `image_url` 当前为 0（本任务不把图片设为发布门）；
3. `tags` 混合速度、难度、蛋白、菜型，且 protein 粒度不一致；
4. 现有外食 `warming/cooling` 布尔应逐步映射为允许 unknown 的公共字段；
5. `meal_format=steamed_set` 跨个人/共享重用，需明确其 sub-family 语义而非靠字符串碰运气。

## 7. 建议质量门

| 维度 | 家庭候选 | 外食方向 | Recipe |
|---|---|---|---|
| approved 数量 | 205–250 | 300–320 | 当前 120 全保留；未来 180–240 |
| 稳定 key 唯一 | 100% | 100% | 通过 Food key 关联 |
| 指定公共字段结构完整 | 100% | 100% | 不强制复制候选分类 |
| `seasonal_solar_terms` 非空 | 100%，允许 `all_season` | 100%，允许 `all_season` | 继承候选，不写入步骤 |
| `nature` 非空 | 100%，允许 `unknown` | 100%，允许 `unknown` | 不单独要求 |
| 主来源 HTTPS | approved 100% | approved 100% | approved 100% |
| 数字营养依据 | 有数值即 100% | 有数值/范围即 100% | 100% |
| 硬重复 | 0 | 0 | food_name 0 重复 |
| 近重复未决 | 0 | 0 | 批次内 0 |
| 无依据医疗/保证性承诺 | 0 | 0 | 0 |
| 批次大小 | 约 40–45 条审核 | 45–60 条审核 | <=30 |

额外外食分布门：

- individual >=180；
- shared >=90；
- 至少 10 个 meal family；
- 单 family <=20%；
- delivery high+medium >=70%。

## 8. 外部一手资料与设计含义

| 一手来源 | 核实到的事实 | 对本项目的含义 |
|---|---|---|
| [WHO Healthy diet](https://www.who.int/news-room/fact-sheets/detail/healthy-diet) | 健康饮食强调充分、平衡、适度、多样和安全；具体构成受个体、文化与当地可得食物影响 | 目录应服务多样性和可执行性，不把单一标签包装成万能健康结论 |
| [USDA FoodData Central Data Documentation](https://fdc.nal.usda.gov/data-documentation/) | 营养数据分分析值、研究文献、调查编制、制造商标签、历史数据库等来源类型 | 必须存来源类型、URL 和估算口径；字段完整不等于证据完整 |
| [UNESCO 二十四节气](https://ich.unesco.org/en/RL/the-twenty-four-solar-terms-knowledge-in-china-of-time-and-practices-developed-through-observation-of-the-suns-annual-motion-00647) | 二十四节气是基于太阳周年运动及季节/自然观察形成的知识与社会实践 | 节气可以作为文化和季节性轻量标签，不应自动变成医疗功效 |
| [Schema.org Recipe](https://schema.org/Recipe) | Recipe 分开描述 cookingMethod、nutrition、recipeCategory、recipeCuisine、ingredient、instructions、yield | 分类、菜系、营养、食材和步骤应分字段治理 |
| [Schema.org MenuItem](https://schema.org/MenuItem) | MenuItem 将 nutrition、offers、dietary suitability 分开 | 外食价格、营养、饮食限制各有独立来源与时效，不应互相臆测 |

## 9. 推荐实施顺序

1. 冻结 205/120/57 基线及旧 key；
2. 定义词表、stable key、来源与审核状态；
3. 先写新 validator/失败测试；
4. additive migration + 幂等 importer；
5. 分 5 批审核现有 205 家庭候选，先解决来源和 38 条功效文案；
6. 分 6 批把外食扩到 300–320，并用分类矩阵补缺；
7. 功能开关下切换外食读取，保留 57 条 fallback；
8. Recipe 独立按 <=30/批从 120 到 180，再评估是否继续到 210/240。

详细迁移、去重、审核和测试方案见 [design.md](../design.md) 与 [implement.md](../implement.md)。

## 10. 审计限制

- 本审计验证了现有文件、脚本和测试，没有逐条访问候选来源，因为当前数据根本没有来源 URL；
- 38 条功效性描述来自关键词筛查，是人工审核入口，不代表 38 条都能用简单正则判定真伪；
- exact-name 去重只证明字符串不相同，无法代替语义/结构去重；
- 外食价格和商户菜单具有地域与时效性，本任务只规划通用方向，不声称实时可售；
- 未对现有 205 条营养数值逐条做营养学复算；在来源补齐前，不应把 100% 字段完整当成 100% 可信。
