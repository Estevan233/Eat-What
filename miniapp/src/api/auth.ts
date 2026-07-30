/**
 * 认证 API - 微信登录 + 游客登录。
 *
 * 学习点：
 * - request<T> 把后端统一响应 {ok, code, data} 自动解包，返回 data
 * - 类型 LoginResponse 让调用方拿到完整 TS 类型推断
 * - guestLogin 不调 wx.login，直接发 guestId 给后端复用 / 创建游客用户
 */
import { request } from './request'
import type { LoginResponse } from '@/types/api'

export const wxLogin = (code: string, nickname?: string, avatarUrl?: string) =>
  request<LoginResponse>({
    url: '/v1/auth/wx-login',
    method: 'POST',
    data: { code, nickname, avatarUrl },
  })

/**
 * 游客登录 - 用 guestId 复用 / 创建一个游客用户。
 * guestId 由前端生成（UUID）并落 storage，下次登录传回同一 guestId → 复用同一 user。
 */
export const guestLogin = (guestId: string, nickname?: string) =>
  request<LoginResponse>({
    url: '/v1/auth/guest-login',
    method: 'POST',
    data: { guestId, nickname },
  })
