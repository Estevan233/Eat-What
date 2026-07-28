"""统一响应包装 - 所有路由返回 {ok, code, message, data}。

学习点：
- 统一响应格式让前端拦截器逻辑一致
- success() / error() 工厂避免手写 dict
"""
from typing import Any


def success(data: Any = None, message: str | None = None) -> dict[str, Any]:
    return {"ok": True, "code": "OK", "message": message, "data": data}


def error(code: str, message: str, data: Any = None) -> dict[str, Any]:
    return {"ok": False, "code": code, "message": message, "data": data}
