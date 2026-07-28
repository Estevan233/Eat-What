"""错误体系 - 业务异常用 AppError 子类，service 抛，路由转 HTTPException。

学习点：
- service 层不应感知 HTTP，所以不直接抛 HTTPException
- 用 code 字段做机器可读的错误标识，前端可分支处理
"""
from typing import Any


class AppError(Exception):
    """所有业务异常的基类。"""

    def __init__(self, message: str, code: str = "UNKNOWN", status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class AuthError(AppError):
    def __init__(self, message: str = "认证失败"):
        super().__init__(message, "AUTH_ERROR", 401)


class NotFoundError(AppError):
    def __init__(self, resource: str, ident: Any):
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
