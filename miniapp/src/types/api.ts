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
 * 9 种中医体质标识符 - 与后端 backend/app/schemas/constitution.py 的 ConstitutionType 同步。
 */
export type ConstitutionType =
  | 'pinghe' | 'qixu' | 'yangxu' | 'yinxu' | 'tanshi'
  | 'shire' | 'xueyu' | 'qiyu' | 'tebing'

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
  /** T06 新增：体质判定结果字符串，如 "qixu;shire"（主+兼夹分号串）。 */
  constitutionType?: string | null
  /** T06 新增：完整转化分，如 { pinghe: 0, qixu: 100, ... }。 */
  constitutionScores?: Record<ConstitutionType, number> | null
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

/**
 * 体质判定结果（POST/GET /profile/constitution 的 data）。
 * 字段名经 request.ts 的 snakeToCamel 转换。
 */
export interface ConstitutionResult {
  primary: ConstitutionType
  secondary: ConstitutionType[]
  scoresNormalized: Record<ConstitutionType, number>
  constitutionTypeStr: string
}

/** GET /profile/constitution/questions 的 data。 */
export interface ConstitutionQuestionsPayload {
  questions: ConstitutionQuestion[]
  options: ConstitutionOption[]
}

export interface ConstitutionQuestion {
  id: number
  text: string
  /** 后端 QUESTIONS 里 type 字段是字符串（含 "pinghe_reverse"），前端只用来展示。 */
  type: string
}

export interface ConstitutionOption {
  value: number
  label: string
}

/**
 * 12 西方星座英文键，与后端 backend/app/services/solar_terms.py 的
 * compute_zodiac 返回值同步。
 */
export type ZodiacSign =
  | 'aries' | 'taurus' | 'gemini' | 'cancer' | 'leo' | 'virgo'
  | 'libra' | 'scorpio' | 'sagittarius' | 'capricorn' | 'aquarius' | 'pisces'

/**
 * 今日历法上下文 - GET /context/today 返回的 data。
 * 字段经 request.ts 的 snakeToCamel 转换。
 */
export interface TodayContext {
  date: string
  /** 当前节气中文名，非节气日为空字符串 */
  solarTermCurrent: string
  solarTermNextName: string
  solarTermNextDate: string
  zodiacSign: ZodiacSign
  /** 生肖中文名：马 / 羊 / 猴 ... */
  animal: string
  lunarMonth: number
  lunarDay: number
  isLeapMonth: boolean
}

/**
 * 天气离散标签 - 给推荐算法 6+1 种，与后端 backend/app/schemas/weather.py WeatherTag 同步。
 */
export type WeatherTag = 'cold' | 'hot' | 'rainy' | 'snowy' | 'dry' | 'mild' | 'any'

/**
 * 当前实况天气 - POST /context/weather 返回的 data。
 * 字段经 request.ts 的 snakeToCamel 转换。
 */
export interface WeatherData {
  locationName: string
  tempC: number
  feelsLikeC: number
  /** 晴/多云/小雨/雪/阵雨/雷暴 - 后端映射的 WMO code 中文 */
  text: string
  windDir: string
  windScale: string
  humidity: number
  precipitationMm: number
  weatherTag: WeatherTag
  fetchedAt: string
}

/** POST /context/weather 请求体。 */
export interface WeatherRequest {
  lat: number
  lng: number
}

/**
 * 单条带理由的推荐结果 - POST /daily/recommend 响应中的 food 项。
 * 字段经 request.ts 的 snakeToCamel 转换。
 */
export interface FoodWithReason {
  id: number
  name: string
  category: string
  ingredients: string[]
  caloriesKcalPer100g?: number
  nutrition: Record<string, number>
  nature: string
  flavor: string[]
  organMeridians: string[]
  suitableConstitutions: string[]
  suitableWeathers: string[]
  forbiddenFor: string[]
  tags: string[]
  cookingMethod: string
  cookingTimeMin?: number
  imageUrl?: string
  seasonalSolarTerms: string[]
  description?: string
  /** T10: 自然语言推荐理由 */
  reason: string
  /** T10: 0-100 打分（含小数） */
  score: number
}

/**
 * 推荐结果附带的上下文 - POST /daily/recommend 响应中的 context。
 * 字段经 request.ts 的 snakeToCamel 转换。
 */
export interface RecommendContext {
  weather: WeatherData
  today: TodayContext
}

/**
 * POST /daily/recommend 请求体（前端 camelCase）。
 * request.ts 会在发送前自动转 snake_case。
 */
export interface RecommendRequest {
  mood: Mood
  activityLevel: ActivityLevel
  lat?: number
  lng?: number
}

/** POST /daily/recommend 成功响应的 data。 */
export interface RecommendResponse {
  foods: FoodWithReason[]
  context: RecommendContext
}
