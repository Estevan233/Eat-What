/**
 * 统一请求封装。
 * - 自动加 Authorization: Bearer <token>
 * - 401 清 token 并跳登录引导
 * - 统一 toast 错误（5xx 不 toast，标 loading）
 * - 超时 10 秒
 *
 * 注意：不在顶层 import useUserStore，避免 stores/user ↔ api/request 循环依赖。
 *      改成调用时动态 import，webpack/uni 都能正确做 code splitting。
 */
import { ApiError, type ApiResult } from '@/types/api'

export interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'OPTIONS' | 'HEAD' | 'TRACE' | 'CONNECT'
  data?: Record<string, unknown>
  header?: Record<string, string>
  loading?: boolean
  timeout?: number
}

const DEFAULT_TIMEOUT = 10_000
const BASE_URL = 'http://localhost:8000'

export async function request<T>(opts: RequestOptions): Promise<T> {
  // 动态 import 避免 stores/user ↔ api/request 循环依赖
  // （user.ts 顶层 import wxLogin → auth.ts → request.ts → user.ts 会循环）
  const { useUserStore } = await import('@/stores/user')
  const userStore = useUserStore()
  const token = userStore.token

  const header: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.header || {}),
  }
  if (token) {
    header.Authorization = `Bearer ${token}`
  }

  if (opts.loading !== false) {
    uni.showLoading({ title: '加载中', mask: true })
  }

  return new Promise<T>((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}${opts.url}`,
      method: opts.method || 'GET',
      data: opts.data,
      header,
      timeout: opts.timeout || DEFAULT_TIMEOUT,
      success: (res) => {
        const status = res.statusCode || 0
        const body = res.data as ApiResult<T>

        if (status === 401) {
          userStore.clear()
          uni.showToast({ title: '请先登录', icon: 'none' })
          uni.navigateTo({ url: '/pages/auth/auth' })
          reject(new ApiError('未登录', 'AUTH_ERROR', 401))
          return
        }

        if (status >= 500) {
          // 5xx 不 toast，留给调用方决定（可重试）
          reject(new ApiError('服务器错误', 'INTERNAL', status))
          return
        }

        if (status >= 400 || !body.ok) {
          const message = body.message || '请求失败'
          uni.showToast({ title: message, icon: 'none' })
          reject(new ApiError(message, body.code, status))
          return
        }

        resolve(body.data)
      },
      fail: (err) => {
        const message = err.errMsg || '网络异常'
        uni.showToast({ title: message, icon: 'none' })
        reject(new ApiError(message, 'NETWORK_ERROR'))
      },
      complete: () => {
        if (opts.loading !== false) {
          uni.hideLoading()
        }
      },
    })
  })
}
