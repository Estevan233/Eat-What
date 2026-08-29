import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  AUTH_STORAGE_KEYS,
  clearAuthStorage,
  getStoredToken,
  promoteToWechatSession,
  readStoredJson,
  saveLoginSession,
  subscribeAuthClear,
  writeStoredString,
} from './storage'

describe('auth storage', () => {
  const values = new Map<string, unknown>()

  beforeEach(() => {
    values.clear()
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn((key: string) => values.get(key) ?? ''),
      setStorageSync: vi.fn((key: string, value: unknown) => values.set(key, value)),
      removeStorageSync: vi.fn((key: string) => values.delete(key)),
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('persists and restores a login session', () => {
    const user = {
      id: 7,
      nickname: '测试用户',
      accountKind: 'wechat' as const,
      profileComplete: false,
    }

    saveLoginSession('token-7', user)

    expect(getStoredToken()).toBe('token-7')
    expect(readStoredJson(AUTH_STORAGE_KEYS.profile)).toEqual(user)
  })

  it('promotes a guest session only after the formal response is available', () => {
    writeStoredString(AUTH_STORAGE_KEYS.guestId, 'guest-8')
    writeStoredString(AUTH_STORAGE_KEYS.userProfile, 'guest-health-cache')
    writeStoredString(AUTH_STORAGE_KEYS.constitution, 'guest-constitution-cache')
    const user = {
      id: 9,
      nickname: '微信用户',
      accountKind: 'wechat' as const,
      profileComplete: false,
    }

    promoteToWechatSession('wechat-token', user)

    expect(getStoredToken()).toBe('wechat-token')
    expect(readStoredJson(AUTH_STORAGE_KEYS.profile)).toEqual(user)
    expect(values.has(AUTH_STORAGE_KEYS.guestId)).toBe(false)
    expect(values.has(AUTH_STORAGE_KEYS.userProfile)).toBe(false)
    expect(values.has(AUTH_STORAGE_KEYS.constitution)).toBe(false)
  })

  it('clears session data while preserving the guest identity after a 401', () => {
    saveLoginSession('expired-token', {
      id: 8,
      nickname: '游客',
      accountKind: 'guest',
      profileComplete: false,
    })
    writeStoredString(AUTH_STORAGE_KEYS.guestId, 'guest-8')
    const listener = vi.fn()
    const unsubscribe = subscribeAuthClear(listener)

    clearAuthStorage({ includeGuestId: false })

    expect(getStoredToken()).toBe('')
    expect(readStoredJson(AUTH_STORAGE_KEYS.profile)).toBeNull()
    expect(values.get(AUTH_STORAGE_KEYS.guestId)).toBe('guest-8')
    expect(listener).toHaveBeenCalledWith(false)
    unsubscribe()
  })
})
