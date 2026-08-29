"""节气 + 星座 + 生肖 service - 用 lunar_python 离线计算。

学习点：
- lunar_python 是纯 Python 实现，无需联网，启动期就能算
- 星座用阳历，按月份固定分界表（不同年份可能差 1 天，可接受）
- 缓存按 ISO 日期 key，避免同一天重复计算（用 dict + date key，进程内）
"""
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from lunar_python import Solar

from app.schemas.today_context import TodayContext

# 12 星座分界：起始月日（mmdd 整数）→ 星座英文键
# 通用边界（部分年份会有 ±1 天差异，PRD 接受）
# 顺序：aquarius(1.20) → pisces(2.19) → aries(3.21) → taurus(4.20) →
#       gemini(5.21) → cancer(6.22) → leo(7.23) → virgo(8.23) →
#       libra(9.23) → scorpio(10.24) → sagittarius(11.23) → capricorn(12.22)
# 注：12/22 ~ 1/19 是跨年 capricorn，1/20 前算去年 capricorn
_ZODIAC_BOUNDARIES: tuple[tuple[int, str], ...] = (
    (120, "aquarius"),
    (219, "pisces"),
    (321, "aries"),
    (420, "taurus"),
    (521, "gemini"),
    (622, "cancer"),
    (723, "leo"),
    (823, "virgo"),
    (923, "libra"),
    (1024, "scorpio"),
    (1123, "sagittarius"),
    (1222, "capricorn"),
)

# 星座中文名（与前端同步）
ZODIAC_NAMES_ZH: dict[str, str] = {
    "aries": "白羊座", "taurus": "金牛座", "gemini": "双子座",
    "cancer": "巨蟹座", "leo": "狮子座", "virgo": "处女座",
    "libra": "天秤座", "scorpio": "天蝎座", "sagittarius": "射手座",
    "capricorn": "摩羯座", "aquarius": "水瓶座", "pisces": "双鱼座",
}


def compute_zodiac(month: int, day: int) -> str:
    """按阳历 month/day 返回星座英文键。

    边界策略：拼成 mmdd 整数比较，先处理跨年 capricorn（12/22+ 或 1/1~1/19），
    其余从升序边界找最后一个 md >= 边界 的星座。
    """
    md = month * 100 + day
    # 跨年：12/22 ~ 12/31 + 1/1 ~ 1/19 都是 capricorn
    if md >= 1222 or md < 120:
        return "capricorn"
    last_sign = "capricorn"  # 兜底（理论上不会走到）
    for bm, sign in _ZODIAC_BOUNDARIES:
        if md < bm:
            break
        last_sign = sign
    return last_sign


def get_today_context(dt: datetime | None = None) -> TodayContext:
    """计算今天的节气/星座/生肖/农历上下文。

    Args:
        dt: 用于计算的日期，None 表示今天。便于测试固定日期。

    Returns:
        TodayContext：含星级、节气、生肖、农历月日等。
    """
    if dt is None:
        dt = datetime.now()

    solar = Solar.fromDate(dt)
    lunar = solar.getLunar()

    # 节气
    current_jq = lunar.getJieQi()  # 节气当天返回中文名，否则空串
    next_jq = lunar.getNextJieQi()  # 下一节气对象（当天为当前节气）
    next_jq_name = next_jq.getName()
    next_jq_date_str = next_jq.getSolar().toYmd()

    # 星座
    zodiac = compute_zodiac(solar.getMonth(), solar.getDay())

    # 生肖
    animal = lunar.getYearShengXiao()

    # 农历：lunar_python 的 getMonth() 在闰月返回负数（如 -6 表示闰六月）
    lunar_month_raw = lunar.getMonth()
    is_leap = lunar_month_raw < 0
    lunar_month = abs(lunar_month_raw)
    lunar_day = lunar.getDay()

    return TodayContext(
        date=dt.date(),
        solar_term_current=current_jq,
        solar_term_next_name=next_jq_name,
        solar_term_next_date=next_jq_date_str,
        zodiac_sign=zodiac,
        animal=animal,
        lunar_month=lunar_month,
        lunar_day=lunar_day,
        is_leap_month=is_leap,
    )


# 按 ISO 日期字符串缓存：同一天同一进程内只算一次
@lru_cache(maxsize=128)
def _get_today_context_cached(date_str: str) -> dict[str, Any]:
    """内部缓存入口：按日期 ISO 字符串 key。"""
    dt = datetime.fromisoformat(date_str)
    return get_today_context(dt).model_dump()


def get_today_context_cached(dt: datetime | None = None) -> TodayContext:
    """带进程缓存的 get_today_context（按 ISO 日期 key）。

    用法：路由调用这个，service 内测试可调底层 get_today_context 注入固定日期。
    """
    if dt is None:
        dt = datetime.now()
    data = _get_today_context_cached(dt.date().isoformat())
    return TodayContext.model_validate(data)


# ---- rules_v6 节气周期（仅供排序内部使用，不改 TodayContext 对外语义） ----


@dataclass(frozen=True)
class SolarTermCycle:
    """当前节气周期：active 节气 → next 节气之间的三档周期。

    phase_index 0/1/2 分别对应前/中/后段；节气当天归入新周期前段。
    """

    active_name: str
    active_date: date
    next_name: str
    next_date: date
    elapsed_days: int
    cycle_days: int
    phase_index: int  # 0=前 1=中 2=后


def _solar_to_date(solar: Any) -> date:
    return date(solar.getYear(), solar.getMonth(), solar.getDay())


@lru_cache(maxsize=128)
def get_solar_term_cycle(as_of: date) -> SolarTermCycle:
    """计算 as_of 所在节气周期。

    节气当天以当天为 active（getJieQi 命中），下一节气取 getNextJieQi；
    非节气日以 getPrevJieQi 为 active，getNextJieQi 为 next。
    phase_index = min(2, floor(3 * elapsed / cycle_days))，按比例而非固定天数。
    """
    solar = Solar.fromYmd(as_of.year, as_of.month, as_of.day)
    lunar = solar.getLunar()
    current_jq = lunar.getJieQi()  # 节气当天返中文名，否则空串
    if current_jq:
        active_name = current_jq
        active_date = as_of
        next_obj = lunar.getNextJieQi(whole_day=True)
    else:
        prev_obj = lunar.getPrevJieQi(whole_day=True)
        active_name = prev_obj.getName()
        active_date = _solar_to_date(prev_obj.getSolar())
        next_obj = lunar.getNextJieQi(whole_day=True)
    next_name = next_obj.getName()
    next_date = _solar_to_date(next_obj.getSolar())
    elapsed_days = (as_of - active_date).days
    cycle_days = max(1, (next_date - active_date).days)
    phase_index = min(2, 3 * elapsed_days // cycle_days)
    return SolarTermCycle(
        active_name=active_name,
        active_date=active_date,
        next_name=next_name,
        next_date=next_date,
        elapsed_days=elapsed_days,
        cycle_days=cycle_days,
        phase_index=phase_index,
    )
