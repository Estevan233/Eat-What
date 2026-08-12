import { describe, expect, it } from 'vitest'

import { applySubstitution, estimateMealTime, sumNutrition } from './meal'
import type { MealSnapshot, MealSubstitution } from '@/types/api'

const primaryMeal: MealSnapshot = {
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
}

const substitution: MealSubstitution = {
  targetRole: 'vegetable',
  replacement: {
    ...primaryMeal.items[1],
    foodId: 4,
    name: '清炒西兰花',
    cookingMethod: 'blanch',
    prepTimeMin: 7,
    cookTimeMin: 8,
    nutritionPerServing: { energyKcal: 110, proteinG: 6, fatG: 4, carbG: 13 },
  },
  resultingTotal: { energyKcal: 590, proteinG: 27, fatG: 18, carbG: 77 },
  reason: '热量接近，烹饪方式更清淡',
}

describe('meal domain', () => {
  it('sums per-serving nutrition and estimates parallel cooking time', () => {
    expect(sumNutrition(primaryMeal.items)).toEqual(primaryMeal.totalNutrition)
    expect(estimateMealTime(primaryMeal.items)).toBe(41)
  })

  it('applies a substitution without mutating the server snapshot', () => {
    const before = JSON.stringify(primaryMeal)

    const updated = applySubstitution(primaryMeal, substitution)

    expect(updated.items.find((item) => item.mealRole === substitution.targetRole)?.foodId)
      .toBe(substitution.replacement.foodId)
    expect(updated.totalNutrition).toEqual(sumNutrition(updated.items))
    expect(updated.estimatedTimeMin).toBe(43)
    expect(JSON.stringify(primaryMeal)).toBe(before)
  })

  it('rejects a replacement whose role does not match the target slot', () => {
    expect(() => applySubstitution(primaryMeal, {
      ...substitution,
      replacement: { ...substitution.replacement, mealRole: 'main' },
    })).toThrow(/角色/)
  })
})
