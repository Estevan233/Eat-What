import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestMock } = vi.hoisted(() => ({
  requestMock: vi.fn(),
}))

vi.mock('./request', () => ({
  request: requestMock,
}))

import { cloudLogin } from './auth'

describe('cloudLogin', () => {
  beforeEach(() => {
    requestMock.mockReset()
    requestMock.mockResolvedValue({
      token: 'token',
      user: { id: 1, nickname: '微信用户' },
    })
  })

  it('uses the trusted-header login endpoint without a wx code', async () => {
    await cloudLogin()

    expect(requestMock).toHaveBeenCalledWith({
      url: '/api/v1/auth/cloud-login',
      method: 'POST',
      data: {},
      loading: false,
    })
  })
})
