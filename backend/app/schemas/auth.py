"""登录相关 schema - 请求/响应的 Pydantic 模型。

学习点：
- SQLModel 已经是 Pydantic 了，但路由的「响应形状」可能与表结构不一样
  （比如不想把 session_key、openid 暴露给前端）
- 所以单独定义 Read 模型控制「对外暴露什么」
- from_orm 把 ORM 对象转 Pydantic 模型
"""

from pydantic import BaseModel, ConfigDict


class WxLoginRequest(BaseModel):
    """前端 POST /auth/wx-login 的 body。"""
    code: str
    nickname: str | None = None
    avatarUrl: str | None = None  # camelCase 与微信小程序 wx.getUserProfile 返回一致


class AuthUserRead(BaseModel):
    """登录响应里对外暴露的用户字段 - 不含 openid/unionid/secret。

    命名 AuthUserRead 表明它专用于「认证响应」场景，
    与 schemas/profile.py 的 UserRead（含 profile 字段）区分开。
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    avatar_url: str | None = None


class LoginResponse(BaseModel):
    """登录成功响应。"""
    token: str
    user: AuthUserRead
