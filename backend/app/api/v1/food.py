"""食物库路由 - GET /food（分页）/ /food/{id}（详情）/ /food/search。

学习点：
- 食物库是只读数据，所有路由都是 GET，无需登录（推荐算法的后端数据源，前端也会查）
- 分页 size clamp 到 1-50，避免恶意大 size 拖垮 DB
- search 用 query param q，空串返 400（pydantic min_length=1）
- response_model 用 dict[str, Any] + success() 自己包，与 profile/constitution 一致
"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.deps import get_db
from app.core.errors import NotFoundError
from app.services import food_service, recipe_service
from app.utils.response import success

router = APIRouter(prefix="/food", tags=["food"])

MAX_PAGE_SIZE = 50


@router.get("", response_model=dict[str, Any])
def list_food_route(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    category: str | None = Query(default=None),
    nature: str | None = Query(default=None),
    cooking_method: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """分页查询食物列表。

    Query: page(≥1) / size(1-50) / category / nature / cooking_method（可选过滤）
    Returns: {"ok": true, "data": {"items": [...], "page": 1, "size": 20, "total": 200}}
    """
    items, total = food_service.get_all(
        session,
        page=page,
        size=size,
        category=category,
        nature=nature,
        cooking_method=cooking_method,
    )
    return success(
        data={
            "items": [f.to_read_dict() for f in items],
            "page": page,
            "size": size,
            "total": total,
        }
    )


@router.get("/search", response_model=dict[str, Any])
def search_food_route(
    q: str = Query(..., min_length=1, description="按 name 模糊搜索的关键词"),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """按 name 模糊搜索食物。

    Query: q(非空) / limit(1-50)
    Returns: {"ok": true, "data": {"items": [...], "q": "番茄"}}
    """
    items = food_service.search(session, q, limit=limit)
    return success(data={"items": [f.to_read_dict() for f in items], "q": q})


@router.get("/{food_id}", response_model=dict[str, Any])
def get_food_route(
    food_id: int,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """按 id 取食物详情。不存在 → 404。"""
    food = food_service.get_by_id(session, food_id)
    if food is None:
        raise NotFoundError("food", food_id)
    return success(data=food.to_read_dict())


@router.get("/{food_id}/recipe", response_model=dict[str, Any])
def get_food_recipe_route(
    food_id: int,
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """返回稳定的结构化菜谱；没有菜谱的 Food 明确返回 404。"""
    recipe = recipe_service.get_by_food_id(session, food_id)
    if recipe is None:
        raise NotFoundError("recipe", food_id)
    return success(data=recipe.model_dump(mode="json"))
