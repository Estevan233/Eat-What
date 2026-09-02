<template>
  <view class="page">
    <!-- 头部：标题 + 连续打卡 + 视图切换 -->
    <view class="heading">
      <view class="title-row">
        <text class="page-title">餐食日记</text>
        <text v-if="streakDays > 0" class="streak-pill">🔥 已连记 {{ streakDays }} 天</text>
      </view>
      <text class="page-sub">
        {{ streakDays > 0 ? `第 ${streakDays} 天，好好吃饭；今天也别忘了记一笔` : '记下每一餐，攒下好好吃饭的轨迹' }}
      </text>
      <view class="view-toggle">
        <text
          class="view-toggle-btn"
          :class="{ 'view-toggle-on': viewMode === 'list' }"
          @click="viewMode = 'list'"
        >📋 列表</text>
        <text
          class="view-toggle-btn"
          :class="{ 'view-toggle-on': viewMode === 'calendar' }"
          @click="viewMode = 'calendar'"
        >🗓 日历</text>
      </view>
    </view>

    <!-- 搜索 -->
    <view class="search-box">
      <text class="search-icon">🔍</text>
      <input
        class="search-input"
        :value="query"
        maxlength="64"
        placeholder="搜菜名、店名或备注"
        confirm-type="search"
        @input="onQueryInput"
        @confirm="loadList"
      />
      <text v-if="query" class="search-clear" @click="clearQuery">✕</text>
    </view>

    <!-- 日历视图 -->
    <view v-if="viewMode === 'calendar'" class="calendar">
      <view class="calendar-head">
        <text class="calendar-nav" @click="calendarMonth = shiftMonth(calendarMonth.year, calendarMonth.month, -1)">‹</text>
        <text class="calendar-title">{{ calendarMonth.year }} 年 {{ calendarMonth.month }} 月</text>
        <text class="calendar-nav" @click="calendarMonth = shiftMonth(calendarMonth.year, calendarMonth.month, 1)">›</text>
      </view>
      <view class="calendar-weekrow">
        <text v-for="week in WEEKDAYS" :key="`week-${week}`" class="calendar-weeklabel">{{ week }}</text>
      </view>
      <view class="calendar-grid">
        <view
          v-for="cell in monthDays(calendarMonth.year, calendarMonth.month)"
          :key="cell.iso"
          class="calendar-cell"
          :class="{ 'calendar-cell-off': !cell.inMonth, 'calendar-cell-today': cell.iso === today, 'calendar-cell-edited': cell.iso === editedDayIso }"
          @click="jumpToDay(cell.iso)"
        >
          <text class="calendar-cell-day">{{ cell.iso.slice(-2) }}</text>
          <view
            v-if="cell.inMonth && dominantMood(cell.iso)"
            class="calendar-cell-mood"
            :style="{ background: moodColor(dominantMood(cell.iso)) }"
          />
          <text v-if="cell.inMonth && dayLogCount(cell.iso)" class="calendar-cell-dining">🥡</text>
        </view>
      </view>
      <view class="calendar-legend">
        <text class="calendar-legend-text">点击任意一天跳回列表对应记录；🥡 表示当天有外食小本记录。</text>
      </view>
    </view>

    <!-- 加载骨架 -->
    <view v-if="viewMode === 'list' && loading && items.length === 0" class="list">
      <view v-for="n in 3" :key="n" class="skeleton-card">
        <view class="sk sk-title" />
        <view class="sk sk-line short" />
        <view class="sk sk-line" />
        <view class="sk sk-line short" />
      </view>
    </view>

    <!-- 空态 -->
    <view v-else-if="viewMode === 'list' && !loading && groups.length === 0" class="empty">
      <text class="empty-emoji">{{ query ? '🔍' : '🥗' }}</text>
      <text class="empty-title">{{ query ? `没有找到「${query}」的记录` : '还没有记录' }}</text>
      <text class="empty-text">
        {{ query ? '换个关键词试试，或直接把这顿补记下来' : '三餐、外食、下午那杯奶茶……都值得被记住' }}
      </text>
      <button class="empty-cta" @click="openRecord()">
        {{ query ? '✍️ 补记一笔' : '✍️ 记下今天第一餐' }}
      </button>
    </view>

    <!-- 加载失败 -->
    <view v-else-if="viewMode === 'list' && pageError" class="empty">
      <text class="empty-emoji">😵</text>
      <text class="empty-title">日记加载失败</text>
      <text class="empty-text">{{ pageError }}</text>
      <button class="empty-cta" @click="loadList">重新加载</button>
    </view>

    <!-- 列表 -->
    <view v-else-if="viewMode === 'list'" class="list">
      <text v-if="query.trim()" class="result-hint">找到 {{ total }} 条记录</text>
      <view
        v-for="(day, dayIndex) in groups"
        :id="`day-card-${day.date}`"
        :key="day.date"
        class="day-card"
        :style="{ animationDelay: `${Math.min(dayIndex, 8) * 70}ms` }"
      >
        <view class="day-head">
          <view class="day-left">
            <text class="day-date">{{ dayLabel(day.date) }}</text>
            <text class="day-week">{{ weekdayLabel(day.date) }}</text>
          </view>
          <view class="day-tags">
            <text v-if="inStreakRun(day.date)" class="flame">🔥</text>
            <text class="day-count">{{ day.logs.length }} 条</text>
          </view>
        </view>

        <view class="meal-seg">
          <template v-for="slot in MEAL_SLOT_OPTIONS" :key="slot.value">
            <view class="seg-head">
              <text class="seg-emoji">{{ slot.emoji }}</text>
              <text class="seg-label">{{ slot.label }}</text>
              <text v-if="logsFor(day.date, slot.value).length" class="seg-dot">·</text>
            </view>
            <view v-if="logsFor(day.date, slot.value).length" class="seg-entries">
              <view
                v-for="log in logsFor(day.date, slot.value)"
                :key="log.id"
                class="entry"
                hover-class="entry-hover"
                @click="openEdit(log)"
              >
                <view class="entry-dishes">
                  <view v-for="dish in dishLines(log)" :key="dish.key" class="dish-line">
                    <text class="dish-icon">{{ dish.icon }}</text>
                    <text class="dish-name">{{ dish.name }}</text>
                    <text v-if="dish.kcal" class="dish-kcal">≈{{ dish.kcal }} kcal</text>
                  </view>
                  <view v-if="dishLines(log).length === 0" class="dish-line legacy">
                    <text class="dish-icon">🗒️</text>
                    <text class="dish-name">旧版记录{{ log.chosenFoodIds.length ? `：选择了 ${log.chosenFoodIds.length} 道` : '' }}</text>
                  </view>
                </view>
                <view v-if="logMetaLines(log).length" class="entry-meta">
                  <text v-for="line in logMetaLines(log)" :key="line" class="meta-line">{{ line }}</text>
                </view>
              </view>
            </view>
            <view v-else class="fill-pill" @click="openRecord(slot.value)">
              ＋ 补记{{ slot.label }}
            </view>
          </template>
        </view>

        <view v-if="dayLogCount(day.date) > 0" class="dining-memory-row">
          <text class="dining-memory-icon">🥡</text>
          <text class="dining-memory-text">
            外食小本：{{ dayLogCount(day.date) }} 条
          </text>
          <view class="dining-memory-link" @click="openDiningMemoryForDay(day.date)">
            去外食小本看看 ›
          </view>
        </view>
      </view>
    </view>

    <!-- 悬浮记一笔 -->
    <view class="fab" hover-class="fab-hover" @click="openRecord()">
      <text class="fab-icon">＋</text>
      <text class="fab-text">记一笔</text>
    </view>

    <!-- ===== 底部半屏弹层（记一笔 / 编辑） ===== -->
    <view
      v-if="recordOpen || editOpen"
      class="overlay"
      @touchmove.stop.prevent="noop"
      @click="closeSheets"
    >
      <view class="sheet" @click.stop>
        <view class="sheet-handle" />

        <!-- 记一笔：AI 一句话自记 -->
        <template v-if="recordOpen">
          <view class="sheet-head">
            <text class="sheet-title">{{ recordStep === 'preview' ? '确认这顿吃的' : '记一笔' }}</text>
            <text class="sheet-close" @click="closeRecord">✕</text>
          </view>

          <!-- step 1: 一句话 -->
          <view v-if="recordStep === 'sentence'" class="sheet-body">
            <view class="field">
              <text class="field-label">今天吃了什么？一句话就行</text>
              <view class="sentence-wrap">
                <textarea
                  class="sentence-input"
                  :value="sentenceText"
                  maxlength="100"
                  placeholder="例如：早上吃了小笼包和豆浆"
                  @input="onSentenceInput"
                />
                <text class="counter">{{ sentenceText.length }}/100</text>
              </view>
            </view>
            <view class="hint-chips">
              <text
                v-for="example in EXAMPLE_SENTENCES"
                :key="example"
                class="hint-chip"
                @click="sentenceText = example"
              >{{ example }}</text>
            </view>
            <button class="primary-btn" :disabled="parsingBusy" @click="startParse">
              {{ parsingBusy ? '正在理解…' : '✨ AI 帮我记' }}
            </button>
            <view class="skip-row">
              <text class="skip-text" @click="skipAi">先不解析，我直接填</text>
            </view>
            <view class="note-tip">AI 只做文字理解，记没记对由你确认；落库不经过 AI，断网也能直接填。</view>
          </view>

          <!-- step 2: AI 理解中 -->
          <view v-else-if="recordStep === 'parsing'" class="sheet-body parsing">
            <view class="thinking">
              <text class="thinking-emoji">🤔</text>
              <text class="thinking-text">AI 正在理解…</text>
            </view>
            <view class="dots">
              <text v-for="n in 3" :key="n" class="dot" :style="{ animationDelay: `${n * 180}ms` }" />
            </view>
            <text class="parsing-tip">正在识别餐次、菜品，并给每道菜估个能量</text>
          </view>

          <!-- step 3: 表单预览修正 -->
          <view v-else class="sheet-body">
            <view v-if="recDegraded" class="warn-banner">
              AI 这次没看懂，已把原话作为备注；可以直接在下面补上菜名和店名。
            </view>
            <view class="field">
              <text class="field-label">哪一餐</text>
              <view class="chip-row">
                <text
                  v-for="option in MEAL_SLOT_OPTIONS"
                  :key="option.value"
                  class="chip"
                  :class="{ 'chip-on': recSlot === option.value }"
                  @click="recSlot = option.value"
                >{{ option.emoji }} {{ option.label }}</text>
              </view>
            </view>
            <view class="field">
              <text class="field-label">吃了什么</text>
              <view class="dish-editor">
                <view v-for="(dish, index) in recDishes" :key="`rec-dish-${index}`" class="dish-row">
                  <input
                    class="dish-name-input"
                    :value="dish.name"
                    maxlength="40"
                    placeholder="菜名，例如：小笼包"
                    @input="onRecDishName(index, $event)"
                  />
                  <input
                    class="dish-kcal-input"
                    type="digit"
                    :value="dish.kcal"
                    maxlength="4"
                    placeholder="kcal"
                    @input="onRecDishKcal(index, $event)"
                  />
                  <text class="dish-remove" @click="removeRecDish(index)">✕</text>
                </view>
                <view class="add-dish" @click="addRecDish">＋ 再加一道</view>
              </view>
            </view>
            <view class="field">
              <text class="field-label">店铺（外食才填）</text>
              <input
                class="text-input"
                :value="recShop"
                maxlength="80"
                placeholder="例如：楼下老王面馆"
                @input="onRecShopInput"
              />
            </view>
            <view class="field">
              <text class="field-label">备注</text>
              <input
                class="text-input"
                :value="recNote"
                maxlength="200"
                placeholder="和谁吃的、好不好吃……（可选）"
                @input="onRecNoteInput"
              />
            </view>
            <button class="primary-btn" :disabled="!canSaveRecord || recSaving" @click="saveRecord">
              {{ recSaving ? '正在保存…' : '保存到日记' }}
            </button>
          </view>
        </template>

        <!-- 编辑一条记录 -->
        <template v-else-if="editOpen && editLog">
          <view class="sheet-head">
            <text class="sheet-title">编辑记录</text>
            <text class="sheet-close" @click="closeSheets">✕</text>
          </view>
          <view class="sheet-body">
            <view v-if="!isEditManual" class="warn-banner warn-soft">
              这一餐来自「就吃这个」快照，只能改餐次和备注，菜品不能改动。
            </view>
            <view class="field">
              <text class="field-label">哪一餐</text>
              <view class="chip-row">
                <text
                  v-for="option in MEAL_SLOT_OPTIONS"
                  :key="option.value"
                  class="chip"
                  :class="{ 'chip-on': editSlot === option.value }"
                  @click="editSlot = option.value"
                >{{ option.emoji }} {{ option.label }}</text>
              </view>
            </view>

            <template v-if="isEditManual">
              <view class="field">
                <text class="field-label">吃了什么</text>
                <view class="dish-editor">
                  <view v-for="(dish, index) in editDishes" :key="`edit-dish-${index}`" class="dish-row">
                    <input
                      class="dish-name-input"
                      :value="dish.name"
                      maxlength="40"
                      placeholder="菜名"
                      @input="onEditDishName(index, $event)"
                    />
                    <input
                      class="dish-kcal-input"
                      type="digit"
                      :value="dish.kcal"
                      maxlength="4"
                      placeholder="kcal"
                      @input="onEditDishKcal(index, $event)"
                    />
                    <text class="dish-remove" @click="removeEditDish(index)">✕</text>
                  </view>
                  <view class="add-dish" @click="addEditDish">＋ 再加一道</view>
                </view>
              </view>
              <view class="field">
                <text class="field-label">店铺（外食才填）</text>
                <input
                  class="text-input"
                  :value="editShop"
                  maxlength="80"
                  placeholder="例如：楼下老王面馆"
                  @input="onEditShopInput"
                />
              </view>
            </template>
            <view v-else class="field">
              <text class="field-label">当时吃的</text>
              <view class="snapshot">
                <view v-for="item in editSnapshotItems" :key="item" class="snapshot-line">{{ item }}</view>
              </view>
            </view>

            <view class="field">
              <text class="field-label">备注</text>
              <input
                class="text-input"
                :value="editNote"
                maxlength="500"
                placeholder="补充点什么？（可选）"
                @input="onEditNoteInput"
              />
            </view>
            <button class="primary-btn" :disabled="!canSaveEdit || editSaving" @click="saveEdit">
              {{ editSaving ? '正在保存…' : '保存修改' }}
            </button>
            <view class="delete-row" @click="confirmDelete">
              <text class="delete-text">删除这条记录</text>
            </view>
          </view>
        </template>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShareAppMessage, onShareTimeline, onShow } from '@dcloudio/uni-app'

