/**
 * 收藏 API - 切换/搜索/自定义收藏/备注。
 *
 * 学习点：
 * - toggle 是 POST 语义：已收藏→取消，未收藏→新增
 * - 列表为统一收藏项：普通收藏带 food（Food 摘要），自定义收藏带 customName/note、food 为 null
 * - GET 支持 query 关键词（命中菜名/自定义名/备注）
 */
import { request } from './request'

/** POST /favorite/{foodId} 响应 data。 */
export type FavoriteToggleResponse = {
  foodId: number
  favorited: boolean
}

/** Food.to_read_dict() 的 camelCase 版（snakeToCamel 深递归转换）。 */
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
  mealRole?: import('@/types/api').MealRole | null
  recipeReady?: boolean
  visualKey?: string | null
  seasonalSolarTerms: string[]
  description?: string
}

/** GET /favorite 列表项 - 普通收藏 food 非空；自定义收藏 food 为空、customName 非空。 */
export type FavoriteItem = {
  favoriteId: number
  foodId: number | null
  customName: string | null
  note: string | null
  createdAt: string | null
  food: FavoriteFood | null
}

export type FavoriteListResponse = {
  items: FavoriteItem[]
  page: number
  size: number
  total: number
}

/** POST /favorite/custom 请求体。 */
export type AddCustomFavoriteRequest = {
  customName: string
  note?: string | null
}

/** POST /favorite/{foodId} - 切换收藏状态。 */
export const toggleFavorite = (foodId: number): Promise<FavoriteToggleResponse> =>
  request<FavoriteToggleResponse>({ url: `/api/v1/favorite/${foodId}`, method: 'POST' })

/** GET /favorite - 分页查询收藏列表（含自定义收藏），支持关键词搜索。 */
export const listFavorites = (
  page: number = 1,
  size: number = 20,
  query: string = '',
): Promise<FavoriteListResponse> => {
  const queryParam = query.trim() ? `&query=${encodeURIComponent(query.trim())}` : ''
  return request<FavoriteListResponse>({
    url: `/api/v1/favorite?page=${page}&size=${size}${queryParam}`,
    loading: false,
  })
}

/** POST /favorite/custom - 手动添加自定义收藏（不依赖候选菜库）。 */
export const addCustomFavorite = (
  data: AddCustomFavoriteRequest,
): Promise<{ favoriteId: number; customName: string; note: string | null }> =>
  request<{ favoriteId: number; customName: string; note: string | null }, AddCustomFavoriteRequest>(
    {
      url: '/api/v1/favorite/custom',
      method: 'POST',
      data,
    },
  )

/** PUT /favorite/{favoriteId} - 编辑收藏备注（后端同时提供 PATCH 别名；小程序通道不支持 PATCH）。 */
export const updateFavoriteNote = (
  favoriteId: number,
  note: string | null,
): Promise<{ favoriteId: number; note: string | null }> =>
  request<{ favoriteId: number; note: string | null }>({
    url: `/api/v1/favorite/${favoriteId}`,
    method: 'PUT',
    data: { note },
  })

/** DELETE /favorite/{favoriteId} - 删除收藏（普通/自定义通用）。 */
export const deleteFavorite = (
  favoriteId: number,
): Promise<{ favoriteId: number; deleted: boolean }> =>
  request<{ favoriteId: number; deleted: boolean }>({
    url: `/api/v1/favorite/${favoriteId}`,
    method: 'DELETE',
  })
