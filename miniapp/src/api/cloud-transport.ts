import type { CloudConfig } from '@/config/env'
import { getCloudContainerApi } from '@/platform/cloudbase'
import { ApiError } from '@/types/api'
import type {
  Transport,
  TransportRequest,
  TransportResponse,
} from './transport'

export class CloudTransport implements Transport {
  constructor(private readonly config: CloudConfig) {}

  execute(request: TransportRequest): Promise<TransportResponse> {
    const cloud = getCloudContainerApi()
    if (!cloud) {
      return Promise.reject(
        new ApiError('当前环境不支持 CloudBase 云托管', 'SERVICE_CONFIG_ERROR'),
      )
    }

    return new Promise((resolve, reject) => {
      cloud.callContainer({
        config: { env: this.config.environmentId },
        path: request.path,
        method: request.method,
        data: request.data,
        header: {
          ...request.headers,
          'X-WX-SERVICE': this.config.serviceName,
        },
        timeout: request.timeout,
        success: (response) => {
          const headers = response.header
          resolve({
            statusCode: response.statusCode,
            body: response.data,
            requestId:
              headers?.['X-WX-REQUEST-ID'] ||
              headers?.['x-wx-request-id'],
          })
        },
        fail: (error) => {
          const message = error.errMsg || 'CloudBase 网络异常'
          if (/access[_ ]?token\s+missing/i.test(message)) {
            reject(
              new ApiError(
                '云开发登录态缺失，请重新进入小程序',
                'CLOUDBASE_AUTH_ERROR',
              ),
            )
            return
          }
          if (/service|env|environment/i.test(message)) {
            reject(
              new ApiError(
                '服务配置错误，请联系开发者',
                'SERVICE_CONFIG_ERROR',
              ),
            )
            return
          }
          reject(new ApiError(message, 'NETWORK_ERROR'))
        },
      })
    })
  }
}
