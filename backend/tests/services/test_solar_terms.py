"""rules_v6 节气周期（SolarTermCycle）单测。

固定 2026 年节气日期验证前/中/后三档与边界切换：
- 立秋 2026-08-07 → 处暑 2026-08-23（cycle=16 天）
"""
from datetime import date, datetime

from app.services.solar_terms import (
    get_solar_term_cycle,
    get_today_context,
)


def test_solar_term_cycle_switches_on_term_day() -> None:
    # 立秋当天归入新周期前段，active=立秋，next=处暑
    cycle = get_solar_term_cycle(date(2026, 8, 7))
    assert cycle.active_name == "立秋"
    assert cycle.active_date == date(2026, 8, 7)
    assert cycle.next_name == "处暑"
    assert cycle.next_date == date(2026, 8, 23)
    assert cycle.phase_index == 0
    assert cycle.elapsed_days == 0


def test_solar_term_cycle_has_previous_and_next_boundaries() -> None:
    # 立秋→处暑周期中段，active 仍为立秋
    cycle = get_solar_term_cycle(date(2026, 8, 13))
    assert cycle.active_name == "立秋"
    assert cycle.active_date == date(2026, 8, 7)
    assert cycle.next_name == "处暑"
    assert cycle.cycle_days == 16
    assert cycle.elapsed_days == 6
    assert cycle.phase_index == 1


def test_solar_term_cycle_phase_tiers_across_period() -> None:
    # 前/中/后三档按比例切分：elapsed 0/5→前，6→中，11/15→后
    assert get_solar_term_cycle(date(2026, 8, 7)).phase_index == 0   # 前（当天）
    assert get_solar_term_cycle(date(2026, 8, 12)).phase_index == 0  # 前（elapsed 5）
    assert get_solar_term_cycle(date(2026, 8, 13)).phase_index == 1  # 中（elapsed 6）
    assert get_solar_term_cycle(date(2026, 8, 18)).phase_index == 2  # 后（elapsed 11）
    assert get_solar_term_cycle(date(2026, 8, 22)).phase_index == 2  # 后（elapsed 15）


def test_solar_term_cycle_next_term_day_starts_new_period() -> None:
    # 处暑当天切新周期前段
    cycle = get_solar_term_cycle(date(2026, 8, 23))
    assert cycle.active_name == "处暑"
    assert cycle.active_date == date(2026, 8, 23)
    assert cycle.next_name == "白露"
    assert cycle.phase_index == 0


def test_today_context_existing_current_term_semantics_are_unchanged() -> None:
    # TodayContext.solar_term_current 仍只在节气当天有值；周期是排序内部上下文
    ctx_on = get_today_context(datetime(2026, 8, 7))
    assert ctx_on.solar_term_current == "立秋"
    ctx_off = get_today_context(datetime(2026, 8, 15))
    assert ctx_off.solar_term_current == ""
