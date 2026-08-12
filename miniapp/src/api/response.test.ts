import { describe, expect, it } from 'vitest'

import { ApiError } from '@/types/api'
import { normalizeTransportResponse } from './response'

describe('normalizeTransportResponse', () => {
  it('parses CloudBase string JSON and keeps the request id', () => {
    const result = normalizeTransportResponse<{ user_id: number }>({
      statusCode: 200,
      body: JSON.stringify({ ok: true, data: { user_id: 7 } }),
      requestId: 'wx-request-7',
    })

    expect(result.data).toEqual({ user_id: 7 })
    expect(result.requestId).toBe('wx-request-7')
  })

  it('maps a missing CloudBase service to a stable error', () => {
    expect.assertions(3)
    try {
      normalizeTransportResponse({
        statusCode: 404,
        body: {
          ok: false,
          code: 'SERVICE_NOT_FOUND',
          message: 'missing service',
        },
        requestId: 'wx-request-404',
      })
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).code).toBe('SERVICE_CONFIG_ERROR')
      expect((error as ApiError).message).toContain('服务配置错误')
    }
  })

  it('rejects a malformed success envelope', () => {
    expect(() =>
      normalizeTransportResponse({
        statusCode: 200,
        body: '<html>not json</html>',
      }),
    ).toThrowError(/响应格式/)
  })
})
