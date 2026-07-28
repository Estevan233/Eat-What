/**
 * 用户 Store - 全局登录态 + 档案。
 * token 与 profile 落 storage，刷新页面不丢。
 *
 * login() 流程：
 *   wx.login() → 拿 code → 调 api.auth.wxLogin(code) → 拿 {token, user} → 存 store + storage
 *
 * learn point：
 * - Pinia 用 setup 语法，token/profile 都是 ref，computed 自动响应
 * - uni.login 是异步 API，回调里 resolve/reject
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { wxLogin } from '@/api/auth'
import type { UserRead } from '@/types/api'

const TOKEN_KEY = 'eat_what_token'
const PROFILE_KEY = 'eat_what_profile'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>('')
  const profile = ref<UserRead | null>(null)

  // 启动时从 storage 恢复
  token.value = uni.getStorageSync(TOKEN_KEY) || ''
  const storedProfile = uni.getStorageSync(PROFILE_KEY)
  if (storedProfile) {
    try {
      profile.value = JSON.parse(storedProfile) as UserRead
    } catch {
      profile.value = null
    }
  }

  /** 调 wx.login 拿 code */
  function getWxCode(): Promise<string> {
    return new Promise((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: (res) => {
          if (res.code) {
            resolve(res.code)
          } else {
            reject(new Error('wx.login 未返回 code'))
          }
        },
        fail: (err) => reject(new Error(err.errMsg || 'wx.login 失败')),
      })
    })
  }

  /** 完整登录流程：wx.login → wxLogin API → 存 token/profile */
  async function login(): Promise<UserRead> {
    const code = await getWxCode()
    const data = await wxLogin(code)
    token.value = data.token
    profile.value = data.user
    uni.setStorageSync(TOKEN_KEY, data.token)
    uni.setStorageSync(PROFILE_KEY, JSON.stringify(data.user))
    return data.user
  }

  function setToken(t: string) {
    token.value = t
    uni.setStorageSync(TOKEN_KEY, t)
  }

  function setProfile(p: UserRead) {
    profile.value = p
    uni.setStorageSync(PROFILE_KEY, JSON.stringify(p))
  }

  function clear() {
    token.value = ''
    profile.value = null
    uni.removeStorageSync(TOKEN_KEY)
    uni.removeStorageSync(PROFILE_KEY)
  }

  const isLoggedIn = computed(() => !!token.value)

  return { token, profile, getWxCode, login, setToken, setProfile, clear, isLoggedIn }
})
