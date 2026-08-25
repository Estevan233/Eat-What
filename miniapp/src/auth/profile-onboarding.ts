import type { UserRead } from '@/types/api'
import { resolvePostLoginNavigation } from './navigation'

type LegacyUserRead = {
  id: number
  nickname: string
  avatarUrl?: string
  profileComplete?: boolean
  avatar_url?: string
  profile_complete?: boolean
}

const DISMISS_PREFIX = 'profile_onboarding_dismissed_v1:'

export function normalizeUserRead(raw: LegacyUserRead): UserRead {
  const avatarUrl = raw.avatarUrl ?? raw.avatar_url
  const profileComplete = raw.profileComplete
    ?? raw.profile_complete
    ?? Boolean(
      avatarUrl
      && raw.nickname.trim()
      && !['微信用户', '用户'].includes(raw.nickname.trim()),
    )
  return {
    id: raw.id,
    nickname: raw.nickname,
    ...(avatarUrl ? { avatarUrl } : {}),
    profileComplete,
  }
}

export function profileOnboardingStorageKey(userId: number): string {
  return `${DISMISS_PREFIX}${userId}`
}

export function shouldOfferProfileOnboarding(
  user: UserRead,
  isGuest: boolean,
): boolean {
  if (isGuest || user.profileComplete) return false
  return uni.getStorageSync(profileOnboardingStorageKey(user.id)) !== '1'
}

export function dismissProfileOnboarding(userId: number): void {
  uni.setStorageSync(profileOnboardingStorageKey(userId), '1')
}

export function buildProfileOnboardingUrl(encodedRedirect?: string): string {
  const destination = resolvePostLoginNavigation(encodedRedirect).url
  return `/pages/account-profile/account-profile?redirect=${encodeURIComponent(destination)}`
}
