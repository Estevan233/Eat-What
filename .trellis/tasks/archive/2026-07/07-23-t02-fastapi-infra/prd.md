# T02 FastAPI 基础设施

## Goal

为后端项目搭建可被业务模块复用的核心：配置、日志、数据库、安全（JWT）、依赖注入、错误体系、统一响应包装。完成后，T04 起的业务任务可直接基于这些写接口。

## Requirements

### `app/core/config.py`

- 用 `pydantic-settings.BaseSettings` 定义 `Settings`
- 字段：`database_url`（默认 `sqlite:///./dev.db`）、`jwt_secret`、`jwt_algorithm="HS256"`、`jwt_ttl_minutes=10080`（7 天）、`wx_appid`、`wx_secret`、`hefeng_key`、`hefeng_api`、`amap_key`、`environment="dev"`、`debug=True`
- 从 `.env` 读取，未填关键字段启动时 raise（`jwt_secret`、`wx_appid`、`wx_secret`）
- 单例：`get_settings()` 用 `lru_cache`

### `app/core/logging.py`

- structlog 配置（按 spec 的 `logging-guidelines.md` 实现）
- `configure_logging(debug)` 函数，开发用 ConsoleRenderer，生产用 JSONRenderer
- 提供 `RequestContextMiddleware` 注入 `request_id`

### `app/core/errors.py`

- `AppError` 基类 + `AuthError` / `NotFoundError` / `ValidationError` / `ExternalAPIError` / `RateLimitError`
- 按 spec 的 `error-handling.md` 实现

### `app/core/security.py`

- `create_access_token(user_id: int) -> str`：JWT，payload 含 `sub`、`iat`、`exp`
- `decode_token(token: str) -> dict`：失败抛 `AuthError`
- `hash_password` / `verify_password`：用 `passlib[bcrypt]`（虽然微信登录无需密码，但为后续多账号留接口）

### `app/core/deps.py`

- `get_db() -> Generator[Session, None, None]`：从 `db.py` 的 session factory yield
- `get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_db)) -> User`：解析 JWT，查 User，失败抛 `AuthError`
  - 注：本任务不创建 User 模型，可临时返回 `{id: sub}` 字典，T04 时替换为真实 `User`
- `get_settings() -> Settings`：lru_cache 单例

### `app/db.py`

- `engine = create_engine(settings.database_url, echo=settings.debug)`
- `SessionLocal = sessionmaker(engine, class_=Session)`
- `init_db()`: `SQLModel.metadata.create_all(engine)`

### `app/main.py`

- 实例化 FastAPI，title=`今天吃啥 API`，version=`0.1.0`
- 注册 `RequestContextMiddleware`
- 启动时调 `configure_logging(settings.debug)` 与 `init_db()`
- 注册全局异常处理器（`AppError` 与兜底 `Exception`）
- `GET /health` 返回 `{"ok": True, "data": {"status": "healthy", "env": settings.environment}}`
- 暂不挂业务路由（T04 起挂）

### `app/utils/response.py`（可选）

- `success(data: T) -> dict`、`error(code, message)` 工厂，保证所有路由返回 `{ok, code, message, data}`

### `.env.example` 更新

按 config 字段列全，含中文注释

### 测试

- `tests/conftest.py`：test client、test db fixtures（按 spec）
- `tests/test_health.py`：`GET /health` 200
- `tests/test_security.py`：token 编解码单测

## Acceptance Criteria

- [ ] `pip install -e ".[dev]"` 后 `uvicorn app.main:app --reload` 启动无 error
- [ ] `/health` 返回 `{ok: true, data: {status: healthy, env: dev}}`
- [ ] `/docs` 可见 `/health` 接口与 OpenAPI schema
- [ ] 缺失 `.env` 关键字段时启动报错并提示哪一项缺失
- [ ] `ruff check app/` 0 警告
- [ ] `mypy app/` 0 错
- [ ] `pytest tests/` 全绿
- [ ] 全局异常处理器被未捕获异常触发时返回 `{ok: false, code: INTERNAL, message: "服务器内部错误"}` 且日志含 request_id 与堆栈

## Dependencies

- T01（项目骨架与依赖）

## Notes

- 本任务**不**创建 `User` 表，仅在 deps.py 用占位 dict
- 本任务**不**引入 Alembic
- `get_current_user` 占位用 dict 即可，T04 替换
