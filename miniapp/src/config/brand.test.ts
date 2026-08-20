import { describe, expect, it } from 'vitest'

import { APP_NAME, BRAND_SUBTITLE, HERO_TITLE } from './brand'

describe('brand copy', () => {
  it('uses the approved 饭卜卜 identity', () => {
    expect(APP_NAME).toBe('饭卜卜')
    expect(HERO_TITLE).toBe('今天吃啥嘞')
    expect(BRAND_SUBTITLE).toBe('Eat-What，卜一卜 → 补一补')
  })
})
