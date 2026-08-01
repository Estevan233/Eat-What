/**
 * 体质测试 API 封装。
 *
 * 学习点：
 * - request 层会自动 camelToSnake 入参、snakeToCamel 出参
 * - answers 的 key 是数字 1-9，camelToSnake 不动数字 key（只转 string key），所以安全
 * - getResult 在后端没记录时返回 404，request 层会 toast + reject，调用方需 try/catch
 */
import { request } from './request'
import type {
  ConstitutionQuestionsPayload,
  ConstitutionResult,
} from '@/types/api'

/** GET /profile/constitution/questions - 拉取题面 + 5 级 Likert 选项。公开端点。 */
export const getQuestions = () =>
  request<ConstitutionQuestionsPayload>({
    url: '/api/v1/profile/constitution/questions',
  })

/** POST /profile/constitution - 提交问卷、判定、存档、返回结果。 */
export const submit = (answers: Record<number, number>) =>
  request<ConstitutionResult>({
    url: '/api/v1/profile/constitution',
    method: 'POST',
    data: { answers }, // 数字 key 不被 camelToSnake 改动
  })

/** GET /profile/constitution - 读上次判定结果。无记录时 404。 */
export const getResult = () =>
  request<ConstitutionResult>({
    url: '/api/v1/profile/constitution',
  })