import {
  MEAL_SLOT_OPTIONS,
  inferMealSlotByClock,
  parseMealNote,
  type ParsedMealNote,
} from '@/ai/meal-log'
import { createManualLog, deleteLog, getHistory, updateLog, type DailyLogRead } from '@/api/daily'
import type { ManualDishItem } from '@/api/daily'
import { listDiningMemories, type DiningMemoryRead } from '@/api/dining'
import { MOOD_LABELS } from '@/constants/daily'
import { WEATHER_TAG_LABEL } from '@/constants/weather'
import { useDailyStore } from '@/stores/daily'
import type { MealRole, MealSlot, Mood } from '@/types/api'

const HISTORY_DAYS = 90
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const roleIcon: Record<MealRole, string> = { main: '🥘', vegetable: '🥬', staple: '🍚' }
const MOOD_EMOJI: Record<Mood, string> = {
  happy: '😄', neutral: '😌', tired: '😪', stressed: '😣', anxious: '😰',
}
const EXAMPLE_SENTENCES = [
  '早上吃了小笼包和豆浆',
  '中午在楼下老王面馆吃了红烧牛肉面',
  '晚上自己煮了番茄鸡蛋面，加了个蛋',
]

const dailyStore = useDailyStore()

const items = ref<DailyLogRead[]>([])
const total = ref(0)
const streakDays = ref(0)
const loading = ref(false)
const pageError = ref('')
const query = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined

