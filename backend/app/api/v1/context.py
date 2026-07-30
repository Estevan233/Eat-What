"""今日上下文路由 - GET /context/today。

学习点：
- 公开接口，无需登录（首页天气卡片要显示节气）
- 用 service 层的进程内缓存（按 ISO 日期），同一天多次调用一致
- response_model 用 dict[str, Any] + success() 包，与其它路由一致
"""
from typing import Any

from fastapi import APIRouter

from app.services.solar_terms import get_today_context_cached
from app.utils.response import success

router = APIRouter(prefix="/context", tags=["context"])


@router.get("/today", response_model=dict[str, Any])
def get_today_context_route() -> dict[str, object]:
    """返回今日历法上下文（星座/生肖/节气/农历）。

    公开端点，无需登录。同一天进程内缓存命中，响应一致。
    """
    ctx = get_today_context_cached()
    return success(data=ctx.model_dump(mode="json"))
