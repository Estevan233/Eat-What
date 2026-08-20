import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CloudContainerOptions } from '@/platform/cloudbase'
import { CloudTransport } from './cloud-transport'

describe('CloudTransport', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('calls the configured CloudBase service', async () => {
    const callContainer = vi.fn((options: CloudContainerOptions) => {
      options.success?.({
        statusCode: 200,
        data: { ok: true, data: { token: 'token' } },
        header: { 'X-WX-REQUEST-ID': 'request-cloud-1' },
        errMsg: 'cloud.callContainer:ok',
      })
    })
    vi.stubGlobal('wx', { cloud: { callContainer } })
    const transport = new CloudTransport({
      environmentId: 'cloud-test',
      serviceName: 'api-service',
    })

    const response = await transport.execute({
      path: '/api/v1/auth/cloud-login',
      method: 'POST',
      data: {},
      headers: { Authorization: 'Bearer token' },
      timeout: 10_000,
    })

    const call = callContainer.mock.calls[0]?.[0]
    expect(call.config?.env).toBe('cloud-test')
    expect(call.header?.['X-WX-SERVICE']).toBe('api-service')
    expect(call.path).toBe('/api/v1/auth/cloud-login')
    expect(call.method).toBe('POST')
    expect(response.requestId).toBe('request-cloud-1')
  })

  it('maps platform failure to a network error', async () => {
    const callContainer = vi.fn((options: CloudContainerOptions) => {
      options.fail?.({ errMsg: 'cloud.callContainer:fail timeout' })
    })
    vi.stubGlobal('wx', { cloud: { callContainer } })
    const transport = new CloudTransport({
      environmentId: 'cloud-test',
      serviceName: 'api-service',
    })

    await expect(
      transport.execute({
        path: '/health',
        method: 'GET',
        headers: {},
        timeout: 10_000,
      }),
    ).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
    })
  })

  it('maps a missing CloudBase access token to an actionable auth error', async () => {
    const callContainer = vi.fn((options: CloudContainerOptions) => {
      options.fail?.({
        errMsg: 'cloud.callContainer:fail Error: access_token missing (trace: system error)',
      })
    })
    vi.stubGlobal('wx', { cloud: { callContainer } })
    const transport = new CloudTransport({
      environmentId: 'cloud-test',
      serviceName: 'api-service',
    })

    await expect(
      transport.execute({
        path: '/api/v1/auth/cloud-login',
        method: 'POST',
        data: {},
        headers: {},
        timeout: 10_000,
      }),
    ).rejects.toMatchObject({
      code: 'CLOUDBASE_AUTH_ERROR',
      message: '云开发登录态缺失，请重新进入小程序',
    })
  })
})