const today = ref(todayStr())

type CalendarMode = 'list' | 'calendar'
const viewMode = ref<CalendarMode>('list')
const calendarMonth = ref<{ year: number; month: number }>(currentMonth())
const diningMemoriesByDate = ref<Map<string, DiningMemoryRead[]>>(new Map())
const editedDayIso = ref<string>('')

interface DayGroup {
  date: string
  logs: DailyLogRead[]
}

const groups = computed<DayGroup[]>(() => {
  const map = new Map<string, DailyLogRead[]>()
  for (const log of items.value) {
    const list = map.get(log.logDate)
    if (list) list.push(log)
    else map.set(log.logDate, [log])
  }
  return Array.from(map.entries()).map(([date, logs]) => ({ date, logs }))
})

/** 一组展示行（与模板函数共用的小类型）。 */
interface DishLine {
  key: string
  icon: string
  name: string
  kcal?: number | null
}

// ---------- 加载与搜索 ----------

async function loadList(): Promise<void> {
  loading.value = true
  pageError.value = ''
  try {
    const keyword = query.value.trim()
    const response = await getHistory(HISTORY_DAYS, keyword)
    items.value = response.items
    total.value = response.total
    streakDays.value = response.streakDays
    today.value = todayStr()
    await loadDiningMemories()
  } catch (error) {
    pageError.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

async function loadDiningMemories(): Promise<void> {
  try {
    // 拉取最近最多 200 条外食记忆（个人级数据量），按本地日期分组。
    const list = await listDiningMemories(1, 200)
    const map = new Map<string, DiningMemoryRead[]>()
    for (const memory of list.items) {
      const iso = memory.createdAt.slice(0, 10)
      const arr = map.get(iso) ?? []
      arr.push(memory)
      map.set(iso, arr)
    }
    diningMemoriesByDate.value = map
  } catch {
    // 外食记忆是辅助视图，失败时不影响日记主流程
    diningMemoriesByDate.value = new Map()
  }
}

function onQueryInput(event: Event): void {
  query.value = inputValue(event)
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    loadList()
  }, 300)
}

function clearQuery(): void {
  query.value = ''
  loadList()
}

