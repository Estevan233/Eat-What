/**
 * 通用 CloudBase AI 模型调用服务。
 *
 * 所有 AI 功能（用餐意图解析、推荐理由生成等）共用此模块，
 * 确保凭据管理一致、降级逻辑统一、超时可控。
 *
 * 任何失败（开关关闭、无运行时、超时、出错）都返回 null，由调用方降级。
 */
import {
  AI_MEAL_INTENT_ENABLED,
  AI_MEAL_INTENT_MODEL,
  AI_MEAL_INTENT_PROVIDER,
} from '@/config/env'

const CALL_TIMEOUT_MS = 8000

type AiChatModel = {
  generateText: (payload: {
    model: string
    messages: Array<{ role: string; content: string }>
  }) => Promise<unknown>
}

type AiExtension = {
  createModel: (provider: string) => AiChatModel
}

export function isAiEnabled(): boolean {
  return AI_MEAL_INTENT_ENABLED
}

function getAiExtension(): AiExtension | null {
  const cloud = (globalThis as {
    wx?: { cloud?: { extend?: { AI?: AiExtension } } }
  }).wx?.cloud
  return cloud?.extend?.AI ?? null
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('AI_TIMEOUT')),
      timeoutMs,
    )
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
 * 调用 CloudBase AI 模型生成文本。
 *
 * @param systemPrompt system 角色的指令
 * @param userMessage user 角色的输入
 * @returns 模型生成的文本；开关关闭、超时或出错时返回 null
 */
export async function generateText(
  systemPrompt: string,
  userMessage: string,
): Promise<string | null> {
  if (!AI_MEAL_INTENT_ENABLED || !systemPrompt.trim() || !userMessage.trim()) {
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
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userMessage },
        ],
      }),
      CALL_TIMEOUT_MS,
    )
    return extractResponseText(response)
  } catch {
    return null
  }
}
