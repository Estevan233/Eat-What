/**
 * 餐食日记的展示模型：日期换算、可见性过滤、按天分组。
 *
 * 全部是纯函数，与页面/组件解耦，便于单测；history.vue 只负责交互与渲染。
 */
import type { DailyLogRead } from '@/api/daily'
import type { MealRole, MealSlot, Mood } from '@/types/api'

export const WEEKDAY_LABELS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

/** 日记里一道菜的最小展示信息（菜名 + 可选能量；推荐快照还带餐位角色）。 */
export interface DiaryDish {
  name: string
  kcal?: number | null
  mealRole?: MealRole
}

/** 分组后的一天（logs 已过滤掉无展示价值的老记录）。 */
export interface DiaryDay {
  date: string
  logs: DailyLogRead[]
}

export function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

export function todayIso(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`
}

export function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function formatIso(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

export function shiftIsoDate(iso: string, deltaDays: number): string {
  const base = parseIsoDate(iso)
  base.setDate(base.getDate() + deltaDays)
  return formatIso(base)
}

/** 今天/昨天/前天…的人话日期；非今年补上年份。 */
export function dayLabel(iso: string, today: string): string {
  if (iso === today) return '今天'
  if (iso === shiftIsoDate(today, -1)) return '昨天'
  const date = parseIsoDate(iso)
  const now = parseIsoDate(today)
  const prefix = date.getFullYear() === now.getFullYear() ? '' : `${date.getFullYear()}年`
  return `${prefix}${date.getMonth() + 1}月${date.getDate()}日`
}

export function weekdayLabel(iso: string): string {
  return WEEKDAY_LABELS[parseIsoDate(iso).getDay()]
}

export function currentYearMonth(now: Date = new Date()): { year: number; month: number } {
  return { year: now.getFullYear(), month: now.getMonth() + 1 }
}

export function shiftYearMonth(
  year: number,
  month: number,
  offset: number,
): { year: number; month: number } {
  const date = new Date(year, month - 1 + offset, 1)
  return { year: date.getFullYear(), month: date.getMonth() + 1 }
}

/** 日历网格：固定 6 周 42 格，保证月份切换时布局不跳。 */
export function monthGrid(year: number, month: number): Array<{ iso: string; inMonth: boolean }> {
  const first = new Date(year, month - 1, 1)
  const start = new Date(year, month - 1, 1 - first.getDay())
  const cells: Array<{ iso: string; inMonth: boolean }> = []
  for (let i = 0; i < 42; i += 1) {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    cells.push({
      iso: formatIso(date),
      inMonth: date.getFullYear() === year && date.getMonth() + 1 === month,
    })
  }
  return cells
}

/** 一条记录的菜品：manual 走 manual_dishes，推荐快照走 chosen_meal.items。 */
export function logDishes(log: DailyLogRead): DiaryDish[] {
  if (log.source === 'manual') {
    return (log.manualDishes ?? []).map((dish) => ({ name: dish.name, kcal: dish.kcal }))
  }
  return (log.chosenMeal?.items ?? []).map((item) => ({ name: item.name, mealRole: item.mealRole }))
}

/**
 * 这条记录是否还有值得展示的内容。
 *
 * chosen_meal_json 缺失的老 schema 记录只剩 chosen_food_ids（一组无名称的 id），
 * 既无菜名也无备注、店铺，渲染出来只剩一行天气标签，对用户无价值。
 */
export function hasVisibleContent(log: DailyLogRead): boolean {
  return logDishes(log).length > 0
    || Boolean(log.note?.trim())
    || Boolean(log.shopName?.trim())
}

/**
 * 按天分组（日期倒序），顺手丢掉没有展示价值的老记录。
 *
 * keepDates 用于保留「只有外食小本记录」的天：这些天日记为空，但 🥡 行仍有信息。
 */
export function groupDiaryDays(logs: DailyLogRead[], keepDates: string[] = []): DiaryDay[] {
  const byDate = new Map<string, DailyLogRead[]>()
  for (const log of logs) {
    if (!hasVisibleContent(log)) continue
    const list = byDate.get(log.logDate)
    if (list) list.push(log)
    else byDate.set(log.logDate, [log])
  }
  for (const date of keepDates) {
    if (!byDate.has(date)) byDate.set(date, [])
  }
  return Array.from(byDate.entries())
    .map(([date, list]) => ({ date, logs: list }))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
}

export function logsForSlot(day: DiaryDay | undefined, slot: MealSlot): DailyLogRead[] {
  if (!day) return []
  return day.logs.filter((log) => log.mealSlot === slot)
}

/** 一天里出现次数最多的心情，用于日历色点。 */
export function dominantMood(logs: DailyLogRead[]): Mood | undefined {
  const counts = new Map<string, number>()
  for (const log of logs) {
    counts.set(log.mood, (counts.get(log.mood) ?? 0) + 1)
  }
  let best: string | undefined
  let bestCount = 0
  for (const [mood, count] of counts.entries()) {
    if (count > bestCount) {
      best = mood
      bestCount = count
    }
  }
  return best as Mood | undefined
}

/**
 * 这一天是否落在当前连续打卡区间内。
 *
 * 今天还没记时，后端算的连续天数以昨天为锚点，这里保持一致，否则🔥会错位。
 */
export function inStreakWindow(
  iso: string,
  today: string,
  streakDays: number,
  hasTodayLog: boolean,
): boolean {
  if (streakDays <= 0) return false
  const anchor = hasTodayLog ? today : shiftIsoDate(today, -1)
  const start = shiftIsoDate(anchor, -(streakDays - 1))
  return iso >= start && iso <= anchor
}
