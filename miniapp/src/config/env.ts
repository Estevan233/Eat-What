const LOCAL_API_BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : ''
const DEFAULT_CLOUDBASE_ENV_ID = 'cloud1-d8gz4jm8vb964a1c9'
const DEFAULT_CLOUDBASE_SERVICE = 'eat-what-api'

export type CloudConfig = {
  environmentId: string
  serviceName: string
}

export function resolveCloudConfig(
  environmentId?: string,
  serviceName?: string,
): CloudConfig {
  const environment = environmentId?.trim() || ''
  const service = serviceName?.trim() || ''
  if (!environment || !service) {
    throw new Error('CloudBase 环境或服务名未配置')
  }
  return {
    environmentId: environment,
    serviceName: service,
  }
}

export function resolveApiBaseUrl(value?: string): string {
  const resolved = value?.trim() || LOCAL_API_BASE_URL
  return resolved.replace(/\/+$/, '')
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
)

export const CLOUDBASE_ENV_ID =
  import.meta.env.VITE_CLOUDBASE_ENV_ID?.trim() || DEFAULT_CLOUDBASE_ENV_ID
export const CLOUDBASE_SERVICE =
  import.meta.env.VITE_CLOUDBASE_SERVICE?.trim() || DEFAULT_CLOUDBASE_SERVICE

export function getCloudConfig(): CloudConfig {
  return resolveCloudConfig(CLOUDBASE_ENV_ID, CLOUDBASE_SERVICE)
}

/**
 * AI 用餐意图开关。
 *
 * 默认关闭：只有真实模型预检通过后才在部署环境变量中打开。关闭时首页不呈现
 * 任何 AI 入口，基础规则推荐不受影响。
 */
export const AI_MEAL_INTENT_ENABLED =
  import.meta.env.VITE_AI_MEAL_INTENT_ENABLED === 'true'

/**
 * 二期小程序成长计划：provider 为 hunyuan-v3，模型为 hy3-preview。
 * hunyuan-v3 无需在控制台手动开启模型开关，仅消耗成长计划免费额度。
 * 详见 .trellis/tasks/08-25-fanbubu-production-v2/research/ai-preflight.md
 */
export const AI_MEAL_INTENT_PROVIDER =
  import.meta.env.VITE_AI_MEAL_INTENT_PROVIDER?.trim() || 'hunyuan-v3'
export const AI_MEAL_INTENT_MODEL =
  import.meta.env.VITE_AI_MEAL_INTENT_MODEL?.trim() || 'hy3-preview'