onShow(() => {
  loadList()
})

// ---------- 展示工具 ----------

function inputValue(event: Event): string {
  const inputEvent = event as unknown as { detail?: { value?: string } }
  return inputEvent.detail?.value || ''
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

function parseLocalDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatIso(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

function shiftDate(iso: string, delta: number): string {
  const base = parseLocalDate(iso)
  base.setDate(base.getDate() + delta)
  return formatIso(base)
}

function dayLabel(iso: string): string {
  const date = parseLocalDate(iso)
  const now = parseLocalDate(today.value)
  const isToday = formatIso(date) === today.value
  const isYesterday = date.getTime() === now.getTime() - 24 * 60 * 60 * 1000
  if (isToday) return '今天'
  if (isYesterday) return '昨天'
  const sameYear = date.getFullYear() === now.getFullYear()
  const prefix = sameYear ? '' : `${date.getFullYear()}年`
  return `${prefix}${date.getMonth() + 1}月${date.getDate()}日`
}

function weekdayLabel(iso: string): string {
  return WEEKDAYS[parseLocalDate(iso).getDay()]
}

function inStreakRun(iso: string): boolean {
  if (!streakDays.value) return false
  let anchor = today.value
  if (!items.value.some((log) => log.logDate === today.value)) {
    anchor = shiftDate(today.value, -1)
  }
  const start = shiftDate(anchor, -(streakDays.value - 1))
  return iso >= start && iso <= anchor
}

function currentMonth(): { year: number; month: number } {
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() + 1 }
}

function monthDays(year: number, month: number): Array<{ iso: string; inMonth: boolean }> {
  // 返回整 6 周共 42 个日期，便于网格稳定。
  const first = new Date(year, month - 1, 1)
  const offset = first.getDay()
  const start = new Date(year, month - 1, 1 - offset)
  const days: Array<{ iso: string; inMonth: boolean }> = []
  for (let i = 0; i < 42; i += 1) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    days.push({
      iso: formatIso(d),
      inMonth: d.getMonth() + 1 === month && d.getFullYear() === year,
    })
  }
  return days
}

function shiftMonth(year: number, month: number, offset: number): { year: number; month: number } {
  const d = new Date(year, month - 1 + offset, 1)
  return { year: d.getFullYear(), month: d.getMonth() + 1 }
}

