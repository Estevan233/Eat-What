# Logging Guidelines

> structlog 结构化日志规范。

---

## Overview

- 库：**structlog**（输出 JSON，开发环境用 console renderer 美化）
- 日志是排查线上问题的主要手段，必须按结构化方式打
- 敏感信息（token、openid、用户手机号）一律不进日志

---

## Log Levels

| 级别 | 何时用 | 例子 |
|---|---|---|
| `debug` | 详细内部状态，默认关 | `log.debug("recommender_scores", scores=scores)` |
| `info` | 关键业务事件、外部 API 调用结果 | `log.info("user_logged_in", user_id=uid)` |
| `warning` | 异常但可恢复，需关注 | `log.warning("weather_cache_miss", lat=lat)` |
| `error` | 业务失败、外部 API 失败 | `log.error("hefeng_call_failed", status=502)` |
| `critical` | 系统级故障 | `log.critical("db_unreachable")` |

生产默认级别：`info`；开发期：`debug`。

---

## Structured Logging

### 配置

```python
# app/core/logging.py
import structlog
import logging

def configure_logging(debug: bool = False) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
            if not debug
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_wrapper(logging.INFO),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
```

### 使用

```python
import structlog
log = structlog.get_logger(__name__)

# 在 service 里
async def recommend(session: Session, user: User, mood: str) -> RecommendResponse:
    log.info("recommend_start", user_id=user.id, mood=mood)
    try:
        weather = await weather_client.get(user.lat, user.lng)
    except ExternalAPIError as e:
        log.warning("recommend_weather_fallback", error=str(e))
        weather = Weather.default()
    ...
    log.info("recommend_done", user_id=user.id, food_ids=[f.id for f in result.foods])
    return result
```

### Request context（可选）

用 middleware 给每个请求加 `request_id`：

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

---

## What to Log

- ✅ 用户登录、登出（uid 即可，不记 openid）
- ✅ 外部 API 调用：服务名、耗时、状态码、关键参数（lat/lng 等不敏感的）
- ✅ 推荐算法：输入用户 id、mood、候选数、最终选中的 food ids、打分排名前 3
- ✅ 缓存命中/未命中
- ✅ 异常路径（warning/error）

---

## What NOT to Log

- ❌ JWT token、`Authorization` header
- ❌ openid、unionid、手机号、邮箱、身份证
- ❌ 用户密码（即便哈希过也不记）
- ❌ 完整请求 body（可能含密码字段）
- ❌ 用户的完整 forbidden_tags 列表（含个人健康信息）
- ❌ 大对象（食物库全量、用户列表）

打日志前自问：这条日志被拿到第三方能造成损害吗？能 → 不打。

---

## Common Mistakes

- ❌ `print()` —— 一律用 structlog
- ❌ f-string 拼接日志：`log.info(f"user {uid}")` —— 用结构化：`log.info("user", uid=uid)`
- ❌ 日志里打 `request.headers` 整个 dict —— 含敏感字段
- ❌ 异常路径没打日志 —— `try/except` 内必须有 `log.warning` 或 `log.error`
- ❌ 日志级别不分 —— debug/info/warning/error 必须按定义使用
