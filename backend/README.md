# Eat What API

“今天吃啥”微信小程序的 FastAPI 后端，提供 CloudBase 身份登录、个人档案、完整餐盘推荐、菜谱、收藏和历史记录接口。

## Runtime

- Python 3.10+
- FastAPI + Uvicorn
- SQLModel + Alembic
- SQLite（本地开发）或 MySQL/PyMySQL（CloudBase）

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

`Dockerfile` 默认监听 `${PORT:-8080}`，容器启动时依次执行数据库迁移、幂等种子导入和 Uvicorn。生产环境至少需要配置 `JWT_SECRET`、`WX_APPID`、`CLOUDBASE_ENV_ID`，正式保存数据时还需配置 MySQL `DATABASE_URL`。

当前 CloudBase 私有链路登录不需要把微信 AppSecret 放进容器或前端。完整部署步骤见 `../docs/guides/cloudbase-cloudrun-deploy.md`。
