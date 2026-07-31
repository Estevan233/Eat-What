/**
 * 收藏 API - 切换/列表。
 *
 * 学习点：
 * - toggle 是 POST 语义：已收藏→取消，未收藏→新增
 * - list 分页，JOIN Food 返回完整菜信息
 */
import { request } from './request'

/** POST /favorite/{foodId} 响应 data。 */
export type FavoriteToggleResponse = {
  foodId: number
  favorited: boolean
}

/** GET /favorite 列表项（Food.to_read_dict() 的 camelCase 版）。 */
export type FavoriteFood = {
  id: number
  name: string
  category: string
  ingredients: string[]
  caloriesKcalPer100g?: number
  nutrition: Record<string, number>
  nature: string
  flavor: string[]
  organMeridians: string[]
  suitableConstitutions: string[]
  suitableWeathers: string[]
  forbiddenFor: string[]
  tags: string[]
  cookingMethod: string
  cookingTimeMin?: number
  imageUrl?: string
  seasonalSolarTerms: string[]
  description?: string
}

export type FavoriteListResponse = {
  items: FavoriteFood[]
  page: number
  size: number
  total: number
}

/** POST /favorite/{foodId} - 切换收藏状态。 */
export const toggleFavorite = (foodId: number): Promise<FavoriteToggleResponse> =>
  request<FavoriteToggleResponse>({ url: `/v1/favorite/${foodId}`, method: 'POST' })

/** GET /favorite - 分页查询收藏列表。 */
export const listFavorites = (
  page: number = 1,
  size: number = 20,
): Promise<FavoriteListResponse> =>
  request<FavoriteListResponse>({ url: `/v1/favorite?page=${page}&size=${size}` })