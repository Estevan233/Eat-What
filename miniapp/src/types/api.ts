/**
 * API 类型骨架。
 * T04 完成后用 `npm run gen:api` 从后端 OpenAPI 重新生成覆盖这里。
 *
 * 字段命名约定：
 * - 前端 TS 类型用 camelCase（与 JS 社区惯例 + 微信小程序原生 API 一致）
 * - 后端 API 用 snake_case
 * - request.ts 拦截层做双向转换：发送前 camelToSnake，接收后 snakeToCamel
 * - UserRead 也使用 camelCase；旧版缓存由 profile-onboarding.ts 迁移。
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
  requestId?: string

  constructor(message: string, code?: string, statusCode?: number, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.statusCode = statusCode
    this.requestId = requestId
  }
}

export type Gender = 'male' | 'female' | 'other'

export type Mood = 'happy' | 'neutral' | 'tired' | 'stressed' | 'anxious'

export type ActivityLevel = 'light' | 'normal' | 'high'

export type DiningMode = 'cook' | 'eat_out'

export type Audience = 'personal' | 'family'

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
  avatarUrl?: string
  profileComplete: boolean
}

export interface AccountProfilePatch {
  nickname?: string
  avatarUrl?: string
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
  providerAvailable: boolean
  source?: 'qweather' | 'cache' | 'neutral'
  isStale?: boolean
  observedAt?: string | null
  locationName: string
  tempC: number
  feelsLikeC: number
  /** 晴/多云/小雨/雪/雷暴 - 和风天气描述 */
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
  requestId?: string
  mood: Mood
  activityLevel: ActivityLevel
  lat?: number
  lng?: number
  diningMode: DiningMode
  audience: Audience
  partySize: number
  excludeFoodIds?: number[]
  weatherSnapshot?: WeatherData
  mealIntent?: MealIntent
}

export type MealGoal = 'balanced' | 'weight_control' | 'high_protein'

export interface MealIntent {
  availableIngredients: string[]
  excludedIngredients: string[]
  maxTimeMinutes: number | null
  goal: MealGoal | null
  diningModeHint: DiningMode | null
  summary: string
}

export type MealRole = 'main' | 'vegetable' | 'staple'

export interface NutritionTotal {
  energyKcal: number
  proteinG: number
  fatG: number
  carbG: number
}

export type NutritionPerServing = NutritionTotal

export interface MealItem {
  foodId: number
  name: string
  mealRole: MealRole
  category: string
  cookingMethod: string
  visualKey: string
  prepTimeMin: number
  cookTimeMin: number
  nutritionPerServing: NutritionPerServing
  reason: string
  score: number
}

export interface MealSnapshot {
  items: MealItem[]
  totalNutrition: NutritionTotal
  estimatedTimeMin: number
  reason: string
}

export interface MealSubstitution {
  targetRole: MealRole
  replacement: MealItem
  resultingTotal: NutritionTotal
  reason: string
}

/** POST /daily/recommend 成功响应中的完整餐数据。 */
export interface MealRecommendation {
  foods: FoodWithReason[]
  recommendationId: number
  primaryMeal: MealSnapshot
  substitutions: MealSubstitution[]
  substitutionNotice?: string | null
  engine: string
  context: RecommendContext
  weightProfile: RecommendationWeightProfile
  wellnessDisclaimer: string
}

export interface RecommendationWeightProfile {
  nutrition: number
  seasonalWellness: number
  personalFamily: number
  preferenceHistory: number
  feasibility: number
  diversity: number
  weatherModifierLimit: number
}

export type RecommendResponse = MealRecommendation

export interface MealChoiceSubstitution {
  targetRole: MealRole
  replacementFoodId: number
}

export interface ChooseMealRequest {
  recommendationId: number
  selectedFoodIds: number[]
  substitutions: MealChoiceSubstitution[]
}

export interface RecipeIngredient {
  name: string
  amount?: number | null
  unit: string
  optional: boolean
}

export interface RecipeRead {
  foodId: number
  foodName: string
  mealRole: MealRole
  visualKey: string
  servings: number
  ingredients: RecipeIngredient[]
  steps: string[]
  prepTimeMin: number
  cookTimeMin: number
  nutritionPerServing: NutritionPerServing
  difficulty: string
  sourceUrl?: string | null
  nutritionBasis: string
  version: number
}

export type DiningVerdict = 'liked' | 'neutral' | 'avoided'

export interface DiningMemoryUpsert {
  shopName: string
  dishName: string
  verdict: DiningVerdict
  note?: string | null
}

export interface DiningMemoryRead extends DiningMemoryUpsert {
  id: number
  createdAt: string
  updatedAt: string
}

export interface DiningMemoryList {
  items: DiningMemoryRead[]
  page: number
  size: number
  total: number
}

export interface ExternalDiningRequest {
  mood: Mood
  activityLevel: ActivityLevel
  audience: Audience
  partySize: number
  city?: string
  lat?: number
  lng?: number
  excludeKeys?: string[]
}

export interface ExternalDiningSuggestion {
  key: string
  shopName?: string | null
  dishName: string
  category: string
  mealFormat: string
  servingStyle: 'individual' | 'shared'
  energyKcalMinPerPerson: number
  energyKcalMaxPerPerson: number
  searchKeywords: string[]
  orderTips: string[]
  reason: string
  seasonalNote: string
  nutritionNote: string
  source: 'rules' | 'memory'
}

export interface ExternalDiningResponse {
  audience: Audience
  partySize: number
  cityLabel: string
  suggestions: ExternalDiningSuggestion[]
  rotationRestarted: boolean
  disclaimer: string
}
