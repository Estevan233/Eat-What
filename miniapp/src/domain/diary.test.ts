import { describe, expect, it } from 'vitest'

import {
  dayLabel,
  dominantMood,
  groupDiaryDays,
  hasVisibleContent,
  inStreakWindow,
  logDishes,
  logsForSlot,
  monthGrid,
  shiftIsoDate,
  shiftYearMonth,
  todayIso,
  weekdayLabel,
} from './diary'
import type { DailyLogRead } from '@/api/daily'
import type { MealSnapshot } from '@/types/api'

function snapshot(names: string[]): MealSnapshot {
  return {
    items: names.map((name, index) => ({
      foodId: index + 1,
      name,
      mealRole: index === 0 ? 'main' : 'vegetable',
      category: 'homedish',
      cookingMethod: 'stirfry',
      visualKey: name,
      prepTimeMin: 5,
      cookTimeMin: 10,
      nutritionPerServing: { energyKcal: 200, proteinG: 10, fatG: 5, carbG: 20 },
      reason: '',
      score: 80,
    })),
    totalNutrition: { energyKcal: 600, proteinG: 30, fatG: 15, carbG: 60 },
    estimatedTimeMin: 25,
    reason: '',
  }
}

function log(overrides: Partial<DailyLogRead> = {}): DailyLogRead {
  return {
    id: 1,
    userId: 7,
    logDate: '2026-09-07',
    mealSlot: 'dinner',
    source: 'manual',
    shopName: null,
    note: null,
    recommendedFoodIds: [],
    chosenFoodIds: [],
    recommendationId: null,
    recommendedMeal: null,
    chosenMeal: null,
    manualDishes: null,
    chosenTotalNutrition: null,
    mood: 'neutral',
    activityLevel: 'normal',
    weatherTag: null,
    diningMode: 'cook',
    audience: 'personal',
    partySize: 1,
    ...overrides,
  }
}

describe('日期换算', () => {
  it('todayIso 用本地时区，不受 UTC 偏移影响', () => {
    expect(todayIso(new Date(2026, 8, 7, 23, 30))).toBe('2026-09-07')
    expect(todayIso(new Date(2026, 0, 1, 0, 10))).toBe('2026-01-01')
  })

  it('shiftIsoDate 跨月跨年都按自然日走', () => {
    expect(shiftIsoDate('2026-09-01', -1)).toBe('2026-08-31')
    expect(shiftIsoDate('2026-12-31', 1)).toBe('2027-01-01')
    expect(shiftIsoDate('2028-02-28', 1)).toBe('2028-02-29')
  })

  it('dayLabel 认今天/昨天，跨年补年份', () => {
    expect(dayLabel('2026-09-07', '2026-09-07')).toBe('今天')
    expect(dayLabel('2026-09-06', '2026-09-07')).toBe('昨天')
    expect(dayLabel('2026-08-30', '2026-09-07')).toBe('8月30日')
    expect(dayLabel('2025-12-30', '2026-09-07')).toBe('2025年12月30日')
  })

  it('weekdayLabel 与本地星期一致', () => {
    // 2026-09-07 是周一
    expect(weekdayLabel('2026-09-07')).toBe('周一')
    expect(weekdayLabel('2026-09-06')).toBe('周日')
  })

  it('monthGrid 固定 42 格且当月之外的格子标记 inMonth=false', () => {
    const cells = monthGrid(2026, 9)
    expect(cells).toHaveLength(42)
    // 2026-09-01 是周二，网格从周日 2026-08-30 开头
    expect(cells[0]).toEqual({ iso: '2026-08-30', inMonth: false })
    expect(cells[2].iso).toBe('2026-09-01')
    expect(cells[2].inMonth).toBe(true)
    expect(cells.filter((cell) => cell.inMonth)).toHaveLength(30)
  })

  it('shiftYearMonth 跨年翻页', () => {
    expect(shiftYearMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 })
    expect(shiftYearMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 })
  })
})

