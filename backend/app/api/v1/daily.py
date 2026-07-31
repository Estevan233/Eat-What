"""每日推荐路由 - POST /daily/recommend。

学习点：
- 登录依赖：推荐是用户个性化的，未登录直接 401
- service 层做业务逻辑，路由只负责「收请求、调 service、返响应」
- response_model 用 dict[str, Any] + success() 包，与其它路由一致
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.daily import RecommendRequest, RecommendResponse
from app.services import recommender
from app.utils.response import success

router = APIRouter(prefix="/daily", tags=["daily"])


@router.post("/recommend", response_model=dict[str, Any])
async def recommend_route(
    body: RecommendRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /daily/recommend - 拿到今天 3 道菜的推荐。

    Body: RecommendRequest (mood / activity_level / lat? / lng?)
    Returns: {"ok": true, "data": RecommendResponse}
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")

    resp: RecommendResponse = await recommender.recommend(session, user, body)
    return success(data=resp.model_dump(mode="json"))
