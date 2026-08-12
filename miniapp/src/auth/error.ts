import { ApiError } from '@/types/api'

const AUTH_ERROR_FALLBACK = '登录失败，请检查网络或后端服务'

export function shouldShowAuthErrorToast(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true
  return (error.statusCode ?? 0) >= 500
}

export function toAuthErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message.trim()
  }

  if (typeof error === 'string' && error.trim()) {
    return error.trim()
  }

  if (error && typeof error === 'object' && 'errMsg' in error) {
    const errMsg = (error as { errMsg?: unknown }).errMsg
    if (typeof errMsg === 'string' && errMsg.trim()) {
      return errMsg.trim()
    }
  }

  return AUTH_ERROR_FALLBACK
}
