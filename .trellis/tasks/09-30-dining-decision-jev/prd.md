# 轻量餐食决策：多样性优化、Jev 评估与可选附近店铺

## 目标与状态
帮助用户少纠结、选好这一餐；降低重复，提高当次需求匹配，不建设商家平台。
2026-09-30：用户确认产品边界并授权写入方案；本任务仅 planning，尚未批准模型上线或产品代码实施。
2026-09-30 二轮探讨后确认：阶段化推进（见"阶段化路线"）；Jev 采用离线预计算为主；"换一批"排除语义待 Phase 0 测量后定。
权威源码 /root/miniapp-trellis；基线 main@1cb705d；miniapp/dist/build/mp-weixin 为构建输出，不编辑。

## 已确认需求
- R1：主功能仍为"今天吃什么"；不新增地图首页、独立聊天页、必填问卷或菜单上传。
- R2："附近店铺参考"为外食的可选辅助。无定位、地图漏店、接口错误或授权不满足时，基础推荐独立可用。
- R3：优先评估腾讯位置服务；地图展示、地点搜索、微信审核、商业授权分别核验，不以同属腾讯推定免费或免审。
- R4：地图结果不代表全部餐厅；无可靠菜单时只给点单方向，不声称某店必售某菜、实时营业或可配送。
- R5：复用个人店＋菜记忆，允许没有地图 POI 的食堂、小店参与私人推荐；不建设公开商家库。
- R6：重复控制第一杠杆是候选可达性与池规模（核验线上 catalog 开关、扩充候选来源），其次才是语义近重复与跨轮多样性；不得以换名称冒充新菜。
- R7：Jev 仅用于受控候选的离线语义近重复判定（Noul 布尔断言）；不能生成菜品、店铺事实、营养数值或健康功效，不能覆盖硬约束，不参与 forbidden_tags 判定（忌口匹配留在规则侧：精确匹配＋别名表）。
- R8：模型和地图均可独立关闭；继续沿用 CloudBase HTTP Repository，不引入公网 MySQL 依赖。

## Jev 适配评估（2026-09-30 联网核查）
- Jev 是 TypeSafe AI 2026-09-15 发布的 "System One" 决策模型（early access），非 embedding、非生成模型；原语为 Noul（布尔＋校准概率）/Choice（枚举）/Score（打分）。
- 定价 $0.042/百万输入 token、输出免费，延迟 70–500ms；开源复刻 Nimble（Qwen3.5-9B 微调）可自托管。
- 形态定为离线预计算：候选两两近重复判定约 n² 次（57 个候选约 1600 次），成本可忽略；结果存为"相似度边表"，由规则消费，在线路径不调用 Jev。
- 阈值分流（利用 RLCD 校准概率）：≥0.9 自动合并、0.7–0.9 人工复核、<0.7 视为独立。
- 已知边界：中文能力未验证（gate 项，菜名全中文；Nimble 自托管路线中文可能更稳）；"零幻觉"仅指零类型错误，语义仍可能错；供应商仅两周历史，只做离线批处理、可整体回退规则别名表。
- 候选来源仍为规则目录＋catalog＋私人记忆，Jev 不新增候选。

## 现状证据
- 2026-09-30 Phase 0 实测（详见 research/phase0-measurement.md）：外食 251 事件，full_batch_reuse 79.7%（整批 3 个键全部 7 天内已曝光），换一批 63.6% 有重叠，批内餐型重复 8.0%——根因假设证实：池太小，7 天窗口必然耗尽。
- 2026-09-30 catalog 开关核验完成：线上 external_catalog_enabled 实际为 false。证据：753 个曝光键 0 个 catalog_key 形态；catalog 315 个 approved+active 中 258 个 legacy_key 为空；主力用户 distinct 键=57 恰好等于本地池。catalog 已审核候选 315 个（individual 195 / shared 105 / either 15）待命。
- external_dining.py:31 外食曝光窗口为 7 天；:32 探索质量带为 5 分；:497 探索仅在最高分质量带内；:708 候选库有开关和回退。
- 规则候选库共 57 个（external_dining.py:52-318），shared 约 21 个、individual 约 36 个；每批输出 3 个（external_dining.py:599）。
- 根因假设（待 Phase 0 验证）：个人池约 36 个 vs 每批 3 个 × 7 天窗口，曝光消耗速率超过池规模，bounded reuse（external_dining.py:618-621）频繁触发是"重复性高"的主因；语义去重解决不了池耗尽。
- request_id 幂等重放已实现（external_dining.py:720-727、:804-812、:579-583 并发兜底），AC3 幂等要求改为补测试即可。
- core/config.py:48 external_catalog_enabled 默认 false；这不是生产环境变量证据，线上实际值待核验（Phase 0 任务）。
- config.py:50-57 specialty_ai 已有"可配置开关＋超时＋缓存降级"模式，Jev 离线管线沿用同一工程原则。
- dining_memory_service.py 已实现私人店＋菜记忆及 HTTP Repository 路径，不重复造表。
- miniapp/src/ai/meal-intent.ts 已有受控意图抽取；旧任务 08-30-ai-agent-meal-intent 仍为 planning，不能仅凭状态认定未开发。
- 本任务补充旧 AI 任务的后端评估方向，不自动推翻其前端意图方案或修改旧任务状态。

