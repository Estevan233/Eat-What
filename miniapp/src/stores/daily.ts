/**
 * 今日数据 Store - T09 提前实现 weather / todayContext 部分，
 * T11 会扩展推荐/历史/收藏字段。
 *
 * 设计：
 * - todayContext：节气上下文（公开 API 拉取，不需登录）
 * - weather：当前实况（需登录 + 已授权位置后调 api.context.getWeather），
 *   落 storage 避免重启丢失
 * - fetchTodayContext / fetchWeather 两个 action，调用方自行处理 error
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getToday, getWeather } from '@/api/context'
import type { TodayContext, WeatherData } from '@/types/api'

const WEATHER_KEY = 'eat_what_weather'
const TODAY_CTX_KEY = 'eat_what_today_ctx'

export const useDailyStore = defineStore('daily', () => {
  const todayContext = ref<TodayContext | null>(null)
  const weather = ref<WeatherData | null>(null)

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

  function todayStr(): string {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }

  return {
    todayContext,
    weather,
    fetchTodayContext,
    fetchWeather,
    clearWeather,
  }
})