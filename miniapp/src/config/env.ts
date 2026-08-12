const LOCAL_API_BASE_URL = import.meta.env.DEV ? 'http://localhost:8000' : ''
const DEFAULT_CLOUDBASE_ENV_ID = 'cloud1-d8gz4jm8vb964a1c9'
const DEFAULT_CLOUDBASE_SERVICE = 'eat-what-api'

export type CloudConfig = {
  environmentId: string
  serviceName: string
}

export function resolveCloudConfig(
  environmentId?: string,
  serviceName?: string,
): CloudConfig {
  const environment = environmentId?.trim() || ''
  const service = serviceName?.trim() || ''
  if (!environment || !service) {
    throw new Error('CloudBase 环境或服务名未配置')
  }
  return {
    environmentId: environment,
    serviceName: service,
  }
}

export function resolveApiBaseUrl(value?: string): string {
  const resolved = value?.trim() || LOCAL_API_BASE_URL
  return resolved.replace(/\/+$/, '')
}

export const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
)

export const CLOUDBASE_ENV_ID =
  import.meta.env.VITE_CLOUDBASE_ENV_ID?.trim() || DEFAULT_CLOUDBASE_ENV_ID
export const CLOUDBASE_SERVICE =
  import.meta.env.VITE_CLOUDBASE_SERVICE?.trim() || DEFAULT_CLOUDBASE_SERVICE

export function getCloudConfig(): CloudConfig {
  return resolveCloudConfig(CLOUDBASE_ENV_ID, CLOUDBASE_SERVICE)
}
