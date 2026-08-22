/**
 * 体质相关常量 - 与后端 backend/app/services/constitution.py 的 CONSTITUTION_NAMES / OPTIONS 手抄同步。
 *
 * 学习点：
 * - 前后端共享 9 种体质标识符（字符串字面量），双方各写一份常量是过渡方案，
 *   待 npm run gen:api 自动化后这部分会从 OpenAPI 生成。
 * - 中文名映射用来在 UI 展示 "pinghe" → "平和质"。
 */
import type { ConstitutionQuestion, ConstitutionType } from '@/types/api'

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

/** 本地题库兜底，避免静态题面接口短暂失败时整页空白。 */
export const CONSTITUTION_QUESTIONS: ReadonlyArray<ConstitutionQuestion> = [
  { id: 1, text: '您精力充沛吗？', type: 'pinghe_reverse' },
  { id: 2, text: '您容易疲乏吗？', type: 'qixu' },
  { id: 3, text: '您手脚发凉吗？', type: 'yangxu' },
  { id: 4, text: '您手脚心发热吗？', type: 'yinxu' },
  { id: 5, text: '您体型偏胖、腹部松软吗？', type: 'tanshi' },
  { id: 6, text: '您面部或额头易出油、生痘吗？', type: 'shire' },
  { id: 7, text: '您皮肤易瘀青、有黑斑吗？', type: 'xueyu' },
  { id: 8, text: '您容易闷闷不乐、多愁善感吗？', type: 'qiyu' },
  { id: 9, text: '您过敏（鼻塞/皮疹）吗？', type: 'tebing' },
] as const

/** 5 级 Likert 选项（与后端 OPTIONS 同步）。 */
export const CONSTITUTION_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 1, label: '没有' },
  { value: 2, label: '很少' },
  { value: 3, label: '有时' },
  { value: 4, label: '经常' },
  { value: 5, label: '总是' },
] as const
