import type {
  MealItem,
  MealSnapshot,
  MealSubstitution,
  NutritionTotal,
} from '@/types/api'

const NUTRITION_FIELDS = ['energyKcal', 'proteinG', 'fatG', 'carbG'] as const

function roundDisplay(value: number): number {
  return Math.round((value + Number.EPSILON) * 10) / 10
}

export function sumNutrition(items: MealItem[]): NutritionTotal {
  const result = {} as NutritionTotal
  for (const field of NUTRITION_FIELDS) {
    result[field] = roundDisplay(
      items.reduce((total, item) => total + item.nutritionPerServing[field], 0),
    )
  }
  return result
}

/** Prep is sequential; the longest cook is treated as the critical parallel path. */
export function estimateMealTime(items: MealItem[]): number {
  if (items.length === 0) return 0
  return items.reduce((total, item) => total + item.prepTimeMin, 0)
    + Math.max(...items.map((item) => item.cookTimeMin))
}

export function applySubstitution(
  meal: MealSnapshot,
  substitution: MealSubstitution,
): MealSnapshot {
  if (substitution.replacement.mealRole !== substitution.targetRole) {
    throw new Error('换菜角色与目标餐位不一致')
  }
  const targetExists = meal.items.some((item) => item.mealRole === substitution.targetRole)
  if (!targetExists) throw new Error('当前餐单不存在目标角色')

  const items = meal.items.map((item) =>
    item.mealRole === substitution.targetRole
      ? { ...substitution.replacement }
      : { ...item },
  )
  return {
    ...meal,
    items,
    totalNutrition: sumNutrition(items),
    estimatedTimeMin: estimateMealTime(items),
  }
}
