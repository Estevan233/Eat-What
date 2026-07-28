/**
 * 统一请求封装。
 * - 自动加 Authorization: Bearer <token>
 * - 401 清 token 并跳登录引导
 * - 统一 toast 错误（5xx 不 toast，标 loading）
 * - 超时 10 秒
 * - 字段命名：发送前 camelToSnake，接收后 snakeToCamel（前后端约定）
 *
 * 注意：不在顶层 import useUserStore，避免 stores/user ↔ api/request 循环依赖。
 *      改成调用时动态 import，webpack/uni 都能正确做 code splitting。
 */
import { ApiError, type ApiResult } from '@/types/api'
import { camelToSnake, snakeToCamel } from '@/utils/case'

export interface RequestOptions<TData = Record<string, unknown>> {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'OPTIONS' | 'HEAD' | 'TRACE' | 'CONNECT'
  data?: TData
  header?: Record<string, string>
  loading?: boolean
  timeout?: number
}

const DEFAULT_TIMEOUT = 10_000
const BASE_URL = 'http://localhost:8000'

// data 形状是任意对象（接口类型也可），request 内部用 camelToSnake 转 dict 再发
export async function request<T, TData = Record<string, unknown>>(opts: RequestOptions<TData>): Promise<T> {
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

  // 发送前 camelCase → snake_case（递归转 data 里所有 key）
  const outboundData = opts.data ? camelToSnake(opts.data) : undefined

  return new Promise<T>((resolve, reject) => {
    uni.request({
      url: `${BASE_URL}${opts.url}`,
      method: opts.method || 'GET',
      data: outboundData as Record<string, unknown> | undefined,
      header,
      timeout: opts.timeout || DEFAULT_TIMEOUT,
      success: (res) => {
        const status = res.statusCode || 0
        const rawBody = res.data as ApiResult<unknown>

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

        if (status >= 400 || !rawBody.ok) {
          const message = rawBody.message || '请求失败'
          uni.showToast({ title: message, icon: 'none' })
          reject(new ApiError(message, rawBody.code, status))
          return
        }

        // 接收后 snake_case → camelCase（递归转 data 里所有 key）
        const data = snakeToCamel<T>(rawBody.data)
        resolve(data)
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
