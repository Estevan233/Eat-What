# Phase 0 测量结果：外食推荐多样性现状

测量日期：2026-09-30
数据来源：CloudBase MySQL（cloud1-d8gz4jm8vb964a1c9）`recommendation_events` / `external_dining_candidates`，经 MCP runQuery 只读查询
窗口：全表（2026-08-17 ~ 2026-09-28，613 事件；外食 251 事件）
口径说明：曝光复用按引擎语义（event_date 的 [d-6, d] 窗口，含当日更早请求）；换一批对 = 同用户同日相邻外食请求间隔 ≤30 分钟；均为日期粒度近似。

## 核心结论：根因假设证实——池太小，7 天窗口必然耗尽

### 1. 曝光复用（外食，241 个有前史事件）

| 指标 | 值 |
|---|---|
| 任一键 7 天内已曝光（any_reuse） | **85.1%**（205/241） |
| 整批 3 个键全部 7 天内已曝光（full_reuse） | **79.7%**（192/241） |
| 平均重复键占比 | **0.82** |

近 80% 的响应整批都是一周内见过的 → 用户感知就是"重复性太高"。

### 2. 换一批重复（206 对相邻请求）

| 指标 | 值 |
|---|---|
| 至少 1 个键与上批重叠 | **63.6%**（131/206） |
| 平均重叠键数 | 0.79 / 3 |

### 3. 批内餐型重复

251 批中 20 批（**8.0%**）含重复 meal_format。`select_rotating_suggestions` 第一遍优先新餐型的设计预期恒为 0，重复全部来自池耗尽后的有界复用分支（external_dining.py:618-621）。

### 4. catalog 开关核验：线上实际为 false（PRD 待核验项关闭）

证据链：
- 753 个曝光键中：rule- 形态 592 + memory- 形态 161，**0 个 catalog_key 形态**；
- catalog 表 315 个 approved+active 中 **258 个 legacy_key 为空**（若开关开启，这些必以 catalog_key 形态出现）；
- 主力用户 distinct 键 = **57**，精确等于本地规则池大小（开关联动 315 候选不可能 708 个曝光位只落出 57 个）。

### 5. 池规模对照（Phase 1 杠杆量化）

| 来源 | 候选数 | individual | shared |
|---|---|---|---|
| 本地规则池（现生效） | 57 | ~36 | ~21 |
| catalog 已审核待命（开关 false 未启用） | **315** | **195**（另 either 15） | 105 |

打开 `external_catalog_enabled` 后个人池从 ~36 → ~195+，约 5.4 倍；57 个 legacy_key 映射保证历史曝光记录连续性。

### 6. 用户结构

- user 3 为绝对主力：236 事件，2026-08-27 ~ 09-28 活跃，distinct 键 = 57（全池耗尽）；
- 其余 7 个用户为 2026-08-31 / 09-01 的一日 guest/测试（共 15 事件）。

## Phase 1 建议动作（按优先级）

1. **打开 catalog 开关**：CloudRun EnvParams 加 `EXTERNAL_CATALOG_ENABLED=true`（updateConfig 即可，无需重新构建）。风险低：catalog 行全部 approved+active，能量区间/禁忌标签字段完整，且代码有回退（external_dining.py:710-712）。
2. **打开后复测**：同一组 SQL 指标对比（预期 full_reuse 从 ~80% 显著下降）。
3. **会话级强排除**（AC3）：在打开开关后按新池数据决定"换一批"的 7 天窗口语义。
4. 质量带（EXTERNAL_QUALITY_BAND=5）与窗口长度待新池基线确定后再调。

## 开关上线验证（2026-09-30 16:21 起）

- CloudRun eat-what-api 版本 034（config-only 重新发布，镜像未变），Status=normal；EnvParams 已含 EXTERNAL_CATALOG_ENABLED。
- `GET /__tcb_probe__` 404 为平台探针打到 FastAPI 的正常响应（无此路由但端口存活），非部署失败。
- 功能实测（guest 账号直连线上 API，6 次请求）：18/18 个 key 全部不重复，16 个 catalog 新菜（batch1-7/b-review），仅 2 个 legacy rule key。
- 当日外食事件 key 形态（13 事件 39 槽位）：catalog 33（84.6%）/ rule-legacy 6 / memory 0。
- 复测安排：正常使用数日后再跑"曝光复用/换一批"两组 SQL，与本文基线（full_reuse 79.7% / 换一批重叠 63.6%）对比，决定 7 天窗口语义与质量带。

## 查询审计

- MySQL 8.0.30-cynos；只读网关不支持 WITH，全部改写为派生表。
- 关键 requestId：总量 d97c1b68；键形态 d76a5b24；曝光复用 2a939a3f；换一批 2d8f9fbf；catalog 分布 9bec7706 / 7d76bba6；餐型重复 61c41bc9。
- 复杂自连接首次超时（ca3c6642），改为"按 (user, key, date) 去重的小表 + 区间连接"后通过。
