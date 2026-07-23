# Database Guidelines

> SQLModel + SQLite（开发）/ PostgreSQL（生产）。

---

## Overview

- ORM: **SQLModel**（FastAPI 作者出品，Pydantic v2 + SQLAlchemy 2.0）
- 迁移：开发期用 `SQLModel.metadata.create_all` 直接建表；上线前引入 Alembic
- 数据库切换：开发用 `sqlite:///./dev.db`，生产用 `postgresql+psycopg://...`，通过 `Settings.database_url` 切换，代码无需改

---

## Query Patterns

### 创建/查询

```python
from sqlmodel import Session, select
from app.models import User

def get_user_by_openid(session: Session, openid: str) -> User | None:
    stmt = select(User).where(User.openid == openid)
    return session.exec(stmt).first()

def create_user(session: Session, openid: str, nickname: str) -> User:
    user = User(openid=openid, nickname=nickname)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
```

### 批量操作

```python
# 批量插入（避免循环里 commit）
session.add_all([Food(**f) for f in foods])
session.commit()

# 批量查询
stmt = select(Food).where(Food.id.in_(food_ids))
foods = session.exec(stmt).all()
```

### 事务

`Session` 本身就是一个事务作用域。复杂业务用 `with session.begin()` 显式：

```python
with session.begin():
    session.add(user)
    session.add(profile)
    # 出错自动 rollback
```

跨多事务的复杂流程很少，必要时用 `session.begin_nested()` 做 savepoint。

---

## Migrations

### 开发期（MVP 阶段）

每次模型变更：

```bash
# 1. 改 app/models/*.py
# 2. 删 dev.db 重启（开发期可接受）
rm dev.db
uvicorn app.main:app --reload  # startup 时 create_all
```

### 生产期

引入 Alembic：

```bash
alembic init alembic
alembic revision --autogenerate -m "add user table"
alembic upgrade head
```

迁移文件必须 review（autogenerate 不识别 server_default 等细节）。

---

## Naming Conventions

| 元素 | 规则 | 例子 |
|---|---|---|
| 表名 | 复数 snake_case | `users`、`daily_logs` |
| 模型类名 | 单数 PascalCase | `User`、`DailyLog` |
| 主键 | `id`，Integer，自增 | `id: int = Field(primary_key=True)` |
| 外键 | `<单数表名>_id` | `user_id`、`food_id` |
| 索引 | `ix_<table>_<col>` | `ix_users_openid` |
| 时间戳 | `created_at` / `updated_at` | DateTime，默认 `datetime.utcnow` |
| 布尔 | `is_xxx` 或 `has_xxx` | `is_active`、`has_plan` |
| JSON 字段 | 复数 + 后缀 `_json` | `tags_json`、`forbidden_tags_json` |

---

## Model 定义规范

```python
# app/models/user.py
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import String

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    openid: str = Field(unique=True, index=True, max_length=64)
    nickname: str = Field(max_length=64)
    avatar_url: Optional[str] = Field(default=None, max_length=512)

    # 个人档案（一对一可放同表）
    birthday: Optional[str] = Field(default=None)  # ISO YYYY-MM-DD
    gender: Optional[str] = Field(default=None)    # 'male' | 'female' | 'other'
    height_cm: Optional[int] = Field(default=None)
    weight_kg: Optional[float] = Field(default=None)
    constitution_type: Optional[str] = Field(default=None)
    forbidden_tags: List[str] = Field(default=[], sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.nickname}>"
```

---

## Common Mistakes

- ❌ 在路由 handler 里直接 `session.exec(...)` —— 走 service 层
- ❌ 在 service 里 `session.commit()` 后还返回 ORM 对象（id/关系可能未 refresh）—— 加 `session.refresh(obj)`
- ❌ `select(User).where(...)` 忘记 `.first()` / `.all()` —— `session.exec(stmt).first()`
- ❌ 用 N+1 查询（循环里查关联）—— 用 `select(...).options(selectinload(...))`
- ❌ 在 model 上放业务方法（充血模型）—— 业务逻辑放 service
- ❌ 字符串时间用 `datetime` 字段 —— 用 `DateTime` 列存 ISO 字符串需 `String` 列
- ❌ 删除用 `DELETE` 物理删 —— 业务上「不再使用」用 `is_active=False` 软删
