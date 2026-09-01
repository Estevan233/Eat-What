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

/**
 * 默认超时。
 *
 * 个人版套餐下云托管实例会缩容到 0，且关系型数据库默认开启自动暂停。首次请求需要
 * 同时等待容器冷启动和数据库唤醒，实测可超过 10 秒。这里放宽到 20 秒，
 * 配合下面的冷启动重试，避免把正常的唤醒过程当成失败抛给用户。
 */
const DEFAULT_TIMEOUT = 20_000
/** 冷启动重试：只重试一次，重试前短暂等待，避免连续请求放大唤醒压力。 */
const COLD_START_MAX_RETRIES = 1
const COLD_START_RETRY_DELAY_MS = 500

let loadingReferences = 0
let authRedirectPending = false

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

/**
 * 判断是否值得重试：仅当请求没有拿到 HTTP 状态码（说明服务未响应，可能是冷启动/网络抖动）时重试。
 * 已经拿到状态码的错误是业务结果，重试只会制造重复写入。
 */
function isColdStartRetryable(error: ApiError): boolean {
  if (error.statusCode !== undefined) return false
  if (error.code === 'CLOUDBASE_AUTH_ERROR') return false
  if (error.code === 'SERVICE_CONFIG_ERROR') return false
  return error.code === 'NETWORK_ERROR'
}

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

/**
 * 执行一次请求，并在遇到"服务未响应"类错误时重试一次。
 *
 * 这是针对个人版套餐冷启动的兜底：容器缩容到 0 且数据库自动暂停时，首次真实请求会超时，
 * 第二次请求通常命中已唤醒的实例。业务错误（已拿到 HTTP 状态码）不重试。
 */
async function executeWithColdStartRetry<T, TData>(
  options: RequestOptions<TData>,
  headers: Record<string, string>,
): Promise<T> {
  const transport = createPlatformTransport()
  let lastError: ApiError | null = null

  for (let attempt = 0; attempt <= COLD_START_MAX_RETRIES; attempt += 1) {
    try {
      const response = await transport.execute({
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
      lastError = apiError

      if (apiError.statusCode === 401) {
        redirectToLoginOnce()
        throw new ApiError('未登录', 'AUTH_ERROR', 401, apiError.requestId)
      }

      if (attempt < COLD_START_MAX_RETRIES && isColdStartRetryable(apiError)) {
        await sleep(COLD_START_RETRY_DELAY_MS)
        continue
      }

      showRequestError(apiError, options.silentErrorStatuses)
      throw apiError
    }
  }

  throw lastError ?? new ApiError('网络异常', 'NETWORK_ERROR')
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
    return await executeWithColdStartRetry<T, TData>(options, headers)
  } finally {
    stopLoading(loadingEnabled)
  }
}
