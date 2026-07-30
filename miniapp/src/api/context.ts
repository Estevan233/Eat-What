/**
 * 今日上下文 API - 节气/星座/生肖/农历。
 *
 * 学习点：
 * - 公开端点，无需登录（首页天气卡片显示用）
 * - request 层会自动 snakeToCamel，所以拿到的是 TodayContext camelCase 类型
 */
import { request } from './request'
import type { TodayContext } from '@/types/api'

export const getToday = () =>
  request<TodayContext>({ url: '/v1/context/today' })