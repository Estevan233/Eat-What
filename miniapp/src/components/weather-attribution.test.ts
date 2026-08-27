import { describe, expect, it } from 'vitest'
import source from './WeatherBadge.vue?raw'

describe('WeatherBadge attribution', () => {
  it('shows the provider name and URL when provider weather is rendered', () => {
    expect(source).toContain('天气服务：和风天气')
    expect(source).toContain('qweather.com')
    expect(source).toContain('weather?.providerAvailable')
  })
})
