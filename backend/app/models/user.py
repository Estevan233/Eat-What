"""用户表 - 微信小程序登录的核心身份表。

学习点：
- SQLModel 一个类同时是 ORM 表 + Pydantic schema，省了一个文件
- openid 是微信给「你这个 AppID 下的这个用户」的唯一 ID
- 档案字段（生日/性别/身高/体重/体质）放扩展表 UserProfile，T05 再建
"""
from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

ACCOUNT_KINDS = frozenset({"guest", "wechat"})
ACCOUNT_STATUSES = frozenset({"active", "merging", "merged"})


class User(SQLModel, table=True):
    """微信小程序用户。table=True 表示这是一个真实的表。"""

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_account_kind_status", "account_kind", "account_status"),
        Index("ix_users_merged_into_user_id", "merged_into_user_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    openid: str = Field(unique=True, index=True, max_length=64)
    unionid: str | None = Field(default=None, max_length=64)
    account_kind: str = Field(default="wechat", max_length=16)
    account_status: str = Field(default="active", max_length=16)
    merged_into_user_id: int | None = Field(
        default=None,
        foreign_key="users.id",
    )
    merge_started_at: datetime | None = Field(default=None)
    merged_at: datetime | None = Field(default=None)
    nickname: str = Field(default="微信用户", max_length=64)
    avatar_url: str | None = Field(default=None, max_length=512)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
