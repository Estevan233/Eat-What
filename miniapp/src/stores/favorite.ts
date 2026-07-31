/**
 * 收藏 Store - 收藏状态 + 列表缓存。
 *
 * 设计：
 * - favoritedIds：已收藏的 food id 集合（用于 FoodCard 渲染心形图标状态）
 * - favorites：完整的菜列表（收藏页展示用，按需延迟加载）
 * - toggle 调 API 后立即同步 favoritedIds，保证 FoodCard 响应即时
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { listFavorites, toggleFavorite } from '@/api/favorite'
import type { FavoriteFood } from '@/api/favorite'

const FAVORITED_IDS_KEY = 'eat_what_favorited_ids'

export const useFavoriteStore = defineStore('favorite', () => {
  /** 已收藏的 food id 集合。 */
  const favoritedIds = ref<Set<number>>(new Set())
  const favorites = ref<FavoriteFood[]>([])
  const loading = ref(false)
  /** 是否已加载过列表（避免进页重复拉）。 */
  const loaded = ref(false)

  // 启动时从 storage 恢复 favoritedIds（存为数组）
  const stored = uni.getStorageSync(FAVORITED_IDS_KEY)
  if (stored) {
    try {
      const arr = JSON.parse(stored) as number[]
      favoritedIds.value = new Set(arr)
    } catch {
      favoritedIds.value = new Set()
    }
  }

  function persistIds(): void {
    uni.setStorageSync(FAVORITED_IDS_KEY, JSON.stringify(Array.from(favoritedIds.value)))
  }

  /** 切换收藏状态，同步本地集合。不会拉列表。 */
  async function toggle(foodId: number): Promise<boolean> {
    const result = await toggleFavorite(foodId)
    const { favorited } = result
    if (favorited) {
      favoritedIds.value.add(foodId)
    } else {
      favoritedIds.value.delete(foodId)
    }
    persistIds()
    return favorited
  }

  /** 加载收藏列表（收藏页 onLoad 或 today 页 onShow 用）。 */
  async function fetchList(force = false): Promise<FavoriteFood[]> {
    if (loaded.value && !force) return favorites.value
    loading.value = true
    try {
      const data = await listFavorites(1, 50)
      favorites.value = data.items
      favoritedIds.value = new Set(data.items.map((f) => f.id))
      persistIds()
      loaded.value = true
      return data.items
    } finally {
      loading.value = false
    }
  }

  /** 检查某道菜是否已收藏（O(1) 查集合）。 */
  function isFavorited(foodId: number): boolean {
    return favoritedIds.value.has(foodId)
  }

  return {
    favoritedIds,
    favorites,
    loading,
    toggle,
    fetchList,
    isFavorited,
  }
})