describe('可见性过滤', () => {
  it('manual 记录读 manual_dishes', () => {
    const dishes = logDishes(log({ manualDishes: [{ name: '小笼包', kcal: 220 }] }))
    expect(dishes).toEqual([{ name: '小笼包', kcal: 220 }])
  })

  it('推荐快照记录带餐位角色，便于配图标', () => {
    const dishes = logDishes(log({ source: 'recommendation', chosenMeal: snapshot(['红烧肉', '炒青菜']) }))
    expect(dishes.map((dish) => dish.mealRole)).toEqual(['main', 'vegetable'])
  })

  it('只剩 chosen_food_ids 的老记录没有展示价值', () => {
    const legacy = log({ source: 'recommendation', chosenFoodIds: [1, 2, 3], weatherTag: 'sunny' })
    expect(hasVisibleContent(legacy)).toBe(false)
  })

  it('有菜名/备注/店铺任意一项就保留', () => {
    expect(hasVisibleContent(log({ note: '和同事吃的' }))).toBe(true)
    expect(hasVisibleContent(log({ shopName: '老王面馆' }))).toBe(true)
    // 纯空白备注不算内容
    expect(hasVisibleContent(log({ note: '   ' }))).toBe(false)
  })
})

describe('按天分组', () => {
  it('丢掉无展示价值的记录，并按日期倒序', () => {
    const days = groupDiaryDays([
      log({ id: 1, logDate: '2026-09-05', chosenFoodIds: [9] }),
      log({ id: 2, logDate: '2026-09-07', manualDishes: [{ name: '豆浆' }] }),
      log({ id: 3, logDate: '2026-09-06', note: '加班外卖' }),
    ])
    expect(days.map((day) => day.date)).toEqual(['2026-09-07', '2026-09-06'])
    expect(days[0].logs).toHaveLength(1)
  })

  it('整条被过滤光的天不再出现空卡片', () => {
    const days = groupDiaryDays([log({ logDate: '2026-09-05', chosenFoodIds: [9] })])
    expect(days).toEqual([])
  })

  it('keepDates 保留只有外食小本记录的天（日记为空）', () => {
    const days = groupDiaryDays([], ['2026-09-03'])
    expect(days).toEqual([{ date: '2026-09-03', logs: [] }])
  })

  it('keepDates 不会覆盖已有日记的那天', () => {
    const days = groupDiaryDays(
      [log({ logDate: '2026-09-03', manualDishes: [{ name: '牛肉面' }] })],
      ['2026-09-03'],
    )
    expect(days).toHaveLength(1)
    expect(days[0].logs).toHaveLength(1)
  })

  it('logsForSlot 按餐次取过滤后的记录', () => {
    const days = groupDiaryDays([
      log({ id: 1, logDate: '2026-09-07', mealSlot: 'lunch', note: '午饭' }),
      log({ id: 2, logDate: '2026-09-07', mealSlot: 'dinner', note: '晚饭' }),
    ])
    expect(logsForSlot(days[0], 'dinner').map((item) => item.id)).toEqual([2])
    expect(logsForSlot(days[0], 'breakfast')).toEqual([])
    expect(logsForSlot(undefined, 'dinner')).toEqual([])
  })
})

describe('日历心情与连续打卡', () => {
  it('dominantMood 取出现最多的一天心情', () => {
    const logs = [
      log({ mood: 'happy' }),
      log({ mood: 'tired' }),
      log({ mood: 'tired' }),
    ]
    expect(dominantMood(logs)).toBe('tired')
    expect(dominantMood([])).toBeUndefined()
  })

  it('今天已记：连续 3 天覆盖今天与前两天', () => {
    expect(inStreakWindow('2026-09-07', '2026-09-07', 3, true)).toBe(true)
    expect(inStreakWindow('2026-09-05', '2026-09-07', 3, true)).toBe(true)
    expect(inStreakWindow('2026-09-04', '2026-09-07', 3, true)).toBe(false)
  })

  it('今天还没记：锚点退到昨天，避免🔥错位到明天', () => {
    expect(inStreakWindow('2026-09-07', '2026-09-07', 2, false)).toBe(false)
    expect(inStreakWindow('2026-09-06', '2026-09-07', 2, false)).toBe(true)
    expect(inStreakWindow('2026-09-05', '2026-09-07', 2, false)).toBe(true)
  })

  it('连续 0 天时不显示火焰', () => {
    expect(inStreakWindow('2026-09-07', '2026-09-07', 0, true)).toBe(false)
  })
})