function dominantMood(date: string): Mood | undefined {
  const group = groups.value.find((g) => g.date === date)
  if (!group) return undefined
  const counts = new Map<string, number>()
  for (const log of group.logs) {
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

function moodColor(mood: Mood | undefined): string {
  switch (mood) {
    case 'happy':
      return '#FFD9BF'
    case 'neutral':
      return '#FFE7C2'
    case 'tired':
      return '#C5D8F0'
    case 'stressed':
      return '#F4C7BE'
    case 'anxious':
      return '#E0CFE8'
    default:
      return '#E5DDD3'
  }
}

function dayLogCount(date: string): number {
  return diningMemoriesByDate.value.get(date)?.length ?? 0
}

function jumpToDay(date: string): void {
  editedDayIso.value = date
  viewMode.value = 'list'
  // 等列表重新渲染后再滚动，避免选择器尚未挂载
  setTimeout(() => {
    uni.pageScrollTo({ selector: `#day-card-${date}`, duration: 280, offsetTop: 60 })
  }, 80)
}

function openDiningMemoryForDay(date: string): void {
  // 跳到外食小本，附带日期查询参数便于聚焦这一天。
  // 后端 v033+ 才会按日期过滤；当前已部署版本会忽略 date 参数，页面仍可按需搜索。
  uni.navigateTo({ url: `/pages/dining-memory/dining-memory?date=${date}` })
}

function logsFor(date: string, slot: MealSlot): DailyLogRead[] {
  const day = groups.value.find((group) => group.date === date)
  if (!day) return []
  return day.logs.filter((log) => log.mealSlot === slot)
}

function dishLines(log: DailyLogRead): DishLine[] {
  if (log.source === 'manual') {
    return (log.manualDishes ?? []).map((dish, index) => ({
      key: `${log.id}-m-${index}`,
      icon: '🍴',
      name: dish.name,
      kcal: dish.kcal,
    }))
  }
  if (log.chosenMeal?.items?.length) {
    return log.chosenMeal.items.map((item, index) => ({
      key: `${log.id}-r-${index}`,
      icon: roleIcon[item.mealRole] ?? '🥘',
      name: item.name,
    }))
  }
  return []
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

function logMetaLines(log: DailyLogRead): string[] {
  const lines: string[] = []
  if (log.shopName) lines.push(`🥡 ${log.shopName}`)
  else if (log.diningMode === 'eat_out') lines.push('🥡 外出就餐')
  if (log.source !== 'manual' && log.chosenTotalNutrition) {
    const kcal = Math.round(log.chosenTotalNutrition.energyKcal)
    const protein = log.chosenTotalNutrition.proteinG
    const minutes = log.chosenMeal?.estimatedTimeMin
    lines.push(
      `约 ${kcal} kcal / 份${protein != null ? ` · 蛋白质 ${formatNumber(protein)}g` : ''}${minutes ? ` · 约 ${minutes} 分钟` : ''}`,
    )
  }
  if (log.note) lines.push(`📝 ${log.note}`)
  const mood = log.mood as Mood
  if (mood && mood !== 'neutral' && MOOD_LABELS[mood]) {
    lines.push(`${MOOD_EMOJI[mood]} ${MOOD_LABELS[mood]}`)
  }
  if (log.weatherTag && (WEATHER_TAG_LABEL as Record<string, string>)[log.weatherTag]) {
    lines.push(`${(WEATHER_TAG_LABEL as Record<string, string>)[log.weatherTag]}`)
  }
  return lines
}

function errorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : ''
  if (message) return message.length > 60 ? `${message.slice(0, 60)}…` : message
  return '网络似乎开小差了，请稍后再试'
}

function noop(): void {
  // 拦截弹层内滚动冒泡到页面。
}

// ---------- 记一笔（AI 一句话自记） ----------

type DishRow = { name: string; kcal: string }
const recordOpen = ref(false)
const recordStep = ref<'sentence' | 'parsing' | 'preview'>('sentence')
const parsingBusy = ref(false)
const sentenceText = ref('')
const recSlot = ref<MealSlot>('dinner')
const recDishes = ref<DishRow[]>([])
const recShop = ref('')
const recNote = ref('')
const recDegraded = ref(false)
const recSaving = ref(false)

const canSaveRecord = computed(() => {
  return recDishes.value.some((dish) => dish.name.trim()) || Boolean(recNote.value.trim())
})

function blankDishRows(): DishRow[] {
  return []
}

function openRecord(slot?: MealSlot): void {
  recordOpen.value = true
  editOpen.value = false
  recordStep.value = 'sentence'
  parsingBusy.value = false
  recSlot.value = slot ?? inferMealSlotByClock()
  sentenceText.value = ''
  recDishes.value = blankDishRows()
  recShop.value = ''
  recNote.value = ''
  recDegraded.value = false
  recSaving.value = false
}

function closeRecord(): void {
  recordOpen.value = false
}

function closeSheets(): void {
  recordOpen.value = false
  editOpen.value = false
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

async function startParse(): Promise<void> {
  const sentence = sentenceText.value.trim()
  if (!sentence) {
    uni.showToast({ title: '先写一句今天吃了什么', icon: 'none' })
    return
  }
  if (parsingBusy.value) return
  parsingBusy.value = true
  recordStep.value = 'parsing'
  const [parsed] = await Promise.all([parseMealNote(sentence), delay(420)])
  applyParsed(parsed ?? {
    mealSlot: inferMealSlotByClock(),
    dishes: [],
    shopName: null,
    note: sentence,
    degraded: true,
  })
  parsingBusy.value = false
  if (recordOpen.value) recordStep.value = 'preview'
}

function applyParsed(parsed: ParsedMealNote): void {
  recSlot.value = parsed.mealSlot
  recDishes.value = parsed.dishes.map((dish) => ({ name: dish.name, kcal: dish.kcal == null ? '' : String(dish.kcal) }))
  recShop.value = parsed.shopName ?? ''
  recNote.value = parsed.note ?? ''
  recDegraded.value = parsed.degraded
}

function skipAi(): void {
  if (!recDishes.value.some((dish) => dish.name.trim()) && !recNote.value.trim()) {
    recNote.value = sentenceText.value.trim()
  }
  recordStep.value = 'preview'
  recDegraded.value = false
}

function onSentenceInput(event: Event): void {
  sentenceText.value = inputValue(event)
}

function addRecDish(): void {
  recDishes.value.push({ name: '', kcal: '' })
}

function removeRecDish(index: number): void {
  recDishes.value.splice(index, 1)
}

function onRecDishName(index: number, event: Event): void {
  recDishes.value[index] = { ...recDishes.value[index], name: inputValue(event) }
}

function onRecDishKcal(index: number, event: Event): void {
  recDishes.value[index] = { ...recDishes.value[index], kcal: inputValue(event) }
}

function onRecShopInput(event: Event): void {
  recShop.value = inputValue(event)
}

function onRecNoteInput(event: Event): void {
  recNote.value = inputValue(event)
}

function toKcalNumber(raw: string): number | null | undefined {
  const trimmed = raw.trim()
  if (!trimmed) return undefined
  const value = Number(trimmed)
  if (!Number.isFinite(value) || value <= 0) return null
  return Math.round(value)
}

function buildDishPayload(rows: DishRow[]): ManualDishItem[] {
  const payload: ManualDishItem[] = []
  for (const row of rows) {
    const name = row.name.trim()
    if (!name) continue
    const kcal = toKcalNumber(row.kcal)
    if (kcal === undefined) payload.push({ name })
    else payload.push({ name, kcal })
  }
  return payload
}

async function saveRecord(): Promise<void> {
  if (recSaving.value || !canSaveRecord.value) return
  recSaving.value = true
  try {
    const shop = recShop.value.trim()
    const saveDate = todayStr()
    const created = await createManualLog({
      logDate: saveDate,
      mealSlot: recSlot.value,
      dishes: buildDishPayload(recDishes.value),
      shopName: shop || null,
      note: recNote.value.trim() || null,
    })
    haptic()
    uni.showToast({ title: '已记入日记', icon: 'success' })
    const isManualToday = created.logDate === saveDate
    closeRecord()
    await loadList()
    if (isManualToday) {
      dailyStore.fetchTodayLogs().catch(() => undefined)
    }
    if (shop) suggestDiningMemory(shop, recDishes.value)
  } catch (error) {
    uni.showToast({ title: errorMessage(error), icon: 'none' })
  } finally {
    recSaving.value = false
  }
}

/** 自记带店铺后，提示是否顺手记进外食小本（喜欢/避雷反哺推荐）。 */
function suggestDiningMemory(shop: string, rows: DishRow[]): void {
  const firstDish = rows.find((row) => row.name.trim())?.name.trim() || ''
  uni.showModal({
    title: '记进外食小本？',
    content: firstDish
      ? `可以顺手把这顿记进外食小本（${firstDish} · ${shop}），下次推荐会更懂你的口味。`
      : `可以顺手把 ${shop} 记进外食小本，下次推荐会更懂你的口味。`,
    confirmText: '去记录',
    cancelText: '不用了',
    success: (result) => {
      if (!result.confirm) return
      uni.navigateTo({
        url: `/pages/dining-memory/dining-memory?shopName=${encodeURIComponent(shop)}&dishName=${encodeURIComponent(firstDish)}`,
      })
    },
  })
}

function haptic(): void {
  try {
    uni.vibrateShort({})
  } catch {
    // 部分端不支持震动，忽略。
  }
}

// ---------- 编辑 ----------

const editOpen = ref(false)
const editLog = ref<DailyLogRead | null>(null)
const editSlot = ref<MealSlot>('dinner')
const editDishes = ref<DishRow[]>([])
const editShop = ref('')
const editNote = ref('')
const editSaving = ref(false)

const isEditManual = computed(() => editLog.value?.source === 'manual')
const canSaveEdit = computed(() => {
  if (isEditManual.value) {
    return editDishes.value.some((dish) => dish.name.trim()) || Boolean(editNote.value.trim())
  }
  return true
})
const editSnapshotItems = computed<string[]>(() => {
  const log = editLog.value
  if (!log) return []
  return dishLines(log).map((dish) => `${dish.icon} ${dish.name}`)
})

function openEdit(log: DailyLogRead): void {
  editLog.value = log
  editSlot.value = log.mealSlot
  editDishes.value = (log.manualDishes ?? []).map((dish) => ({
    name: dish.name,
    kcal: dish.kcal == null ? '' : String(dish.kcal),
  }))
  editShop.value = log.shopName ?? ''
  editNote.value = log.note ?? ''
  editOpen.value = true
  recordOpen.value = false
  editSaving.value = false
}

function addEditDish(): void {
  editDishes.value.push({ name: '', kcal: '' })
}

function removeEditDish(index: number): void {
  editDishes.value.splice(index, 1)
}

function onEditDishName(index: number, event: Event): void {
  editDishes.value[index] = { ...editDishes.value[index], name: inputValue(event) }
}

function onEditDishKcal(index: number, event: Event): void {
  editDishes.value[index] = { ...editDishes.value[index], kcal: inputValue(event) }
}

function onEditShopInput(event: Event): void {
  editShop.value = inputValue(event)
}

function onEditNoteInput(event: Event): void {
  editNote.value = inputValue(event)
}

async function saveEdit(): Promise<void> {
  const log = editLog.value
  if (!log || editSaving.value || !canSaveEdit.value) return
  editSaving.value = true
  try {
    const body: { mealSlot: MealSlot; note: string | null; dishes?: ManualDishItem[]; shopName?: string | null } = {
      mealSlot: editSlot.value,
      note: editNote.value.trim() || null,
    }
    if (log.source === 'manual') {
      body.dishes = buildDishPayload(editDishes.value)
      body.shopName = editShop.value.trim() || null
    }
    await updateLog(log.id, body)
    haptic()
    uni.showToast({ title: '已保存', icon: 'success' })
    const isToday = log.logDate === today.value
    closeSheets()
    await loadList()
    if (isToday) {
      dailyStore.fetchTodayLogs().catch(() => undefined)
    } else {
      // 编辑过去的记录：跳回那一天，避免用户看不到保存结果
      jumpToDay(log.logDate)
    }
  } catch (error) {
    uni.showToast({ title: errorMessage(error), icon: 'none' })
  } finally {
    editSaving.value = false
  }
}

function confirmDelete(): void {
  const log = editLog.value
  if (!log) return
  uni.showModal({
    title: '删除这条记录？',
    content: '删除后这一餐就不再出现在日记里，连续打卡可能受影响。',
    confirmText: '删除',
    confirmColor: '#c34c36',
    success: async (result) => {
      if (!result.confirm) return
      try {
        await deleteLog(log.id)
        uni.showToast({ title: '已删除', icon: 'success' })
        const isToday = log.logDate === today.value
        closeSheets()
        await loadList()
        if (isToday) {
          dailyStore.fetchTodayLogs().catch(() => undefined)
        }
      } catch (error) {
        uni.showToast({ title: errorMessage(error), icon: 'none' })
      }
    },
  })
}

onShareAppMessage(() => {
  return {
    title: '饭卜卜 · 我的餐食日记',
    path: '/pages/history/history',
  }
})

onShareTimeline(() => {
  return {
    title: '饭卜卜 · 我的餐食日记',
  }
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: 32rpx 32rpx 240rpx;
  box-sizing: border-box;
  background: $bg;
}

/* 头部 */
.heading {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-bottom: 24rpx;
}
.title-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.page-title {
  color: $ink;
  font-size: 44rpx;
  font-weight: 800;
  letter-spacing: 1rpx;
}
.streak-pill {
  padding: 7rpx 16rpx;
  border-radius: 999rpx;
  color: $brand-dark;
  background: $brand-light;
  font-size: 20rpx;
  font-weight: 700;
  box-shadow: 0 4rpx 12rpx rgba(232, 89, 12, 0.12);
}
.page-sub {
  color: $ink-3;
  font-size: 22rpx;
  line-height: 1.6;
}

/* 搜索 */
.search-box {
  display: flex;
  align-items: center;
  gap: 10rpx;
  height: 84rpx;
  padding: 0 24rpx;
  border: 1rpx solid $line;
  border-radius: 999rpx;
  background: $card;
  box-shadow: $shadow-card;
  box-sizing: border-box;
}
.search-icon {
  font-size: 26rpx;
}
.search-input {
  flex: 1;
  min-width: 0;
  color: $ink;
  font-size: 25rpx;
}
.search-clear {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44rpx;
  height: 44rpx;
  border-radius: 50%;
  color: $ink-3;
  background: $bg;
  font-size: 22rpx;
}

/* 列表与分组卡片 */
.list {
  display: flex;
  flex-direction: column;
  gap: 24rpx;
  margin-top: 26rpx;
}
.result-hint {
  color: $ink-3;
  font-size: 21rpx;
  text-align: center;
}
.day-card {
  padding: 26rpx 26rpx 12rpx;
  border: 1rpx solid $line;
  border-radius: $radius-md;
  background: $card;
  box-shadow: $shadow-card;
  animation: rise 0.45s ease both;
}
@keyframes rise {
  from { opacity: 0; transform: translateY(26rpx); }
  to { opacity: 1; transform: translateY(0); }
}
.day-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid $line;
}
.day-left {
  display: flex;
  align-items: baseline;
  gap: 12rpx;
}
.day-date {
  color: $ink;
  font-size: 29rpx;
  font-weight: 750;
}
.day-week {
  color: $ink-3;
  font-size: 21rpx;
}
.day-tags {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.flame {
  font-size: 26rpx;
}
.day-count {
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  color: $ink-2;
  background: $bg;
  font-size: 19rpx;
}

/* 餐次分段 */
.meal-seg {
  padding-top: 6rpx;
}
.seg-head {
  display: flex;
  align-items: center;
  gap: 10rpx;
  padding: 18rpx 2rpx 10rpx;
}
.seg-emoji {
  font-size: 25rpx;
}
.seg-label {
  color: $ink-2;
  font-size: 23rpx;
  font-weight: 700;
}
.seg-dot {
  color: $brand;
}
.seg-entries {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.entry {
  padding: 18rpx 20rpx;
  border: 1rpx solid $line;
  border-radius: $radius-sm;
  background: $bg;
  transition: transform 0.12s ease;
}
.entry-hover {
  transform: scale(0.985);
  background: #f7efe6;
}
.entry-dishes {
  display: flex;
  flex-direction: column;
  gap: 9rpx;
}
.dish-line {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.dish-line.legacy {
  color: $ink-3;
  font-size: 22rpx;
}
.dish-icon {
  flex: 0 0 auto;
  font-size: 22rpx;
}
.dish-name {
  min-width: 0;
  flex: 1;
  color: $ink;
  font-size: 25rpx;
  font-weight: 600;
  word-break: break-all;
}
.dish-kcal {
  flex: 0 0 auto;
  color: $ink-3;
  font-size: 19rpx;
}
.entry-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx 18rpx;
  padding-top: 12rpx;
  margin-top: 12rpx;
  border-top: 1rpx dashed $line;
}
.meta-line {
  color: $ink-2;
  font-size: 19rpx;
  line-height: 1.5;
}

/* 补记入口 */
.fill-pill {
  margin: 6rpx 0 10rpx;
  padding: 16rpx;
  border: 2rpx dashed $brand-soft;
  border-radius: $radius-sm;
  color: $brand;
  background: #fffaf5;
  font-size: 22rpx;
  text-align: center;
}
.fill-pill:active {
  background: $brand-light;
}

/* 骨架屏 */
.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  padding: 26rpx;
  border: 1rpx solid $line;
  border-radius: $radius-md;
  background: $card;
}
.sk {
  height: 26rpx;
  border-radius: 10rpx;
  background: linear-gradient(90deg, #f4ece2 25%, #faf3ea 50%, #f4ece2 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
.sk-title {
  width: 36%;
  height: 30rpx;
}
.sk-line.short { width: 58%; }
.sk-line { width: 88%; }
@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* 空态 */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14rpx;
  min-height: 48vh;
  justify-content: center;
  text-align: center;
  padding: 0 40rpx;
}
.empty-emoji {
  font-size: 84rpx;
  line-height: 1;
}
.empty-title {
  color: $ink;
  font-size: 29rpx;
  font-weight: 750;
}
.empty-text {
  color: $ink-3;
  font-size: 22rpx;
  line-height: 1.6;
}
.empty-cta {
  height: 84rpx;
  line-height: 84rpx;
  margin-top: 16rpx;
  padding: 0 44rpx;
  border-radius: 999rpx;
  color: #fff;
  background: $grad-brand;
  box-shadow: $shadow-cta;
  font-size: 26rpx;
  font-weight: 700;
}
.empty-cta::after {
  border: none;
}

/* 悬浮记一笔 */
.fab {
  position: fixed;
  right: 36rpx;
  bottom: 48rpx;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 8rpx;
  height: 96rpx;
  padding: 0 30rpx;
  border-radius: 999rpx;
  color: #fff;
  background: $grad-brand;
  box-shadow: $shadow-cta;
}
.fab-hover {
  opacity: 0.9;
  transform: scale(0.97);
}
.fab-icon {
  font-size: 34rpx;
  font-weight: 400;
  line-height: 1;
}
.fab-text {
  font-size: 27rpx;
  font-weight: 750;
}

/* 弹层通用 */
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: flex-end;
  background: rgba(43, 35, 32, 0.45);
  animation: fade-in 0.2s ease;
}
@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
.sheet {
  width: 100%;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  border-radius: 36rpx 36rpx 0 0;
  background: $card;
  box-shadow: 0 -10rpx 40rpx rgba(43, 35, 32, 0.16);
  animation: slide-up 0.26s ease;
}
@keyframes slide-up {
  from { transform: translateY(60rpx); opacity: 0.6; }
  to { transform: translateY(0); opacity: 1; }
}
.sheet-handle {
  flex: 0 0 auto;
  width: 72rpx;
  height: 8rpx;
  margin: 16rpx auto 6rpx;
  border-radius: 999rpx;
  background: $line;
}
.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18rpx 32rpx 10rpx;
}
.sheet-title {
  color: $ink;
  font-size: 33rpx;
  font-weight: 800;
}
.sheet-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52rpx;
  height: 52rpx;
  border-radius: 50%;
  color: $ink-2;
  background: $bg;
  font-size: 24rpx;
}
.sheet-body {
  max-height: 74vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 12rpx 32rpx calc(env(safe-area-inset-bottom) + 40rpx);
}
.sheet-body.parsing {
  min-height: 420rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 22rpx;
}
.thinking {
  display: flex;
  align-items: center;
  gap: 14rpx;
}
.thinking-emoji {
  font-size: 52rpx;
}
.thinking-text {
  color: $ink;
  font-size: 32rpx;
  font-weight: 750;
}
.dots {
  display: flex;
  gap: 14rpx;
}
.dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 50%;
  background: $brand;
  opacity: 0.3;
  animation: dot-pulse 0.9s ease infinite;
}
@keyframes dot-pulse {
  0%, 100% { opacity: 0.25; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.25); }
}
.parsing-tip {
  color: $ink-3;
  font-size: 22rpx;
}

