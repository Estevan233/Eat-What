"""用户档案表 - 健康档案（生日/性别/身高/体重/忌口/体质）。

学习点：
- 1:1 关系实现：user_id 同时是外键 + 主键，DB 层强制一对一
- forbidden_tags / constitution_scores 用 JSON 列存整个结构（MVP 不需反查）
- birthday 用 ISO 字符串不用 Date 类型，避免 SQLite driver 时区行为差异
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class UserProfile(SQLModel, table=True):
    """用户健康档案。与 User 1:1。"""

    __tablename__ = "user_profiles"

    # user_id 既是外键又是主键 → DB 强制 1:1（一个 user 只能有一行 profile）
    user_id: int = Field(foreign_key="users.id", primary_key=True)
    birthday: str = Field(max_length=10)            # ISO YYYY-MM-DD 字符串
    gender: str = Field(max_length=8)               # 'male' | 'female' | 'other'
    height_cm: int | None = Field(default=None)
    weight_kg: float | None = Field(default=None)
    # JSON 列存 list；sa_column 让 SQLModel 把这字段映射成 SQLAlchemy JSON 类型
    forbidden_tags: list[str] = Field(default=[], sa_column=Column(JSON))
    # T06 新增：体质判定结果（主+兼夹分号串，如 "qixu;shire"）
    constitution_type: str | None = Field(default=None, max_length=64)
    # T06 新增：完整转化分（{"pinghe": 0, "qixu": 100, ...}）
    constitution_scores: dict[str, int] | None = Field(default=None, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_read_dict(self) -> dict[str, Any]:
        """转成 ProfileRead 形状（含 zodiac_sign 占位 None）。"""
        return {
            "user_id": self.user_id,
            "birthday": self.birthday,
            "gender": self.gender,
            "height_cm": self.height_cm,
            "weight_kg": self.weight_kg,
            "forbidden_tags": list(self.forbidden_tags),
            "constitution_type": self.constitution_type,
            "constitution_scores": dict(self.constitution_scores) if self.constitution_scores else None,
            "zodiac_sign": None,  # T08 实现
            "updated_at": self.updated_at,
        }
