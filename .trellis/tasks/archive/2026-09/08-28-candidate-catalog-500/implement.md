# 500+ 结构化候选库实施计划

> 当前状态：已于 2026-08-31 确认范围并启动实施。目标为 205 个家庭候选 + 315 个外食方向，语义去重后不少于 500 个；120 个既有 Recipe 保持独立质量门。

## 实施原则

- 一次只推进一个可回滚批次；
- 先加兼容结构，再导数据，最后切读路径；
- 只有 `approved` 数据进入发布统计和线上推荐；
- 现有 205 家庭候选、120 Recipe、57 外食规则先冻结为回归基线；
- 不把来源审查、近重复审查或健康表述审查自动化成“脚本没报错，所以肯定没问题”。脚本擅长抓低级错误，不会突然长出营养学学位。

## 0. 评审与基线冻结

- [x] 0.1 评审需求口径与质量门
  - 确认家庭候选 205–250、外食 300–320、去重后总计 >=500。
  - 确认 120 Recipe 保留，未来按 <=30/批渐进到 180–240。
  - 确认 `nature=unknown`、`seasonal_solar_terms=[all_season]` 为合法完整值。
  - 确认体质/性味不承担无证据的医疗硬过滤。
  - _Requirements: R1, R3, R6, R8_
  - 已确认：外食平台菜单仅作现实存在性验证，不作为唯一主来源；新增候选按 75% 邻近扩展、20% 中国常见缺口、最多 5% 探索控制。

- [x] 0.2 生成不可变基线清单
  - 固化 205 个家庭名称、120 个 Recipe 名称及 50/50/20 角色摘要、57 个外食旧 key。
  - 记录 seed SHA256、当前 validator 输出与测试结果。
  - 记录现有 38 条功效性描述作为待清理清单，不能在迁移时静默改写。
  - _Requirements: R6, R7, R8_

- [x] 0.3 建立版本化词表
  - 定义 `meal_family/sub_family/cuisine_region` registry v1。
  - 定义 `staple_type/protein_types/serving_style/meal_periods/delivery_fit/price_band/nature/review_status` 枚举。
  - 为所有词表增加 schema fixture 和非法值测试。
  - _Requirements: R2, R3, R5_

**Review gate G0**：没有基线摘要、词表 v1 和对“不知道就填 unknown”的书面确认，不进入数据库迁移。

## 1. 先写失败测试与校验契约

- [ ] 1.1 扩展家庭 seed validator 测试
  - 覆盖 `catalog_key`、公共分类、来源、审核状态、`unknown`、`all_season` 与数组互斥。
  - 覆盖 205–250 数量范围与现有 205 名称集合不丢失。
  - 覆盖描述/说明中的无依据治疗与保证性承诺扫描。
  - _Requirements: R1, R2, R3, R4, R8_

- [x] 1.2 新建外食目录 validator 测试
  - 覆盖 300–320 总量、个人 >=180、共享 >=90。
  - 覆盖至少 10 个 family、单 family <=20%、`delivery_fit high|medium >=70%`。
  - 覆盖能量上下界、受控词表、来源状态、硬重复和近重复报告。
  - _Requirements: R1, R4, R5, R8_

- [ ] 1.3 改造 Recipe validator 测试
  - 保留 120 基线集合、50/50/20 与严格内容规则回归。
  - 增加可配置目标范围、`--batch-manifest`、每批 <=30 和全量审核 manifest。
  - 拒绝删除既有 Recipe、空来源、未量化食材和不完整熟制提示。
  - _Requirements: R4, R6, R8_

- [ ] 1.4 新建跨目录校验测试
  - 覆盖稳定键全局唯一、跨目录近重复、approved 统计、总数 >=500。
  - 对“同一道菜 + 配米饭/配青菜”等弱变体生成待审报告。
  - _Requirements: R1, R5_

**建议验证命令**：

```powershell
Set-Location backend
pytest tests/services/test_food_seed.py tests/services/test_recipe_seed.py tests/services/test_external_dining.py -q
```

**Review gate G1**：测试应先证明旧实现无法满足新契约，再开始模型与导入器实现。

## 2. 数据库与模型的兼容迁移

- [x] 2.1 为 `foods` 增加目录字段
  - 先新增 nullable/有安全默认值的字段与索引。
  - JSON 数组使用独立 default factory；避免共享可变默认值。
  - `catalog_key` 在回填完成前不立刻强制非空，避免老库升级失败。
  - _Requirements: R2, R3, R4, R7_

