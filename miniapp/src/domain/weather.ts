import { WEATHER_TAG_LABEL } from '@/constants/weather'
import type { WeatherData } from '@/types/api'

/**
 * 首页天气徽标只陈述服务端已经确认的事实。
 * 陈旧缓存必须明确标注，避免把数小时前的观测伪装成实时天气。
 */
export function formatWeatherChip(weather: WeatherData | null): string {
  if (!weather) return ''
  if (!weather.providerAvailable) return '天气暂不可用'

  const temperature = Math.round(weather.tempC)
  const cacheSuffix = weather.isStale ? ' · 缓存天气' : ''
  return `${temperature}° ${weather.text} · ${WEATHER_TAG_LABEL[weather.weatherTag]}${cacheSuffix}`
}
