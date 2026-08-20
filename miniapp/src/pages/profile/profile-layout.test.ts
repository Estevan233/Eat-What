import { describe, expect, it } from 'vitest'
import source from './profile.vue?raw'

describe('profile native numeric inputs', () => {
  it('uses an explicit line box without vertical padding', () => {
    const inputRule = source.match(/\.input\s*\{[\s\S]*?\}/)?.[0] || ''

    expect(inputRule).toContain('height: 76rpx')
    expect(inputRule).toContain('line-height: 76rpx')
    expect(inputRule).toContain('padding: 0 20rpx')
    expect(inputRule).toContain('width: 100%')
    expect(inputRule).toContain('box-sizing: border-box')
  })
})
