"""每日推荐日志表 - 记录每次推荐的输入与产出。

学习点：
- (user_id, log_date) 联合唯一约束：一天一行，重选覆盖
- chosen_food_ids 用 JSON 列存列表（MVP 不需反查到 Food）
- mood/activity_level 落库便于事后做反馈分析（T10 只写不读，T11 后续读）
"""
from datetime import date, datetime
from typing import Any

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


class DailyLog(SQLModel, table=True):
    """用户每日推荐日志。

    一行 = 用户某一天的「推荐结果 + 用户实际选择」。
    T10 推荐时写入（recommended_*），T11 用户选择后更新 chosen_food_ids。
    """

    __tablename__ = "daily_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "log_date", name="uq_daily_logs_user_date"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    log_date: date = Field(index=True)
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
