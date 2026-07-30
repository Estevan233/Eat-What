/**
 * 12 星座中文名映射 - 与后端 backend/app/services/solar_terms.py
 * 的 ZODIAC_NAMES_ZH 同步。
 */
import type { ZodiacSign } from '@/types/api'

export const ZODIAC_NAMES_ZH: Record<ZodiacSign, string> = {
  aries: '白羊座',
  taurus: '金牛座',
  gemini: '双子座',
  cancer: '巨蟹座',
  leo: '狮子座',
  virgo: '处女座',
  libra: '天秤座',
  scorpio: '天蝎座',
  sagittarius: '射手座',
  capricorn: '摩羯座',
  aquarius: '水瓶座',
  pisces: '双鱼座',
}

/**
 * 计算距下一节气还有几天（用于「距XX还有 X 天」展示）。
 * @param nextDateStr 下一节气 ISO 日期 YYYY-MM-DD
 * @param fromDate 起始日期（默认今天）
 * @returns 整数天数；同天返回 0
 */
export function daysUntilSolarTerm(
  nextDateStr: string,
  fromDate: Date = new Date(),
): number {
  const next = new Date(nextDateStr + 'T00:00:00')
  const from = new Date(
    fromDate.getFullYear(),
    fromDate.getMonth(),
    fromDate.getDate(),
  )
  const ms = next.getTime() - from.getTime()
  return Math.round(ms / 86400000)
}