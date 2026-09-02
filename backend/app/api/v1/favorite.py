"""收藏路由 - POST/DELETE/GET /favorite + 自定义收藏 + 搜索。

学习点：
- POST /favorite/{food_id} 用 toggle 语义：已收藏则取消，未收藏则新增
  前端一个按钮两种操作，比 POST + DELETE 分开更简洁
- GET /favorite 分页列表（含自定义收藏），支持 query 关键词搜索
- POST /favorite/custom 手动添加自定义收藏（不依赖候选库）
- PATCH /favorite/{favorite_id} 改备注；DELETE /favorite/{favorite_id} 删除
- 需登录：收藏是用户私有数据
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.core.errors import NotFoundError
from app.models.food import Food
from app.models.user import User
from app.services import favorite_service
from app.utils.response import success

router = APIRouter(prefix="/favorite", tags=["favorite"])

MAX_PAGE_SIZE = 50


class CustomFavoriteRequest(BaseModel):
    """POST /favorite/custom 请求体。"""

    custom_name: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class UpdateFavoriteRequest(BaseModel):
    """PATCH /favorite/{favorite_id} 请求体。"""

    note: str | None = Field(default=None, max_length=500)


@router.post("/custom", response_model=dict[str, Any])
def add_custom_favorite_route(
    body: CustomFavoriteRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """POST /favorite/custom - 手动添加自定义收藏。"""
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    record = favorite_service.add_custom_favorite(
        session,
        user.id,
        custom_name=body.custom_name,
        note=body.note,
    )
    return success(
        data={
            "favorite_id": record.id,
            "custom_name": record.custom_name,
            "note": record.note,
        }
    )


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
    query: str = Query(default="", max_length=64),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """GET /favorite - 分页查询收藏列表（含自定义收藏），支持关键词搜索。

    Query: page(≥1) / size(1-50) / query(菜名·分类·备注)
    Returns: {"ok": true, "data": {"items": [...], "page": 1, "size": 20, "total": 5}}
    """
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    entries, total = favorite_service.list_favorites_detailed(
        session,
        user.id,
        page=page,
        size=size,
        query=query,
    )
    items: list[dict[str, Any]] = []
    for entry in entries:
        food = entry.get("food")
        items.append(
            {
                "favorite_id": entry["favorite_id"],
                "food_id": entry["food_id"],
                "custom_name": entry["custom_name"],
                "note": entry["note"],
                "created_at": entry["created_at"],
                "food": food.to_read_dict() if food is not None else None,
            }
        )
    return success(data={"items": items, "page": page, "size": size, "total": total})


@router.patch("/{favorite_id}", response_model=dict[str, Any])
@router.put("/{favorite_id}", response_model=dict[str, Any])
def update_favorite_route(
    favorite_id: int,
    body: UpdateFavoriteRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """PATCH|PUT /favorite/{favorite_id} - 编辑收藏备注（PUT 供小程序通道使用）。"""
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    record = favorite_service.update_favorite_note(session, user.id, favorite_id, body.note)
    return success(
        data={
            "favorite_id": record.id,
            "food_id": record.food_id,
            "custom_name": record.custom_name,
            "note": record.note,
        }
    )


@router.delete("/{favorite_id}", response_model=dict[str, Any])
def delete_favorite_route(
    favorite_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """DELETE /favorite/{favorite_id} - 删除一条收藏（普通/自定义通用）。"""
    if user.id is None:  # pragma: no cover
        raise RuntimeError("user.id 不应为 None")

    favorite_service.delete_favorite(session, user.id, favorite_id)
    return success(data={"favorite_id": favorite_id, "deleted": True})
