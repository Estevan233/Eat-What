import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  AUTH_STORAGE_KEYS,
  clearAuthStorage,
  getStoredToken,
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
    const user = { id: 7, nickname: '测试用户' }

    saveLoginSession('token-7', user)

    expect(getStoredToken()).toBe('token-7')
    expect(readStoredJson(AUTH_STORAGE_KEYS.profile)).toEqual(user)
  })

  it('clears session data while preserving the guest identity after a 401', () => {
    saveLoginSession('expired-token', { id: 8, nickname: '游客' })
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
