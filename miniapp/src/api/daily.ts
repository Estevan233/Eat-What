/**
 * 日常推荐 API - 推荐/选择/今日日志/历史/日记 CRUD。
 *
 * 学习点：
 * - request 层自动 camelToSnake 入参、snakeToCamel 出参
 * - recommend 接口每次都重新算，不缓存
 * - GET /daily/today 返回当天全部日志行 {items: []}（三餐 + 自记），不再是单条
 */
import { request } from './request'
import type {
  ChooseMealRequest,
  LogSource,
  MealSlot,
  MealSnapshot,
  NutritionTotal,
  RecommendRequest,
  RecommendResponse,
} from '@/types/api'

/** 自记的一道菜（chosen_meal_json 中 manual 快照拆出的条目）。 */
export type ManualDishItem = {
  name: string
  kcal?: number | null
}

/** 一条日志（推荐确认快照或手动自记）。 */
export type DailyLogRead = {
  id: number
  userId: number
  logDate: string
  mealSlot: MealSlot
  source: LogSource
  shopName?: string | null
  note?: string | null
  recommendedFoodIds: number[]
  chosenFoodIds: number[]
  recommendationId?: number | null
  recommendedMeal?: MealSnapshot | null
  chosenMeal?: MealSnapshot | null
  /** source=manual 时的菜品列表（由后端从 chosen_meal_json 拆分）。 */
  manualDishes?: ManualDishItem[] | null
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
  /** 连续有记录的自然日天数（今天无记录则从昨天倒推）。 */
  streakDays: number
}

/** GET /daily/today 响应 data。 */
export type TodayLogsResponse = {
  items: DailyLogRead[]
}

/** 手动自记落库请求。 */
export type ManualLogRequest = {
  logDate: string
  mealSlot: MealSlot
  dishes: ManualDishItem[]
  shopName?: string | null
  note?: string | null
}

/** PATCH /daily/logs/{id} 请求体（recommendation 仅 mealSlot/note 生效）。 */
export type UpdateLogRequest = {
  mealSlot?: MealSlot
  note?: string | null
  dishes?: ManualDishItem[]
  shopName?: string | null
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
    loading: false,
  })

/** POST /daily/choose - 选择一道菜写入 DailyLog。 */
export const chooseFood = (foodId: number, mealSlot?: MealSlot): Promise<DailyLogRead> =>
  request<DailyLogRead, { foodId: number; mealSlot?: MealSlot }>({
    url: '/api/v1/daily/choose',
    method: 'POST',
    data: { foodId, mealSlot },
  })

/** POST /daily/choose - 一次确认主菜、蔬菜、主食和已应用换菜。 */
export const chooseMeal = (data: ChooseMealRequest): Promise<DailyLogRead> =>
  request<DailyLogRead, ChooseMealRequest>({
    url: '/api/v1/daily/choose',
    method: 'POST',
    data,
  })

/** GET /daily/today - 取今天的全部日志行，没有则 items 为空。 */
export const getTodayLogs = (): Promise<TodayLogsResponse> =>
  request<TodayLogsResponse>({ url: '/api/v1/daily/today', loading: false })

/** GET /daily/history - 近 N 天日志（支持关键词搜索）。 */
export const getHistory = (
  days: number = 30,
  query: string = '',
): Promise<HistoryResponse> => {
  const queryParam = query.trim() ? `&query=${encodeURIComponent(query.trim())}` : ''
  return request<HistoryResponse>({
    url: `/api/v1/daily/history?days=${days}${queryParam}`,
    loading: false,
  })
}

/**
 * POST /daily/logs/manual - 自记落库（确认后的结构化数据，不调 AI）。
 * 解析由 ai/meal-log.ts 的 parseMealNote 在客户端完成（与 wx.cloud.extend.AI 同通道）。
 */
export const createManualLog = (data: ManualLogRequest): Promise<DailyLogRead> =>
  request<DailyLogRead, ManualLogRequest>({
    url: '/api/v1/daily/logs/manual',
    method: 'POST',
    data,
  })

/** PUT /daily/logs/{id} - 编辑一条日志（后端同时提供 PATCH 别名；小程序通道不支持 PATCH）。 */
export const updateLog = (logId: number, data: UpdateLogRequest): Promise<DailyLogRead> =>
  request<DailyLogRead, UpdateLogRequest>({
    url: `/api/v1/daily/logs/${logId}`,
    method: 'PUT',
    data,
  })

/** DELETE /daily/logs/{id} - 删除一条日志。 */
export const deleteLog = (logId: number): Promise<{ id: number; deleted: boolean }> =>
  request<{ id: number; deleted: boolean }>({
    url: `/api/v1/daily/logs/${logId}`,
    method: 'DELETE',
  })
