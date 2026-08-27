import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
  deleteMemoryMock,
  listMemoriesMock,
  recommendExternalMock,
  upsertMemoryMock,
} = vi.hoisted(() => ({
  deleteMemoryMock: vi.fn(),
  listMemoriesMock: vi.fn(),
  recommendExternalMock: vi.fn(),
  upsertMemoryMock: vi.fn(),
}))

vi.mock('@/api/dining', () => ({
  deleteDiningMemory: deleteMemoryMock,
  listDiningMemories: listMemoriesMock,
  recommendExternal: recommendExternalMock,
  upsertDiningMemory: upsertMemoryMock,
}))

import { useDiningStore } from './dining'

const externalResult = {
  audience: 'personal' as const,
  partySize: 1,
  cityLabel: '杭州',
  suggestions: [{
    key: 'rule-1',
    shopName: null,
    dishName: '鸡肉时蔬饭',
    category: '均衡套餐',
    energyKcalMinPerPerson: 520,
    energyKcalMaxPerPerson: 700,
    searchKeywords: ['杭州', '鸡肉时蔬饭'],
    orderTips: ['少油少盐'],
    reason: '兼顾营养和可执行性',
    seasonalNote: '节气仅作轻量参考',
    nutritionNote: '优先蛋白质和蔬菜',
    source: 'rules' as const,
  }],
  disclaimer: '结果仅作决策辅助。',
}

const memory = {
  id: 7,
  shopName: '小王食堂',
  dishName: '番茄鸡蛋饭',
  verdict: 'liked' as const,
  note: '少油好吃',
  createdAt: '2026-08-17T00:00:00Z',
  updatedAt: '2026-08-17T00:00:00Z',
}

function storageStub() {
  const storage = new Map<string, string>()
  return {
    getStorageSync: vi.fn((key: string) => storage.get(key) || ''),
    setStorageSync: vi.fn((key: string, value: string) => storage.set(key, value)),
  }
}

function externalResultWithKeys(keys: [string, string, string]) {
  return {
    ...externalResult,
    suggestions: keys.map((key, index) => ({
      ...externalResult.suggestions[0],
      key,
      dishName: `外食方向${index + 1}`,
      category: `类别${index + 1}`,
    })),
  }
}

describe('external dining store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    recommendExternalMock.mockReset().mockResolvedValue(externalResult)
    listMemoriesMock.mockReset().mockResolvedValue({ items: [memory], page: 1, size: 20, total: 1 })
    upsertMemoryMock.mockReset().mockResolvedValue(memory)
    deleteMemoryMock.mockReset().mockResolvedValue({ deleted: true })
    vi.stubGlobal('uni', storageStub())
  })

  it('keeps an external dining result and its honest energy range', async () => {
    const store = useDiningStore()
    await store.fetchRecommendation({
      mood: 'neutral',
      activityLevel: 'normal',
      audience: 'personal',
      partySize: 1,
      city: '杭州',
    })

    expect(store.recommendation?.cityLabel).toBe('杭州')
    expect(store.recommendation?.suggestions[0].energyKcalMaxPerPerson).toBe(700)
  })

  it('upserts and deletes a private exact shop+dish memory', async () => {
    const store = useDiningStore()
    await store.fetchMemories()
    expect(store.memories).toEqual([memory])

    await store.saveMemory({
      shopName: '小王食堂',
      dishName: '番茄鸡蛋饭',
      verdict: 'liked',
      note: '少油好吃',
    })
    await store.removeMemory(7)

    expect(upsertMemoryMock).toHaveBeenCalledOnce()
    expect(deleteMemoryMock).toHaveBeenCalledWith(7)
    expect(store.memories).toEqual([])
  })

  it('sends four fresh request ids and retains thirty recent external directions', async () => {
    recommendExternalMock
      .mockResolvedValueOnce(externalResultWithKeys(['rule-1', 'rule-2', 'rule-3']))
      .mockResolvedValueOnce(externalResultWithKeys(['rule-4', 'rule-5', 'rule-6']))
      .mockResolvedValueOnce(externalResultWithKeys(['rule-7', 'rule-8', 'rule-9']))
      .mockResolvedValueOnce(externalResultWithKeys(['rule-10', 'rule-11', 'rule-12']))
    const store = useDiningStore()
    const request = {
      mood: 'neutral' as const,
      activityLevel: 'normal' as const,
      audience: 'personal' as const,
      partySize: 1,
    }

    await store.fetchRecommendation(request)
    await store.fetchRecommendation(request)
    await store.fetchRecommendation(request)
    await store.fetchRecommendation(request)

    expect(recommendExternalMock).toHaveBeenNthCalledWith(4, {
      ...request,
      requestId: expect.any(String),
      excludeKeys: [
        'rule-1', 'rule-2', 'rule-3',
        'rule-4', 'rule-5', 'rule-6',
        'rule-7', 'rule-8', 'rule-9',
      ],
    })
    const requestIds = recommendExternalMock.mock.calls.map(([body]) => body.requestId)
    expect(new Set(requestIds).size).toBe(4)
    expect(uni.setStorageSync).toHaveBeenLastCalledWith(
      'eat_what_recent_dining_keys_v1',
      JSON.stringify([
        'rule-1', 'rule-2', 'rule-3',
        'rule-4', 'rule-5', 'rule-6',
        'rule-7', 'rule-8', 'rule-9',
        'rule-10', 'rule-11', 'rule-12',
      ]),
    )
  })
})
