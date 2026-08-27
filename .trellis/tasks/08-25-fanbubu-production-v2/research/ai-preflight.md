# CloudBase AI 预检记录

日期：2026-08-26  
目标环境：`cloud1-d8gz4jm8vb964a1c9`

按 `ai-model-wechat` 的强制顺序尝试了三项只读查询：

1. `tcb env list --json`
2. `DescribeActivityInfo(ActivityNames=[ai_miniprogram_inspire_plan])`
3. `DescribeAIModels(EnvId=cloud1-d8gz4jm8vb964a1c9)`

三项均在请求云端资源前被本机 CLI 拒绝，统一返回：`No valid identity information, please use cloudbase login to login`。因此当前没有资格声称成长计划或某个模型组已经可调用，也没有在小程序代码中写入 `wx.cloud.extend.AI.createModel(...)`。

后续恢复步骤：

1. 由环境所有者在本机执行 `tcb login` 完成身份授权；
2. 重跑成长计划资格查询；命中后才选择 `hunyuan-exp`；
3. 重跑 `DescribeAIModels`，确认组状态为 1 且目标模型确实存在；
4. 预检通过后才实现真实模型适配器并在体验版验证；
5. 未通过前 `VITE_AI_MEAL_INTENT_ENABLED` 保持关闭。

本阶段已独立完成不依赖模型权益的后端 `MealIntent` 契约、食材硬过滤与有界软评分；它们是加法兼容变更，不会使基础推荐依赖 AI。
