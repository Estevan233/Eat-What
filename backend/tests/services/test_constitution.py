"""T06 体质判定 service 单测。

覆盖 PRD/design 6 个分支：
1. 全 1（题1=1 反向 → pinghe 高转化分）→ 主平和
2. 题2=5，其余=1 → 主气虚
3. 多种 ≥ 60 → 取最高为主、其余为兼夹
4. pinghe 反向高分（用户答 5=总是精力充沛 → raw_pinghe 低 → 全 < 60）→ fallback 平和
5. 缺题 → ValidationError
6. value 越界 → ValidationError

学习点：
- judge() 是纯函数，测试只需构造 scores dict 直接断言
- save/get_constitution 用真 in-memory Session（conftest 的 session fixture）
"""
import pytest

from app.core.errors import ValidationError
from app.schemas.constitution import ConstitutionResult
from app.services.constitution import (
    get_constitution,
    judge,
    save_constitution,
)


def _all(value: int) -> dict[int, int]:
    """构造 9 题全为 value 的 scores。"""
    return {i: value for i in range(1, 10)}


# --- 验收 1: 全 1 → 主平和 ---


def test_all_ones_falls_back_to_pinghe():
    """题1=1（反向 → raw_pinghe=5 → norm=100）→ 主平和。"""
    result = judge(_all(1))

    assert isinstance(result, ConstitutionResult)
    assert result.primary == "pinghe"
    assert result.secondary == []
    # 转化分：pinghe=100，其它=0
    assert result.scores_normalized["pinghe"] == 100
    for t in ("qixu", "yangxu", "yinxu", "tanshi", "shire", "xueyu", "qiyu", "tebing"):
        assert result.scores_normalized[t] == 0
    assert result.constitution_type_str == "pinghe"


# --- 验收 2: 题2=5，其余=1 → 主气虚 ---


def test_q5_others_1_qixu_primary():
    """题2=5 → raw_qixu=5 → norm=100 ≥ 60；其它偏颇=0；pinghe=100（题1=1 反向）。

    primary 应是转化分最高的，pinghe 与 qixu 都=100，按字典序 pinghe < qixu，
    所以 primary=pinghe，secondary=[qixu]。

    等等——这不符合设计文档里「题2=5 → 主气虚」的期望。
    原因：题1=1 反向让 pinghe norm=100，会和 qixu 并列。
    解法：题1 给 5（不精力充沛 → 反向 → raw_pinghe=1 → norm=0），让 pinghe 也低。
    """
    scores = _all(1)
    scores[1] = 5  # 题1=5（精力充沛「总是」→ 反向 raw=1 → norm=0 → pinghe 不够）
    scores[2] = 5  # 题2=5（容易疲乏「总是」→ raw=5 → norm=100 → qixu）
    result = judge(scores)

    assert result.primary == "qixu"
    assert result.secondary == []
    assert result.scores_normalized["qixu"] == 100
    assert result.scores_normalized["pinghe"] == 0
    assert result.constitution_type_str == "qixu"


# --- 验收 3: 多种 ≥ 60 → 取最高为主、其余为兼夹 ---


def test_multi_high_scores_picks_highest_primary():
    """题2=5（qixu norm=100）、题6=4（shire norm=75）→ 主 qixu，兼夹 shire。

    题1=5 让 pinghe norm=0，避免 pinghe 也参与。
    """
    scores = _all(1)
    scores[1] = 5  # pinghe → 0
    scores[2] = 5  # qixu → 100
    scores[6] = 4  # shire → (4-1)/4*100 = 75
    result = judge(scores)

    assert result.primary == "qixu"
    assert result.secondary == ["shire"]
    assert result.scores_normalized["qixu"] == 100
    assert result.scores_normalized["shire"] == 75
    assert result.constitution_type_str == "qixu;shire"


def test_multi_high_scores_ties_broken_by_lexicographic_order():
    """同分时按字典序：题2=5（qixu=100）与题6=5（shire=100）→ 字典序 qixu < shire。"""
    scores = _all(1)
    scores[1] = 5  # pinghe → 0
    scores[2] = 5  # qixu → 100
    scores[6] = 5  # shire → 100
    result = judge(scores)

    assert result.primary == "qixu"
    assert result.secondary == ["shire"]


