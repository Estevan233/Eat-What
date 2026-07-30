/**
 * 用户 Store - 全局登录态 + 档案 + 体质。
 * token / profile / userProfile / constitution 落 storage，刷新页面不丢。
 *
 * login() 流程：
 *   wx.login() → 拿 code → 调 api.auth.wxLogin(code) → 拿 {token, user} → 存 store + storage
 *
 * guestLogin() 流程（游客模式）：
 *   读 storage 里的 guest_id，没有就生成 UUID → 调 api.auth.guestLogin(guestId) → 存 store + storage
 *
 * 字段命名约定：
 * - token / profile（UserRead，含 nickname）= 认证场景的状态
 * - userProfile（ProfileRead）= 档案详情，T05 新增
 * - constitution（ConstitutionResult）= 体质判定结果，T06 新增
 * - guestId = 游客身份持久化标识，仅游客模式用
 *
 * learn point：
 * - Pinia 用 setup 语法，token/profile 都是 ref，computed 自动响应
 * - uni.login 是异步 API，回调里 resolve/reject
 * - 注意区分 user（id+nickname+avatar_url）与 userProfile（生日/性别/身高/...）
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { guestLogin, wxLogin } from '@/api/auth'
import { getProfile, upsertProfile } from '@/api/profile'
import { getResult, submit as submitConstitution } from '@/api/constitution'
import type {
  ConstitutionResult,
  ProfileRead,
  ProfileUpsert,
  UserRead,
} from '@/types/api'

const TOKEN_KEY = 'eat_what_token'
const PROFILE_KEY = 'eat_what_profile'
const USER_PROFILE_KEY = 'eat_what_user_profile'
const GUEST_ID_KEY = 'eat_what_guest_id'
const CONSTITUTION_KEY = 'eat_what_constitution'

/** 生成一个游客身份标识（UUID v4 风格，无依赖）。 */
function generateGuestId(): string {
  // 优先用 uni 的 uuid（部分基础库支持），否则用回退实现
  if (typeof uni !== 'undefined' && typeof uni.getStorageSync === 'function') {
    // 简单回退：时间戳 + 随机串，足够区分不同游客，碰撞概率极低
    const rand = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1)
    return `${Date.now().toString(16)}-${rand()}${rand()}-${rand()}-${rand()}${rand()}${rand()}`
  }
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>('')
  // user = 登录响应里的 UserRead（id + nickname + avatar_url）
  const profile = ref<UserRead | null>(null)
  // userProfile = 档案详情（生日/性别/身高/体重/忌口）
  const userProfile = ref<ProfileRead | null>(null)
  // T06 新增：体质判定结果（POST 后缓存，避免每次进页都拉）
  const constitution = ref<ConstitutionResult | null>(null)
  // 游客身份持久化标识
  const guestId = ref<string>('')

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
  const storedConstitution = uni.getStorageSync(CONSTITUTION_KEY)
  if (storedConstitution) {
    try {
      constitution.value = JSON.parse(storedConstitution) as ConstitutionResult
    } catch {
      constitution.value = null
    }
  }
  guestId.value = uni.getStorageSync(GUEST_ID_KEY) || ''

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

  /**
   * 游客登录流程：用 guestId 调后端 → 存 token/profile/guestId。
   * guestId 没有 storage 记录就新生成并持久化，下次复用同一行 user。
   */
  async function loginAsGuest(nickname?: string): Promise<UserRead> {
    if (!guestId.value) {
      guestId.value = generateGuestId()
      uni.setStorageSync(GUEST_ID_KEY, guestId.value)
    }
    const data = await guestLogin(guestId.value, nickname)
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

  /**
   * 提交体质问卷（POST /profile/constitution），存 store + storage。
   * 返回判定结果。
   */
  async function saveConstitution(answers: Record<number, number>): Promise<ConstitutionResult> {
    const result = await submitConstitution(answers)
    constitution.value = result
    uni.setStorageSync(CONSTITUTION_KEY, JSON.stringify(result))
    // 同步把档案里的 constitutionType / constitutionScores 字段也刷新一次
    // 避免下次 GET /profile 时显示旧字段
    if (userProfile.value) {
      userProfile.value = {
        ...userProfile.value,
        constitutionType: result.constitutionTypeStr,
        constitutionScores: result.scoresNormalized,
      }
      uni.setStorageSync(USER_PROFILE_KEY, JSON.stringify(userProfile.value))
    }
    return result
  }

  /** 拉取上次体质判定结果（GET /profile/constitution）。无记录抛错，调用方自行处理。 */
  async function fetchConstitution(): Promise<ConstitutionResult | null> {
    try {
      const result = await getResult()
      constitution.value = result
      uni.setStorageSync(CONSTITUTION_KEY, JSON.stringify(result))
      return result
    } catch (e) {
      // 404 / 网络错误都清空缓存，避免显示旧结果
      constitution.value = null
      uni.removeStorageSync(CONSTITUTION_KEY)
      throw e
    }
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
    constitution.value = null
    guestId.value = ''
    uni.removeStorageSync(TOKEN_KEY)
    uni.removeStorageSync(PROFILE_KEY)
    uni.removeStorageSync(USER_PROFILE_KEY)
    uni.removeStorageSync(CONSTITUTION_KEY)
    uni.removeStorageSync(GUEST_ID_KEY)
  }

  const isLoggedIn = computed(() => !!token.value)
  const hasProfile = computed(() => userProfile.value !== null)
  const hasConstitution = computed(() => constitution.value !== null)
  const isGuest = computed(() => !!guestId.value && guestId.value.length > 0)

  return {
    token,
    profile,
    userProfile,
    constitution,
    guestId,
    getWxCode,
    login,
    loginAsGuest,
    fetchUserProfile,
    saveUserProfile,
    saveConstitution,
    fetchConstitution,
    setToken,
    setProfile,
    clear,
    isLoggedIn,
    hasProfile,
    hasConstitution,
    isGuest,
  }
})
