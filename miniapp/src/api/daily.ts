/**
 * 日常推荐 API - 推荐/选择/今日日志/历史。
 *
 * 学习点：
 * - request 层自动 camelToSnake 入参、snakeToCamel 出参
 * - recommend 接口每次都重新算，不缓存
 */
import { request } from './request'
import type {
  ChooseMealRequest,
  MealSnapshot,
  NutritionTotal,
  RecommendRequest,
  RecommendResponse,
} from '@/types/api'

/** GET /daily/today 响应 data（不存在时后端返 null）。 */
export type DailyLogRead = {
  id: number
  userId: number
  logDate: string
  recommendedFoodIds: number[]
  chosenFoodIds: number[]
  recommendationId?: number | null
  recommendedMeal?: MealSnapshot | null
  chosenMeal?: MealSnapshot | null
  chosenTotalNutrition?: NutritionTotal | null
  mood: string
  activityLevel: string
  weatherTag?: string | null
  diningMode: 'cook' | 'eat_out'
  audience: 'personal' | 'family'
  partySize: number
}

/** GET /daily/history 响应 data。 */
export type HistoryResponse = {
  items: DailyLogRead[]
  total: number
}

/**
 * POST /daily/recommend - 获取今天 3 道菜推荐。
 * Body: RecommendRequest (mood/activityLevel/location/diningMode/audience/partySize)
 */
export const recommend = (data: RecommendRequest): Promise<RecommendResponse> =>
  request<RecommendResponse, RecommendRequest>({
    url: '/api/v1/daily/recommend',
    method: 'POST',
    data,
  })

/** POST /daily/choose - 选择一道菜写入 DailyLog。 */
export const chooseFood = (foodId: number): Promise<DailyLogRead> =>
  request<DailyLogRead, { foodId: number }>({
    url: '/api/v1/daily/choose',
    method: 'POST',
    data: { foodId },
  })

/** POST /daily/choose - 一次确认主菜、蔬菜、主食和已应用换菜。 */
export const chooseMeal = (data: ChooseMealRequest): Promise<DailyLogRead> =>
  request<DailyLogRead, ChooseMealRequest>({
    url: '/api/v1/daily/choose',
    method: 'POST',
    data,
  })

/** GET /daily/today - 取今天的 DailyLog，不存在返回 null。 */
export const getTodayLog = (): Promise<DailyLogRead | null> =>
  request<DailyLogRead | null>({ url: '/api/v1/daily/today' })

/** GET /daily/history - 近 N 天的日志列表。 */
export const getHistory = (days: number = 30): Promise<HistoryResponse> =>
  request<HistoryResponse>({ url: `/api/v1/daily/history?days=${days}` })
