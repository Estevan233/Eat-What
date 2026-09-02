/**
 * AI 外食本地特色菜推荐。
 *
 * 用户在外食模式选好城市后，AI 生成 3-5 道当地真正有名气的特色菜
 * （名称 + 一句推荐理由），用于"不知道吃什么"的灵感区。
 *
 * 设计：
 * - 只输出 JSON，防幻觉约束：只推荐确实存在的当地菜；不确定就返回空数组
 * - 结果带 24h 本地缓存（storage key 含城市），控 token 成本
 * - 任何失败（开关关、无运行时、超时、非 JSON）都返回空数组静默降级
 * - UI 必须标注"AI 推荐 · 仅供参考"
 */
import {
  AI_MEAL_INTENT_ENABLED,
  AI_MEAL_INTENT_MODEL,
  AI_MEAL_INTENT_PROVIDER,
} from '@/config/env'
import { stripCodeFence } from '@/ai/meal-intent'

export type CitySpecialty = { name: string; reason: string }

const SPECIALTY_TTL_MS = 24 * 60 * 60 * 1000
const CALL_TIMEOUT_MS = 8000
const MAX_ITEMS = 6
const MAX_NAME = 30
const MAX_REASON = 50

const SYSTEM_PROMPT = [
  '你是一个只输出 JSON 的本地美食顾问。',
  '只推荐下列城市真实存在、当地有口碑的经典菜品或特色小吃，最多 6 道。',
  '只输出一个 JSON 对象：{ "dishes": [ { "name": "菜名(不超过30字)", "reason": "一句话推荐理由(不超过50字)" } ] }',
  '严格约束：不确定某个菜是否属于该城市就删掉；宁缺毋滥，实在没有把握就输出空数组；',
  '不要编造城市、不要杜撰菜名。',
].join('\n')

type AiChatModel = {
  generateText: (payload: {
    model: string
    messages: Array<{ role: string; content: string }>
  }) => Promise<unknown>
}

type AiExtension = {
  createModel: (provider: string) => AiChatModel
}

type CacheEntry = { savedAt: number; items: CitySpecialty[] }

function cacheKey(city: string): string {
  return `eat_what_specialty_${encodeURIComponent(city)}`
}

function readCache(city: string): CitySpecialty[] | null {
  try {
    const raw = uni.getStorageSync(cacheKey(city))
    if (!raw) return null
    const entry = JSON.parse(raw) as CacheEntry
    if (!entry?.savedAt || !Array.isArray(entry.items)) return null
    if (Date.now() - entry.savedAt > SPECIALTY_TTL_MS) return null
    return entry.items
  } catch {
    return null
  }
}

function writeCache(city: string, items: CitySpecialty[]): void {
  try {
    uni.setStorageSync(cacheKey(city), JSON.stringify({ savedAt: Date.now(), items }))
  } catch {
    // 缓存写失败不影响本次展示。
  }
}

function getAiExtension(): AiExtension | null {
  const cloud = (globalThis as { wx?: { cloud?: { extend?: { AI?: AiExtension } } } }).wx
    ?.cloud
  return cloud?.extend?.AI ?? null
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('AI_SPECIALTY_TIMEOUT')), timeoutMs)
    promise.then(
      (value) => {
        clearTimeout(timer)
        resolve(value)
      },
      (error: unknown) => {
        clearTimeout(timer)
        reject(error instanceof Error ? error : new Error(String(error)))
      },
    )
  })
}

function extractResponseText(response: unknown): string {
  if (typeof response === 'string') return response
  if (typeof response !== 'object' || response === null) return ''
  const record = response as {
    choices?: Array<{ message?: { content?: unknown } }>
    text?: unknown
  }
  const content = record.choices?.[0]?.message?.content
  if (typeof content === 'string') return content
  if (typeof record.text === 'string') return record.text
  return ''
}

/** 收敛模型输出；任一越界返回 null（整体降级为空数组）。 */
function normalizeSpecialties(raw: unknown): CitySpecialty[] | null {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return null
  const list = (raw as Record<string, unknown>).dishes
  if (!Array.isArray(list)) return null
  const items: CitySpecialty[] = []
  for (const item of list) {
    if (typeof item !== 'object' || item === null) return null
    const name = String((item as Record<string, unknown>).name ?? '').trim()
    const reason = String((item as Record<string, unknown>).reason ?? '').trim()
    if (!name || name.length > MAX_NAME) return null
    if (!reason || reason.length > MAX_REASON) return null
    items.push({ name, reason })
  }
  return items.slice(0, MAX_ITEMS)
}

/**
 * 获取某城市的本地特色菜。优先读 24h 缓存，缓存未命中且 AI 可用时现算。
 * AI 不可用/失败/城市为空 → 空数组（UI 隐藏该区块）。
 */
export async function fetchCitySpecialties(city: string): Promise<CitySpecialty[]> {
  const normalizedCity = city.trim()
  if (!normalizedCity) return []
  const cached = readCache(normalizedCity)
  if (cached) return cached

  if (!AI_MEAL_INTENT_ENABLED) return []
  const ai = getAiExtension()
  if (!ai) return []

  try {
    const model = ai.createModel(AI_MEAL_INTENT_PROVIDER)
    const response = await withTimeout(
      model.generateText({
        model: AI_MEAL_INTENT_MODEL,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: normalizedCity },
        ],
      }),
      CALL_TIMEOUT_MS,
    )
    const content = extractResponseText(response)
    if (!content) return []
    const parsed: unknown = JSON.parse(stripCodeFence(content))
    const items = normalizeSpecialties(parsed)
    if (!items || items.length === 0) return []
    writeCache(normalizedCity, items)
    return items
  } catch {
    return []
  }
}
