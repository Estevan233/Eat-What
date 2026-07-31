/**
 * 今日数据 Store
 *
 * - todayContext：节气上下文（公开 API 拉取，不需登录）- T09 实现
 * - weather：当前实况（需登录 + 已授权位置后调 api.context.getWeather）- T09 实现
 * - recommendation：当前推荐结果（3 道菜）- T11 新增
 * - todayLog：今天已写的 DailyLog（选择后更新）- T11 新增
 * - mood / activityLevel：用户选择的输入 - T11 新增
 * - fetchRecommend / chooseFood / fetchTodayLog - T11 新增
 *
 * 设计：
 * - weather 落 storage 避免重启丢失
 * - mood/activityLevel 落 storage 跨页面保持
 * - recommendation 不落盘（每次进页重新拉用户可刷新）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getToday, getWeather } from '@/api/context'
import { chooseFood as apiChoose, getHistory, getTodayLog, recommend as apiRecommend } from '@/api/daily'
import type {
  ActivityLevel,
  Mood,
  RecommendRequest,
  RecommendResponse,
  TodayContext,
  WeatherData,
} from '@/types/api'
import type { DailyLogRead, HistoryResponse } from '@/api/daily'

const WEATHER_KEY = 'eat_what_weather'
const TODAY_CTX_KEY = 'eat_what_today_ctx'
const MOOD_KEY = 'eat_what_mood'
const ACTIVITY_KEY = 'eat_what_activity'

export const useDailyStore = defineStore('daily', () => {
  const todayContext = ref<TodayContext | null>(null)
  const weather = ref<WeatherData | null>(null)

  // T11 新增
  const recommendation = ref<RecommendResponse | null>(null)
  const todayLog = ref<DailyLogRead | null>(null)
  const mood = ref<Mood>('neutral')
  const activityLevel = ref<ActivityLevel>('normal')
  const loading = ref(false)

  // 启动时从 storage 恢复（weather 1h 内复用比 token 短）
  const storedWeather = uni.getStorageSync(WEATHER_KEY)
  if (storedWeather) {
    try {
      weather.value = JSON.parse(storedWeather) as WeatherData
    } catch {
      weather.value = null
    }
  }
  const storedCtx = uni.getStorageSync(TODAY_CTX_KEY)
  if (storedCtx) {
    try {
      todayContext.value = JSON.parse(storedCtx) as TodayContext
    } catch {
      todayContext.value = null
    }
  }
  const storedMood = uni.getStorageSync(MOOD_KEY)
  if (storedMood) {
    mood.value = storedMood as Mood
  }
  const storedActivity = uni.getStorageSync(ACTIVITY_KEY)
  if (storedActivity) {
    activityLevel.value = storedActivity as ActivityLevel
  }

  /**
   * 拉节气上下文（公开 API）。本日已缓存不再拉。
   * @param force 强制刷新（用于测试或用户手动拉取）
   */
  async function fetchTodayContext(force = false): Promise<TodayContext> {
    if (!force && todayContext.value && todayContext.value.date === todayStr()) {
      return todayContext.value
    }
    const data = await getToday()
    todayContext.value = data
    uni.setStorageSync(TODAY_CTX_KEY, JSON.stringify(data))
    return data
  }

  /**
   * 拉当前坐标天气。调用方需先做登录 + 位置授权校验。
   * @param lat 纬度
   * @param lng 经度
   */
  async function fetchWeather(lat: number, lng: number): Promise<WeatherData> {
    const data = await getWeather(lat, lng)
    weather.value = data
    uni.setStorageSync(WEATHER_KEY, JSON.stringify(data))
    return data
  }

  function clearWeather() {
    weather.value = null
    uni.removeStorageSync(WEATHER_KEY)
  }

  // ---------- T11 新增 ----------

  /**
   * 调 POST /daily/recommend 获取推荐。
   * lat/lng 可选，不传走后端 fallback。
   * 成功后写入 recommendation 和 todayLog。
   */
  async function fetchRecommend(lat?: number, lng?: number): Promise<RecommendResponse> {
    loading.value = true
    try {
      const body: RecommendRequest = {
        mood: mood.value,
        activityLevel: activityLevel.value,
        lat,
        lng,
      }
      const data = await apiRecommend(body)
      recommendation.value = data
      // 推荐后 todayLog 也应被后端写入，同步刷新一次
      await fetchTodayLog()
      return data
    } finally {
      loading.value = false
    }
  }

  /** POST /daily/choose 选择菜，成功后更新 todayLog。 */
  async function chooseFood(foodId: number): Promise<DailyLogRead> {
    const data = await apiChoose(foodId)
    todayLog.value = data
    return data
  }

  /** GET /daily/today 取今天的日志，不存在 todalogLog=null。 */
  async function fetchTodayLog(): Promise<DailyLogRead | null> {
    try {
      const data = await getTodayLog()
      todayLog.value = data
      if (data !== null) {
        // 同步 mood/activity 也同步成后端存的状态
        mood.value = data.mood as Mood
        activityLevel.value = data.activityLevel as ActivityLevel
        uni.setStorageSync(MOOD_KEY, mood.value)
        uni.setStorageSync(ACTIVITY_KEY, activityLevel.value)
      }
      return data
    } catch {
      // 错误由 request 层已 toast，这里不重抛
      return null
    }
  }

  /** GET /daily/history 取近 N 天日志列表（每页一次性拉）。 */
  async function fetchHistory(days: number = 30): Promise<HistoryResponse | null> {
    try {
      return await getHistory(days)
    } catch {
      return null
    }
  }

  function setMood(m: Mood) {
    mood.value = m
    uni.setStorageSync(MOOD_KEY, m)
  }

  function setActivityLevel(a: ActivityLevel) {
    activityLevel.value = a
    uni.setStorageSync(ACTIVITY_KEY, a)
  }

  function todayStr(): string {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  return {
    todayContext,
    weather,
    recommendation,
    todayLog,
    mood,
    activityLevel,
    loading,
    fetchTodayContext,
    fetchWeather,
    clearWeather,
    fetchRecommend,
    chooseFood,
    fetchTodayLog,
    fetchHistory,
    setMood,
    setActivityLevel,
  }
})