/**
 * 餐次工具与自记辅助。
 *
 * 与后端 schemas/daily.py 的 MealSlot 语义保持一致：
 * - 前端按用户本地时间推断默认餐次（10:30 前早餐、16:00 前午餐、其余晚餐）
 * - 餐次展示标签/emoji/顺序在此集中维护，today 页、餐食日记页复用
 *
 * AI 一句话自记解析（parseMealNote）：
 * - 由小程序端 wx.cloud.extend.AI 完成（与用餐意图/特色菜同通道，后端不持 LLM 凭据）
 * - 只输出 JSON + 强约束收敛，失败重试 1 次后降级为「整句作备注 + 按时间推断餐次」
 * - 解析结果仅作表单预览，确认后走 /daily/logs/manual 落库（落库路径不依赖 AI）
 */
import {
  AI_MEAL_INTENT_ENABLED,
  AI_MEAL_INTENT_MODEL,
  AI_MEAL_INTENT_PROVIDER,
} from '@/config/env'
import type { MealSlot } from '@/types/api'
import { stripCodeFence } from './meal-intent'

/** 一天的餐次展示顺序（早 → 中 → 晚）。 */
export const MEAL_SLOT_ORDER: readonly MealSlot[] = ['breakfast', 'lunch', 'dinner']

export const MEAL_SLOT_LABELS: Record<MealSlot, string> = {
  breakfast: '早餐',
  lunch: '午餐',
  dinner: '晚餐',
}

export const MEAL_SLOT_EMOJI: Record<MealSlot, string> = {
  breakfast: '🌅',
  lunch: '☀️',
  dinner: '🌙',
}

/** 餐次选择 chips 的统一数据源。 */
export const MEAL_SLOT_OPTIONS = MEAL_SLOT_ORDER.map((value) => ({
  value,
  label: MEAL_SLOT_LABELS[value],
  emoji: MEAL_SLOT_EMOJI[value],
}))

/** 收敛成合法 MealSlot；非法值回退 null。 */
export function toMealSlot(value: unknown): MealSlot | null {
  return MEAL_SLOT_ORDER.includes(value as MealSlot) ? (value as MealSlot) : null
}

/**
 * 按本地时间推断默认餐次（与后端 infer_meal_slot 一致，前端用于表单默认值）：
 * <10:30 早餐、<16:00 午餐、其余晚餐。
 */
export function inferMealSlotByClock(now: Date = new Date()): MealSlot {
  const minutes = now.getHours() * 60 + now.getMinutes()
  if (minutes < 10 * 60 + 30) return 'breakfast'
  if (minutes < 16 * 60) return 'lunch'
  return 'dinner'
}

/** 自记的一道菜（解析结果与 manual 落库请求共用形状）。 */
export type ParsedMealDish = {
  name: string
  kcal?: number | null
}

/** AI 一句话自记解析结果（表单预览数据源）。 */
export type ParsedMealNote = {
  mealSlot: MealSlot
  dishes: ParsedMealDish[]
  shopName: string | null
  note: string | null
  /** AI 解析失败降级（整句塞 note、按时间推断餐次）时置 true。 */
  degraded: boolean
}

const MAX_DISHES = 8
const MAX_DISH_NAME = 40
const MAX_SHOP_NAME = 80
const MAX_NOTE_LENGTH = 200
const MAX_KCAL = 1500
const CALL_TIMEOUT_MS = 6000

const SYSTEM_PROMPT = [
  '你是一个只输出 JSON 的餐食记录助手。用户用一句话说他（在某个店）吃了什么，你把它整理成结构化记录。',
  '只输出一个 JSON 对象，不要任何解释或多余文字：',
  '{',
  '  "meal_slot": "breakfast" 或 "lunch" 或 "dinner"（按描述判断；判断不出就按当地时间：10:30 前早餐、16:00 前午餐、其余晚餐）',
  '  "dishes": [{ "name": "菜名不超过40字", "kcal": 常见一份的估算千卡整数(1-1500)或null }]',
  '  "shop_name": "店铺名(不超过80字)" 或 null（只在明确提到具体店/食堂/馆子时填写）',
  '  "note": "不超过200字的补充" 或 null（例如：和同事聚餐、点的外卖、有点油）',
  '}',
  '规则：',
  '- 只提取输入中确实提到的食物；没提到的不要编造。喝的（豆浆/咖啡/奶茶/酒）也算一道。',
  '- dishes 最多 8 道，同一食物合并成一道。',
  '- 每道菜估算一个常见分量的千卡数；不确定就填 null，宁缺毋滥。',
  '- 输入没有实质内容时输出：{"meal_slot":"dinner","dishes":[],"shop_name":null,"note":"<原文>"}',
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

function getAiExtension(): AiExtension | null {
  const cloud = (globalThis as { wx?: { cloud?: { extend?: { AI?: AiExtension } } } }).wx
    ?.cloud
  return cloud?.extend?.AI ?? null
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('AI_MEAL_NOTE_TIMEOUT')), timeoutMs)
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

