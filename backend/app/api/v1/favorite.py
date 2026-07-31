"""收藏路由 - POST/DELETE/GET /favorite。

学习点：
- POST /favorite/{food_id} 用 toggle 语义：已收藏则取消，未收藏则新增
  前端一个按钮两种操作，比 POST + DELETE 分开更简洁
- GET /favorite 分页列表，JOIN Food 返回完整菜信息
- 需登录：收藏是用户私有数据
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import NotFoundError
from app.models.food import Food
from app.models.user import User
from app.services import favorite_service
from app.utils.response import success

router = APIRouter(prefix="/favorite", tags=["favorite"])

MAX_PAGE_SIZE = 50


@router.post("/{food_id}", response_model=dict[str, Any])
def toggle_favorite_route(
    food_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /favorite/{food_id} - 切换收藏状态。

    已收藏 → 取消，未收藏 → 新增。幂等。
    Returns: {"ok": true, "data": {"food_id": 1, "favorited": true}}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    food = session.get(Food, food_id)
    if food is None:
        raise NotFoundError("food", food_id)

    favorited = favorite_service.toggle_favorite(session, user.id, food_id)
    return success(data={"food_id": food_id, "favorited": favorited})


@router.get("", response_model=dict[str, Any])
def list_favorites_route(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """GET /favorite - 分页查询收藏列表。

    Query: page(≥1) / size(1-50)
    Returns: {"ok": true, "data": {"items": [...], "page": 1, "size": 20, "total": 5}}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    items, total = favorite_service.list_favorites(session, user.id, page=page, size=size)
    return success(
        data={
            "items": [f.to_read_dict() for f in items],
            "page": page,
            "size": size,
            "total": total,
        }
    )
