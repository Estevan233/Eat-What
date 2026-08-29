# 总体实施计划

- [ ] 1. 完成并评审三个子任务的 PRD、设计、实施计划和研究文件。
  - 验证：三个子目录均含 `prd.md`、`design.md`、`implement.md`。
  - _Requirement: 全部_
- [ ] 2. 先执行微信身份合并子任务。
  - 通过后端单元/集成测试、CloudBase REST fake repository 测试、前端 store/storage 测试。
  - _Requirement: 身份统一_
- [ ] 3. 再执行 rules_v6 子任务。
  - 通过 14/30 天历史、平局、节气周期、偏好偏差、多轮不重复测试。
  - _Requirement: 推荐多样性_
- [ ] 4. 执行候选库字段迁移和第一批数据扩充。
  - 先完成 schema/validator/分布报告；批量数据不得绕过审核状态。
  - _Requirement: 500+ 数据基础_
- [ ] 5. 运行全链路验证。
  - 后端：`JWT_SECRET=test-only-jwt-secret-32-bytes-minimum pytest -q`。
  - 前端：`npm test`、`npm run type-check`、`npm run build:mp-weixin`。
  - 静态：`ruff check app tests`、`mypy app`。
  - _Requirement: 全部_
- [ ] 6. 完成 CloudBase 专项代码审查和发布门检查。
  - 不自动部署；输出可部署压缩包、迁移顺序、环境变量差异和回滚步骤供用户确认。
  - _Requirement: 安全上线_

