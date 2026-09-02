import { describe, expect, it } from 'vitest'

import { degradeMealNote, inferMealSlotByClock, normalizeParsedMealNote, parseMealNote } from './meal-log'

describe('inferMealSlotByClock', () => {
  it.each([
    ['10:29 前归早餐', '2026-09-02T10:29:00', 'breakfast'],
    ['10:30 起归午餐', '2026-09-02T10:30:00', 'lunch'],
    ['15:59 仍归午餐', '2026-09-02T15:59:00', 'lunch'],
    ['16:00 起归晚餐', '2026-09-02T16:00:00', 'dinner'],
    ['深夜也归晚餐', '2026-09-02T23:59:00', 'dinner'],
  ])('%s → %s', (_name, iso, expected) => {
    expect(inferMealSlotByClock(new Date(iso))).toBe(expected)
  })
})

describe('normalizeParsedMealNote', () => {
  it('解析完整合法输入', () => {
    const result = normalizeParsedMealNote({
      meal_slot: 'lunch',
      dishes: [
        { name: '红烧牛肉面', kcal: 520 },
        { name: '豆浆', kcal: null },
      ],
      shop_name: '楼下老王面馆',
      note: '和同事一起吃的',
    })
    expect(result).toEqual({
      mealSlot: 'lunch',
      dishes: [
        { name: '红烧牛肉面', kcal: 520 },
        { name: '豆浆' },
      ],
      shopName: '楼下老王面馆',
      note: '和同事一起吃的',
      degraded: false,
    })
  })

  it('丢弃未知字段、容忍缺省字段', () => {
    const result = normalizeParsedMealNote({
      meal_slot: 'dinner',
      dishes: [{ name: '番茄鸡蛋面', extra: true }],
      calories: 999,
      explanation: '不应该透传',
    })
    expect(result?.dishes[0]).toEqual({ name: '番茄鸡蛋面' })
    expect(result).not.toHaveProperty('calories')
    expect(result).not.toHaveProperty('explanation')
  })

  it('菜品为空但店铺/备注有值时仍合法（留白让用户手动补菜）', () => {
    expect(normalizeParsedMealNote({ meal_slot: 'lunch', dishes: [], shop_name: '星巴克' }))
      .not.toBeNull()
    expect(normalizeParsedMealNote({ meal_slot: 'dinner', dishes: [], note: '随便吃了点' }))
      .not.toBeNull()
  })

  it('菜品超 8 道时截断而不是整体失败', () => {
    const result = normalizeParsedMealNote({
      meal_slot: 'dinner',
      dishes: Array.from({ length: 12 }, (_, i) => ({ name: `菜${i}` })),
    })
    expect(result?.dishes).toHaveLength(8)
  })

  it.each([
    ['meal_slot 非法', { meal_slot: 'brunch', dishes: [{ name: 'a' }] }],
    ['dishes 不是数组', { meal_slot: 'lunch', dishes: '一碗面' }],
    ['菜品不是对象', { meal_slot: 'lunch', dishes: ['小笼包'] }],
    ['菜品名为空', { meal_slot: 'lunch', dishes: [{ name: '  ' }] }],
    ['菜名超 40 字', { meal_slot: 'lunch', dishes: [{ name: '菜'.repeat(41) }] }],
    ['kcal 越界过大', { meal_slot: 'lunch', dishes: [{ name: 'a', kcal: 9999 }] }],
    ['kcal 非数字', { meal_slot: 'lunch', dishes: [{ name: 'a', kcal: '很多' }] }],
    ['店名超 80 字', { meal_slot: 'lunch', dishes: [{ name: 'a' }], shop_name: '店'.repeat(81) }],
    ['备注超 200 字', { meal_slot: 'lunch', dishes: [{ name: 'a' }], note: '记'.repeat(201) }],
    ['空菜品空店空备注', { meal_slot: 'lunch', dishes: [], shop_name: null, note: null }],
  ])('字段越界时整体失败：%s', (_name, payload) => {
    expect(normalizeParsedMealNote(payload)).toBeNull()
  })

  it.each([[null], [undefined], ['字符串'], [[]], [42]])(
    '非对象输入返回 null：%s',
    (value) => {
      expect(normalizeParsedMealNote(value)).toBeNull()
    },
  )
})

describe('degradeMealNote', () => {
  it('AI 不可用时整句作备注并按本地时间推断餐次', () => {
    const noon = new Date('2026-09-02T12:00:00')
    const result = degradeMealNote('中午随便吃了碗面', noon)
    expect(result).toEqual({
      mealSlot: 'lunch',
      dishes: [],
      shopName: null,
      note: '中午随便吃了碗面',
      degraded: true,
    })
  })

  it('空输入备注为 null', () => {
    expect(degradeMealNote('   ', new Date('2026-09-02T08:00:00'))).toEqual({
      mealSlot: 'breakfast',
      dishes: [],
      shopName: null,
      note: null,
      degraded: true,
    })
  })

  it('超长文本按 200 字截断', () => {
    const note = '吃'.repeat(300)
    expect(degradeMealNote(note, new Date('2026-09-02T08:00:00')).note).toHaveLength(200)
  })
})

describe('parseMealNote 降级', () => {
  it('空输入与纯空白返回 null', async () => {
    await expect(parseMealNote('')).resolves.toBeNull()
    await expect(parseMealNote('   \n  ')).resolves.toBeNull()
  })

  it('AI 开关未开启时降级为整句备注（不抛错、不阻塞记一笔）', async () => {
    // 开关默认关闭（测试环境）：degradeMealNote 内部按系统时间推断餐次，
    // 这里只验证非空降级结果与 degraded 标记。
    const result = await parseMealNote('中午吃了小笼包和豆浆')
    expect(result).not.toBeNull()
    expect(result?.degraded).toBe(true)
    expect(result?.dishes).toEqual([])
    expect(result?.shopName).toBeNull()
    expect(result?.note).toContain('小笼包')
    expect(['breakfast', 'lunch', 'dinner']).toContain(result?.mealSlot)
  })
})
