# Eat What API

“今天吃啥”微信小程序的 FastAPI 后端，提供 CloudBase 身份登录、个人档案、完整餐盘推荐、菜谱、收藏和历史记录接口。

## Runtime

- Python 3.10+
- FastAPI + Uvicorn
- SQLModel + Alembic
- SQLite（本地开发）
- CloudBase MySQL HTTPS REST Repository（生产运行链路）

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
eat-what seed-all
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

健康检查：`GET /health`。

## CloudBase

`Dockerfile` 默认监听容器的 `PORT`，只启动 Uvicorn。数据库迁移和幂等种子导入必须在发布窗口显式执行 `/app/scripts/release.sh`，不能让多个扩容实例争着改表。当前 release 脚本已按 `DATABASE_BACKEND` 分流：REST 模式通过 CloudBase HTTPS Repository 导入，SQLAlchemy 模式只用于本地/受控原生 MySQL 迁移。

当前生产运行时使用 `DATABASE_BACKEND=cloudbase_rest`，业务 Repository 已覆盖登录、档案、体质、菜品/菜谱、收藏、外食记录、推荐事件和日报投影。新版本不得配置 `DATABASE_URL`；CloudBase MySQL 公网访问保持关闭。部署后必须先运行只读契约检查，再显式运行 `--write` 验证 Insert、Update、Delete 和自动清理，两项均通过后才切换流量。

云托管开启“API Key 设置”后会把所选 Server API Key 自动注入为 `CLOUDBASE_APIKEY`；代码同时兼容本地/旧版本显式变量 `CLOUDBASE_DB_API_KEY`。不要为了迁就变量名再复制一份明文密钥。

外食候选目录默认由 `EXTERNAL_CATALOG_ENABLED=false` 保护。只有目录迁移、B0/后续批次来源审核、幂等导入和 CloudBase 影子回归完成后，才可在灰度版本将其设为 `true`；否则继续使用既有规则 fallback。

当前 CloudBase 可信身份头登录不需要微信 AppSecret。保持 `ENABLE_CODE2SESSION=false`，不要把重置后的 AppSecret 放进容器、前端、Git 或聊天。完整部署步骤见 `../docs/guides/cloudbase-cloudrun-deploy.md`。
