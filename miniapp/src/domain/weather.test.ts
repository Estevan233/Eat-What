import { describe, expect, it } from 'vitest'
import { formatWeatherChip } from './weather'
import type { WeatherData } from '@/types/api'

const LIVE_WEATHER: WeatherData = {
  providerAvailable: true,
  source: 'qweather',
  isStale: false,
  observedAt: '2026-08-25T08:00:00+08:00',
  locationName: '和风天气',
  tempC: 28.4,
  feelsLikeC: 30,
  text: '多云',
  windDir: '东南风',
  windScale: '2级',
  humidity: 65,
  precipitationMm: 0,
  weatherTag: 'hot',
  fetchedAt: '2026-08-25T00:01:00Z',
}

describe('formatWeatherChip', () => {
  it('formats a live QWeather observation', () => {
    expect(formatWeatherChip(LIVE_WEATHER)).toBe('28° 多云 · 炎热')
  })

  it('labels stale last-good data as cached weather', () => {
    expect(formatWeatherChip({
      ...LIVE_WEATHER,
      source: 'cache',
      isStale: true,
    })).toBe('28° 多云 · 炎热 · 缓存天气')
  })

  it('does not present neutral fallback as a live observation', () => {
    expect(formatWeatherChip({
      ...LIVE_WEATHER,
      providerAvailable: false,
      source: 'neutral',
      weatherTag: 'mild',
    })).toBe('天气暂不可用')
  })
})
