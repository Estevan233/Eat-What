"""登录相关 schema - 请求/响应的 Pydantic 模型。

学习点：
- SQLModel 已经是 Pydantic 了，但路由的「响应形状」可能与表结构不一样
  （比如不想把 session_key、openid 暴露给前端）
- 所以单独定义 Read 模型控制「对外暴露什么」
- from_orm 把 ORM 对象转 Pydantic 模型
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class WxLoginRequest(BaseModel):
    """前端 POST /auth/wx-login 的 body。"""
    code: str
    nickname: str | None = None
    # snake_case 与全项目约定一致；前端 request.ts 会 camelToSnake 自动转换
    avatar_url: str | None = None


class GuestLoginRequest(BaseModel):
    """前端 POST /auth/guest-login 的 body。

    guest_id 由前端生成（建议 UUID v4）并落 storage，下次登录传回同一 guest_id
    → 后端复用同一 user 行。不传时后端会生成一个，但前端拿不到无法复用，
    所以推荐前端必传。
    """
    guest_id: str = Field(..., min_length=1, max_length=128)
    nickname: str | None = Field(default=None, max_length=64)


class AuthUserRead(BaseModel):
    """登录响应里对外暴露的用户字段 - 不含 openid/unionid/secret。

    命名 AuthUserRead 表明它专用于「认证响应」场景，
    与 schemas/profile.py 的 UserRead（含 profile 字段）区分开。
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    avatar_url: str | None = None
    account_kind: Literal["guest", "wechat"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def profile_complete(self) -> bool:
        """头像和非默认昵称齐全才算公开资料完成；不影响登录状态。"""
        nickname = self.nickname.strip()
        return bool(
            self.avatar_url
            and nickname
            and nickname not in {"微信用户", "用户"}
        )


class LoginResponse(BaseModel):
    """登录成功响应。"""
    token: str
    user: AuthUserRead
    merge_status: Literal["not_requested", "completed"] = "not_requested"
