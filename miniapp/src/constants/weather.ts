/**
 * 天气相关常量 - 与后端 weather_client.py 的归类保持一致。
 *
 * - WEATHER_TAG_LABEL：weather_tag 6+1 标签的中文展示
 * - WMO_TEXT_MAP：前端独立 WMO code → 中文映射（同后端，供调试）
 */
import type { WeatherTag } from '@/types/api'

/** weather_tag 6+1 离散标签的中文展示映射。 */
export const WEATHER_TAG_LABEL: Record<WeatherTag, string> = {
  cold: '寒冷',
  hot: '炎热',
  rainy: '雨天',
  snowy: '雪天',
  dry: '干燥',
  mild: '温和',
  any: '一般',
}

/** tag → 颜色（chip 背景色）便于 UI 区分。 */
export const WEATHER_TAG_COLOR: Record<WeatherTag, string> = {
  cold: '#3b82f6',    // 蓝
  hot: '#dc2626',    // 红
  rainy: '#0891b2',  // 青
  snowy: '#64748b',  // 灰蓝
  dry: '#d97706',   // 橙
  mild: '#16a34a',  // 绿
  any: '#94a3b8',   // 中性灰
}