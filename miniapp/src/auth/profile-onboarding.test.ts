import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  buildProfileOnboardingUrl,
  dismissProfileOnboarding,
  normalizeUserRead,
  shouldOfferProfileOnboarding,
} from './profile-onboarding'

describe('profile onboarding', () => {
  beforeEach(() => {
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn(() => ''),
      setStorageSync: vi.fn(),
    })
  })

  it('normalizes legacy snake-case cached users', () => {
    expect(normalizeUserRead({
      id: 7,
      nickname: '饭饭',
      avatar_url: 'cloud://avatar.png',
      profile_complete: true,
    })).toEqual({
      id: 7,
      nickname: '饭饭',
      avatarUrl: 'cloud://avatar.png',
      accountKind: 'wechat',
      profileComplete: true,
    })
  })

  it('offers completion only to incomplete non-guest users that did not skip', () => {
    const user = {
      id: 8,
      nickname: '微信用户',
      accountKind: 'wechat' as const,
      profileComplete: false,
    }

    expect(shouldOfferProfileOnboarding(user, false)).toBe(true)
    expect(shouldOfferProfileOnboarding(user, true)).toBe(false)

    dismissProfileOnboarding(user.id)
    expect(uni.setStorageSync).toHaveBeenCalledWith(
      'profile_onboarding_dismissed_v1:8',
      '1',
    )
  })

  it('preserves a safe post-login destination through the completion page', () => {
    expect(buildProfileOnboardingUrl(encodeURIComponent('/pages/mine/mine'))).toBe(
      '/pages/account-profile/account-profile?redirect=%2Fpages%2Fmine%2Fmine',
    )
    expect(buildProfileOnboardingUrl('https%3A%2F%2Fevil.example')).toBe(
      '/pages/account-profile/account-profile?redirect=%2Fpages%2Ftoday%2Ftoday',
    )
  })
})
