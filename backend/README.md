# Eat What API

“今天吃啥”微信小程序的 FastAPI 后端，提供 CloudBase 身份登录、个人档案、完整餐盘推荐、菜谱、收藏和历史记录接口。

## Runtime

- Python 3.10+
- FastAPI + Uvicorn
- SQLModel + Alembic
- SQLite（本地开发）或 MySQL/PyMySQL（CloudBase 过渡链路）
- CloudBase MySQL HTTPS REST Repository（生产迁移中的安全目标链路）

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

`Dockerfile` 默认监听容器的 `PORT`，只启动 Uvicorn。数据库迁移和幂等种子导入必须在发布窗口显式执行 `/app/scripts/release.sh`，不能让多个扩容实例争着改表。

当前生产过渡配置使用 `DATABASE_BACKEND=sqlalchemy` 和 MySQL `DATABASE_URL`。HTTPS REST 客户端目前只用于独立只读验收；业务 Repository 尚未全表切换，因此生产若设置 `DATABASE_BACKEND=cloudbase_rest` 会明确拒绝启动，绝不会偷偷落到默认 SQLite。完成真实 Server API Key、过滤、Upsert、错误语义、用户隔离和投影修复验收后，再解除代码闸门并切换生产。

云托管开启“API Key 设置”后会把所选 Server API Key 自动注入为 `CLOUDBASE_APIKEY`；代码同时兼容本地/旧版本显式变量 `CLOUDBASE_DB_API_KEY`。不要为了迁就变量名再复制一份明文密钥。

当前 CloudBase 可信身份头登录不需要微信 AppSecret。保持 `ENABLE_CODE2SESSION=false`，不要把重置后的 AppSecret 放进容器、前端、Git 或聊天。完整部署步骤见 `../docs/guides/cloudbase-cloudrun-deploy.md`。
