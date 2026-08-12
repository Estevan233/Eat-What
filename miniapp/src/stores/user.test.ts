import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { cloudLoginMock, wxLoginMock } = vi.hoisted(() => ({
  cloudLoginMock: vi.fn(),
  wxLoginMock: vi.fn(),
}))

vi.mock('@/api/auth', () => ({
  cloudLogin: cloudLoginMock,
  guestLogin: vi.fn(),
  wxLogin: wxLoginMock,
}))

vi.mock('@/api/profile', () => ({
  getProfile: vi.fn(),
  upsertProfile: vi.fn(),
}))

vi.mock('@/api/constitution', () => ({
  getResult: vi.fn(),
  submit: vi.fn(),
}))

import { useUserStore } from './user'

describe('user store cloud login', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    cloudLoginMock.mockReset()
    wxLoginMock.mockReset()
    cloudLoginMock.mockResolvedValue({
      token: 'cloud-token',
      user: { id: 7, nickname: '微信用户' },
    })
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn(() => ''),
      setStorageSync: vi.fn(),
      removeStorageSync: vi.fn(),
    })
    vi.stubGlobal('wx', {
      cloud: { callContainer: vi.fn() },
    })
  })

  it('uses CloudBase trusted-header login without asking wx.login for a code', async () => {
    const store = useUserStore()

    await expect(store.login()).resolves.toEqual({ id: 7, nickname: '微信用户' })

    expect(cloudLoginMock).toHaveBeenCalledOnce()
    expect(wxLoginMock).not.toHaveBeenCalled()
    expect(store.token).toBe('cloud-token')
  })
})
