import { request } from './request'
import type { RecipeRead } from '@/types/api'

export const getRecipe = (foodId: number): Promise<RecipeRead> =>
  request<RecipeRead>({ url: `/api/v1/food/${foodId}/recipe` })
