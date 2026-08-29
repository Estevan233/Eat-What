# CloudBase AI 预检记录

日期：2026-08-26（首次，被 CLI 未登录阻塞）/ 2026-08-29（经 MCP 完成真实查询）
目标环境：`cloud1-d8gz4jm8vb964a1c9`

## 2026-08-29 预检结果（MCP callCloudApi 真实查询）

### 1. 成长计划（ai_miniprogram_inspire_plan）

- `AttendAble: false`，Reason `OverLimited`（"活动已达到最大参与次数"）
- `AttendRecords` 显示本环境（Uin 100051558681）已于 **2026-08-15 17:35:32** 参加过该活动，`Status=0`，`SubStatus="Deal:20260815681165857967801"`
- 活动有效期至 2026-12-31；不能再重复参加

### 2. 模型可用性（DescribeAIModels）

| Group | Status | 模型 | 结论 |
|---|---|---|---|
| `cloudbase` | 1 | **空** | 无可用文本模型 |
| `hunyuan-exp` | 1 | **空** | 成长计划权益未体现为可用模型 |
| `hunyuan-image` | 1 | 4 个图像模型（hunyuan-image 等） | 仅图像生成 |
| `hunyuan-v3` | 1 | `hy3-preview` | 非标准文档组（小程序 SDK 文档组为 hunyuan-exp/cloudbase/custom-*） |

### 3. 结论

**预检不通过**：两个标准文本模型组（`cloudbase`、`hunyuan-exp`）的 `Models` 列表均为空，即当前环境没有可调用的文本大模型。按既定设计：

- 不在小程序代码中写入 `wx.cloud.extend.AI.createModel(...)` 真实调用；
- `VITE_AI_MEAL_INTENT_ENABLED` 保持关闭；
- 基础规则推荐与后端 `MealIntent` 契约不受影响（它们不依赖模型权益）。

### 4. 需要环境所有者在控制台确认的事项

1. CloudBase 控制台 → AI+ → 大模型：确认文本模型（DeepSeek/混元/Kimi 等）的开启状态，检查 Token Credits 资源包余量（成长计划 8-15 已参加，但权益未见模型生效，可能需要手动开启或额度已耗尽）。
2. 若控制台确认可开启某文本模型，重跑本预检（DescribeAIModels）确认组与模型出现后再实现适配器。
3. `hunyuan-v3` 组的 `hy3-preview` 不在小程序 SDK 标准组列表中，如需使用须先在真机验证 `wx.cloud.extend.AI.createModel` 是否接受该 group。

## 2026-08-26 首次记录（已解决）

本机 CLI 未登录导致三项只读查询全部被拒（`tcb env list --json`、`DescribeActivityInfo`、`DescribeAIModels`）。该阻塞已于 2026-08-29 通过 MCP 已认证会话绕过，无需再执行 `tcb login`。
