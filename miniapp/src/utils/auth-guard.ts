/**
 * 路由守卫工具。
 * 未登录时 uni.navigateTo 到登录页。
 * T04 会实现真正的登录页与回跳逻辑。
 */
import { useUserStore } from '@/stores/user'

export function requireLogin(redirectAfter?: string): boolean {
  const userStore = useUserStore()
  if (userStore.isLoggedIn) {
    return true
  }
  const url = redirectAfter
    ? `/pages/auth/auth?redirect=${encodeURIComponent(redirectAfter)}`
    : '/pages/auth/auth'
  uni.navigateTo({ url })
  return false
}
