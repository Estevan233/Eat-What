# Backend Development Guidelines

> FastAPI + SQLModel + SQLite(开发) / PostgreSQL(生产)。

---

## Pre-Development Checklist

写代码前快速过一遍：

- [ ] 新接口在 `app/api/v1/<module>.py` 加路由，并在 `app/main.py` 注册 router
- [ ] 数据模型用 SQLModel（同一个类既 ORM 又是 Pydantic schema）；如需分离用 `Model` / `Create` / `Read` / `Update` 后缀
- [ ] 业务逻辑放 `app/services/`，**禁止** 在路由 handler 里直接写查询
- [ ] 外部 API 调用放 `app/services/<name>_client.py`，必须超时 + 重试 + 缓存
- [ ] 配置走 `app/core/config.py` 的 `Settings` 类，不读裸 env
- [ ] 所有路由加依赖注入（`Depends(get_db)`、`Depends(get_current_user)`）

---

## Quality Check

- [ ] `ruff check app/` 通过
- [ ] `mypy app/` 通过（strict 模式）
- [ ] `pytest tests/` 通过，新接口必须有集成测试
- [ ] 所有外部 API 调用有 mock 测试
- [ ] 启动 `uvicorn app.main:app --reload` 无报错，`/docs` 可见新接口

---

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | app/ 模块与文件布局 |
| [Database Guidelines](./database-guidelines.md) | SQLModel、迁移、查询约定 |
| [Error Handling](./error-handling.md) | 异常类型、HTTPException、错误响应 |
| [Logging Guidelines](./logging-guidelines.md) | structlog、日志级别 |
| [Quality Guidelines](./quality-guidelines.md) | ruff、mypy、pytest 要求 |

---

## 技术栈固定版本

| 依赖 | 版本范围 | 备注 |
|---|---|---|
| python | 3.11+ | 推荐 3.12 |
| fastapi | ^0.110 | |
| uvicorn[standard] | ^0.27 | |
| sqlmodel | ^0.14 | |
| pydantic | ^2.6 | v2，与 fastapi 配套 |
| pydantic-settings | ^2.2 | |
| httpx | ^0.27 | async http client |
| lunar-python | ^3.2 | 节气/农历 |
| pytest | ^8.0 | |
| pytest-asyncio | ^0.23 | |
| ruff | ^0.3 | lint + format |
| mypy | ^1.9 | |

---

## 启动方式

```bash
# 开发
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 测试
pytest tests/

# 类型检查 + lint
ruff check app/ --fix
mypy app/
```

---

**语言**：所有 spec 文档使用中文编写，代码注释同。
