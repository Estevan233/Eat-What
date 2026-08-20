/**
 * 统一业务请求内核。
 *
 * H5 使用 HttpTransport，微信小程序使用 CloudTransport。页面和 Store 不感知平台，
 * 只依赖本文件导出的 request()。
 */
import { clearAuthStorage, getStoredToken } from '@/auth/storage'
import { getCloudConfig } from '@/config/env'
import { getCloudContainerApi } from '@/platform/cloudbase'
import { ApiError } from '@/types/api'
import { camelToSnake, snakeToCamel } from '@/utils/case'
import { CloudTransport } from './cloud-transport'
import { HttpTransport } from './http-transport'
import { normalizeTransportResponse } from './response'
import type {
  Transport,
  TransportMethod,
} from './transport'

export interface RequestOptions<TData = Record<string, unknown>> {
  url: string
  method?: TransportMethod
  data?: TData
  header?: Record<string, string>
  loading?: boolean
  timeout?: number
  silentErrorStatuses?: number[]
}

const DEFAULT_TIMEOUT = 10_000
let loadingReferences = 0
let authRedirectPending = false

function cloudTransportAvailable(): boolean {
  return getCloudContainerApi() !== null
}

function createPlatformTransport(): Transport {
  if (cloudTransportAvailable()) {
    return new CloudTransport(getCloudConfig())
  }
  return new HttpTransport()
}

function startLoading(enabled: boolean): void {
  if (!enabled) return
  loadingReferences += 1
  if (loadingReferences === 1) {
    uni.showLoading({ title: '加载中', mask: true })
  }
}

function stopLoading(enabled: boolean): void {
  if (!enabled) return
  loadingReferences = Math.max(0, loadingReferences - 1)
  if (loadingReferences === 0) {
    uni.hideLoading()
  }
}

function redirectToLoginOnce(): void {
  if (authRedirectPending) return
  authRedirectPending = true
  clearAuthStorage({ includeGuestId: false })
  uni.showToast({ title: '请先登录', icon: 'none' })
  uni.navigateTo({ url: '/pages/auth/auth' })
  setTimeout(() => {
    authRedirectPending = false
  }, 0)
}

function showRequestError(error: ApiError, silentStatuses: number[] = []): void {
  if (error.statusCode === 401) return
  if ((error.statusCode ?? 0) >= 500) return
  if (error.statusCode !== undefined && silentStatuses.includes(error.statusCode)) return
  uni.showToast({ title: error.message, icon: 'none' })
}

export async function request<T, TData = Record<string, unknown>>(
  options: RequestOptions<TData>,
): Promise<T> {
  const loadingEnabled = options.loading !== false
  startLoading(loadingEnabled)

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.header || {}),
  }
  const token = getStoredToken()
  if (token) headers.Authorization = 'Bearer ' + token

  try {
    const response = await createPlatformTransport().execute({
      path: options.url,
      method: options.method || 'GET',
      data: options.data ? camelToSnake(options.data) : undefined,
      headers,
      timeout: options.timeout || DEFAULT_TIMEOUT,
    })
    const normalized = normalizeTransportResponse<unknown>(response)
    return snakeToCamel<T>(normalized.data)
  } catch (error) {
    const apiError =
      error instanceof ApiError
        ? error
        : new ApiError(
          error instanceof Error ? error.message : '网络异常',
          'NETWORK_ERROR',
        )
    if (apiError.statusCode === 401) {
      redirectToLoginOnce()
      throw new ApiError(
        '未登录',
        'AUTH_ERROR',
        401,
        apiError.requestId,
      )
    }
    showRequestError(apiError, options.silentErrorStatuses)
    throw apiError
  } finally {
    stopLoading(loadingEnabled)
  }
}
