# 实施计划

权威执行清单：

- docs/superpowers/plans/2026-08-11-recommendation-diversity.md

执行约束：

1. 使用 TDD，严格按清单顺序完成。
2. 当前任务采用 Codex inline 路径，不要求预填 implement.jsonl/check.jsonl。
3. project.config.json 与 project.private.config.json 属于用户文件，不修改、不暂存、不提交。
4. 后端必须通过 ruff、mypy 和完整 pytest；前端必须通过 lint、type-check、H5 与 mp-weixin 构建。
5. 最终提交必须遵守 Trellis Phase 3.4，一次展示提交分组并获得确认后执行。
6. 同步交付 Windows 微信开发者工具连接 WSL、模拟器调试和 HTTPS 真机预览文档。

## 执行结果

- [x] 新增 RecommendationEvent，并与 DailyLog 原子持久化。
- [x] 建立 Agent 候选重排协议、候选 ID 校验和 `[-15, 15]` 调整边界。
- [x] 天气分降至最高 15，加入体质/活动分项并归一化为 100 分展示。
- [x] 实现同日刷新轮换、七天选择/曝光衰减和完整候选池多样性选择。
- [x] API 契约回归、200 菜性能测试、后端全量质量检查。
- [x] API 基址环境化，修正微信 AppID，补充独立 Vitest 配置。
- [x] 生成并验证 `dist/dev/mp-weixin/app.json` 与发布构建。
- [x] 编写 `docs/guides/wechat-devtools-wsl.md`。
- [ ] 用户按指南完成微信开发者工具模拟器与扫码真机验收。
- [ ] 获用户确认后按逻辑分组提交，明确排除两个根目录微信配置文件。

验证记录（2026-08-12）：

- `ruff check app/ tests/`：通过。
- `mypy app/`：49 个源文件通过。
- `pytest tests/ -q`：237 passed，1 个既有短测试密钥警告。
- `npm run lint:check`：0 error，1 个既有 `App.vue` console warning。
- `npm run type-check`、`npm test`、`npm run build:h5`、`npm run build:mp-weixin`：通过。
- 开发构建 `app.json` 存在，生成配置 AppID 为 `wx59c5620b7a894f8e`。
