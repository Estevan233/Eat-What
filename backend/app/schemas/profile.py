"""用户档案 schema - profile 场景的请求/响应模型。

学习点：
- ProfileUpsert 是「写入契约」（请求 body 校验）
- ProfileRead 是「读取契约」（响应序列化）
- UserRead（本文件）= User + profile 组合，是 GET /profile 的响应
- 与 schemas/auth.py 的 AuthUserRead 区分：那个只有 id/nickname/avatar_url，
  这个多一个 profile 字段
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import FORBIDDEN_TAGS_SET
from app.core.errors import ValidationError

Gender = Literal["male", "female", "other"]


class ProfileUpsert(BaseModel):
    """PUT /profile 请求体。"""
    birthday: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    gender: Gender
    height_cm: int | None = Field(default=None, ge=80, le=250)
    weight_kg: float | None = Field(default=None, ge=30, le=300)
    forbidden_tags: list[str] = Field(default_factory=list)

    def validate_tags(self) -> None:
        """校验 forbidden_tags 全部在预定义集合内。schema 校验不了「值在动态集合内」。

        Raises:
            ValidationError: 如果有不在集合内的 tag。
        """
        invalid = [t for t in self.forbidden_tags if t not in FORBIDDEN_TAGS_SET]
        if invalid:
            raise ValidationError(f"未知的忌口标签: {invalid}")


class ProfileRead(BaseModel):
    """GET /profile 返回的 profile 部分。"""
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    birthday: str
    gender: str
    height_cm: int | None = None
    weight_kg: float | None = None
    forbidden_tags: list[str] = []
    zodiac_sign: str | None = None   # 占位，T08 实现
    updated_at: datetime


class UserRead(BaseModel):
    """GET /profile 返回的完整对象 - User + profile 组合。"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    avatar_url: str | None = None
    profile: ProfileRead | None = None
