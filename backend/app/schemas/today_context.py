"""今日上下文 schema - 给推荐算法与 UI 当前历法状态。

学习点：
- TodayContext 把节气/星座/生肖/农历等放在一个对象里，前端一次拉够用
- 字段命名后端 snake_case，前端 camelCase 由 request 层转换
"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class TodayContext(BaseModel):
    """GET /context/today 返回的今日历法上下文。"""

    model_config = ConfigDict(from_attributes=True)

    # ISO 日期，用作缓存 key 与前端展示
    date: date
    # 当前节气中文名（仅在节气当天有值，否则空字符串）
    solar_term_current: str = Field(default="", description="当前节气名，非节气日为空字符串")
    # 下一节气中文名 + ISO 日期，日均会有值
    solar_term_next_name: str
    solar_term_next_date: str = Field(description="下一节气 ISO 日期 YYYY-MM-DD")
    # 西方星座英文键：aries / taurus / gemini / cancer / leo / virgo /
    # libra / scorpio / sagittarius / capricorn / aquarius / pisces
    zodiac_sign: str
    # 生肖中文名：马 / 羊 / 猴 ...
    animal: str
    # 农历月/日（数字，1-12 / 1-30，闰月为负数表示）
    lunar_month: int
    lunar_day: int
    is_leap_month: bool