## 阶段化路线
- Phase 0 测量 ✅ 2026-09-30 完成（MCP runQuery 只读直查，结论见 research/phase0-measurement.md）：full_reuse 79.7%、换一批重叠 63.6%、catalog 开关实测 false、315 候选待命。
- Phase 1 规则改进（无合规风险）：首选打开 catalog 开关（EnvParams EXTERNAL_CATALOG_ENABLED=true，updateConfig 无需重建），个人池 ~36 → ~195+；开关打开后复测同一组指标；实现会话级强排除；质量带/曝光窗口按新池基线再调。"换一批"的 7 天窗口定强约束或降权，由开关打开后的复测数据决定。
  - 2026-09-30 开关已打开并验证生效（版本 034；当日 catalog key 占 84.6%；6 次实测 18/18 key 不重复）。复测待积累数据后进行。
  - 2026-10-04 线上反馈与修复：推荐混入豆腐/菜花/洋芋擦擦等单道菜与小吃。生产证据（10-01~10-04 的 60 批曝光）：315 个 approved 候选中 `meal_family='single_dish'` 59 个 + `'snack_dessert'` 18 个（24%），全部 `staple_type='none'` 或纯点心，能量多为 150–420 kcal，约 1/6 曝光位被非完整餐占用（如 batch7-yangyu-caca 洋芋擦擦、batch7-dry-fried-cauliflower 干煸菜花、batch3-tea-tofu 茶豆腐、batch1-xinjiang-naan 烤馕）。根因：引擎加载 catalog 时忽略 `meal_family`，无"是否完整一餐"过滤。修复：`external_dining.py` 增加 `NON_MEAL_FAMILIES={'single_dish','snack_dessert'}` 加载期排除（排除数写日志，全部排除时回退内置规则库），候选数据保留在库中供未来"加一道菜"场景。修复后个体正餐池 ~159、共享正餐池 ~79（原 36/21），多样性不受损。另发现 1 个疑似误标：`冻豆腐`（soup_meal / light_soup_set / 320kcal）——留作 Phase 2 Jev 离线"完整正餐判定"审计样本。改动仅 backend，无需小程序提审；commit 1073765 留存本地分支待确认后合并。
  - 2026-10-04 部署云托管 eat-what-api-037 并验证：git archive HEAD 导出部署（未携带工作区未提交的附近店铺代码），EnvParams 经 RMW 合并保留 EXTERNAL_CATALOG_ENABLED=true。线上 guest-login 实测：个人 6 批 18 键 + 家庭 1 批 3 键全部为完整餐方向，0 个 single_dish/snack_dessert 键。
- Phase 2 Jev 离线评估：离线预计算两两近重复边表；AC5 对比扩为四组——原算法 / 纯规则改进 / 扩容后纯规则 / 规则＋Jev；中文验证集通过前不接入生产数据。
- Phase 3 附近店铺：拆为独立任务，腾讯位置服务核验通过后启动，不拖累 Phase 0–2。

## 验收标准
- AC1：不授权位置、不输入自然语言时，原有家庭/外食推荐均正常。
- AC2：已知忌口冲突不因 AI 或探索奖励重新进入结果；未知成分不宣称安全；Jev 输出不参与 forbidden_tags 判定。
- AC3：会话内已展示候选强排除；同一会话连续三次换一批不重复稳定 ID，不足时明确提示，不放宽硬约束；重试同一 request_id 保持幂等（复用 external_dining.py 现有重放机制并补测试）。
- AC4：对菜系/餐型/核心食材做语义重复统计，含同菜异名对抗样本对，不能只用 ID 去重证明多样性提升。
- AC5：用冻结数据对比原算法、纯规则改进、扩容后纯规则、规则＋Jev 四组；评审集与调参集隔离，保留负面结果。
- AC6：CloudBase 实测候选来源、筛选后数量、曝光写入/跨请求读取、用户隔离及模型失败回退；报告版本、日期、请求 ID 和脱敏证据。
- AC7：地图结果和私人记忆来源明确；无来源不得声称店内有具体菜品。
- AC8：Jev 中文质量验证集、国内云端延迟、成本、数据出境（TypeSafe API vs Nimble 自托管）与供应商早期风险审查完成前，不启用生产用户调用。

## 不做
多地图聚合、商家入驻/评论、配送承诺、菜单抓取平台、长期位置轨迹、向量数据库、多 Agent 编排、生成式营养或医疗建议、Jev 在线路径。

## 待决策
- Jev 供应形态：TypeSafe API（数据出境、early access 风险）vs Nimble 自托管（中文或更稳、需部署维护），待 Phase 0 期间完成中文验证集测试后定。
- "换一批"的 7 天窗口语义（强排除 vs 降权），待 catalog 开关打开后的复测数据定。
- 附近店铺独立任务 2026-10-01 已启动：.trellis/tasks/10-01-nearby-shops-map（核验完成，PRD 已建；wx.chooseLocation 审核中）。
