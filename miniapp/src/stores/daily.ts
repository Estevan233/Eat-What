import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getToday, getWeather } from '@/api/context'
import {
  chooseFood as apiChooseFood,
  chooseMeal as apiChooseMeal,
  getHistory,
  getTodayLog,
  recommend as apiRecommend,
} from '@/api/daily'
import type { DailyLogRead, HistoryResponse } from '@/api/daily'
import { applySubstitution as replaceMealSlot } from '@/domain/meal'
import { ApiError } from '@/types/api'
import { createRequestId } from '@/utils/id'
import type {
  ActivityLevel,
  Audience,
  DiningMode,
  MealRecommendation,
  MealIntent,
  MealSnapshot,
  MealSubstitution,
  Mood,
  RecommendRequest,
  TodayContext,
  WeatherData,
} from '@/types/api'

const WEATHER_KEY = 'eat_what_weather'
const TODAY_CTX_KEY = 'eat_what_today_ctx'
const MOOD_KEY = 'eat_what_mood'
const ACTIVITY_KEY = 'eat_what_activity'
const DINING_MODE_KEY = 'eat_what_dining_mode'
const AUDIENCE_KEY = 'eat_what_audience'
const PARTY_SIZE_KEY = 'eat_what_party_size'
const CITY_KEY = 'eat_what_city'
const MEAL_CACHE_KEY = 'eat_what_meal_recommendation_v2'
const RECENT_COOK_IDS_KEY = 'eat_what_recent_cook_ids_v1'
const MEAL_CACHE_VERSION = 2
// 覆盖 6 次最大家庭套餐（每套至多 6 道），给 CloudBase 事件读取延迟留出余量。
const MAX_RECENT_RESULT_IDS = 36
const WEATHER_SNAPSHOT_TTL_MS = 2 * 60 * 60 * 1000

interface MealCache {
  version: number
  savedAt: string
  recommendation: MealRecommendation
  currentMeal: MealSnapshot
  appliedSubstitutions: MealSubstitution[]
}

