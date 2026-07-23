# Quality Guidelines

> 后端代码质量基线。

---

## Overview

- Lint + Format：**ruff**（替代 black + isort + flake8 + pyupgrade 全部功能）
- 类型检查：**mypy** strict 模式
- 测试：**pytest** + **pytest-asyncio**
- 提交前：`ruff check app/ && mypy app/ && pytest tests/` 全部通过

---

## Forbidden Patterns

### Python

- ❌ `print()` —— 用 structlog
- ❌ `# type: ignore` 无注释说明原因 —— 必须带 `# type: ignore[code]  # 原因`
- ❌ `Any` —— 用 `object` 后 cast 或用泛型
- ❌ `eval()` / `exec()` / `__import__` 反射
- ❌ mutable default 参数：`def f(x=[])` —— 用 `Optional[list] = None`
- ❌ 模块级副作用（导入时执行 IO/网络）—— 包到函数里

### FastAPI

- ❌ 在路由 handler 里直接查数据库 —— 走 service
- ❌ 在 service 里直接 `raise HTTPException` —— 抛 `AppError`
- ❌ 同步 IO 阻塞 event loop（`requests.get`、`time.sleep`）—— 用 `httpx` async / `asyncio.sleep`
- ❌ 不带超时调外部 API —— 必须 `httpx.AsyncClient(timeout=...)`
- ❌ 路由没加权限依赖（公开接口除外）—— `Depends(get_current_user)`

### SQLModel / SQLAlchemy

- ❌ 在 model 上加业务方法 —— 业务逻辑放 service
- ❌ 不指定 `Field(max_length=...)` 给字符串列 —— 数据库列类型模糊
- ❌ 把密码、token 字段做 `repr=True` —— 模型 `__repr__` 不应泄露

---

## Required Patterns

- ✅ 路由函数签名：`async def endpoint(req: ReqSchema, user: User = Depends(get_current_user), session: Session = Depends(get_db))`
- ✅ Service 函数返回纯数据/DTO，不返回 ORM 模型（除非只读）
- ✅ 所有外部 API 调用：超时 + 重试 + 限流处理
- ✅ Settings 用 `pydantic-settings`，不读裸 env
- ✅ 启动时检查必填 env，缺失即 fail（不要默认空值）
- ✅ 路由分组：`/api/v1/`，未来 v2 不破坏 v1

---

## Testing Requirements

### MVP 阶段

| 模块 | 测试要求 |
|---|---|
| `app/services/recommender.py` | 必须有打分算法的单元测试（覆盖天气/体质/忌口分支） |
| `app/services/constitution.py` | 必须有判定结果单测 |
| `app/services/solar_terms.py` | 必须有节气计算单测（多个固定日期对照） |
| `app/services/weather_client.py` | mock httpx 测试 |
| `app/api/v1/*` | 集成测试（test client + test db） |
| `app/models/*` | 不强制（关系约束在 db 层） |
| `app/core/*` | 工具函数单测 |

### 测试结构

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from app.main import app
from app.core.deps import get_db

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)

@pytest.fixture
def client(test_db):
    def override():
        yield test_db
    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
```

```python
# tests/test_recommender.py
def test_filters_forbidden_food(test_db, sample_user_with_pork_ban):
    foods = [
        Food(name="红烧肉", tags=["pork"]),
        Food(name="番茄炒蛋", tags=["vegetarian"]),
    ]
    result = recommender.recommend(test_db, sample_user_with_pork_ban, foods, ...)
    assert all("pork" not in f.tags for f in result)
```

### 命令

```bash
pytest tests/ -v              # 全部
pytest tests/test_recommender.py -v  # 单文件
pytest --cov=app tests/      # 覆盖率
```

覆盖率目标：服务层 ≥ 80%，路由层 ≥ 60%。

---

## Code Review Checklist

- [ ] `ruff check app/` 通过
- [ ] `mypy app/` 通过
- [ ] `pytest tests/` 通过
- [ ] 新接口有 OpenAPI 文档（FastAPI 自动）+ summary
- [ ] 新接口有集成测试
- [ ] 外部 API 调用有 mock 测试
- [ ] 敏感字段没进日志
- [ ] 路由都有权限依赖（或显式 `public=True` 注释）
- [ ] 数据库迁移文件已 review（如启用 alembic）
- [ ] 接口响应统一 `{ok, code, message, data}` 包装
