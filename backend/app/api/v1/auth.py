"""认证路由 - 微信登录 + 游客登录端点。

学习点：
- @router.post 声明 method + path，response_model 自动校验+过滤响应字段
- Depends() 让 FastAPI 注入 db session
- async 因为 wx_client 是异步 httpx
- response_model=ApiResult[LoginResponse] 让 OpenAPI 文档显示响应结构
"""
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.core.deps import get_db
from app.core.security import create_access_token
from app.schemas.auth import AuthUserRead, GuestLoginRequest, WxLoginRequest
from app.services.user_service import get_or_create_guest, upsert_by_openid
from app.services.wx_client import wx_client
from app.utils.response import success

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/wx-login", response_model=dict[str, Any])
async def wx_login(req: WxLoginRequest, request: Request, session: Session = Depends(get_db)) -> dict[str, object]:
    """小程序登录入口。

    Body: {"code": "...", "nickname"?: "...", "avatarUrl"?: "..."}
    Returns: {"ok": true, "data": {"token": "...", "user": {...}}}
    """
    # 1. 拿 code 换 openid（异步调微信服务器）
    wx_data = await wx_client.code2session(req.code)

    # 2. upsert 用户（首次建，二次更新）
    user = upsert_by_openid(
        session,
        openid=wx_data["openid"],
        unionid=wx_data.get("unionid"),
        nickname=req.nickname,
        avatar_url=req.avatarUrl,
    )

    # 3. 签 JWT（7 天有效，settings.jwt_ttl_minutes 控制）
    # user.id 在 commit/refresh 后必有值，但 SQLModel 类型签名是 Optional[int]
    if user.id is None:
        raise RuntimeError("upsert 后 user.id 不应为 None")
    token = create_access_token(user.id)

    # 4. 包统一响应格式
    return success(
        data={
            "token": token,
            "user": AuthUserRead.model_validate(user).model_dump(),
        }
    )


@router.post("/guest-login", response_model=dict[str, Any])
def guest_login(req: GuestLoginRequest, session: Session = Depends(get_db)) -> dict[str, object]:
    """游客登录入口 - 不调微信，直接按 guest_id 复用 / 创建用户。

    用于小程序体验：用户不想授权微信也能进入应用。

    Body: {"guestId": "<前端生成的 uuid>", "nickname"?: "..."}
    Returns: {"ok": true, "data": {"token": "...", "user": {...}}}
    """
    user = get_or_create_guest(
        session,
        guest_id=req.guestId,
        nickname=req.nickname,
    )

    if user.id is None:
        raise RuntimeError("get_or_create_guest 后 user.id 不应为 None")
    token = create_access_token(user.id)

    return success(
        data={
            "token": token,
            "user": AuthUserRead.model_validate(user).model_dump(),
        }
    )
