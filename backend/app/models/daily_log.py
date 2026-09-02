"""每日推荐日志表 - 记录每次推荐的输入与产出。

学习点：
- (user_id, log_date) 联合唯一约束：一天一行，重选覆盖
- chosen_food_ids 用 JSON 列存列表（MVP 不需反查到 Food）
- mood/activity_level 落库便于事后做反馈分析（T10 只写不读，T11 后续读）
"""
from datetime import date, datetime
from typing import Any

from sqlalchemy import Column, Index
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class DailyLog(SQLModel, table=True):
    """用户每日推荐日志。

    三餐化后：一行 = 用户某一天某一餐的「推荐结果 + 用户实际选择」或一条手动记录。
    - source='recommendation'：推荐/选择记录，按 (user_id, log_date, meal_slot) upsert（重选覆盖同餐次推荐）
    - source='manual'：AI/手动自记，永远追加（一餐可多条）
    唯一性由应用层保证（旧 (user_id, log_date) 唯一约束已在 20260902_10 迁移移除）。
    """

    __tablename__ = "daily_logs"
    __table_args__ = (
        Index("ix_daily_logs_user_date_slot_source", "user_id", "log_date", "meal_slot", "source"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    log_date: date = Field(index=True)
    # 餐次：breakfast / lunch / dinner
    meal_slot: str = Field(default="dinner", max_length=16)
    # 记录来源：recommendation（推荐/选择）或 manual（自记）
    source: str = Field(default="recommendation", max_length=16)
    # 自记外食的店铺名（日记页"外食"段数据来源）
    shop_name: str | None = Field(default=None, max_length=80)
    # 用户备注（自记原文、补充说明等）
    note: str | None = Field(default=None, max_length=500)
    recommendation_event_id: int | None = Field(
        default=None,
        foreign_key="recommendation_events.id",
        index=True,
    )
    # 推荐时写入：这次推荐的 3 道菜的 id（顺序即排名）
    recommended_food_ids_json: list[int] = Field(default=[], sa_column=Column(JSON))
    # 用户实际选择的子集；T10 推荐时为空，T11 选择后更新
    chosen_food_ids_json: list[int] = Field(default=[], sa_column=Column(JSON))
    # 历史必须读取当时的快照，不能反查后来可能已更新的 Recipe。
    recommended_meal_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    chosen_meal_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    chosen_total_nutrition_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    # 用户当时输入
    mood: str = Field(default="neutral", max_length=16)
    activity_level: str = Field(default="normal", max_length=8)
    # 推荐时的天气标签，便于事后按场景回看
    weather_tag: str | None = Field(default=None, max_length=16)
    dining_mode: str = Field(default="cook", max_length=16)
    audience: str = Field(default="personal", max_length=16)
    party_size: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
