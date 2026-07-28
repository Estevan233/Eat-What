"""应用常量 - 跨模块共享的固定值。

学习点：
- 常量集中放 constants.py，避免散落各处难维护
- 用 tuple / frozenset 而非 list（不可变，防误改）
"""
from __future__ import annotations

from typing import Final

# 忌口标签预定义集合。前后端共享语义。
# 前端 miniapp/src/constants/forbidden-tags.ts 需手抄一份（T08 gen:api 后会自动）
FORBIDDEN_TAGS: Final[tuple[str, ...]] = (
    "pork",          # 猪肉
    "beef",          # 牛肉
    "seafood",       # 海鲜
    "spicy",         # 辣
    "raw_cold",      # 生冷
    "greasy",        # 油腻
    "gluten",        # 麸质
    "lactose",       # 乳糖
    "nut",           # 坚果
    "diabetic_sugar", # 控糖
)

FORBIDDEN_TAGS_SET: Final[frozenset[str]] = frozenset(FORBIDDEN_TAGS)
