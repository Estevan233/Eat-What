"""用户档案路由 - GET/PUT /profile。

学习点：
- 路由只做「收请求、调 service、返响应」，业务在 service 层
- Depends(get_current_user) 让 FastAPI 自动校验登录
- response_model 用 dict[str, Any] + success() 自己包，与 auth.py 一致
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.profile import ProfileUpsert, UserRead
from app.services import profile_service
from app.utils.response import success

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=dict[str, Any])
def get_profile_route(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """读当前用户的档案。

    Returns: {"ok": true, "data": {"id": 1, "nickname": "...", "profile": null | {...}}}
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")
    profile = profile_service.get_profile(session, user.id)
    user_read = UserRead(
        id=user.id,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        profile=profile,
    )
    return success(data=user_read.model_dump())


@router.put("", response_model=dict[str, Any])
def upsert_profile_route(
    body: ProfileUpsert,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """创建或更新档案。

    Returns: {"ok": true, "data": {profile 字段}}
    """
    if user.id is None:  # pragma: no cover - DB 行必有 id
        raise RuntimeError("get_current_user 返回的 user.id 不应为 None")
    profile = profile_service.upsert_profile(session, user.id, body)
    return success(data=profile.model_dump())
