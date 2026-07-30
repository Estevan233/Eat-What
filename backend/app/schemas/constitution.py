"""体质判定 schema - 问卷请求/响应模型。

学习点：
- ConstitutionType 是 Literal，限定 9 种体质标识符
- answers 的 key 是 int (1-9)，camelToSnake 不动数字 key，前端转换层安全
"""
from typing import Literal

from pydantic import BaseModel, Field

ConstitutionType = Literal[
    "pinghe", "qixu", "yangxu", "yinxu", "tanshi",
    "shire", "xueyu", "qiyu", "tebing",
]


class ConstitutionQuestionnaire(BaseModel):
    """POST /profile/constitution 请求体。"""
    answers: dict[int, int] = Field(
        ..., description="9 题答案，key=题号1-9，value=1-5"
    )


class ConstitutionResult(BaseModel):
    """判定结果。"""
    primary: ConstitutionType                  # 主体质
    secondary: list[ConstitutionType]           # 兼夹（不含主）
    scores_normalized: dict[ConstitutionType, int]  # 每体质转化分 0-100
    constitution_type_str: str                  # 落库字符串，如 "qixu;shire"


class ConstitutionQuestionsPayload(BaseModel):
    """GET /profile/constitution/questions 响应。"""
    questions: list[dict[str, object]]          # [{id, text, type}, ...]
    options: list[dict[str, object]]            # [{value, label}, ...]
