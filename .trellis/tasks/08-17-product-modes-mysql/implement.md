# 实施计划

- [x] 完成前后端、部署与 CloudBase MySQL 只读勘察。
- [x] 核对 CloudBase 官方内网连接、VPC 与生产秘密管理要求。
- [x] 执行 `docs/superpowers/plans/2026-08-17-product-modes-mysql.md` Task 1-2：MySQL P0 与部署护栏。
- [x] 执行 Task 3-6：用餐上下文、外食记忆、外食推荐与权重解释。
- [x] 执行 Task 7-8：小程序 UI 与全量验证。
- [ ] 用户部署新版镜像并初始化 CloudBase MySQL 后，执行真实微信开发者工具/手机验收。

本地验证基线（2026-08-17）：后端 292 tests + mypy + Ruff，前端 33 tests + vue-tsc + ESLint，H5/mp-weixin 正式构建，SQLite 全量迁移与种子导入，MySQL DDL 离线编译。

执行必须严格 TDD；现有 dirty 文件和两个微信私有配置文件不得被覆盖、暂存或提交。
