import { describe, expect, it } from 'vitest'

import { ApiError } from '@/types/api'
import { shouldShowAuthErrorToast, toAuthErrorMessage } from './error'

describe('toAuthErrorMessage', () => {
  it('uses the concrete runtime error message', () => {
    expect(toAuthErrorMessage(new Error('wx.login 失败'))).toBe('wx.login 失败')
  })

  it('falls back to a useful message for unknown errors', () => {
    expect(toAuthErrorMessage(null)).toBe('登录失败，请检查网络或后端服务')
  })

  it('does not duplicate an API error toast already shown by request', () => {
    expect(shouldShowAuthErrorToast(new ApiError('请求失败', 'BAD_REQUEST', 400))).toBe(false)
    expect(shouldShowAuthErrorToast(new ApiError('网络异常', 'NETWORK_ERROR'))).toBe(false)
  })

  it('shows page-level errors and server errors that request leaves silent', () => {
    expect(shouldShowAuthErrorToast(new Error('wx.login 失败'))).toBe(true)
    expect(shouldShowAuthErrorToast(new ApiError('服务器错误', 'INTERNAL', 500))).toBe(true)
  })
})
