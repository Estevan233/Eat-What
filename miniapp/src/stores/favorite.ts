/**
 * 收藏 Store - 收藏状态 + 统一收藏列表（普通菜谱 / 自定义收藏）。
 *
 * 设计：
 * - favoritedIds：已收藏的 food id 集合（用于 FoodCard 渲染心形图标状态）
 * - items：统一收藏项列表（普通收藏 food 非空；自定义收藏 customName 非空、food 为 null）
 * - fetchList 支持关键词 query；收藏页搜索与卡片心形状态共用同一份数据
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { listFavorites, toggleFavorite, type FavoriteItem } from '@/api/favorite'

const FAVORITED_IDS_KEY = 'eat_what_favorited_ids'

export const useFavoriteStore = defineStore('favorite', () => {
  /** 已收藏的 food id 集合（自定义收藏无 foodId，不进集合）。 */
  const favoritedIds = ref<Set<number>>(new Set())
  /** 统一收藏列表（按后端顺序返回）。 */
  const items = ref<FavoriteItem[]>([])
  const loading = ref(false)
  /** 是否已加载过非搜索列表（避免 today/recipe 反复拉全量）。 */
  const loaded = ref(false)
  /** 当前生效的关键词（搜索态内存缓存隔离）。 */
  const activeQuery = ref('')

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

  function syncIdsFromItems(list: FavoriteItem[]): void {
    const next = new Set<number>()
    for (const item of list) {
      if (item.foodId != null) next.add(item.foodId)
    }
    favoritedIds.value = next
    persistIds()
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

  /** 从收藏页删除后同步移除 ids（避免刷新前心形状态残留）。 */
  function removeLocal(foodId: number | null): void {
    if (foodId == null) return
    favoritedIds.value.delete(foodId)
    persistIds()
  }

  /** 加载收藏列表。query 非空时跳过缓存强制请求（搜索态）。 */
  async function fetchList(force = false, query = ''): Promise<FavoriteItem[]> {
    const keyword = query.trim()
    const cachedList = !keyword && !force && loaded.value
    if (cachedList && activeQuery.value === '') return items.value
    loading.value = true
    try {
      const data = await listFavorites(1, 50, keyword)
      items.value = data.items
      activeQuery.value = keyword
      if (!keyword) {
        syncIdsFromItems(data.items)
        loaded.value = true
      }
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
    items,
    loading,
    fetchList,
    toggle,
    removeLocal,
    isFavorited,
  }
})
