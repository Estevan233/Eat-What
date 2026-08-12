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
import type {
  ActivityLevel,
  MealRecommendation,
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
const MEAL_CACHE_KEY = 'eat_what_meal_recommendation_v1'
const MEAL_CACHE_VERSION = 1

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
  const loading = ref(false)
  const todayLog = ref<DailyLogRead | null>(null)

  const cached = readMealCache()
  const serverRecommendation = ref<MealRecommendation | null>(cached?.recommendation || null)
  const currentMeal = ref<MealSnapshot | null>(cached?.currentMeal || null)
  const appliedSubstitutions = ref<MealSubstitution[]>(cached?.appliedSubstitutions || [])
  const stale = ref(cached !== null)
  const offline = ref(false)
  const lastRequestId = ref<string | null>(null)

  // The old homepage reads recommendation.foods until the plate UI commit lands.
  const recommendation = computed(() => serverRecommendation.value)
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
      const body: RecommendRequest = {
        mood: mood.value,
        activityLevel: activityLevel.value,
        lat,
        lng,
      }
      const data = await apiRecommend(body)
      serverRecommendation.value = data
      currentMeal.value = data.primaryMeal
      appliedSubstitutions.value = []
      stale.value = false
      offline.value = false
      persistMealCache()
      await fetchTodayLog()
      return data
    } catch (error) {
      if (error instanceof ApiError) lastRequestId.value = error.requestId || null
      if (isTransient(error) && serverRecommendation.value && currentMeal.value) {
        stale.value = true
        offline.value = true
        return serverRecommendation.value
      }
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

  return {
    todayContext,
    weather,
    recommendation,
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
  }
})