/** 收敛一道菜；非法行返回 null（整体失败）。 */
function normalizeDish(value: unknown): ParsedMealDish | null {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  const name = String(record.name ?? '').trim()
  if (!name || name.length > MAX_DISH_NAME) return null
  let kcal: number | null = null
  if (record.kcal !== undefined && record.kcal !== null) {
    if (typeof record.kcal !== 'number' || !Number.isFinite(record.kcal)) return null
    const rounded = Math.round(record.kcal)
    if (rounded < 1 || rounded > MAX_KCAL) return null
    kcal = rounded
  }
  return kcal === null ? { name } : { name, kcal }
}

/**
 * 把模型输出严格收敛成 ParsedMealNote；任一字段越界整体失败（null），
 * 由调用方走重试/降级。dish 为空数组但 shop_name/note 有值时仍然合法
 * （例如"下午在公司楼下咖啡店坐了一会儿"，菜品留空让用户手动补）。
 */
export function normalizeParsedMealNote(raw: unknown): ParsedMealNote | null {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return null
  const record = raw as Record<string, unknown>

  const mealSlot = toMealSlot(record.meal_slot)
  if (!mealSlot) return null

  const rawDishes = record.dishes
  if (!Array.isArray(rawDishes)) return null
  const dishes: ParsedMealDish[] = []
  for (const item of rawDishes) {
    const dish = normalizeDish(item)
    if (!dish) return null
    dishes.push(dish)
    if (dishes.length >= MAX_DISHES) break
  }

  let shopName: string | null = null
  if (record.shop_name !== undefined && record.shop_name !== null) {
    const trimmed = String(record.shop_name).trim()
    if (!trimmed || trimmed.length > MAX_SHOP_NAME) return null
    shopName = trimmed
  }

  let note: string | null = null
  if (record.note !== undefined && record.note !== null) {
    const trimmed = String(record.note).trim()
    if (trimmed.length > MAX_NOTE_LENGTH) return null
    note = trimmed || null
  }

  if (dishes.length === 0 && !shopName && !note) return null
  return { mealSlot, dishes, shopName, note, degraded: false }
}

/** AI 不可用/解析失败时的降级结果：整句作备注 + 按本地时间推断餐次。 */
export function degradeMealNote(text: string, now: Date = new Date()): ParsedMealNote {
  const trimmed = text.trim()
  return {
    mealSlot: inferMealSlotByClock(now),
    dishes: [],
    shopName: null,
    note: trimmed ? trimmed.slice(0, MAX_NOTE_LENGTH) : null,
    degraded: true,
  }
}

/** 单次模型调用：开关/运行时缺失或解析失败都返回 null（不抛错）。 */
async function callParserOnce(text: string): Promise<ParsedMealNote | null> {
  if (!AI_MEAL_INTENT_ENABLED) return null
  const ai = getAiExtension()
  if (!ai) return null
  try {
    const model = ai.createModel(AI_MEAL_INTENT_PROVIDER)
    const response = await withTimeout(
      model.generateText({
        model: AI_MEAL_INTENT_MODEL,
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: text },
        ],
      }),
      CALL_TIMEOUT_MS,
    )
    const content = extractResponseText(response)
    if (!content) return null
    return normalizeParsedMealNote(JSON.parse(stripCodeFence(content)))
  } catch {
    return null
  }
}

/**
 * 把一句"今天吃了什么"解析成结构化预览（不落库）。
 * - 空输入返回 null
 * - AI 可用时：调用模型，失败重试 1 次；仍失败则降级
 * - AI 不可用（开关关/无 wx 运行时/超时）：直接降级，不阻塞记一笔
 */
export async function parseMealNote(text: string): Promise<ParsedMealNote | null> {
  const trimmed = text.trim()
  if (!trimmed) return null
  const parsed = (await callParserOnce(trimmed)) ?? (await callParserOnce(trimmed))
  return parsed ?? degradeMealNote(trimmed)
}
