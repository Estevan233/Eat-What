/**
 * AI 推荐理由生成。
 *
 * 基于用户的用餐意图（如有）和推荐结果，调用 AI 生成一句话个性化解释，
 * 让用户理解"为什么推荐这套餐"。
 *
 * 降级时返回 null，不影响推荐展示。
 */
import { generateText, isAiEnabled } from './cloud-model'

const SYSTEM_PROMPT = [
  '你是饭卜卜的推荐解释器。',
  '基于用户的用餐意图和推荐结果，生成一句话（不超过 60 字）解释为什么推荐这套餐。',
  '只输出解释文本，不要 JSON、不要解释逻辑、不要重复菜名。',
  '语气亲切、具体，避免空泛的"营养均衡"。',
  '如果用户有明确意图（食材/时间/目标），解释要与意图挂钩。',
].join('\n')

/**
 * 生成推荐理由。
 *
 * @param userIntentSummary 用户 AI 解析的意图摘要（如 "番茄鸡蛋，20 分钟，少油"），可为 null
 * @param mealNames 推荐菜品名称列表
 * @param diningMode 用餐模式（cook/eat_out）
 * @returns 一句话解释；AI 不可用时返回 null
 */
export async function generateRecommendationExplanation(
  userIntentSummary: string | null,
  mealNames: string[],
  diningMode: string,
): Promise<string | null> {
  if (!isAiEnabled() || mealNames.length === 0) {
    return null
  }

  const intentLine = userIntentSummary
    ? `用户意图：${userIntentSummary}。`
    : ''
  const mealLine = `推荐菜品：${mealNames.join('、')}。`
  const modeLine = `用餐模式：${diningMode === 'cook' ? '自己做' : '外食'}。`

  return generateText(SYSTEM_PROMPT, `${intentLine}${mealLine}${modeLine}`)
}
