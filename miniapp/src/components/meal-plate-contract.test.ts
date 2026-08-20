import { describe, expect, it } from 'vitest'
import source from './MealPlateCard.vue?raw'

describe('MealPlateCard family contract', () => {
  it('derives the role headline from items and uses stable food ids as row keys', () => {
    expect(source).not.toContain('一主菜 · 一蔬菜 · 一主食')
    expect(source).toContain('{{ roleHeadline }}')
    expect(source).toContain(':key="item.foodId"')
  })

  it('shows whole-table energy when more than one person is selected', () => {
    expect(source).toContain('partySize')
    expect(source).toContain('wholeTableEnergy')
    expect(source).toContain('全桌约')
  })
})