function parseStorage<T>(key: string): T | null {
  const value = uni.getStorageSync(key)
  if (!value) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

function readMealCache(): MealCache | null {
  const cache = parseStorage<MealCache>(MEAL_CACHE_KEY)
  if (!cache || cache.version !== MEAL_CACHE_VERSION) return null
  if (!cache.recommendation?.primaryMeal || !cache.currentMeal) return null
  return cache
}

function appendRecentIds(existing: number[], latest: number[]): number[] {
  const uniqueNewest: number[] = []
  const seen = new Set<number>()
  for (const value of [...existing, ...latest].reverse()) {
    if (seen.has(value)) continue
    seen.add(value)
    uniqueNewest.unshift(value)
  }
  return uniqueNewest.slice(-MAX_RECENT_RESULT_IDS)
}

function freshWeatherSnapshot(value: WeatherData | null): WeatherData | undefined {
  if (!value) return undefined
  // 中性 fallback（providerAvailable=false）不算新鲜：
  // 否则一次供应商失败会被前端缓存 2 小时，期间一直显示"天气暂不可用"且不重试。
  if (!value.providerAvailable) return undefined
  const fetchedAt = Date.parse(value.fetchedAt)
  if (!Number.isFinite(fetchedAt)) return undefined
  const age = Date.now() - fetchedAt
  return age >= -5 * 60 * 1000 && age <= WEATHER_SNAPSHOT_TTL_MS
    ? value
    : undefined
}

function isTransient(error: unknown): boolean {
  return error instanceof ApiError && (
    error.code === 'NETWORK_ERROR'
    || error.code === 'TIMEOUT'
    || (error.statusCode ?? 0) >= 500
  )
}

function todayStr(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export const useDailyStore = defineStore('daily', () => {
  const todayContext = ref<TodayContext | null>(parseStorage<TodayContext>(TODAY_CTX_KEY))
  const weather = ref<WeatherData | null>(parseStorage<WeatherData>(WEATHER_KEY))
  const mood = ref<Mood>((uni.getStorageSync(MOOD_KEY) as Mood) || 'neutral')
  const activityLevel = ref<ActivityLevel>(
    (uni.getStorageSync(ACTIVITY_KEY) as ActivityLevel) || 'normal',
  )
  const storedMode = uni.getStorageSync(DINING_MODE_KEY)
  const diningMode = ref<DiningMode>(storedMode === 'eat_out' ? 'eat_out' : 'cook')
  const storedAudience = uni.getStorageSync(AUDIENCE_KEY)
  const audience = ref<Audience>(storedAudience === 'family' ? 'family' : 'personal')
  const storedPartySize = Number(uni.getStorageSync(PARTY_SIZE_KEY))
  const partySize = ref(
    audience.value === 'family'
      ? Math.min(8, Math.max(2, storedPartySize || 2))
      : 1,
  )
  const city = ref(String(uni.getStorageSync(CITY_KEY) || ''))
  const loading = ref(false)
  const todayLog = ref<DailyLogRead | null>(null)

  const cached = readMealCache()
  const serverRecommendation = ref<MealRecommendation | null>(cached?.recommendation || null)
  const currentMeal = ref<MealSnapshot | null>(cached?.currentMeal || null)
  const appliedSubstitutions = ref<MealSubstitution[]>(cached?.appliedSubstitutions || [])
  const stale = ref(cached !== null)
  const offline = ref(false)
  const lastRequestId = ref<string | null>(null)
  const recentCookIds = ref<number[]>(parseStorage<number[]>(RECENT_COOK_IDS_KEY) || [])
  // AI 用餐意图：由首页输入框解析得到；为空时不向后端提交该字段。
  const mealIntent = ref<MealIntent | null>(null)
  let pendingRecommendRequestId: string | null = null

  // The old homepage reads recommendation.foods until the plate UI commit lands.
  const recommendation = computed(() => serverRecommendation.value)
  const hasFreshWeather = computed(() => Boolean(freshWeatherSnapshot(weather.value)))
  const availableSubstitutions = computed(() => {
    if (!serverRecommendation.value || !currentMeal.value) return []
    return serverRecommendation.value.substitutions.filter((option) => {
      const current = currentMeal.value?.items.find(
        (item) => item.mealRole === option.targetRole,
      )
      return current?.foodId !== option.replacement.foodId
    })
  })

  function persistMealCache(): void {
    if (!serverRecommendation.value || !currentMeal.value) return
    const cache: MealCache = {
      version: MEAL_CACHE_VERSION,
      savedAt: new Date().toISOString(),
      recommendation: serverRecommendation.value,
      currentMeal: currentMeal.value,
      appliedSubstitutions: appliedSubstitutions.value,
    }
    uni.setStorageSync(MEAL_CACHE_KEY, JSON.stringify(cache))
  }

  async function fetchTodayContext(force = false): Promise<TodayContext> {
    if (!force && todayContext.value?.date === todayStr()) return todayContext.value
    const data = await getToday()
    todayContext.value = data
    uni.setStorageSync(TODAY_CTX_KEY, JSON.stringify(data))
    return data
  }

  async function fetchWeather(lat: number, lng: number): Promise<WeatherData> {
    const data = await getWeather(lat, lng)
    weather.value = data
    uni.setStorageSync(WEATHER_KEY, JSON.stringify(data))
    return data
  }

  function clearWeather(): void {
    weather.value = null
    uni.removeStorageSync(WEATHER_KEY)
  }

  async function fetchRecommend(lat?: number, lng?: number): Promise<MealRecommendation> {
    loading.value = true
    lastRequestId.value = null
    try {
      const requestId = pendingRecommendRequestId || createRequestId('recommend')
      pendingRecommendRequestId = requestId
      const body: RecommendRequest = {
        requestId,
        mood: mood.value,
        activityLevel: activityLevel.value,
        lat,
        lng,
        diningMode: diningMode.value,
        audience: audience.value,
        partySize: partySize.value,
        excludeFoodIds: [...recentCookIds.value],
        weatherSnapshot: freshWeatherSnapshot(weather.value),
        mealIntent: mealIntent.value ?? undefined,
      }
      const data = await apiRecommend(body)
      pendingRecommendRequestId = null
      serverRecommendation.value = data
      currentMeal.value = data.primaryMeal
      appliedSubstitutions.value = []
      stale.value = false
      offline.value = false
      persistMealCache()
      recentCookIds.value = appendRecentIds(
        recentCookIds.value,
        data.primaryMeal.items.map((item) => item.foodId),
      )
      uni.setStorageSync(RECENT_COOK_IDS_KEY, JSON.stringify(recentCookIds.value))
      return data
    } catch (error) {
      if (error instanceof ApiError) lastRequestId.value = error.requestId || null
      if (isTransient(error) && serverRecommendation.value && currentMeal.value) {
        stale.value = true
        offline.value = true
        return serverRecommendation.value
      }
      pendingRecommendRequestId = null
      throw error
    } finally {
      loading.value = false
    }
  }

  function applySubstitution(substitution: MealSubstitution): void {
    if (stale.value || offline.value) throw new ApiError('离线推荐仅供查看', 'OFFLINE_READ_ONLY')
    if (!currentMeal.value) throw new ApiError('请先获取推荐', 'NO_RECOMMENDATION')
    currentMeal.value = replaceMealSlot(currentMeal.value, substitution)
    appliedSubstitutions.value = [
      ...appliedSubstitutions.value.filter(
        (item) => item.targetRole !== substitution.targetRole,
      ),
      substitution,
    ]
    persistMealCache()
  }

  async function chooseCurrentMeal(): Promise<DailyLogRead> {
    if (stale.value || offline.value) throw new ApiError('离线推荐不能确认', 'OFFLINE_READ_ONLY')
    if (!serverRecommendation.value || !currentMeal.value) {
      throw new ApiError('请先获取推荐', 'NO_RECOMMENDATION')
    }
    const data = await apiChooseMeal({
      recommendationId: serverRecommendation.value.recommendationId,
      selectedFoodIds: currentMeal.value.items.map((item) => item.foodId),
      substitutions: appliedSubstitutions.value.map((item) => ({
        targetRole: item.targetRole,
        replacementFoodId: item.replacement.foodId,
      })),
    })
    todayLog.value = data
    return data
  }

  async function chooseFood(foodId: number): Promise<DailyLogRead> {
    const data = await apiChooseFood(foodId)
    todayLog.value = data
    return data
  }

  async function fetchTodayLog(): Promise<DailyLogRead | null> {
    try {
      const data = await getTodayLog()
      todayLog.value = data
      if (data) {
        mood.value = data.mood as Mood
        activityLevel.value = data.activityLevel as ActivityLevel
        uni.setStorageSync(MOOD_KEY, mood.value)
        uni.setStorageSync(ACTIVITY_KEY, activityLevel.value)
      }
      return data
    } catch (error) {
      if (isTransient(error)) return todayLog.value
      throw error
    }
  }

  async function fetchHistory(days = 30): Promise<HistoryResponse | null> {
    try {
      return await getHistory(days)
    } catch (error) {
      if (isTransient(error)) return null
      throw error
    }
  }

  function setMood(value: Mood): void {
    mood.value = value
    uni.setStorageSync(MOOD_KEY, value)
  }

  function setActivityLevel(value: ActivityLevel): void {
    activityLevel.value = value
    uni.setStorageSync(ACTIVITY_KEY, value)
  }

  function clearMealRecommendation(): void {
    serverRecommendation.value = null
    currentMeal.value = null
    appliedSubstitutions.value = []
    stale.value = false
    offline.value = false
    uni.removeStorageSync(MEAL_CACHE_KEY)
  }

  function setDiningMode(value: DiningMode): void {
    if (diningMode.value === value) return
    diningMode.value = value
    uni.setStorageSync(DINING_MODE_KEY, value)
    clearMealRecommendation()
  }

  function setAudience(value: Audience): void {
    if (audience.value === value) return
    audience.value = value
    uni.setStorageSync(AUDIENCE_KEY, value)
    partySize.value = value === 'personal' ? 1 : Math.max(2, partySize.value)
    uni.setStorageSync(PARTY_SIZE_KEY, partySize.value)
    clearMealRecommendation()
  }

  function setPartySize(value: number): void {
    const nextValue = audience.value === 'personal'
      ? 1
      : Math.min(8, Math.max(2, Math.round(value)))
    if (partySize.value === nextValue) return
    partySize.value = nextValue
    uni.setStorageSync(PARTY_SIZE_KEY, partySize.value)
    clearMealRecommendation()
  }

  function setCity(value: string): void {
    city.value = value.trim()
    uni.setStorageSync(CITY_KEY, city.value)
  }

  /**
   * 设置 AI 解析出的用餐意图。传入 null 表示清除。
   * 变更会让当前推荐失效，下一次推荐请求带上新的意图约束。
   */
  function setMealIntent(intent: MealIntent | null): void {
    mealIntent.value = intent
    clearMealRecommendation()
  }

  function clearMealIntent(): void {
    if (mealIntent.value === null) return
    mealIntent.value = null
    clearMealRecommendation()
  }

  return {
    todayContext,
    weather,
    recommendation,
    hasFreshWeather,
    serverRecommendation,
    currentMeal,
    appliedSubstitutions,
    availableSubstitutions,
    stale,
    offline,
    lastRequestId,
    todayLog,
    mood,
    activityLevel,
    diningMode,
    audience,
    partySize,
    city,
    loading,
    fetchTodayContext,
    fetchWeather,
    clearWeather,
    fetchRecommend,
    applySubstitution,
    chooseCurrentMeal,
    chooseFood,
    fetchTodayLog,
    fetchHistory,
    setMood,
    setActivityLevel,
    setDiningMode,
    setAudience,
    setPartySize,
    setCity,
    mealIntent,
    setMealIntent,
    clearMealIntent,
    clearMealRecommendation,
  }
})
