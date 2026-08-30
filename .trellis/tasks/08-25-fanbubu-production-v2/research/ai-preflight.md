# CloudBase AI 预检记录

目标环境：`cloud1-d8gz4jm8vb964a1c9`
最后更新：2026-08-30（结论修正）

## 结论修正说明

2026-08-29 的预检曾判定"文本模型不可用"，依据是 `cloudbase` 与 `hunyuan-exp` 组的 `Models` 均为空。该结论**已作废**——它套用的是一期成长计划的模型清单（hunyuan-2.0 系列 / `hunyuan-exp` 组）。

本环境于 **2026-08-15** 报名，属于**二期**（2026-07-01 ~ 2026-12-31）。二期文本模型为 `hy3` 与 `hy3-preview`，对应 provider 为 `hunyuan-v3`。因此"标准组为空"不等于无模型可用。

## 二期成长计划权益（来源：docs.cloudbase.net/ai/ai-inspire-plan）

| 项 | 二期（2026-07-01 ~ 2026-12-31） |
|---|---|
| Token 额度 | 10 亿 |
| 图片生成额度 | 10 万张 |
| 文本模型 | `hy3`、`hy3-preview` |
| 生图模型 | `HY-Image-3.0-Plus-4090-Tob-v1.0`、`HY-Image-v3.0-I2I-ToB-v1.0.1` |
| 有效期 | 自申请成功之日起 6 个月 |

活动细则：一个小程序帐号只能参与一次；AI 资源包仅限小程序和云开发服务端使用。

## provider 差异（来源：docs.cloudbase.net/ai/ai-inspire-plan-guide）

| 对比项 | `cloudbase` | `hunyuan-v3` |
|---|---|---|
| 免费额度 | 来源允许时优先消耗 | 仅消耗免费额度 |
| 免费额度耗尽 | 自动消耗套餐额度 | 报错 |
| 套餐额度 | 支持 | 不支持 |
| 适用套餐 | 仅限资源点套餐 | 资源点/非资源点均可 |
| 模型开关 | **需控制台手动开启** `hy3`、`hy3-preview` | **无需开启，也不支持关闭** |

**选定：`hunyuan-v3`** —— 无需控制台额外开启，直接可用。

## 环境实测（DescribeAIModels，2026-08-30）

| Group | Status | Models | 可用性 |
|---|---|---|---|
| `cloudbase` | 1 | 空 | 未开启 `cloudbase` provider 模型开关 |
| `hunyuan-exp` | 1 | 空 | 一期模型，二期不适用 |
| `hunyuan-image` | 1 | 4 个 | 仅生图 |
| **`hunyuan-v3`** | **1** | **`hy3-preview`** | ✅ **选定** |

成长计划：`AttendAble=false`（Reason `OverLimited`），本环境已于 2026-08-15 参加，不能重复报名。

## 小程序端调用方式（来源：docs.cloudbase.net/ai/sdk-reference/wxExtendAi）

基础库 3.7.1+ 内置。初始化：

```js
wx.cloud.init({ env: "cloud1-d8gz4jm8vb964a1c9" });
```

非流式：

```js
const model = wx.cloud.extend.AI.createModel("hunyuan-v3");
const res = await model.generateText({
  model: "hy3-preview",
  messages: [{ role: "user", content: "..." }],
});
// res.choices[0].message.content
```

流式：

```js
const model = wx.cloud.extend.AI.createModel("hunyuan-v3");
const res = await model.streamText({
  data: { model: "hy3-preview", messages: [{ role: "user", content: "..." }] },
  onText: (t) => {}, onEvent: (e) => {}, onFinish: (t) => {},
});
for await (const str of res.textStream) { /* 增量文本 */ }
```

> 注：使用指南页出现的 `model.invoke({model, messages})` 是服务端 SDK 风格，小程序端应使用 `generateText` / `streamText`。

## 待办

- [ ] 在小程序模拟器/真机实调一次 `hunyuan-v3` + `hy3-preview`，确认扣费与响应正常
- [ ] 若需使用 `hy3`（非 preview），需在控制台 `cloudbase` provider 下手动开启