- [x] 2.2 新建 `external_dining_candidates` 模型与迁移
  - 包含公共字段、外食能量范围、忌口、营养说明和下单提示。
  - 为 `catalog_key` 建唯一索引，为 `(review_status,is_active)` 及主要分类建查询索引。
  - _Requirements: R1, R2, R4, R7_

- [x] 2.3 增加 legacy key alias 结构
  - 生成现有 57 条 `rule-<sha1>` 到新 `catalog_key` 的映射。
  - replay/历史读取在过渡期同时识别新旧 key。
  - _Requirements: R7_

- [x] 2.4 验证 SQLite 与 CloudBase MySQL DDL
  - SQLite 运行完整 upgrade/downgrade 测试。
  - 审阅 MySQL JSON、索引长度、布尔默认值和时间字段。
  - 升级后验证旧 205 Food、120 Recipe 可读且接口未变。
  - 2026-08-31 已在 `cloud1-d8gz4jm8vb964a1c9` 实测追加 DDL，`alembic_version=20260831_08`、`foods=205`、`external_dining_candidates=0`；备份创建因环境另一个 paused serverless 实例被平台拒绝，未强行唤醒。
  - _Requirements: R6, R7_

**建议验证命令**：

```powershell
Set-Location backend
pytest tests/test_mysql_migrations.py tests/services/test_food_seed.py tests/services/test_recipe_service.py -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

**Rollback point RP1**：只回退未承载新发布数据的 additive migration；一旦有新数据，正常回滚改为关闭读取开关并保留表/列。

## 3. 校验脚本与质量报告

- [x] 3.1 实现公共 schema/registry 校验模块
  - 统一字段类型、枚举、互斥数组、URL、审核状态和版本约束。
  - 错误必须包含文件、记录索引、`catalog_key`、字段和实际值。
  - _Requirements: R2, R3, R4_

- [ ] 3.2 扩展 `validate_food_seed.py`
  - `nature` 增加 `unknown`；节气增加 `all_season` 并要求 100% 非空。
  - 新增来源、审核、稳定键、声明扫描和数量范围。
  - 旧 50% 节气 warning 删除，改成新发布集的 100% 阻断门。
  - _Requirements: R1, R2, R3, R4, R8_

- [x] 3.3 新增 `validate_external_dining_seed.py`
  - 输出结构错误、硬重复、近重复候选和分类矩阵。
  - 支持稳定的 `--offline` 与发布前 `--check-sources` 模式。
  - _Requirements: R1, R4, R5, R8_

- [ ] 3.4 改造 `validate_recipe_seed.py`
  - 将固定 120 条改为基线保护 + 可配置扩容范围。
  - 全量 manifest 覆盖、来源及批次上限成为发布门。
  - 禁止承诺扫描扩展到所有公开文本字段。
  - _Requirements: R4, R6, R8_

- [x] 3.5 新增全目录质量报告
  - 生成 JSON 与 Markdown：计数、分布、unknown/all_season、来源状态、重复、声明扫描和 Recipe 连续性。
  - 报告中区分 schema completeness 与 evidence completeness。
  - _Requirements: R1, R4, R5, R6, R8_

**建议验证命令**：

```powershell
python backend/scripts/validate_food_seed.py --path backend/data/food_seed.json
python backend/scripts/validate_external_dining_seed.py --path backend/data/external_dining_seed.json --offline
python backend/scripts/validate_recipe_seed.py --path backend/data/recipe_seed.json
python backend/scripts/validate_candidate_catalog.py --offline
```

## 4. 导入服务：稳定键、dry-run、幂等与软停用

- [x] 4.1 改造家庭 seed importer
  - 从按 `name` upsert 迁移到按 `catalog_key` upsert。
  - 首次迁移可通过经审计的 name→key 映射绑定旧行，冲突必须失败。
  - 保持“不删除生产自建 Food”的现有保证。
  - _Requirements: R7_

- [x] 4.2 新增外食 seed importer
  - 仅导入 `approved`；默认非 destructive。
  - 支持 create/update/unchanged/conflict/retire 的 dry-run 汇总。
  - 每批单事务，任一冲突整批回滚。
  - _Requirements: R4, R7_

- [x] 4.3 增加导入幂等与冲突测试
  - 连续导入两次行数不变。
  - 展示名变化更新原记录，stable key 不变。
  - stable key/name 交叉冲突、重复 key、非法 retire 阻断。
  - 用户自建记录和未涉及记录保持不变。
  - _Requirements: R7_

**Rollback point RP2**：导入批次使用事务回滚；已发布错误记录通过批次版本软退役，不物理删除。

## 5. B0 基线迁移

- [ ] 5.1 为现有 205 家庭候选分配稳定键
  - 生成并人工检查 name→`catalog_key` 映射。
  - 不在此步骤改展示名、营养或描述。
  - _Requirements: R1, R6, R7_

- [x] 5.2 为现有 57 外食方向分配稳定键和公共分类
  - 记录 36 individual / 21 shared 基线。
  - 将 56 个唯一 `meal_format` 映射为 registry 中的 sub-family，解决 `steamed_set` 跨 style 冲突的统计语义，不破坏 API。
  - _Requirements: R2, R5, R7_

- [ ] 5.3 补齐 120 Recipe 全量审核 manifest
  - 保留现有内容和版本；补齐前 60 条的审核元数据时必须记录真实依据，不允许自动伪造 reviewer/time/source。
  - 固化 120 名称集合与 50/50/20 回归 fixture。
  - _Requirements: R4, R6_

**Review gate G2**：B0 dry-run 只能出现预期 update/bind，不得 create 重复 Food、删除 Recipe 或改变 API key。

## 6. H1–H5：现有 205 家庭候选结构化与内容清理

- [ ] 6.1 按约 40–45 条/批补齐公共字段
  - 每批覆盖所有分类、时段、主食、蛋白、来源与审核字段。
  - 不可靠的性味填 `unknown`，无具体季节依据填 `[all_season]`。
  - _Requirements: R2, R3, R4_

- [ ] 6.2 审核营养来源
  - 逐条区分每 100 克值、Recipe 每份估算与外部数据库口径。
  - 数值营养必须有 `nutrition_source_url` 与 `nutrition_basis`。
  - _Requirements: R4, R8_

- [ ] 6.3 清理不实/过度健康表述
  - 人工复核审计中至少 38 条功效性描述。
  - 将菜品风味、食材和烹饪事实与传统文化说明分开；禁止治疗性输出。
  - _Requirements: R3, R8_

- [ ] 6.4 每批执行分布与推荐回归
  - 检查不因 `unknown/all_season` 产生负向或健康理由。
  - 检查过敏/明确忌口硬过滤仍优先于软评分。
  - _Requirements: R3, R5, R8_

**每批发布门**：字段 100%、来源 100%、硬重复 0、近重复未决 0、不支持功效承诺 0、旧名称丢失 0。

## 7. H6（可选）：家庭候选补缺到最多 250

- [ ] 7.1 根据 H1–H5 分布报告确定是否需要新增
  - 仅补 `meal_family/sub_family/cuisine_region/staple_type/protein_types/meal_periods` 的真实缺口。
  - 若 205 已满足产品覆盖，不为追求上限硬加 45 条。
  - _Requirements: R1, R5_

- [ ] 7.2 对每个新增候选执行全量来源与近重复审核
  - 新名称不是合格理由，实质差异才是。
  - 家庭总数不得超过 250。
  - _Requirements: R1, R4, R5_

## 8. E1–E6：外食方向扩到 300–320

> E1–E6 合计构成最终 300–320 条发布集，并在相应批次纳入现有 57 条做复核；不是在 57 条之上再添加 300 条。`either` 不重复计数，也不用于满足个人/共享最低配额。

- [ ] 8.1 E1–E3：个人外食方向各 50 条
  - 三批累计形成 150 条 exact `individual`，首批纳入现有个人规则做迁移复核。
  - 覆盖米饭、面粉、粥/汤、点心、轻食、定食等主要 family。
  - 每批基于分类矩阵补缺，不允许 category/sub-family 一条一个新词。
  - _Requirements: R1, R2, R5_

- [ ] 8.2 E4–E5：共享方向各 45 条
  - 两批累计形成 90 条 exact `shared`，纳入现有共享规则做迁移复核。
  - 覆盖家常合菜、地域合菜、锅物/烤物和不同主蛋白组合。
  - 审核 party size 语义、共享份量提示与配送风险。
  - _Requirements: R1, R2, R5, R8_

- [ ] 8.3 E6：最多 60 条分布缺口修复
  - 只补前五批报告暴露的地域、主食、蛋白、时段、价位和 delivery gap。
  - 其中至少 30 条为 exact `individual`，把个人方向从 150 补到不少于 180。
  - 最终总数控制在 300–320，个人 >=180、共享 >=90。
  - _Requirements: R1, R5_

- [ ] 8.4 每批做来源和营养边界审核
  - 来源支持方向存在、主要组成与分类。
  - 商户配方未知时只保留宽能量范围与不确定性说明，不制造精确数值。
  - _Requirements: R4, R8_

**每批发布门**：approved 才计数；source 100%；硬重复 0；近重复未决 0；单 family 累计 <=20%；最终 high/medium delivery >=70%。

## 9. 外食服务切换与兼容

- [x] 9.1 实现 DB→现有响应的适配器
  - `sub_family` 映射到 `meal_format`，`catalog_key` 映射到 suggestion key。
  - 仅读取 approved+active；`either` 可服务个人与家庭。
  - _Requirements: R2, R4, R7_

- [x] 9.2 保留规则 fallback
  - 开关关闭、表为空、读取失败时回到 57 条现有规则。
  - fallback 必须记录结构化指标，不泄漏城市/搜索关键词等隐私。
  - _Requirements: R7_

- [ ] 9.3 回归轮换、忌口和 replay
  - 个人/共享各返回 3 条；候选充足时 format 不重复。
  - 十轮个人推荐覆盖至少 30 个方向；七日历史继续生效。
  - 旧 request id 经 legacy alias 可重放；无法解析时返回既有错误。
  - 忌口始终在轮换前过滤，绝不为凑数放回。
  - _Requirements: R5, R7, R8_

**Rollback point RP3**：关闭目录读取开关，立即恢复硬编码规则；数据库保留以便审计与修复。

## 10. R1–R4：Recipe 渐进扩容（独立发布节奏）

- [ ] 10.1 从未 recipe-ready 的 85 个家庭候选中按产品覆盖选批次
  - 每批最多 30，先补角色/餐型缺口，不按名称热闹程度挑选。
  - _Requirements: R5, R6_

- [ ] 10.2 执行 Recipe 严格审核
  - 量化非可选食材、4–6 步、关键食材出现在步骤、动物性食材熟制提示。
  - 每份营养、估算口径、来源、版本、审核清单齐全。
  - _Requirements: R4, R6, R8_

- [ ] 10.3 分阶段目标
  - R1：120→150；R2：150→180；达到最低目标后做产品评估。
  - 可选 R3：180→210；可选 R4：210→240。
  - 每阶段都验证既有 120 零丢失，不把 240 当 KPI 绑架审核质量。
  - _Requirements: R6_

**Rollback point RP4**：按 Recipe seed/manifest 版本回退本批新增，不回滚候选目录与其他 Recipe。

## 11. 全量验证、灰度与发布

- [ ] 11.1 运行静态质量门
  - 家庭 205–250、外食 300–320、去重后 >=500。
  - 公共字段 100%，硬重复 0，近重复未决 0，禁止承诺 0。
  - 外食个人/共享、family、delivery 分布全部达标。
  - _Requirements: R1-R8_

- [x] 11.2 运行后端全量检查
  - ruff、mypy、pytest 全绿。
  - CloudBase REST repository 与 MySQL migration 相关测试全绿。
  - _Requirements: R7_

- [ ] 11.3 staging 导入与影子比较
  - 连续两次导入验证幂等。
  - 比较新旧硬过滤、空池率、三条多样性、十轮覆盖和 replay。
  - 验证关闭开关可立即 fallback。
  - _Requirements: R5, R7, R8_

- [ ] 11.4 小流量发布与观察
  - 监控目录读取错误、fallback 比例、候选不足、重复率、失效来源和审核版本。
  - 任一 P0 安全/来源问题立即 retire 对应批次并关闭新读路径。
  - _Requirements: R4, R7, R8_

**建议最终命令**：

```powershell
Set-Location backend
ruff check app scripts tests
mypy app
pytest tests -q
python scripts/validate_food_seed.py
python scripts/validate_external_dining_seed.py --offline
python scripts/validate_recipe_seed.py
python scripts/validate_candidate_catalog.py --offline
```

## 12. 最终交付物

- [ ] 版本化词表与字段说明；
- [ ] additive Alembic migration 与模型；
- [ ] enriched `food_seed.json`（205–250）；
- [ ] `external_dining_seed.json`（300–320）；
- [ ] 覆盖全量的 Recipe review manifest；
- [ ] 家庭、外食、Recipe 与跨目录 validator；
- [ ] dry-run/幂等导入器；
- [ ] legacy key alias 与外食 fallback；
- [ ] 自动化测试与发布质量报告；
- [ ] staging/生产导入记录、来源审核记录和回滚演练结果。
