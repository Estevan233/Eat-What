/**
 * 体质相关常量 - 与后端 backend/app/services/constitution.py 的 CONSTITUTION_NAMES / OPTIONS 手抄同步。
 *
 * 学习点：
 * - 前后端共享 9 种体质标识符（字符串字面量），双方各写一份常量是过渡方案，
 *   待 npm run gen:api 自动化后这部分会从 OpenAPI 生成。
 * - 中文名映射用来在 UI 展示 "pinghe" → "平和质"。
 */
import type { ConstitutionType } from '@/types/api'

/** 9 种体质标识符的有序 tuple（与后端 ALL_TYPES 同步）。 */
export const CONSTITUTION_TYPES: readonly ConstitutionType[] = [
  'pinghe', 'qixu', 'yangxu', 'yinxu', 'tanshi',
  'shire', 'xueyu', 'qiyu', 'tebing',
] as const

/** 9 种体质中文名映射。 */
export const CONSTITUTION_NAMES: Record<ConstitutionType, string> = {
  pinghe: '平和质',
  qixu: '气虚质',
  yangxu: '阳虚质',
  yinxu: '阴虚质',
  tanshi: '痰湿质',
  shire: '湿热质',
  xueyu: '血瘀质',
  qiyu: '气郁质',
  tebing: '特禀质',
}

/** 5 级 Likert 选项（与后端 OPTIONS 同步）。 */
export const CONSTITUTION_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 1, label: '没有' },
  { value: 2, label: '很少' },
  { value: 3, label: '有时' },
  { value: 4, label: '经常' },
  { value: 5, label: '总是' },
] as const
