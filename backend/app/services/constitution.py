"""体质判定 service - 9 题问卷算法。

判定依据：中华中医药学会《中医体质分类与判定》（ZYYXH/T157-2009）

学习点：
- 9 种体质标识符贯穿前后端，前端 constants/constitution.ts 同步抄一份
- 平和质反向题用 raw=6-score 让所有 9 体质用同一公式（避免特殊路径）
- 全 < 60 时 fallback 平和（spec 明确，避免「无体质」状态）
"""
from datetime import datetime
from typing import Any, cast

from sqlmodel import Session, select

from app.core.errors import NotFoundError, ValidationError
from app.models.user_profile import UserProfile
from app.schemas.constitution import ConstitutionResult, ConstitutionType

# ---- 题库（题面文本忠于 ZYYXH/T157-2009 标准）----

QUESTIONS: list[dict[str, Any]] = [
    {"id": 1, "text": "您精力充沛吗？", "type": "pinghe_reverse"},
    {"id": 2, "text": "您容易疲乏吗？", "type": "qixu"},
    {"id": 3, "text": "您手脚发凉吗？", "type": "yangxu"},
    {"id": 4, "text": "您手脚心发热吗？", "type": "yinxu"},
    {"id": 5, "text": "您体型偏胖、腹部松软吗？", "type": "tanshi"},
    {"id": 6, "text": "您面部或额头易出油、生痘吗？", "type": "shire"},
    {"id": 7, "text": "您皮肤易瘀青、有黑斑吗？", "type": "xueyu"},
    {"id": 8, "text": "您容易闷闷不乐、多愁善感吗？", "type": "qiyu"},
    {"id": 9, "text": "您过敏（鼻塞/皮疹）吗？", "type": "tebing"},
]

OPTIONS: list[dict[str, object]] = [
    {"value": 1, "label": "没有"},
    {"value": 2, "label": "很少"},
    {"value": 3, "label": "有时"},
    {"value": 4, "label": "经常"},
    {"value": 5, "label": "总是"},
]

# 9 种体质中文名映射（与前端 constants/constitution.ts 同步）
CONSTITUTION_NAMES: dict[str, str] = {
    "pinghe": "平和质",
    "qixu": "气虚质",
    "yangxu": "阳虚质",
    "yinxu": "阴虚质",
    "tanshi": "痰湿质",
    "shire": "湿热质",
    "xueyu": "血瘀质",
    "qiyu": "气郁质",
    "tebing": "特禀质",
}

# 9 种体质的 Python 标识符（用于 scores_normalized 排序与初始化）
ALL_TYPES: tuple[str, ...] = (
    "pinghe", "qixu", "yangxu", "yinxu", "tanshi",
    "shire", "xueyu", "qiyu", "tebing",
)

# 每题对应的体质 type → 9 个体质，1 题对应 1 体质
# 题 1 是 pinghe_reverse：反向题，分数高 → 不偏颇平和（raw 用 6-score）
QUESTION_ID_TO_TYPE: dict[int, str] = {q["id"]: q["type"] for q in QUESTIONS}

# 平和质用反向题，标识符仍是 pinghe
# QUESTION_ID_TO_TYPE[1] == "pinghe_reverse"，需要在算法里特判映射成 "pinghe"


def judge(scores: dict[int, int]) -> ConstitutionResult:
    """9 题问卷判定体质。

    Args:
        scores: {question_id(1-9): 1-5}，必须 9 题，每题 1-5。

    Returns:
        ConstitutionResult：主+兼夹+完整转化分。

    Raises:
        ValidationError: 题数不对或分值越界。
    """
    # 1. 校验
    if len(scores) != 9:
        raise ValidationError(f"应有 9 题答案，实际 {len(scores)} 题")
    for qid in range(1, 10):
        if qid not in scores:
            raise ValidationError(f"缺少题号 {qid} 的答案")
        v = scores[qid]
        if not isinstance(v, int) or v < 1 or v > 5:
            raise ValidationError(f"题 {qid} 分值需在 1-5，实际 {v}")

    # 2. 计算每体质原始分
    raw: dict[str, int] = {t: 0 for t in ALL_TYPES}
    for qid, v in scores.items():
        q_type = QUESTION_ID_TO_TYPE[qid]
        if q_type == "pinghe_reverse":
            # 反向题：精力充沛答 5 → 偏颇打分应低（不偏颇平和）
            raw["pinghe"] = 6 - v  # 5→1, 1→5
        else:
            raw[q_type] = v

    # 3. 转化分 = (原始分 - 题数) / (题数 × 4) × 100
    #    每体质 1 题，题数=1
    normalized: dict[str, int] = {
        t: int((raw[t] - 1) / 4 * 100) for t in ALL_TYPES
    }

    # 4. ≥ 60 的体质为「是」
    high_enough = [t for t in ALL_TYPES if normalized[t] >= 60]

    if high_enough:
        # 主体质 = 转化分最高；兼夹按转化分降序，同分按字典序
        high_enough.sort(key=lambda t: (-normalized[t], t))
        primary = high_enough[0]
        secondary = high_enough[1:]
    else:
        # 全 < 60 → fallback 平和（含平和质转化分高的情况也算平和）
        primary = "pinghe"
        secondary = []

    type_str = primary if not secondary else f"{primary};" + ";".join(secondary)

    return ConstitutionResult(
        primary=cast(ConstitutionType, primary),
        secondary=[cast(ConstitutionType, s) for s in secondary],
        scores_normalized=cast(dict[ConstitutionType, int], normalized),
        constitution_type_str=type_str,
    )


def save_constitution(session: Session, user_id: int, result: ConstitutionResult) -> None:
    """把判定结果写入 UserProfile.constitution_type / constitution_scores。

    要求档案已存在（T05 PUT /profile 才能创建档案）。如果档案不存在，
    抛 NotFoundError（前端应引导用户先填档案）。
    """
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    record = session.exec(stmt).first()
    if record is None:
        raise NotFoundError("user_profile", user_id)

    record.constitution_type = result.constitution_type_str
    record.constitution_scores = {
        cast(str, k): v for k, v in result.scores_normalized.items()
    }
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()


def get_constitution(session: Session, user_id: int) -> ConstitutionResult | None:
    """从 UserProfile 读上次判定结果。不存在返回 None。"""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    record = session.exec(stmt).first()
    if record is None or record.constitution_type is None or record.constitution_scores is None:
        return None

    type_str = record.constitution_type
    parts = type_str.split(";")
    primary = parts[0]
    secondary = parts[1:]

    return ConstitutionResult(
        primary=cast(ConstitutionType, primary),
        secondary=[cast(ConstitutionType, s) for s in secondary],
        scores_normalized=cast(dict[ConstitutionType, int], record.constitution_scores),
        constitution_type_str=type_str,
    )
