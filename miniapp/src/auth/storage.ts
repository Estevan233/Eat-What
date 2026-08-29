import type { UserRead } from '@/types/api'

export const AUTH_STORAGE_KEYS = {
  token: 'eat_what_token',
  profile: 'eat_what_profile',
  userProfile: 'eat_what_user_profile',
  guestId: 'eat_what_guest_id',
  constitution: 'eat_what_constitution',
} as const

type AuthStorageKey = typeof AUTH_STORAGE_KEYS[keyof typeof AUTH_STORAGE_KEYS]
type AuthClearListener = (includeGuestId: boolean) => void

const authClearListeners = new Set<AuthClearListener>()

export function readStoredString(key: AuthStorageKey): string {
  const value = uni.getStorageSync(key)
  return typeof value === 'string' ? value : ''
}

export function readStoredJson<T>(key: AuthStorageKey): T | null {
  const value = uni.getStorageSync(key)
  if (!value) return null

  if (typeof value !== 'string') return value as T

  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

export function writeStoredString(key: AuthStorageKey, value: string): void {
  uni.setStorageSync(key, value)
}

export function writeStoredJson<T>(key: AuthStorageKey, value: T): void {
  uni.setStorageSync(key, JSON.stringify(value))
}

export function removeStoredValue(key: AuthStorageKey): void {
  uni.removeStorageSync(key)
}

export function getStoredToken(): string {
  return readStoredString(AUTH_STORAGE_KEYS.token)
}

export function saveLoginSession(token: string, user: UserRead): void {
  writeStoredString(AUTH_STORAGE_KEYS.token, token)
  writeStoredJson(AUTH_STORAGE_KEYS.profile, user)
}

export function promoteToWechatSession(token: string, user: UserRead): void {
  saveLoginSession(token, user)
  removeStoredValue(AUTH_STORAGE_KEYS.guestId)
  removeStoredValue(AUTH_STORAGE_KEYS.userProfile)
  removeStoredValue(AUTH_STORAGE_KEYS.constitution)
}

export function subscribeAuthClear(listener: AuthClearListener): () => void {
  authClearListeners.add(listener)
  return () => {
    authClearListeners.delete(listener)
  }
}

export function clearAuthStorage(
  options: { includeGuestId?: boolean } = {},
): void {
  const includeGuestId = options.includeGuestId ?? true
  removeStoredValue(AUTH_STORAGE_KEYS.token)
  removeStoredValue(AUTH_STORAGE_KEYS.profile)
  removeStoredValue(AUTH_STORAGE_KEYS.userProfile)
  removeStoredValue(AUTH_STORAGE_KEYS.constitution)
  if (includeGuestId) {
    removeStoredValue(AUTH_STORAGE_KEYS.guestId)
  }

  authClearListeners.forEach((listener) => listener(includeGuestId))
}
