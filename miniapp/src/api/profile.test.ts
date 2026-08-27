import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestMock } = vi.hoisted(() => ({ requestMock: vi.fn() }))

vi.mock('./request', () => ({ request: requestMock }))

import { updateAccountProfile } from './profile'

describe('updateAccountProfile', () => {
  beforeEach(() => requestMock.mockReset())

  it('uses the authenticated public-profile endpoint', async () => {
    requestMock.mockResolvedValue({
      id: 7,
      nickname: '饭饭',
      avatarUrl: 'cloud://avatar.png',
      profileComplete: true,
    })

    await updateAccountProfile({
      nickname: '饭饭',
      avatarUrl: 'cloud://avatar.png',
    })

    expect(requestMock).toHaveBeenCalledWith({
      url: '/api/v1/profile/account',
      method: 'PUT',
      data: {
        nickname: '饭饭',
        avatarUrl: 'cloud://avatar.png',
      },
    })
  })
})
