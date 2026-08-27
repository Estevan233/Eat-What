# 代码基线与已确认事实

- 基线提交：`1a679017f36a606c1ecea7d599dad090eacee6bf`，`main == origin/main`。
- 隔离分支：`codex/fanbubu-production-v2`。
- 任务开始前测试：后端 347 passed；前端 17 个测试文件、59 tests passed；前端 type-check 与 lint 通过。
- 生产数据后端已有 `cloudbase_rest` Repository；本任务不得恢复 `DATABASE_URL` 运行依赖。
- `cloud-login` 已读取 CloudBase 可信身份，但只创建默认“微信用户”，没有资料完善接口和 UI。
- `recipe_seed.json` 现有 60 条，角色分布 25 main / 25 vegetable / 10 staple；Food 总数 205。
- 当前菜谱校验器固定要求 60，只校验基本结构/营养/来源格式，尚未校验时间、角色精确配额和基本熟制安全。
- 当前推荐已有七日选择/曝光惩罚和客户端软排除，但最终相同分数按 food id 决胜，未使用用户稳定探索种子。
- 当前天气只有 Open-Meteo 客户端；路由失败后回中性天气，尚无国内主源和 last-good 跨请求兜底。
- 当前前端未调用 `wx.cloud.extend.AI`。