/* 表单字段 */
.field {
  margin-bottom: 26rpx;
}
.field-label {
  display: block;
  margin-bottom: 12rpx;
  color: $ink;
  font-size: 23rpx;
  font-weight: 700;
}
.sentence-wrap {
  position: relative;
}
.sentence-input {
  width: 100%;
  height: 190rpx;
  padding: 20rpx 20rpx 44rpx;
  border: 1rpx solid $line;
  border-radius: 20rpx;
  color: $ink;
  background: $bg;
  font-size: 25rpx;
  line-height: 1.6;
  box-sizing: border-box;
}
.counter {
  position: absolute;
  right: 16rpx;
  bottom: 12rpx;
  color: $ink-3;
  font-size: 18rpx;
}
.hint-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin: 16rpx 0 6rpx;
}
.hint-chip {
  padding: 10rpx 18rpx;
  border: 1rpx solid $line;
  border-radius: 999rpx;
  color: $ink-2;
  background: $card;
  font-size: 20rpx;
}
.hint-chip:active {
  border-color: $brand-soft;
  color: $brand;
  background: $brand-light;
}
.primary-btn {
  height: 92rpx;
  line-height: 92rpx;
  margin-top: 14rpx;
  border-radius: 999rpx;
  color: #fff;
  background: $grad-brand;
  box-shadow: $shadow-cta;
  font-size: 28rpx;
  font-weight: 750;
}
.primary-btn::after {
  border: none;
}
.primary-btn[disabled] {
  color: #fff;
  opacity: 0.5;
  box-shadow: none;
}
.skip-row {
  margin-top: 20rpx;
  text-align: center;
}
.skip-text {
  color: $ink-3;
  font-size: 22rpx;
  text-decoration: underline;
}
.note-tip {
  margin-top: 18rpx;
  color: $ink-3;
  font-size: 19rpx;
  line-height: 1.6;
  text-align: center;
}
.warn-banner {
  padding: 16rpx 20rpx;
  margin-bottom: 24rpx;
  border-radius: 16rpx;
  color: $warning-dark;
  background: $warning-light;
  font-size: 21rpx;
  line-height: 1.6;
}
.warn-soft {
  color: $ink-2;
  background: $brand-light;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14rpx;
}
.chip {
  padding: 12rpx 26rpx;
  border: 1rpx solid $line;
  border-radius: 999rpx;
  color: $ink-2;
  background: $card;
  font-size: 23rpx;
}
.chip-on {
  color: #fff;
  border-color: transparent;
  background: $grad-brand;
  font-weight: 700;
  box-shadow: 0 6rpx 14rpx rgba(232, 89, 12, 0.22);
}

