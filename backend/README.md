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

当前生产运行时配置使用 `DATABASE_BACKEND=cloudbase_rest`，业务 Repository 已覆盖登录、档案、菜品/菜谱、收藏、外食记录、推荐事件和日报投影。部署后必须先运行只读契约检查，再显式运行 `--write` 验证用户表的 Insert、按主键 Update 和自动清理；两项均通过后才做微信端灰度。`DATABASE_URL` 只保留在上一 SQLAlchemy 回滚版本，REST 灰度完成后从新版本删除并关闭公网 MySQL。

云托管开启“API Key 设置”后会把所选 Server API Key 自动注入为 `CLOUDBASE_APIKEY`；代码同时兼容本地/旧版本显式变量 `CLOUDBASE_DB_API_KEY`。不要为了迁就变量名再复制一份明文密钥。

当前 CloudBase 可信身份头登录不需要微信 AppSecret。保持 `ENABLE_CODE2SESSION=false`，不要把重置后的 AppSecret 放进容器、前端、Git 或聊天。完整部署步骤见 `../docs/guides/cloudbase-cloudrun-deploy.md`。
