import { describe, expect, it } from 'vitest'

import {
  extractMealIntent,
  isMealIntentEnabled,
  normalizeMealIntent,
  stripCodeFence,
} from './meal-intent'

describe('stripCodeFence', () => {
  it('剥离带 json 标记的代码围栏', () => {
    const raw = '```json\n{"goal":"balanced"}\n```'
    expect(stripCodeFence(raw)).toBe('{"goal":"balanced"}')
  })

  it('剥离不带语言标记的代码围栏', () => {
    const raw = '```\n{"goal":null}\n```'
    expect(stripCodeFence(raw)).toBe('{"goal":null}')
  })

  it('没有围栏时截取首尾花括号之间的内容', () => {
    const raw = '好的，结果如下：\n{"goal":"high_protein"}\n希望有帮助！'
    expect(stripCodeFence(raw)).toBe('{"goal":"high_protein"}')
  })

  it('没有 JSON 对象时原样返回', () => {
    expect(stripCodeFence('抱歉，我无法理解')).toBe('抱歉，我无法理解')
  })
})

describe('normalizeMealIntent', () => {
  it('解析完整合法输入', () => {
    const result = normalizeMealIntent({
      availableIngredients: ['番茄', '鸡蛋'],
      excludedIngredients: ['香菜'],
      maxTimeMinutes: 20,
      goal: 'high_protein',
      diningModeHint: 'cook',
      summary: '番茄鸡蛋，20 分钟内',
    })
    expect(result).toEqual({
      availableIngredients: ['番茄', '鸡蛋'],
      excludedIngredients: ['香菜'],
      maxTimeMinutes: 20,
      goal: 'high_protein',
      diningModeHint: 'cook',
      summary: '番茄鸡蛋，20 分钟内',
    })
  })

  it('空对象回落到中性默认值', () => {
    const result = normalizeMealIntent({})
    expect(result).toEqual({
      availableIngredients: [],
      excludedIngredients: [],
      maxTimeMinutes: null,
      goal: null,
      diningModeHint: null,
      summary: '',
    })
  })

  it('丢弃未知字段而不是透传', () => {
    const result = normalizeMealIntent({
      goal: 'balanced',
      foodIds: [1, 2, 3],
      calories: 500,
    })
    expect(result).not.toBeNull()
    expect(result).not.toHaveProperty('foodIds')
    expect(result).not.toHaveProperty('calories')
  })

  it('过滤食材中的空字符串', () => {
    const result = normalizeMealIntent({
      availableIngredients: ['番茄', '', '  ', '鸡蛋'],
    })
    expect(result?.availableIngredients).toEqual(['番茄', '鸡蛋'])
  })

  it.each([
    ['食材超过 12 项', { availableIngredients: Array.from({ length: 13 }, (_, i) => `食材${i}`) }],
    ['食材项非字符串', { availableIngredients: ['番茄', 123] }],
    ['单项食材超长', { availableIngredients: ['菜'.repeat(21)] }],
    ['时间小于 5', { maxTimeMinutes: 4 }],
    ['时间大于 180', { maxTimeMinutes: 181 }],
    ['时间非数字', { maxTimeMinutes: '20' }],
    ['goal 非法', { goal: 'low_carb' }],
    ['用餐模式非法', { diningModeHint: 'delivery' }],
    ['摘要超长', { summary: '菜'.repeat(81) }],
    ['食材不是数组', { excludedIngredients: '香菜' }],
  ])('字段越界时整体失败：%s', (_name, payload) => {
    expect(normalizeMealIntent(payload)).toBeNull()
  })

  it.each([[null], [undefined], ['字符串'], [[]], [42]])(
    '非对象输入返回 null：%s',
    (value) => {
      expect(normalizeMealIntent(value)).toBeNull()
    },
  )
})

describe('extractMealIntent 降级', () => {
  it('功能开关未开启时直接返回 null，不调用任何模型', async () => {
    expect(isMealIntentEnabled()).toBe(false)
    await expect(extractMealIntent('冰箱有番茄鸡蛋')).resolves.toBeNull()
  })

  it('空输入与纯空白返回 null', async () => {
    await expect(extractMealIntent('')).resolves.toBeNull()
    await expect(extractMealIntent('   \n  ')).resolves.toBeNull()
  })
})
