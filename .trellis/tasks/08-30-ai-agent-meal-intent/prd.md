# 小程序 AI Agent 用餐意图推荐

## Goal

在小程序首页加入一个紧凑的自然语言输入框，用 CloudBase 二期成长计划模型把用户输入解析成受控的 `MealIntent`，再交给既有 `rules_v6` 推荐管线处理。

AI 只负责"理解用户说了什么"，最终候选、硬过滤、营养、安全与持久化仍由后端规则服务负责。

## 技术方案（已确认，见 08-25-fanbubu-production-v2/research/ai-preflight.md）

| 项 | 决策 | 依据 |
|---|---|---|
| 调用位置 | 小程序端 `wx.cloud.extend.AI` | 前端不得持有外部大模型 API Key |
| Provider | `hunyuan-v3` | 无需控制台手动开启；仅消耗免费额度；资源点/非资源点套餐均可 |
| 模型 ID | `hy3-preview` | `DescribeAIModels` 实测 `hunyuan-v3` 组存在且 Status=1 |
| 调用方法 | `generateText({ model, messages })` | 小程序基础库 3.7.1+ 内置；非流式足够 |
| 后端 | 复用现有 `MealIntent` 契约 | `schemas/daily.py:23`、`recommender.py` 已实现校验与硬过滤/软加分 |
| 功能开关 | `VITE_AI_MEAL_INTENT_ENABLED`，默认 `false` | 验证通过后开启 |

调用示例：

```js
const model = wx.cloud.extend.AI.createModel("hunyuan-v3");
const res = await model.generateText({
  model: "hy3-preview",
  messages: [
    { role: "system", content: "<抽取规则与 JSON schema>" },
    { role: "user", content: "冰箱有番茄鸡蛋，20 分钟，少油" },
  ],
});
// res.choices[0].message.content
```

## Requirements

### R1. 输入与触发

- R1.1 首页（Today）提供紧凑输入框，占位文案提示可描述"现有食材、时间、忌口、目标"。
- R1.2 输入长度限制 1–200 字符；空输入与纯空白不得触发模型调用。
- R1.3 功能开关关闭时，输入框整体隐藏，不显示任何 AI 入口。

### R2. 模型调用

- R2.1 使用 `wx.cloud.extend.AI.createModel("hunyuan-v3")` 与 `model: "hy3-preview"`。
- R2.2 单次调用设置超时（建议 8 秒）；超时按降级处理，不阻塞基础推荐。
- R2.3 system prompt 只要求从用户文本抽取 JSON，明确禁止生成菜名、营养值、健康结论或诊断。
- R2.4 模型名与 provider 集中配置，便于后续切换到 `hy3` 或 `cloudbase` provider。

### R3. 输出解析与校验

- R3.1 剥离 Markdown 代码围栏后再解析；解析失败按降级处理。
- R3.2 严格校验 JSON：未知字段直接丢弃，字段越界（数量、取值、范围）整体失败。
- R3.3 允许的字段与边界：

  | 字段 | 类型 | 约束 |
  |---|---|---|
  | `availableIngredients` | string[] | 0–12 项，每项 ≤20 字符 |
  | `excludedIngredients` | string[] | 0–12 项，每项 ≤20 字符 |
  | `maxTimeMinutes` | int \| null | 5–180 或 null |
  | `goal` | enum \| null | `balanced` / `weight_control` / `high_protein` |
  | `diningModeHint` | enum \| null | `cook` / `eat_out` |
  | `summary` | string | ≤80 字符 |

- R3.4 校验失败时不得提交任何约束，界面提示"没太理解，可以直接选下面的条件"。

### R4. 标签复核与提交

- R4.1 解析成功后以标签形式展示结果，用户可逐项删除后再提交推荐。
- R4.2 提交时把 `MealIntent` 放入 `POST /api/v1/daily/recommend` 的 `meal_intent` 字段。
- R4.3 `diningModeHint` 只用于预填 UI，不得覆盖用户最终点击的用餐模式。

### R5. 降级与安全

- R5.1 下列任一情况必须静默降级为基础推荐，基础推荐功能不受任何影响：
  - 功能开关关闭；
  - 模型调用超时或抛错；
  - 返回内容为空、非 JSON 或校验失败。
- R5.2 降级不得弹出技术性错误文案，也不得改变既有推荐接口契约。
- R5.3 前端不得持有任何 API Key；模型凭据完全由 CloudBase 运行时注入。
- R5.4 AI 输出不得直接作为菜品 ID、营养值、菜谱内容或数据库写入依据。

### R6. 可观测性

- R6.1 记录模型调用的成功/失败/超时计数与耗时（不记录用户输入原文与模型输出全文）。
- R6.2 记录降级触发原因分类，用于判断是否值得继续投入。

## Acceptance Criteria

- [ ] AC1 — 开关关闭时首页不出现 AI 入口，基础推荐功能完全不受影响。
- [ ] AC2 — 输入自然语言后可解析出合法 `MealIntent` 并展示为可删除的标签。
- [ ] AC3 — 解析结果随推荐请求提交，后端按既有规则把 `excludedIngredients` 作为硬过滤、其余作为有界软加分。
- [ ] AC4 — 模型超时、返回非 JSON、字段越界时静默降级，基础推荐正常返回且无技术报错弹窗。
- [ ] AC5 — 自动化测试覆盖：JSON 围栏清理、字段越界、未知字段丢弃、超时降级、开关关闭降级。
- [ ] AC6 — 小程序模拟器与至少一台真机各完成一次成功解析与一次失败降级验证。
- [ ] AC7 — 前端代码中不存在任何 API Key、Secret 或硬编码凭据。
- [ ] AC8 — `ruff` / `mypy` / `pytest` / `vitest` / `vue-tsc` 全部通过。

## Out of scope

- 通用聊天机器人或多轮对话。
- 医疗诊断、体质判定、自动生成营养数值或未经校验的菜谱。
- 后端侧模型调用、模型微调、向量库或 RAG。
- 生成式图片、语音输入。
- 负反馈 UI（属于 rules_v6 任务的预留接口，不在本任务实现）。
