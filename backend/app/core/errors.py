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


class GuestAccountUpgradedError(AppError):
    """游客账户已进入升级流程，旧游客凭据不再可签发。"""

    def __init__(self) -> None:
        super().__init__("游客账户已升级", "GUEST_ACCOUNT_UPGRADED", 409)


class AccountStateConflictError(AppError):
    """正式身份命中了不一致的账户类型或状态。"""

    def __init__(self) -> None:
        super().__init__("账户身份状态冲突", "ACCOUNT_STATE_CONFLICT", 409)


class MergeTargetConflict(AppError):
    """A guest merge is permanently bound to a different formal account."""

    def __init__(self) -> None:
        super().__init__("游客账户已绑定其他正式账户", "MERGE_TARGET_CONFLICT", 409)


class SessionIdentityConflictError(AppError):
    """An existing formal session belongs to a different WeChat identity."""

    def __init__(self) -> None:
        super().__init__("当前登录态属于其他微信账户", "SESSION_IDENTITY_CONFLICT", 409)


class MergeConsistency(AppError):
    """Stored merge data violates an ownership or uniqueness invariant."""

    def __init__(
        self,
        message: str = "账户合并数据不一致",
        *,
        status_code: int = 409,
    ) -> None:
        super().__init__(message, "MERGE_DATA_CONFLICT", status_code)


class NotFoundError(AppError):
    def __init__(self, resource: str, ident: Any):
        super().__init__(f"{resource} 不存在: {ident}", "NOT_FOUND", 404)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR", 422)


class InvalidMealChoiceError(AppError):
    def __init__(self, message: str):
        super().__init__(message, "INVALID_MEAL_CHOICE", 422)


class MealAlreadyChosenError(AppError):
    def __init__(self, message: str = "今日餐单已经确认，不能改成另一份餐单"):
        super().__init__(message, "MEAL_ALREADY_CHOSEN", 409)


class ExternalAPIError(AppError):
    def __init__(self, service: str, detail: str):
        super().__init__(f"{service} 调用失败: {detail}", "EXTERNAL_API", 502)


class RateLimitError(AppError):
    def __init__(self, service: str):
        super().__init__(f"{service} 限流，请稍后重试", "RATE_LIMIT", 429)
