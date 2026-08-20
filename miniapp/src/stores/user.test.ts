import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { cloudLoginMock, getResultMock, submitMock, wxLoginMock } = vi.hoisted(() => ({
  cloudLoginMock: vi.fn(),
  getResultMock: vi.fn(),
  submitMock: vi.fn(),
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
  getResult: getResultMock,
  submit: submitMock,
}))

import { ApiError } from '@/types/api'
import { useUserStore } from './user'

describe('user store cloud login', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    cloudLoginMock.mockReset()
    getResultMock.mockReset()
    submitMock.mockReset()
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

  it('treats a missing constitution result as an empty first-use state', async () => {
    getResultMock.mockRejectedValue(
      new ApiError('constitution 不存在', 'NOT_FOUND', 404),
    )
    const store = useUserStore()

    await expect(store.fetchConstitution()).resolves.toBeNull()

    expect(store.constitution).toBeNull()
    expect(uni.removeStorageSync).toHaveBeenCalledWith('eat_what_constitution')
  })

  it('preserves the cached constitution when a real request failure occurs', async () => {
    const cached = {
      primary: 'pinghe',
      secondary: [],
      scoresNormalized: {},
      constitutionTypeStr: 'pinghe',
    }
    submitMock.mockResolvedValue(cached)
    getResultMock.mockRejectedValue(
      new ApiError('网络异常', 'NETWORK_ERROR'),
    )
    const store = useUserStore()
    await store.saveConstitution({})

    await expect(store.fetchConstitution()).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
    })

    expect(store.constitution).toEqual(cached)
    expect(uni.removeStorageSync).not.toHaveBeenCalledWith('eat_what_constitution')
  })
})
