import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { cloudLoginMock, getResultMock, submitMock, updateAccountProfileMock, wxLoginMock } = vi.hoisted(() => ({
  cloudLoginMock: vi.fn(),
  getResultMock: vi.fn(),
  submitMock: vi.fn(),
  updateAccountProfileMock: vi.fn(),
  wxLoginMock: vi.fn(),
}))

vi.mock('@/api/auth', () => ({
  cloudLogin: cloudLoginMock,
  guestLogin: vi.fn(),
  wxLogin: wxLoginMock,
}))

vi.mock('@/api/profile', () => ({
  getProfile: vi.fn(),
  updateAccountProfile: updateAccountProfileMock,
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
    updateAccountProfileMock.mockReset()
    wxLoginMock.mockReset()
    cloudLoginMock.mockResolvedValue({
      token: 'cloud-token',
      user: { id: 7, nickname: '微信用户', profileComplete: false },
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

    await expect(store.login()).resolves.toEqual({
      id: 7,
      nickname: '微信用户',
      profileComplete: false,
    })

    expect(cloudLoginMock).toHaveBeenCalledOnce()
    expect(wxLoginMock).not.toHaveBeenCalled()
    expect(store.token).toBe('cloud-token')
  })

  it('clears the local guest identity after trusted WeChat login without merging accounts', async () => {
    vi.mocked(uni.getStorageSync).mockImplementation((key: string) => (
      key === 'eat_what_guest_id' ? 'old-guest-id' : ''
    ))
    const store = useUserStore()

    await store.login()

    expect(store.guestId).toBe('')
    expect(uni.removeStorageSync).toHaveBeenCalledWith('eat_what_guest_id')
  })

  it('updates the public user summary and persistent session after profile completion', async () => {
    updateAccountProfileMock.mockResolvedValue({
      id: 7,
      nickname: '饭饭',
      avatarUrl: 'cloud://avatar.png',
      profileComplete: true,
    })
    const store = useUserStore()
    await store.login()

    await expect(store.saveAccountProfile({
      nickname: '饭饭',
      avatarUrl: 'cloud://avatar.png',
    })).resolves.toMatchObject({ nickname: '饭饭', profileComplete: true })

    expect(store.profile?.avatarUrl).toBe('cloud://avatar.png')
    expect(uni.setStorageSync).toHaveBeenCalledWith(
      'eat_what_profile',
      expect.stringContaining('饭饭'),
    )
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
