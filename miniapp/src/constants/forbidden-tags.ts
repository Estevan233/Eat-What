/**
 * 忌口标签预定义集合。
 * 与后端 backend/app/core/constants.py 的 FORBIDDEN_TAGS 保持同步。
 * T08 接 gen:api 后会从后端 OpenAPI 自动拉，这里手抄是过渡方案。
 */
export const FORBIDDEN_TAGS = [
  'pork',           // 猪肉
  'beef',           // 牛肉
  'seafood',        // 海鲜
  'spicy',          // 辣
  'raw_cold',       // 生冷
  'greasy',         // 油腻
  'gluten',         // 麸质
  'lactose',        // 乳糖
  'nut',            // 坚果
  'diabetic_sugar', // 控糖
] as const

export type ForbiddenTag = (typeof FORBIDDEN_TAGS)[number]

/** FORBIDDEN_TAGS 的可变 Set 形式，便于 O(1) 查重。 */
export const FORBIDDEN_TAGS_SET: ReadonlySet<string> = new Set(FORBIDDEN_TAGS)

/** 中文显示名映射 - 给 picker 用。 */
export const FORBIDDEN_TAGS_LABEL: Record<ForbiddenTag, string> = {
  pork: '猪肉',
  beef: '牛肉',
  seafood: '海鲜',
  spicy: '辣',
  raw_cold: '生冷',
  greasy: '油腻',
  gluten: '麸质',
  lactose: '乳糖',
  nut: '坚果',
  diabetic_sugar: '控糖',
}
