/**
 * API 类型骨架。
 * T04 完成后用 `npm run gen:api` 从后端 OpenAPI 重新生成覆盖这里。
 *
 * 字段命名约定：
 * - 前端 TS 类型用 camelCase（与 JS 社区惯例 + 微信小程序原生 API 一致）
 * - 后端 API 用 snake_case
 * - request.ts 拦截层做双向转换：发送前 camelToSnake，接收后 snakeToCamel
 * - 例外：UserRead（id/nickname/avatar_url）是 T04 直接对后端字段的映射，保留 snake_case 避免回归
 */

export interface ApiResult<T> {
  ok: boolean
  code?: string
  message?: string
  data: T
}

export class ApiError extends Error {
  code?: string
  statusCode?: number

  constructor(message: string, code?: string, statusCode?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.statusCode = statusCode
  }
}

export type Gender = 'male' | 'female' | 'other'

export type Mood = 'happy' | 'neutral' | 'tired' | 'stressed' | 'anxious'

export type ActivityLevel = 'light' | 'normal' | 'high'

/**
 * 用户档案详情（前端 camelCase 版本）。
 * 与后端 ProfileRead 对应，字段名经 request.ts 的 snakeToCamel 转换。
 */
export interface ProfileRead {
  userId: number
  birthday: string
  gender: Gender
  heightCm?: number
  weightKg?: number
  forbiddenTags: string[]
  zodiacSign?: string | null
  updatedAt: string
}

/**
 * PUT /profile 请求体（前端 camelCase）。
 * request.ts 会在发送前自动转 snake_case。
 */
export interface ProfileUpsert {
  birthday: string
  gender: Gender
  heightCm?: number
  weightKg?: number
  forbiddenTags: string[]
}

/**
 * GET /profile 返回的完整对象 = User + profile 组合。
 */
export interface UserWithProfile {
  id: number
  nickname: string
  avatarUrl?: string
  profile: ProfileRead | null
}

/** 后端返回的 user 字段（不含 openid/unionid）。 */
export interface UserRead {
  id: number
  nickname: string
  avatar_url?: string
}

/** POST /auth/wx-login 成功响应的 data。 */
export interface LoginResponse {
  token: string
  user: UserRead
}
