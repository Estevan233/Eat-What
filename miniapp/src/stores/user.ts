/**
 * 用户 Store - 全局登录态 + 档案 + 体质。
 * token / profile / userProfile / constitution 落 storage，刷新页面不丢。
 *
 * login() 流程：
 *   wx.cloud.callContainer() → 云托管注入可信身份头 → 拿 {token, user} → 存 store + storage
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
 * - 正式微信登录不在客户端保存 AppSecret，也不调用 code2session
 * - 注意区分 profile（公开昵称/头像）与 userProfile（生日/性别/身高/...）
 */
import { defineStore } from 'pinia'
import { computed, onScopeDispose, ref } from 'vue'
import { cloudLogin, guestLogin } from '@/api/auth'
import { getProfile, updateAccountProfile, upsertProfile } from '@/api/profile'
import { getResult, submit as submitConstitution } from '@/api/constitution'
import { normalizeUserRead } from '@/auth/profile-onboarding'
import { getCloudContainerApi } from '@/platform/cloudbase'
import { ApiError } from '@/types/api'
import {
  AUTH_STORAGE_KEYS,
  clearAuthStorage,
  getStoredToken,
  readStoredJson,
  readStoredString,
  removeStoredValue,
  saveLoginSession,
  promoteToWechatSession,
  subscribeAuthClear,
  writeStoredJson,
  writeStoredString,
} from '@/auth/storage'
import type {
  AccountProfilePatch,
  ConstitutionResult,
  ProfileRead,
  ProfileUpsert,
  UserRead,
} from '@/types/api'

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
  // profile = 登录响应里的 UserRead（id + nickname + avatarUrl）
  const profile = ref<UserRead | null>(null)
  // userProfile = 档案详情（生日/性别/身高/体重/忌口）
  const userProfile = ref<ProfileRead | null>(null)
  // T06 新增：体质判定结果（POST 后缓存，避免每次进页都拉）
  const constitution = ref<ConstitutionResult | null>(null)
  // 游客身份持久化标识
  const guestId = ref<string>('')

  const unsubscribeAuthClear = subscribeAuthClear((includeGuestId) => {
    token.value = ''
    profile.value = null
    userProfile.value = null
    constitution.value = null
    if (includeGuestId) guestId.value = ''
  })
  onScopeDispose(unsubscribeAuthClear)

  // 启动时从 storage 恢复
  token.value = getStoredToken()
  guestId.value = readStoredString(AUTH_STORAGE_KEYS.guestId)
  const storedProfile = readStoredJson<UserRead>(AUTH_STORAGE_KEYS.profile)
  profile.value = storedProfile
    ? normalizeUserRead(storedProfile, guestId.value ? 'guest' : 'wechat')
    : null
  userProfile.value = readStoredJson<ProfileRead>(AUTH_STORAGE_KEYS.userProfile)
  constitution.value = readStoredJson<ConstitutionResult>(AUTH_STORAGE_KEYS.constitution)

  /**
   * 微信小程序登录走 CloudBase 私有链路，由云托管注入可信身份头。
   * H5 不具备 callContainer，界面应引导用户使用游客登录。
   */
  async function login(): Promise<UserRead> {
    if (!getCloudContainerApi()) {
      throw new Error('微信一键登录仅支持微信小程序，请使用游客登录')
    }

    const data = await cloudLogin()
    const user = normalizeUserRead(data.user)
    token.value = data.token
    profile.value = user
    guestId.value = ''
    userProfile.value = null
    constitution.value = null
    promoteToWechatSession(data.token, user)
    return user
  }

  /**
   * 游客登录流程：用 guestId 调后端 → 存 token/profile/guestId。
   * guestId 没有 storage 记录就新生成并持久化，下次复用同一行 user。
   */
  async function loginAsGuest(nickname?: string): Promise<UserRead> {
    if (!guestId.value) {
      guestId.value = generateGuestId()
      writeStoredString(AUTH_STORAGE_KEYS.guestId, guestId.value)
    }
    const data = await guestLogin(guestId.value, nickname)
    token.value = data.token
    const user = normalizeUserRead(data.user)
    profile.value = user
    saveLoginSession(data.token, user)
    return user
  }

  async function saveAccountProfile(payload: AccountProfilePatch): Promise<UserRead> {
    const updated = normalizeUserRead(await updateAccountProfile(payload))
    profile.value = updated
    writeStoredJson(AUTH_STORAGE_KEYS.profile, updated)
    return updated
  }

  /** 拉取档案详情（GET /profile），存 store + storage */
  async function fetchUserProfile(): Promise<ProfileRead | null> {
    const data = await getProfile()
    userProfile.value = data.profile
    writeStoredJson(AUTH_STORAGE_KEYS.userProfile, data.profile)
    return data.profile
  }

  /** 保存档案（PUT /profile），存 store + storage，返回更新后档案 */
  async function saveUserProfile(payload: ProfileUpsert): Promise<ProfileRead> {
    const data = await upsertProfile(payload)
    userProfile.value = data
    writeStoredJson(AUTH_STORAGE_KEYS.userProfile, data)
    return data
  }

  /**
   * 提交体质问卷（POST /profile/constitution），存 store + storage。
   * 返回判定结果。
   */
  async function saveConstitution(answers: Record<number, number>): Promise<ConstitutionResult> {
    const result = await submitConstitution(answers)
    constitution.value = result
    writeStoredJson(AUTH_STORAGE_KEYS.constitution, result)
    // 同步把档案里的 constitutionType / constitutionScores 字段也刷新一次
    // 避免下次 GET /profile 时显示旧字段
    if (userProfile.value) {
      userProfile.value = {
        ...userProfile.value,
        constitutionType: result.constitutionTypeStr,
        constitutionScores: result.scoresNormalized,
      }
      writeStoredJson(AUTH_STORAGE_KEYS.userProfile, userProfile.value)
    }
    return result
  }

  /** 拉取上次体质判定结果。404 是正常首次空状态，真实故障保留旧缓存。 */
  async function fetchConstitution(): Promise<ConstitutionResult | null> {
    try {
      const result = await getResult()
      constitution.value = result
      writeStoredJson(AUTH_STORAGE_KEYS.constitution, result)
      return result
    } catch (e) {
      if (e instanceof ApiError && e.statusCode === 404) {
        constitution.value = null
        removeStoredValue(AUTH_STORAGE_KEYS.constitution)
        return null
      }
      throw e
    }
  }

  function setToken(t: string) {
    token.value = t
    writeStoredString(AUTH_STORAGE_KEYS.token, t)
  }

  function setProfile(p: UserRead) {
    profile.value = p
    writeStoredJson(AUTH_STORAGE_KEYS.profile, p)
  }

  function clear() {
    clearAuthStorage({ includeGuestId: true })
  }

  const isLoggedIn = computed(() => !!token.value)
  const hasProfile = computed(() => userProfile.value !== null)
  const hasConstitution = computed(() => constitution.value !== null)
  const isGuest = computed(() => profile.value?.accountKind === 'guest')

  return {
    token,
    profile,
    userProfile,
    constitution,
    guestId,
    login,
    loginAsGuest,
    saveAccountProfile,
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
