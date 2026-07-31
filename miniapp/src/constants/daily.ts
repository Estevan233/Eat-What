/**
 * 日常推荐 UI 常量 - 心情/活动量的中文展示。
 */
import type { Mood, ActivityLevel } from '@/types/api'

export const MOOD_LABELS: Record<Mood, string> = {
  happy: '开心',
  neutral: '平常',
  tired: '疲惫',
  stressed: '压力',
  anxious: '焦虑',
}

/**
 * 心情选项展示顺序（chip 排列用）。
 */
export const MOOD_LIST: Mood[] = ['happy', 'neutral', 'tired', 'stressed', 'anxious']

export const ACTIVITY_LABELS: Record<ActivityLevel, string> = {
  light: '轻松',
  normal: '平常',
  high: '高强度',
}

export const ACTIVITY_LIST: ActivityLevel[] = ['light', 'normal', 'high']