/**
 * 认证 API - 微信登录相关。
 *
 * 学习点：
 * - request<T> 把后端统一响应 {ok, code, data} 自动解包，返回 data
 * - 类型 LoginResponse 让调用方拿到完整 TS 类型推断
 */
import { request } from './request'
import type { LoginResponse } from '@/types/api'

export const wxLogin = (code: string, nickname?: string, avatarUrl?: string) =>
  request<LoginResponse>({
    url: '/v1/auth/wx-login',
    method: 'POST',
    data: { code, nickname, avatarUrl },
  })