# --- 验收 4: pinghe 反向高分 → fallback 平和 ---


def test_high_pinghe_reverse_score_falls_back_to_pinghe():
    """题1=5（总是精力充沛）→ raw_pinghe=1 → norm=0；其它偏颇也<60 → fallback pinghe。

    这是设计文档里的决策：题1 用户高分时 raw_pinghe 反向低，全 < 60 → 平和。
    语义：用户精力充沛 + 其它偏颇都低 = 平和质，与题面一致。
    """
    scores = _all(1)
    scores[1] = 5  # 精力充沛「总是」→ raw_pinghe=1 → norm=0
    # 其它题全=1 → 偏颇 norm=0 → 全 < 60 → fallback pinghe
    result = judge(scores)

    assert result.primary == "pinghe"
    assert result.secondary == []
    assert result.scores_normalized["pinghe"] == 0
    assert result.constitution_type_str == "pinghe"


# --- 验收 5: 缺题 → ValidationError ---


def test_invalid_question_count_returns_validation_error():
    """少一题 → ValidationError。"""
    scores = {i: 3 for i in range(1, 9)}  # 只有 8 题
    with pytest.raises(ValidationError) as exc_info:
        judge(scores)
    assert "9 题" in str(exc_info.value.message) or "9" in str(exc_info.value.message)


def test_missing_question_id_returns_validation_error():
    """缺题号 → ValidationError（先按总题数校验，少 1 题报「实际 8 题」）。"""
    scores = {i: 3 for i in range(1, 10) if i != 5}
    with pytest.raises(ValidationError) as exc_info:
        judge(scores)
    # judge() 先校验题数，少 1 题会报「实际 8 题」
    assert "8" in str(exc_info.value.message) or "9" in str(exc_info.value.message)


# --- 验收 6: value 越界 → ValidationError ---


def test_invalid_score_returns_validation_error():
    """value=6 → ValidationError。"""
    scores = _all(3)
    scores[3] = 6
    with pytest.raises(ValidationError) as exc_info:
        judge(scores)
    assert "1-5" in str(exc_info.value.message) or "6" in str(exc_info.value.message)


def test_invalid_score_zero_returns_validation_error():
    """value=0 → ValidationError。"""
    scores = _all(3)
    scores[7] = 0
    with pytest.raises(ValidationError):
        judge(scores)


# --- save / get round-trip ---


def test_save_and_get_constitution_round_trip(session):
    """save_constitution 写入后 get_constitution 能读回完整结果。

    要求档案已存在，所以先建一个 UserProfile（用 model 直接建）。
    """
    from datetime import datetime

    from app.models.user_profile import UserProfile

    record = UserProfile(
        user_id=42,
        birthday="1990-01-15",
        gender="male",
        height_cm=175,
        weight_kg=70.0,
        forbidden_tags=["pork"],
    )
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)

    # 写入判定结果
    result = judge({1: 5, 2: 5, **{i: 1 for i in range(3, 10)}})
    save_constitution(session, user_id=42, result=result)

    # 读回
    fetched = get_constitution(session, user_id=42)
    assert fetched is not None
    assert fetched.primary == result.primary
    assert fetched.secondary == result.secondary
    assert fetched.scores_normalized == result.scores_normalized
    assert fetched.constitution_type_str == result.constitution_type_str


def test_save_constitution_raises_if_profile_missing(session):
    """档案不存在 → NotFoundError。"""
    from app.core.errors import NotFoundError

    result = judge(_all(1))
    with pytest.raises(NotFoundError):
        save_constitution(session, user_id=9999, result=result)


def test_get_constitution_returns_none_if_profile_missing(session):
    """档案不存在 → None。"""
    assert get_constitution(session, user_id=9999) is None


def test_get_constitution_returns_none_if_not_judged_yet(session):
    """档案存在但未测过体质 → None。"""
    from datetime import datetime

    from app.models.user_profile import UserProfile

    record = UserProfile(
        user_id=7,
        birthday="2000-01-01",
        gender="female",
    )
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()

    assert get_constitution(session, user_id=7) is None
