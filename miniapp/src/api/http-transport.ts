import { API_BASE_URL } from '@/config/env'
import { ApiError } from '@/types/api'
import type {
  Transport,
  TransportRequest,
  TransportResponse,
} from './transport'

export class HttpTransport implements Transport {
  execute(request: TransportRequest): Promise<TransportResponse> {
    return new Promise((resolve, reject) => {
      uni.request({
        url: API_BASE_URL + request.path,
        method: request.method,
        data: request.data as Record<string, unknown> | undefined,
        header: request.headers,
        timeout: request.timeout,
        success: (response) => {
          const headers = response.header as Record<string, string> | undefined
          resolve({
            statusCode: response.statusCode || 0,
            body: response.data,
            requestId:
              headers?.['X-Request-ID'] ||
              headers?.['x-request-id'],
          })
        },
        fail: (error) => {
          reject(
            new ApiError(
              error.errMsg || '网络异常',
              'NETWORK_ERROR',
            ),
          )
        },
      })
    })
  }
}
