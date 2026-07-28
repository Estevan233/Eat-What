/**
 * API 类型骨架。
 * T04 完成后用 `npm run gen:api` 从后端 OpenAPI 重新生成覆盖这里。
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

export interface UserProfile {
  id: number
  nickname: string
  avatarUrl?: string
  birthday?: string
  gender?: Gender
  heightCm?: number
  weightKg?: number
  constitutionType?: string
  forbiddenTags: string[]
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
