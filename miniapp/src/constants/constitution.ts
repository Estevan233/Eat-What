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

/** 体质特征 + 饮食建议（结果页展示用）。 */
export const CONSTITUTION_ADVICE: Record<ConstitutionType, {
  traits: string[]
  diet: string[]
  avoid: string[]
}> = {
  pinghe: {
    traits: ['精力充沛', '睡眠良好', '性格开朗'],
    diet: ['饮食均衡', '五谷杂粮搭配', '适量运动'],
    avoid: ['暴饮暴食', '过度辛辣'],
  },
  qixu: {
    traits: ['容易疲乏', '气短懒言', '声音低弱'],
    diet: ['补气食物：黄芪、党参、山药', '温补汤品', '小米粥养脾胃'],
    avoid: ['生冷瓜果', '油腻厚味', '过度劳累'],
  },
  yangxu: {
    traits: ['手脚发凉', '畏寒怕冷', '喜热饮食'],
    diet: ['温阳食物：羊肉、韭菜、生姜', '桂圆红枣茶', '当归炖鸡'],
    avoid: ['生冷寒凉', '冰饮冷食', '绿豆苦瓜过量'],
  },
  yinxu: {
    traits: ['手脚心发热', '口干咽燥', '易失眠'],
    diet: ['滋阴食物：银耳、百合、枸杞', '雪梨百合汤', '鸭肉滋阴'],
    avoid: ['辛辣燥热', '煎炸烧烤', '熬夜'],
  },
  tanshi: {
    traits: ['体型偏胖', '腹部松软', '容易困倦'],
    diet: ['健脾化湿：薏米、红豆、冬瓜', '清淡蒸煮为主', '多食蔬果'],
    avoid: ['甜腻油炸', '暴饮暴食', '久坐不动'],
  },
  shire: {
    traits: ['面部易出油', '口苦口臭', '大便黏滞'],
    diet: ['清热利湿：绿豆、苦瓜、黄瓜', '薏米冬瓜汤', '绿茶清热'],
    avoid: ['辛辣油腻', '烟酒', '甜食'],
  },
  xueyu: {
    traits: ['皮肤易瘀青', '面色晦暗', '易生黑斑'],
    diet: ['活血化瘀：山楂、醋、红糖', '玫瑰花茶疏肝', '黑木耳活血'],
    avoid: ['寒凉收涩', '肥甘厚味', '久坐久卧'],
  },
  qiyu: {
    traits: ['闷闷不乐', '多愁善感', '胁肋胀痛'],
    diet: ['疏肝理气：玫瑰花、陈皮、佛手', '合欢花茶安神', '香橼疏肝'],
    avoid: ['咖啡浓茶', '辛辣刺激', '情绪压抑'],
  },
  tebing: {
    traits: ['容易过敏', '鼻塞喷嚏', '皮肤瘙痒'],
    diet: ['益气固表：黄芪、防风、白术', '红枣枸杞茶', '山药健脾'],
    avoid: ['海鲜发物', '花粉环境', '辛辣刺激'],
  },
}
