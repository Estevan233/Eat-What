/**
 * 用户 Store - 全局登录态 + 档案。
 * token 与 profile 落 storage，刷新页面不丢。
 *
 * login() 流程：
 *   wx.login() → 拿 code → 调 api.auth.wxLogin(code) → 拿 {token, user} → 存 store + storage
 *
 * 字段命名约定：
 * - token / user（UserRead，含 nickname）= 认证场景的状态
 * - userProfile（ProfileRead）= 档案详情，T05 新增
 *
 * learn point：
 * - Pinia 用 setup 语法，token/profile 都是 ref，computed 自动响应
 * - uni.login 是异步 API，回调里 resolve/reject
 * - 注意区分 user（id+nickname+avatar_url）与 userProfile（生日/性别/身高/...）
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { wxLogin } from '@/api/auth'
import { getProfile, upsertProfile } from '@/api/profile'
import type { ProfileRead, ProfileUpsert, UserRead } from '@/types/api'

const TOKEN_KEY = 'eat_what_token'
const PROFILE_KEY = 'eat_what_profile'
const USER_PROFILE_KEY = 'eat_what_user_profile'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>('')
  // user = 登录响应里的 UserRead（id + nickname + avatar_url）
  const profile = ref<UserRead | null>(null)
  // userProfile = 档案详情（生日/性别/身高/体重/忌口）
  const userProfile = ref<ProfileRead | null>(null)

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
  const storedUserProfile = uni.getStorageSync(USER_PROFILE_KEY)
  if (storedUserProfile) {
    try {
      userProfile.value = JSON.parse(storedUserProfile) as ProfileRead
    } catch {
      userProfile.value = null
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

  /** 拉取档案详情（GET /profile），存 store + storage */
  async function fetchUserProfile(): Promise<ProfileRead | null> {
    const data = await getProfile()
    userProfile.value = data.profile
    uni.setStorageSync(USER_PROFILE_KEY, JSON.stringify(data.profile))
    return data.profile
  }

  /** 保存档案（PUT /profile），存 store + storage，返回更新后档案 */
  async function saveUserProfile(payload: ProfileUpsert): Promise<ProfileRead> {
    const data = await upsertProfile(payload)
    userProfile.value = data
    uni.setStorageSync(USER_PROFILE_KEY, JSON.stringify(data))
    return data
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
    userProfile.value = null
    uni.removeStorageSync(TOKEN_KEY)
    uni.removeStorageSync(PROFILE_KEY)
    uni.removeStorageSync(USER_PROFILE_KEY)
  }

  const isLoggedIn = computed(() => !!token.value)
  const hasProfile = computed(() => userProfile.value !== null)

  return {
    token,
    profile,
    userProfile,
    getWxCode,
    login,
    fetchUserProfile,
    saveUserProfile,
    setToken,
    setProfile,
    clear,
    isLoggedIn,
    hasProfile,
  }
})
