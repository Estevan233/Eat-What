"""附近店铺路由 - POST /nearby/shops。学习点：
- 需登录（防滥用，同 /context/weather）：选点坐标只作当次搜索锚点，不落库（PRD R6）
- 开关关闭时返回 provider_available=false，前端隐藏入口/提示，不影响主流程（PRD R2）
- 个人开发者地点搜索配额 200 次/日：服务端 3 位小数网格缓存节流，失败时降级 12h 陈旧缓存
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.core.errors import ExternalAPIError, RateLimitError
from app.models.user import User
from app.schemas.nearby import NearbyShopsRequest, NearbyShopsResponse
from app.services.tencent_lbs_client import tencent_lbs_client, unavailable_shops
from app.utils.response import success

router = APIRouter(prefix="/nearby", tags=["nearby"])


@router.post("/shops", response_model=dict[str, Any])
async def search_nearby_shops_route(
    body: NearbyShopsRequest,
    user: User = Depends(get_current_user),
    _session: Session = Depends(get_db),
) -> dict[str, object]:
    """选点后搜索附近店铺。需登录。

    Body: {"lat": gcj02, "lng": gcj02, "keyword"?, "radius_m"?}
    Returns: {"ok": true, "data": NearbyShopsResponse}
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")

    settings = get_settings()
    if not settings.tencent_lbs_enabled:
        return success(data=unavailable_shops("附近店铺功能未开启").model_dump(mode="json"))

    try:
        data = await tencent_lbs_client.search_nearby_shops(
            body.lat,
            body.lng,
            keyword=body.keyword,
            radius_m=body.radius_m,
        )
    except (ExternalAPIError, RateLimitError):
        data = unavailable_shops("附近店铺服务暂不可用，请稍后再试")
    return success(data=data.model_dump(mode="json"))


__all__ = ["NearbyShopsResponse", "router", "search_nearby_shops_route"]