/* 菜品编辑行 */
.dish-editor {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}
.dish-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.dish-name-input {
  min-width: 0;
  flex: 1;
  height: 78rpx;
  padding: 0 20rpx;
  border: 1rpx solid $line;
  border-radius: 16rpx;
  color: $ink;
  background: $bg;
  font-size: 23rpx;
  box-sizing: border-box;
}
.dish-kcal-input {
  flex: 0 0 150rpx;
  height: 78rpx;
  padding: 0 16rpx;
  border: 1rpx solid $line;
  border-radius: 16rpx;
  color: $ink;
  background: $bg;
  font-size: 23rpx;
  text-align: right;
  box-sizing: border-box;
}
.dish-remove {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56rpx;
  height: 56rpx;
  border-radius: 50%;
  color: $ink-3;
  background: $bg;
  font-size: 20rpx;
}
.add-dish {
  padding: 16rpx;
  border: 2rpx dashed $brand-soft;
  border-radius: 16rpx;
  color: $brand;
  background: #fffaf5;
  font-size: 22rpx;
  text-align: center;
}
.add-dish:active {
  background: $brand-light;
}
.text-input {
  width: 100%;
  height: 80rpx;
  padding: 0 20rpx;
  border: 1rpx solid $line;
  border-radius: 18rpx;
  color: $ink;
  background: $bg;
  font-size: 24rpx;
  box-sizing: border-box;
}
.snapshot {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  padding: 20rpx;
  border: 1rpx solid $line;
  border-radius: 18rpx;
  background: $bg;
}
.snapshot-line {
  color: $ink;
  font-size: 24rpx;
  line-height: 1.5;
}
.delete-row {
  margin-top: 24rpx;
  text-align: center;
}
.delete-text {
  color: #c34c36;
  font-size: 23rpx;
  text-decoration: underline;
}

