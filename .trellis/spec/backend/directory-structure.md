# Directory Structure

> backend 模块组织规范。

---

## Overview

FastAPI 项目按「路由 → 服务 → 模型」分层。**禁止反向依赖**：services 不 import api，models 不 import services。

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI 入口：app = FastAPI()、router 注册、中间件
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Settings (pydantic-settings)
│   │   ├── security.py        # JWT 生成/解析、密码 hash
│   │   ├── deps.py            # 通用依赖：get_db、get_current_user
│   │   └── logging.py         # structlog 配置
│   ├── db.py                  # engine + session factory
│   ├── models/                # SQLModel 表定义
│   │   ├── __init__.py
│   │   ├── user.py            # User、UserProfile
│   │   ├── daily.py           # DailyLog
│   │   ├── food.py            # Food、FoodTag
│   │   └── favorite.py        # Favorite
│   ├── schemas/               # 纯 Pydantic 入参出参（与 model 分离时）
│   │   ├── __init__.py
│   │   ├── auth.py            # LoginRequest、TokenResponse
│   │   ├── daily.py           # RecommendRequest、RecommendResponse
│   │   └── profile.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py    # APIRouter 聚合
│   │       ├── auth.py        # /auth/wx-login
│   │       ├── profile.py     # /profile
│   │       ├── daily.py       # /daily/recommend
│   │       ├── food.py        # /food、/food/{id}
│   │       ├── favorite.py   # /favorite
│   │       └── community.py   # /community
│   ├── services/              # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── recommender.py     # 推荐算法（核心）
│   │   ├── constitution.py    # 体质判定
│   │   ├── weather_client.py  # 和风天气 API
│   │   ├── solar_terms.py     # 节气/星座计算
│   │   └── food_seed.py       # 食物库冷启动导入
│   └── utils/
│       ├── __init__.py
│       ├── datetime.py        # 时间格式化、农历
│       └── jwt_helper.py
├── data/
│   └── food_seed.json         # 食物库冷启动数据
├── tests/
│   ├── conftest.py            # pytest fixture：test client、test db
│   ├── test_auth.py
│   ├── test_recommender.py
│   └── test_api_v1/
│       ├── test_daily.py
│       └── test_food.py
├── alembic/                   # 迁移版本（如启用，初期可不用）
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Module Organization

### 新增接口流程

1. 在 `app/models/<domain>.py` 定义/修改 SQLModel 表
2. 在 `app/schemas/<domain>.py` 定义请求/响应 schema
3. 在 `app/services/<domain>.py` 写业务逻辑
4. 在 `app/api/v1/<domain>.py` 加路由，调用 service
5. 在 `app/api/v1/__init__.py` 注册新 router（如为新模块）
6. 在 `tests/test_api_v1/test_<domain>.py` 加集成测试

### 新增 service 流程

- service 类用普通函数即可，不用类（除非有状态）
- service 函数签名：第一个参数总是 `session: Session`（来自 SQLModel）
- 外部 API 客户端类放 `services/`，类名以 `_Client` 或 `_client` 结尾

---

## Naming Conventions

| 类型 | 规则 | 例子 |
|---|---|---|
| 文件 | snake_case | `weather_client.py` |
| 类 | PascalCase | `WeatherClient`、`User` |
| 函数 | snake_case | `get_today_recommend()` |
| 常量 | UPPER_SNAKE | `CACHE_TTL_SECONDS = 3600` |
| 模型表名 | 复数 snake_case | `users`、`daily_logs`、`foods` |
| 字段 | snake_case | `created_at`、`user_id` |
| 路由路径 | kebab-case | `/api/v1/daily/recommend` |
| 测试函数 | `test_<被测>_<场景>` | `test_recommend_filters_forbidden_food` |

---

## Examples

- 模型示例：`app/models/user.py`
- Service 示例：`app/services/recommender.py`
- 路由示例：`app/api/v1/daily.py`
- 测试示例：`tests/test_recommender.py`
