import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestMock = vi.hoisted(() => vi.fn())

vi.mock('./request', () => ({
  request: requestMock,
}))

import { getToday, getWeather } from './context'
import { getTodayLog, recommend } from './daily'
import { recommendExternal } from './dining'
import { listFavorites } from './favorite'

describe('homepage request loading contract', () => {
  beforeEach(() => {
    requestMock.mockReset().mockResolvedValue({})
  })

  it('keeps homepage background and inline-state requests free of global loading masks', async () => {
    await getToday()
    await getWeather(39.92, 116.41)
    await recommend({
      mood: 'neutral',
      activityLevel: 'normal',
      diningMode: 'cook',
      audience: 'personal',
      partySize: 1,
    })
    await recommendExternal({
      mood: 'neutral',
      activityLevel: 'normal',
      audience: 'personal',
      partySize: 1,
    })
    await getTodayLog()
    await listFavorites()

    expect(requestMock).toHaveBeenCalledTimes(6)
    requestMock.mock.calls.forEach(([options]) => {
      expect(options.loading).toBe(false)
    })
  })
})
