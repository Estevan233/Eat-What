# Error Handling

> FastAPI 错误处理规范。

---

## Overview

- 业务异常用自定义 `AppError` 子类，service 层抛出
- 路由层把 `AppError` 转换为 HTTPException；service 永远不直接抛 HTTPException
- 全局异常处理器（`@app.exception_handler`）兜底未捕获异常
- 第三方 API 失败用 `httpx.HTTPStatusError` / `httpx.RequestError` 捕获后包装为 `AppError`

---

## Error Types

### 顶层基类

```python
# app/core/errors.py
class AppError(Exception):
    """所有业务异常的基类"""
    def __init__(self, message: str, code: str = "UNKNOWN", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)
```

### 常见子类

```python
class AuthError(AppError):
    def __init__(self, message: str = "认证失败"):
        super().__init__(message, "AUTH_ERROR", 401)

class NotFoundError(AppError):
    def __init__(self, resource: str, ident: str | int):
        super().__init__(f"{resource} 不存在: {ident}", "NOT_FOUND", 404)

class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR", 422)

class ExternalAPIError(AppError):
    def __init__(self, service: str, detail: str):
        super().__init__(f"{service} 调用失败: {detail}", "EXTERNAL_API", 502)

class RateLimitError(AppError):
    def __init__(self, service: str):
        super().__init__(f"{service} 限流，请稍后重试", "RATE_LIMIT", 429)
```

---

## Error Handling Patterns

### Service 层

```python
# app/services/weather_client.py
import httpx
from app.core.errors import ExternalAPIError, RateLimitError

class WeatherClient:
    async def get(self, lat: float, lng: float) -> Weather:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.base_url, params={...})
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("hefeng") from e
            raise ExternalAPIError("hefeng", f"HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise ExternalAPIError("hefeng", str(e)) from e
        return self._parse(resp.json())
```

### 路由层

```python
# app/api/v1/daily.py
from fastapi import APIRouter, Depends, HTTPException
from app.core.errors import AppError

router = APIRouter()

@router.post("/recommend")
async def recommend(req: RecommendRequest, user: User = Depends(get_current_user), session: Session = Depends(get_db)):
    try:
        result = await recommender.get_today(session, user, req.mood)
    except AppError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    return result
```

### 全局处理器

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.errors import AppError
import structlog
log = structlog.get_logger()

app = FastAPI()

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    log.warning("app_error", path=request.url.path, code=exc.code, message=exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "code": exc.code, "message": exc.message},
    )

@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("unhandled_error", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "code": "INTERNAL", "message": "服务器内部错误"},
    )
```

---

## API Error Responses

统一响应包装：

```json
{
  "ok": false,
  "code": "NOT_FOUND",
  "message": "Food 不存在: 42",
  "data": null
}
```

成功响应：

```json
{
  "ok": true,
  "code": "OK",
  "message": null,
  "data": { ... }
}
```

---

## Common Mistakes

- ❌ Service 抛 `HTTPException` —— 应抛 `AppError` 子类，路由转换
- ❌ 裸 `except:` / `except Exception:` 吞错 —— 必须记录日志并重新包装
- ❌ 把堆栈字符串返回给客户端 —— 全局 handler 兜底
- ❌ `raise X from None` 隐藏原异常链 —— 用 `raise X from e` 保留
- ❌ 不区分用户输入错误（422）和业务规则错误（400）—— 用 `ValidationError` vs `AppError`
- ❌ 重复定义同样的错误码字符串 —— 抽常量到 `app/core/errors.py`
