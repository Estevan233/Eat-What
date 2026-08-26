import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/types/api'
import type { MealRecommendation, MealSubstitution } from '@/types/api'

const { chooseMealMock, getTodayLogMock, recommendMock } = vi.hoisted(() => ({
  chooseMealMock: vi.fn(),
  getTodayLogMock: vi.fn(),
  recommendMock: vi.fn(),
}))

vi.mock('@/api/daily', () => ({
  chooseFood: vi.fn(),
  chooseMeal: chooseMealMock,
  getHistory: vi.fn(),
  getTodayLog: getTodayLogMock,
  recommend: recommendMock,
}))

vi.mock('@/api/context', () => ({
  getToday: vi.fn(),
  getWeather: vi.fn(),
}))

import { useDailyStore } from './daily'

const substitution: MealSubstitution = {
  targetRole: 'vegetable',
  replacement: {
    foodId: 4,
    name: '清炒西兰花',
    mealRole: 'vegetable',
    category: 'vegetable',
    cookingMethod: 'blanch',
    visualKey: 'veg-broccoli',
    prepTimeMin: 7,
    cookTimeMin: 8,
    nutritionPerServing: { energyKcal: 110, proteinG: 6, fatG: 4, carbG: 13 },
    reason: '更清淡',
    score: 80,
  },
  resultingTotal: { energyKcal: 590, proteinG: 27, fatG: 18, carbG: 77 },
  reason: '热量接近',
}

const recommendation: MealRecommendation = {
  recommendationId: 17,
  foods: [],
  primaryMeal: {
    items: [
      {
        foodId: 1,
        name: '番茄鸡蛋',
        mealRole: 'main',
        category: 'stir_fry',
        cookingMethod: 'stir_fry',
        visualKey: 'main-tomato',
        prepTimeMin: 8,
        cookTimeMin: 10,
        nutritionPerServing: { energyKcal: 260, proteinG: 16, fatG: 12, carbG: 18 },
        reason: '蛋白质适中',
        score: 88,
      },
      {
        foodId: 2,
        name: '蒜蓉生菜',
        mealRole: 'vegetable',
        category: 'vegetable',
        cookingMethod: 'stir_fry',
        visualKey: 'veg-lettuce',
        prepTimeMin: 5,
        cookTimeMin: 6,
        nutritionPerServing: { energyKcal: 90, proteinG: 3, fatG: 4, carbG: 10 },
        reason: '补充膳食纤维',
        score: 80,
      },
      {
        foodId: 3,
        name: '杂粮饭',
        mealRole: 'staple',
        category: 'staple',
        cookingMethod: 'steam',
        visualKey: 'staple-rice',
        prepTimeMin: 3,
        cookTimeMin: 25,
        nutritionPerServing: { energyKcal: 220, proteinG: 5, fatG: 2, carbG: 46 },
        reason: '提供稳定碳水',
        score: 75,
      },
    ],
    totalNutrition: { energyKcal: 570, proteinG: 24, fatG: 18, carbG: 74 },
    estimatedTimeMin: 41,
    reason: '一荤一素一主食',
  },
  substitutions: [substitution],
  substitutionNotice: null,
  engine: 'rules_v4',
  weightProfile: {
    nutrition: 22,
    seasonalWellness: 18,
    personalFamily: 20,
    preferenceHistory: 15,
    feasibility: 15,
    diversity: 10,
    weatherModifierLimit: 3,
  },
  wellnessDisclaimer: '节气与体质内容仅作日常饮食参考。',
  context: {
    weather: {
      providerAvailable: true,
      locationName: '默认城市',
      tempC: 22,
      feelsLikeC: 22,
      text: '温和',
      windDir: '南',
      windScale: '2级',
      humidity: 50,
      precipitationMm: 0,
      weatherTag: 'mild',
      fetchedAt: '2026-08-12T00:00:00Z',
    },
    today: {
      date: '2026-08-12',
      solarTermCurrent: '',
      solarTermNextName: '处暑',
      solarTermNextDate: '2026-08-23',
      zodiacSign: 'leo',
      animal: '马',
      lunarMonth: 7,
      lunarDay: 1,
      isLeapMonth: false,
    },
  },
}

