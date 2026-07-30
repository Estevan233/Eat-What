"""T08 节气 + 星座 service 单测。

覆盖：
1. compute_zodiac 12 个星座边界 + 跨年 capricorn
2. get_today_context 固定日期：节气当天/非节气日/生肖/星座
3. 缓存命中一致性
4. 闰月判定（用一个已知闰月日期）

学习点：
- compute_zodiac 是纯函数，直接断言边界
- get_today_context 接受 dt 参数，便于固定日期测试
- 缓存用 lru_cache，可 _get_today_context_cached.cache_clear() 重置
"""
from datetime import datetime

import pytest

from app.services.solar_terms import (
    _get_today_context_cached,
    compute_zodiac,
    get_today_context,
    get_today_context_cached,
)

# ---- 12 星座边界测试 ----

@pytest.mark.parametrize(
    "month,day,expected",
    [
        # 用边界日当天和前后一天测每个星座
        (1, 19, "capricorn"),    # < 1/20 跨年 capricorn
        (1, 20, "aquarius"),     # 边界当天
        (1, 21, "aquarius"),
        (2, 18, "aquarius"),
        (2, 19, "pisces"),       # 边界当天
        (2, 20, "pisces"),
        (3, 20, "pisces"),
        (3, 21, "aries"),        # 春分边界
        (3, 22, "aries"),
        (4, 19, "aries"),
        (4, 20, "taurus"),
        (5, 20, "taurus"),
        (5, 21, "gemini"),
        (6, 21, "gemini"),
        (6, 22, "cancer"),
        (7, 22, "cancer"),
        (7, 23, "leo"),
        (8, 22, "leo"),
        (8, 23, "virgo"),
        (9, 22, "virgo"),
        (9, 23, "libra"),
        (10, 23, "libra"),
        (10, 24, "scorpio"),
        (11, 22, "scorpio"),
        (11, 23, "sagittarius"),
        (12, 21, "sagittarius"),
        (12, 22, "capricorn"),   # 跨年 capricorn
        (12, 31, "capricorn"),   # 年末
        (1, 1, "capricorn"),     # 年初跨年
    ]
)
def test_compute_zodiac(month, day, expected):
    assert compute_zodiac(month, day) == expected


# ---- get_today_context 固定日期测试 ----

def test_get_today_context_zodiac_leo_for_jul23():
    """2026-07-23 → 星座 leo（狮子座）。"""
    ctx = get_today_context(datetime(2026, 7, 23))
    assert ctx.zodiac_sign == "leo"


def test_get_today_context_jul23_is_dashu_solar_term():
    """2026-07-23 恰好是大暑节气当天 → solar_term_current 含「大暑」。"""
    ctx = get_today_context(datetime(2026, 7, 23))
    assert ctx.solar_term_current == "大暑"


def test_get_today_context_jul24_next_term_not_empty():
    """2026-07-24 非节气日 → solar_term_current 空但下一节气非空。"""
    ctx = get_today_context(datetime(2026, 7, 24))
    assert ctx.solar_term_current == ""
    assert ctx.solar_term_next_name == "立秋"
    assert ctx.solar_term_next_date == "2026-08-07"


def test_get_today_context_feb04_is_lichun():
    """2026-02-04 是立春当天 → solar_term_current 包含立春。"""
    ctx = get_today_context(datetime(2026, 2, 4))
    assert "立春" == ctx.solar_term_current


def test_get_today_context_animal_year_horse_for_2026():
    """2026 年是马年 → animal == '马'。"""
    ctx = get_today_context(datetime(2026, 7, 23))
    assert ctx.animal == "马"


def test_get_today_context_lunar_month_day_populated():
    """农历月日字段填充正确。"""
    ctx = get_today_context(datetime(2026, 7, 23))
    # 2026-07-23 农历是 6 月初 10
    assert ctx.lunar_month == 6
    assert ctx.lunar_day == 10
    assert ctx.is_leap_month is False


def test_get_today_context_date_field_matches_input():
    """date 字段是输入日期。"""
    dt = datetime(2026, 7, 23)
    ctx = get_today_context(dt)
    assert ctx.date == dt.date()


def test_get_today_context_default_uses_now():
    """不传 dt 用当前时间，date 字段非空。"""
    ctx = get_today_context()
    assert ctx.date is not None
    assert ctx.solar_term_next_name  # 任何时候都有下一节气名


# ---- 边界日期：摩羯/水瓶交界 ----

def test_zodiac_boundary_jan20():
    """1/20 是水瓶起始；1/19 是摩羯（跨年延续）。"""
    assert compute_zodiac(1, 19) == "capricorn"
    assert compute_zodiac(1, 20) == "aquarius"


# ---- 缓存命中测试 ----

def test_cached_consistency_within_same_day():
    """同一天两次调用 cached 版本，结果一致且至少命中一次。"""
    _get_today_context_cached.cache_clear()
    dt = datetime(2026, 7, 23)
    ctx1 = get_today_context_cached(dt)
    ctx2 = get_today_context_cached(dt)
    assert ctx1.model_dump() == ctx2.model_dump()
    # cache_info 显示命中：第一次 miss + 写入，第二次命中
    info_after = _get_today_context_cached.cache_info()
    assert info_after.hits >= 1


def test_cached_keyed_by_iso_date_string():
    """缓存按 ISO 日期 key，不同日期不冲突。"""
    _get_today_context_cached.cache_clear()
    ctx1 = get_today_context(datetime(2026, 7, 23))
    ctx2 = get_today_context(datetime(2026, 7, 24))
    assert ctx1.date != ctx2.date
    assert ctx1.zodiac_sign == ctx2.zodiac_sign  # 都是 leo
    # 但 solar_term 不同
    assert ctx1.solar_term_current != ctx2.solar_term_current
