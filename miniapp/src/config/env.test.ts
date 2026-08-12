import { describe, expect, it } from 'vitest'

import { resolveApiBaseUrl, resolveCloudConfig } from './env'

describe('resolveApiBaseUrl', () => {
  it('uses the WSL localhost backend during local development', () => {
    expect(resolveApiBaseUrl(undefined)).toBe('http://localhost:8000')
  })

  it('uses an HTTPS preview backend and removes trailing slashes', () => {
    expect(resolveApiBaseUrl(' https://api.example.com/// ')).toBe(
      'https://api.example.com',
    )
  })
})

describe('resolveCloudConfig', () => {
  it('trims and returns the CloudBase environment and service', () => {
    expect(resolveCloudConfig(' cloud-test ', ' api-service ')).toEqual({
      environmentId: 'cloud-test',
      serviceName: 'api-service',
    })
  })

  it('rejects a missing environment', () => {
    expect(() => resolveCloudConfig('', 'api-service')).toThrow('CloudBase')
  })

  it('rejects a missing service name', () => {
    expect(() => resolveCloudConfig('cloud-test', '')).toThrow('CloudBase')
  })
})
