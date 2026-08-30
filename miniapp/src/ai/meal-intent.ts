/**
 * AI 用餐意图抽取。
 *
 * 职责边界：AI 只把自然语言"翻译"成受控的 MealIntent。它不生成菜品 ID、
 * 营养值、菜谱或健康结论；最终候选、硬过滤、安全与持久化全部由后端规则服务负责。
 *
 * 任何失败（开关关闭、无运行时、超时、非 JSON、字段越界）都必须静默返回 null，
 * 由调用方继续走基础推荐，绝不把技术错误抛给用户。
 */
import {
  AI_MEAL_INTENT_ENABLED,
  AI_MEAL_INTENT_MODEL,
  AI_MEAL_INTENT_PROVIDER,
} from '@/config/env'
import type { DiningMode, MealGoal, MealIntent } from '@/types/api'

const MAX_INGREDIENTS = 12
const MAX_INGREDIENT_LENGTH = 20
const MAX_SUMMARY_LENGTH = 80
const MIN_TIME_MINUTES = 5
const MAX_TIME_MINUTES = 180
const CALL_TIMEOUT_MS = 8000

const GOALS: readonly MealGoal[] = ['balanced', 'weight_control', 'high_protein']
const DINING_MODES: readonly DiningMode[] = ['cook', 'eat_out']

const SYSTEM_PROMPT = [
  '你是一个只输出 JSON 的用餐意图抽取器。',
  '从用户输入中抽取下列字段，不要生成菜名、营养数值、健康结论或诊断建议。',
  '只输出一个 JSON 对象，不要任何解释或多余文字：',
  '- availableIngredients：字符串数组，用户已有的食材，最多 12 项',
  '- excludedIngredients：字符串数组，用户明确不想吃的食材，最多 12 项',
  '- maxTimeMinutes：整数或 null，可接受的最长烹饪分钟数，取值 5-180',
  '- goal：只能取 balanced、weight_control、high_protein 或 null',
  '- diningModeHint：只能取 cook、eat_out 或 null',
  '- summary：不超过 80 字的一句话摘要',
  '无法判断的字段一律用 null 或空数组，不要猜测。',
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

type ValidationResult<T> = { ok: true; value: T } | { ok: false }

export function isMealIntentEnabled(): boolean {
  return AI_MEAL_INTENT_ENABLED
}

function getAiExtension(): AiExtension | null {
  const cloud = (globalThis as { wx?: { cloud?: { extend?: { AI?: AiExtension } } } }).wx
    ?.cloud
  return cloud?.extend?.AI ?? null
}

/**
 * 剥离 Markdown 代码围栏；没有围栏时截取第一个完整 JSON 对象。
 */
export function stripCodeFence(raw: string): string {
  const trimmed = raw.trim()
  const fenced = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i)
  if (fenced?.[1]) {
    return fenced[1].trim()
  }
  const start = trimmed.indexOf('{')
  const end = trimmed.lastIndexOf('}')
  if (start >= 0 && end > start) {
    return trimmed.slice(start, end + 1)
  }
  return trimmed
}

function normalizeStringList(value: unknown): string[] | null {
  if (value === undefined || value === null) {
    return []
  }
  if (!Array.isArray(value)) {
    return null
  }
  const cleaned: string[] = []
  for (const item of value) {
    if (typeof item !== 'string') {
      return null
    }
    const trimmed = item.trim()
    if (!trimmed) {
      continue
    }
    if (trimmed.length > MAX_INGREDIENT_LENGTH) {
      return null
    }
    cleaned.push(trimmed)
  }
  if (cleaned.length > MAX_INGREDIENTS) {
    return null
  }
  return cleaned
}

function normalizeTime(value: unknown): ValidationResult<number | null> {
  if (value === undefined || value === null) {
    return { ok: true, value: null }
  }
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return { ok: false }
  }
  const rounded = Math.round(value)
  if (rounded < MIN_TIME_MINUTES || rounded > MAX_TIME_MINUTES) {
    return { ok: false }
  }
  return { ok: true, value: rounded }
}

function normalizeGoal(value: unknown): ValidationResult<MealGoal | null> {
  if (value === undefined || value === null) {
    return { ok: true, value: null }
  }
  if (typeof value !== 'string' || !GOALS.includes(value as MealGoal)) {
    return { ok: false }
  }
  return { ok: true, value: value as MealGoal }
}

function normalizeDiningMode(value: unknown): ValidationResult<DiningMode | null> {
  if (value === undefined || value === null) {
    return { ok: true, value: null }
  }
  if (typeof value !== 'string' || !DINING_MODES.includes(value as DiningMode)) {
    return { ok: false }
  }
  return { ok: true, value: value as DiningMode }
}

function normalizeSummary(value: unknown): ValidationResult<string> {
  if (value === undefined || value === null) {
    return { ok: true, value: '' }
  }
  if (typeof value !== 'string') {
    return { ok: false }
  }
  const trimmed = value.trim()
  if (trimmed.length > MAX_SUMMARY_LENGTH) {
    return { ok: false }
  }
  return { ok: true, value: trimmed }
}

/**
 * 把模型输出严格收敛成 MealIntent；任何越界整体失败，不提交错误约束。
 */
export function normalizeMealIntent(raw: unknown): MealIntent | null {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    return null
  }
  const record = raw as Record<string, unknown>

  const available = normalizeStringList(record.availableIngredients)
  if (available === null) {
    return null
  }
  const excluded = normalizeStringList(record.excludedIngredients)
  if (excluded === null) {
    return null
  }
  const time = normalizeTime(record.maxTimeMinutes)
  if (!time.ok) {
    return null
  }
  const goal = normalizeGoal(record.goal)
  if (!goal.ok) {
    return null
  }
  const mode = normalizeDiningMode(record.diningModeHint)
  if (!mode.ok) {
    return null
  }
  const summary = normalizeSummary(record.summary)
  if (!summary.ok) {
    return null
  }

  return {
    availableIngredients: available,
    excludedIngredients: excluded,
    maxTimeMinutes: time.value,
    goal: goal.value,
    diningModeHint: mode.value,
    summary: summary.value,
  }
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('AI_MEAL_INTENT_TIMEOUT'))
    }, timeoutMs)
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
  if (typeof response === 'string') {
    return response
  }
  if (typeof response !== 'object' || response === null) {
    return ''
  }
  const record = response as {
    choices?: Array<{ message?: { content?: unknown } }>
    text?: unknown
  }
  const content = record.choices?.[0]?.message?.content
  if (typeof content === 'string') {
    return content
  }
  if (typeof record.text === 'string') {
    return record.text
  }
  return ''
}

/**
 * 调用模型把自然语言解析成 MealIntent。
 * 开关关闭、无 AI 运行时、超时、解析失败或字段越界时返回 null。
 */
export async function extractMealIntent(text: string): Promise<MealIntent | null> {
  const trimmed = text.trim()
  if (!isMealIntentEnabled() || !trimmed) {
    return null
  }
  const ai = getAiExtension()
  if (!ai) {
    return null
  }

  try {
    const model = ai.createModel(AI_MEAL_INTENT_PROVIDER)
    const response = await withTimeout(
      model.generateText({
        model: AI_MEAL_INTENT_MODEL,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: trimmed },
        ],
      }),
      CALL_TIMEOUT_MS,
    )
    const content = extractResponseText(response)
    if (!content) {
      return null
    }
    const parsed: unknown = JSON.parse(stripCodeFence(content))
    return normalizeMealIntent(parsed)
  } catch {
    return null
  }
}
