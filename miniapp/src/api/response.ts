import { ApiError, type ApiResult } from '@/types/api'
import type { TransportResponse } from './transport'

const SERVICE_CONFIGURATION_CODES = new Set([
  'SERVICE_NOT_FOUND',
  'ENV_NOT_FOUND',
  'INVALID_ENV',
  'INVALID_SERVICE',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseBody(response: TransportResponse): Record<string, unknown> {
  if (isRecord(response.body)) return response.body
  if (typeof response.body === 'string') {
    try {
      const parsed: unknown = JSON.parse(response.body)
      if (isRecord(parsed)) return parsed
    } catch {
      // 统一在下方抛出稳定的格式错误。
    }
  }
  throw new ApiError(
    '服务响应格式异常',
    'INVALID_RESPONSE',
    response.statusCode,
    response.requestId,
  )
}

export function normalizeTransportResponse<T>(
  response: TransportResponse,
): { data: T; requestId?: string } {
  const body = parseBody(response) as Partial<ApiResult<unknown>>
  const code = typeof body.code === 'string' ? body.code : undefined
  const message =
    typeof body.message === 'string' && body.message.trim()
      ? body.message
      : '请求失败'

  if (
    SERVICE_CONFIGURATION_CODES.has(code || '') ||
    (response.statusCode === 404 && /service|env/i.test(message))
  ) {
    throw new ApiError(
      '服务配置错误，请联系开发者',
      'SERVICE_CONFIG_ERROR',
      response.statusCode,
      response.requestId,
    )
  }

  if (response.statusCode < 200 || response.statusCode >= 300 || body.ok !== true) {
    throw new ApiError(
      message,
      code || 'REQUEST_FAILED',
      response.statusCode,
      response.requestId,
    )
  }

  return {
    data: body.data as T,
    requestId: response.requestId,
  }
}
