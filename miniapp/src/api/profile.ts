/**
 * 用户档案 API。
 *
 * 学习点：
 * - request 层会自动 camelToSnake 入参、snakeToCamel 出参
 * - 所以这里直接传 camelCase 类型的 data，拿 camelCase 类型的返回
 */
import { request } from './request'
import type { ProfileRead, ProfileUpsert, UserWithProfile } from '@/types/api'

export const getProfile = () =>
  request<UserWithProfile>({ url: '/api/v1/profile' })

export const upsertProfile = (data: ProfileUpsert) =>
  request<ProfileRead, ProfileUpsert>({ url: '/api/v1/profile', method: 'PUT', data })