/* 视图切换 */
.view-toggle {
  display: flex;
  gap: 12rpx;
  margin-top: 18rpx;
}
.view-toggle-btn {
  flex: 0 0 auto;
  padding: 10rpx 22rpx;
  border-radius: 999rpx;
  background: $card;
  color: $ink-2;
  font-size: 23rpx;
  border: 1rpx solid $line;
}
.view-toggle-on {
  background: $grad-brand;
  color: #fff;
  border-color: transparent;
  font-weight: 700;
}

/* 日历视图 */
.calendar {
  margin: 24rpx 0 32rpx;
  padding: 24rpx;
  border-radius: $radius-lg;
  background: $card;
  box-shadow: $shadow-card;
}
.calendar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18rpx;
}
.calendar-title {
  color: $ink;
  font-size: 29rpx;
  font-weight: 800;
}
.calendar-nav {
  width: 60rpx;
  text-align: center;
  color: $ink-2;
  font-size: 32rpx;
  font-weight: 700;
}
.calendar-weekrow {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6rpx;
  margin-bottom: 8rpx;
}
.calendar-weeklabel {
  text-align: center;
  color: $ink-3;
  font-size: 20rpx;
}
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 6rpx;
}
.calendar-cell {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 92rpx;
  border-radius: 16rpx;
  background: $bg;
  color: $ink;
  font-size: 24rpx;
}
.calendar-cell-off {
  color: $ink-3;
  opacity: 0.5;
}
.calendar-cell-today {
  border: 1rpx solid $brand;
}
.calendar-cell-edited {
  outline: 2rpx solid $brand;
  outline-offset: -2rpx;
}
.calendar-cell-mood {
  position: absolute;
  bottom: 8rpx;
  left: 50%;
  width: 18rpx;
  height: 18rpx;
  border-radius: 50%;
  transform: translateX(-50%);
}
.calendar-cell-dining {
  position: absolute;
  top: 6rpx;
  right: 8rpx;
  font-size: 18rpx;
}
.calendar-legend {
  margin-top: 14rpx;
  color: $ink-3;
  font-size: 20rpx;
  line-height: 1.5;
}
.calendar-legend-text {
  display: block;
}

/* 外食小本行 */
.dining-memory-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-top: 18rpx;
  padding: 14rpx 18rpx;
  border-radius: 18rpx;
  background: #fff8ef;
  border: 1rpx solid $brand-soft;
}
.dining-memory-icon {
  font-size: 26rpx;
}
.dining-memory-text {
  flex: 1;
  color: $ink-2;
  font-size: 23rpx;
}
.dining-memory-link {
  color: $brand;
  font-size: 23rpx;
  font-weight: 600;
}
</style>