function storageStub(initial = '') {
  const storage = new Map<string, string>()
  if (initial) storage.set('eat_what_meal_recommendation_v2', initial)
  return {
    getStorageSync: vi.fn((key: string) => storage.get(key) || ''),
    setStorageSync: vi.fn((key: string, value: string) => storage.set(key, value)),
    removeStorageSync: vi.fn((key: string) => storage.delete(key)),
    showToast: vi.fn(),
  }
}

function cachedEnvelope(): string {
  return JSON.stringify({
    version: 2,
    savedAt: '2026-08-12T00:00:00Z',
    recommendation,
    currentMeal: recommendation.primaryMeal,
    appliedSubstitutions: [],
  })
}

function recommendationWithIds(ids: [number, number, number]): MealRecommendation {
  const next = JSON.parse(JSON.stringify(recommendation)) as MealRecommendation
  next.recommendationId = ids[0] * 10
  next.primaryMeal.items.forEach((item, index) => {
    item.foodId = ids[index]
  })
  return next
}

describe('daily complete meal store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    chooseMealMock.mockReset()
    getTodayLogMock.mockReset().mockResolvedValue(null)
    recommendMock.mockReset().mockResolvedValue(recommendation)
    vi.stubGlobal('uni', storageStub())
  })

  it('saves a versioned cache and restores it as stale read-only state', async () => {
    const first = useDailyStore()
    await first.fetchRecommend()
    const write = vi.mocked(uni.setStorageSync).mock.calls.find(
      ([key]) => key === 'eat_what_meal_recommendation_v2',
    )
    expect(JSON.parse(String(write?.[1])).version).toBe(2)

    vi.stubGlobal('uni', storageStub(String(write?.[1])))
    setActivePinia(createPinia())
    const restored = useDailyStore()
    expect(restored.currentMeal?.items).toHaveLength(3)
    expect(restored.stale).toBe(true)
    expect(restored.offline).toBe(false)
  })

  it('falls back to cached read-only state only for network failures', async () => {
    vi.stubGlobal('uni', storageStub(cachedEnvelope()))
    recommendMock.mockRejectedValueOnce(new ApiError('断网', 'NETWORK_ERROR'))
    const store = useDailyStore()

    await expect(store.fetchRecommend()).resolves.toEqual(recommendation)
    expect(store.stale).toBe(true)
    expect(store.offline).toBe(true)
  })

  it('reuses the same request id after a transient failure and rotates after success', async () => {
    vi.stubGlobal('uni', storageStub(cachedEnvelope()))
    recommendMock
      .mockRejectedValueOnce(new ApiError('断网', 'NETWORK_ERROR'))
      .mockResolvedValueOnce(recommendation)
      .mockResolvedValueOnce(recommendationWithIds([4, 5, 6]))
    const store = useDailyStore()

    await store.fetchRecommend()
    await store.fetchRecommend()
    await store.fetchRecommend()

    const firstRequestId = recommendMock.mock.calls[0][0].requestId
    expect(recommendMock.mock.calls[1][0].requestId).toBe(firstRequestId)
    expect(recommendMock.mock.calls[2][0].requestId).not.toBe(firstRequestId)
  })

  it('does not hide authentication or service configuration errors', async () => {
    vi.stubGlobal('uni', storageStub(cachedEnvelope()))
    const error = new ApiError('未登录', 'AUTH_ERROR', 401, 'req-auth-1')
    recommendMock.mockRejectedValueOnce(error)
    const store = useDailyStore()

    await expect(store.fetchRecommend()).rejects.toBe(error)
    expect(store.lastRequestId).toBe('req-auth-1')
    expect(store.offline).toBe(false)
  })

  it('recovers from cached state after a successful refresh', async () => {
    vi.stubGlobal('uni', storageStub(cachedEnvelope()))
    const store = useDailyStore()
    expect(store.stale).toBe(true)

    await store.fetchRecommend()

    expect(store.stale).toBe(false)
    expect(store.offline).toBe(false)
  })

  it('recalculates substitutions and submits the whole current meal', async () => {
    chooseMealMock.mockResolvedValue({ id: 1, chosenFoodIds: [1, 4, 3] })
    const store = useDailyStore()
    await store.fetchRecommend()

    store.applySubstitution(substitution)
    expect(store.currentMeal?.items.map((item) => item.foodId)).toEqual([1, 4, 3])
    expect(store.currentMeal?.totalNutrition.energyKcal).toBe(590)

    await store.chooseCurrentMeal()
    expect(chooseMealMock).toHaveBeenCalledWith({
      recommendationId: 17,
      selectedFoodIds: [1, 4, 3],
      substitutions: [{ targetRole: 'vegetable', replacementFoodId: 4 }],
    })
  })

  it('persists meal context and sends family party size to recommendation API', async () => {
    const store = useDailyStore()
    expect(store.diningMode).toBe('cook')
    expect(store.audience).toBe('personal')
    expect(store.partySize).toBe(1)

    store.setAudience('family')
    store.setPartySize(4)
    await store.fetchRecommend()

    expect(recommendMock).toHaveBeenCalledWith(expect.objectContaining({
      diningMode: 'cook',
      audience: 'family',
      partySize: 4,
    }))
    expect(uni.setStorageSync).toHaveBeenCalledWith('eat_what_audience', 'family')
    expect(uni.setStorageSync).toHaveBeenCalledWith('eat_what_party_size', 4)
  })

  it('sends the previous two cook batches without refetching today', async () => {
    recommendMock
      .mockResolvedValueOnce(recommendationWithIds([1, 2, 3]))
      .mockResolvedValueOnce(recommendationWithIds([4, 5, 6]))
      .mockResolvedValueOnce(recommendationWithIds([7, 8, 9]))
    const store = useDailyStore()

    await store.fetchRecommend()
    await store.fetchRecommend()
    await store.fetchRecommend()

    expect(recommendMock).toHaveBeenNthCalledWith(3, expect.objectContaining({
      excludeFoodIds: [1, 2, 3, 4, 5, 6],
    }))
    expect(getTodayLogMock).not.toHaveBeenCalled()
  })

  it('keeps at least five prior batches when requesting the sixth recommendation', async () => {
    recommendMock
      .mockResolvedValueOnce(recommendationWithIds([1, 2, 3]))
      .mockResolvedValueOnce(recommendationWithIds([4, 5, 6]))
      .mockResolvedValueOnce(recommendationWithIds([7, 8, 9]))
      .mockResolvedValueOnce(recommendationWithIds([10, 11, 12]))
      .mockResolvedValueOnce(recommendationWithIds([13, 14, 15]))
      .mockResolvedValueOnce(recommendationWithIds([16, 17, 18]))
    const store = useDailyStore()

    for (let index = 0; index < 6; index += 1) await store.fetchRecommend()

    expect(recommendMock).toHaveBeenNthCalledWith(6, expect.objectContaining({
      excludeFoodIds: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
    }))
  })

  it('reuses a fresh weather snapshot when requesting recommendations', async () => {
    const freshWeather = {
      ...recommendation.context.weather,
      fetchedAt: new Date().toISOString(),
    }
    uni.setStorageSync('eat_what_weather', JSON.stringify(freshWeather))
    setActivePinia(createPinia())
    const store = useDailyStore()

    await store.fetchRecommend(39.92, 116.41)

    expect(recommendMock).toHaveBeenCalledWith(expect.objectContaining({
      weatherSnapshot: freshWeather,
    }))
    expect(store.hasFreshWeather).toBe(true)
  })

  it('does not treat neutral fallback weather (providerAvailable=false) as fresh', async () => {
    const neutralWeather = {
      ...recommendation.context.weather,
      providerAvailable: false,
      fetchedAt: new Date().toISOString(),
    }
    uni.setStorageSync('eat_what_weather', JSON.stringify(neutralWeather))
    setActivePinia(createPinia())
    const store = useDailyStore()

    expect(store.hasFreshWeather).toBe(false)

    await store.fetchRecommend(39.92, 116.41)

    expect(recommendMock).toHaveBeenCalledWith(expect.objectContaining({
      weatherSnapshot: undefined,
    }))
  })

  it('invalidates a cooking recommendation when switching to external dining', async () => {
    const store = useDailyStore()
    await store.fetchRecommend()
    expect(store.currentMeal).not.toBeNull()

    store.setDiningMode('eat_out')

    expect(store.currentMeal).toBeNull()
    expect(store.serverRecommendation).toBeNull()
    expect(uni.removeStorageSync).toHaveBeenCalledWith('eat_what_meal_recommendation_v2')
  })
})
