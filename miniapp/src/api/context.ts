/**
 * 今日上下文 API - 节气/星座/生肖/农历 + 天气。
 *
 * 学习点：
 * - /today 公开端点，无需登录（首页节气卡片显示用）
 * - /weather 需登录（PRD：防滥用），POST body 含 lat/lng
 * - request 层会自动 snakeToCamel，拿到的是 TodayContext / WeatherData camelCase 类型
 */
import { request } from './request'
import type { TodayContext, WeatherData, WeatherRequest } from '@/types/api'

export const getToday = () =>
  request<TodayContext>({ url: '/v1/context/today' })

/**
 * 取当前坐标的实时天气。需登录 + 用户授权位置后由调用方传 lat/lng。
 * lat/lng 是数字字面量，request 层的 camelToSnake 不动它们。
 */
export const getWeather = (lat: number, lng: number) =>
  request<WeatherData, WeatherRequest>({
    url: '/v1/context/weather',
    method: 'POST',
    data: { lat, lng },
  })