import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  deleteDiningMemory,
  listDiningMemories,
  recommendExternal,
  upsertDiningMemory,
} from '@/api/dining'
import { ApiError } from '@/types/api'
import type {
  DiningMemoryRead,
  DiningMemoryUpsert,
  DiningVerdict,
  ExternalDiningRequest,
  ExternalDiningResponse,
} from '@/types/api'

const RECENT_DINING_KEYS_KEY = 'eat_what_recent_dining_keys_v1'
const MAX_RECENT_RESULT_KEYS = 6

function readRecentKeys(): string[] {
  const value = uni.getStorageSync(RECENT_DINING_KEYS_KEY)
  if (!value) return []
  try {
    const parsed = JSON.parse(String(value))
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === 'string').slice(-MAX_RECENT_RESULT_KEYS)
      : []
  } catch {
    return []
  }
}

function appendRecentKeys(existing: string[], latest: string[]): string[] {
  const uniqueNewest: string[] = []
  const seen = new Set<string>()
  for (const value of [...existing, ...latest].reverse()) {
    if (seen.has(value)) continue
    seen.add(value)
    uniqueNewest.unshift(value)
  }
  return uniqueNewest.slice(-MAX_RECENT_RESULT_KEYS)
}

export const useDiningStore = defineStore('dining', () => {
  const recommendation = ref<ExternalDiningResponse | null>(null)
  const memories = ref<DiningMemoryRead[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const lastRequestId = ref<string | null>(null)
  const recentKeys = ref<string[]>(readRecentKeys())

  async function fetchRecommendation(
    body: ExternalDiningRequest,
  ): Promise<ExternalDiningResponse> {
    loading.value = true
    lastRequestId.value = null
    try {
      const data = await recommendExternal({
        ...body,
        excludeKeys: [...recentKeys.value],
      })
      recommendation.value = data
      recentKeys.value = appendRecentKeys(
        recentKeys.value,
        data.suggestions.map((item) => item.key),
      )
      uni.setStorageSync(RECENT_DINING_KEYS_KEY, JSON.stringify(recentKeys.value))
      return data
    } catch (error) {
      if (error instanceof ApiError) lastRequestId.value = error.requestId || null
      throw error
    } finally {
      loading.value = false
    }
  }

  async function fetchMemories(verdict?: DiningVerdict): Promise<DiningMemoryRead[]> {
    const data = await listDiningMemories(1, 50, verdict)
    memories.value = data.items
    return data.items
  }

  async function saveMemory(body: DiningMemoryUpsert): Promise<DiningMemoryRead> {
    saving.value = true
    try {
      const saved = await upsertDiningMemory(body)
      memories.value = [
        saved,
        ...memories.value.filter((item) => item.id !== saved.id),
      ]
      return saved
    } finally {
      saving.value = false
    }
  }

  async function removeMemory(memoryId: number): Promise<void> {
    await deleteDiningMemory(memoryId)
    memories.value = memories.value.filter((item) => item.id !== memoryId)
  }

  function clearRecommendation(): void {
    recommendation.value = null
  }

  return {
    recommendation,
    memories,
    loading,
    saving,
    lastRequestId,
    fetchRecommendation,
    fetchMemories,
    saveMemory,
    removeMemory,
    clearRecommendation,
  }
})
