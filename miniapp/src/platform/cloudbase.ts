import type { TransportMethod } from '@/api/transport'

export type CloudContainerResponse = {
  statusCode: number
  data: unknown
  header?: Record<string, string>
  errMsg: string
}

export type CloudContainerError = {
  errMsg: string
}

export type CloudContainerOptions = {
  config: { env: string }
  path: string
  method: TransportMethod
  data?: unknown
  header?: Record<string, string>
  timeout?: number
  success?: (response: CloudContainerResponse) => void
  fail?: (error: CloudContainerError) => void
}

export type CloudContainerApi = {
  callContainer(options: CloudContainerOptions): unknown
}

/** 微信类型包暂未完整声明 callContainer，在这里集中完成一次运行时收窄。 */
export function getCloudContainerApi(): CloudContainerApi | null {
  if (typeof wx === 'undefined' || typeof wx.cloud === 'undefined') return null

  const cloud = wx.cloud as unknown as Partial<CloudContainerApi>
  return typeof cloud.callContainer === 'function'
    ? (cloud as CloudContainerApi)
    : null
}
