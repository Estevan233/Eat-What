import { afterEach, describe, expect, it, vi } from 'vitest'

import { request } from './request'

describe('request', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends a request without requiring an active Pinia instance', async () => {
    const requestMock = vi.fn((options: UniApp.RequestOptions) => {
      options.success?.({
        data: { ok: true, data: { value: 'ok' } },
        statusCode: 200,
        header: {},
        cookies: [],
        errMsg: 'request:ok',
      })
      options.complete?.({ errMsg: 'request:ok' })
      return {} as UniApp.RequestTask
    })

    vi.stubGlobal('uni', {
      getStorageSync: vi.fn(() => 'stored-token'),
      request: requestMock,
      showLoading: vi.fn(),
      hideLoading: vi.fn(),
      showToast: vi.fn(),
      navigateTo: vi.fn(),
    })

    await expect(
      request<{ value: string }>({ url: '/health', loading: false }),
    ).resolves.toEqual({ value: 'ok' })

    expect(requestMock).toHaveBeenCalledOnce()
    expect(requestMock.mock.calls[0]?.[0].header).toMatchObject({
      Authorization: 'Bearer stored-token',
    })
  })

  it('uses one loading indicator for concurrent requests', async () => {
    const pending: UniApp.RequestOptions[] = []
    const showLoading = vi.fn()
    const hideLoading = vi.fn()
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn(() => ''),
      request: vi.fn((options: UniApp.RequestOptions) => {
        pending.push(options)
        return {} as UniApp.RequestTask
      }),
      showLoading,
      hideLoading,
      showToast: vi.fn(),
      navigateTo: vi.fn(),
      removeStorageSync: vi.fn(),
    })

    const first = request<{ value: number }>({ url: '/first' })
    const second = request<{ value: number }>({ url: '/second' })

    expect(showLoading).toHaveBeenCalledTimes(1)
    pending[0]?.success?.({
      data: { ok: true, data: { value: 1 } },
      statusCode: 200,
      header: {},
      cookies: [],
      errMsg: 'request:ok',
    })
    pending[0]?.complete?.({ errMsg: 'request:ok' })
    await expect(first).resolves.toEqual({ value: 1 })
    expect(hideLoading).not.toHaveBeenCalled()

    pending[1]?.success?.({
      data: { ok: true, data: { value: 2 } },
      statusCode: 200,
      header: {},
      cookies: [],
      errMsg: 'request:ok',
    })
    pending[1]?.complete?.({ errMsg: 'request:ok' })
    await expect(second).resolves.toEqual({ value: 2 })
    expect(hideLoading).toHaveBeenCalledTimes(1)
  })

  it('redirects once for concurrent 401 responses and preserves guest id', async () => {
    const navigateTo = vi.fn()
    const removeStorageSync = vi.fn()
    const requestMock = vi.fn((options: UniApp.RequestOptions) => {
      options.success?.({
        data: {
          ok: false,
          code: 'AUTH_ERROR',
          message: 'expired',
          data: null,
        },
        statusCode: 401,
        header: {},
        cookies: [],
        errMsg: 'request:ok',
      })
      options.complete?.({ errMsg: 'request:ok' })
      return {} as UniApp.RequestTask
    })
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn((key: string) =>
        key === 'eat_what_guest_id' ? 'guest-stays' : 'expired-token',
      ),
      request: requestMock,
      showLoading: vi.fn(),
      hideLoading: vi.fn(),
      showToast: vi.fn(),
      navigateTo,
      removeStorageSync,
    })

    const results = await Promise.allSettled([
      request({ url: '/one', loading: false }),
      request({ url: '/two', loading: false }),
    ])

    expect(results.every((result) => result.status === 'rejected')).toBe(true)
    expect(navigateTo).toHaveBeenCalledTimes(1)
    expect(removeStorageSync).not.toHaveBeenCalledWith('eat_what_guest_id')
  })

  it('can silence an expected 404 without swallowing the rejection', async () => {
    const showToast = vi.fn()
    vi.stubGlobal('uni', {
      getStorageSync: vi.fn(() => 'stored-token'),
      request: vi.fn((options: UniApp.RequestOptions) => {
        options.success?.({
          data: {
            ok: false,
            code: 'NOT_FOUND',
            message: 'constitution 不存在',
            data: null,
          },
          statusCode: 404,
          header: {},
          cookies: [],
          errMsg: 'request:ok',
        })
        options.complete?.({ errMsg: 'request:ok' })
        return {} as UniApp.RequestTask
      }),
      showLoading: vi.fn(),
      hideLoading: vi.fn(),
      showToast,
      navigateTo: vi.fn(),
    })

  await expect(request({
    url: '/profile/constitution',
    loading: false,
    silentErrorStatuses: [404],
  })).rejects.toMatchObject({ statusCode: 404, code: 'NOT_FOUND' })
  expect(showToast).not.toHaveBeenCalled()
})

it('retries a GET once while the paused database wakes up', async () => {
  const requestMock = vi.fn((options: UniApp.RequestOptions) => {
    const isFirstAttempt = requestMock.mock.calls.length === 1
    options.success?.(
      isFirstAttempt
        ? {
            data: {
              ok: false,
              code: 'DATABASE_ERROR',
              message: '数据服务请求失败，请稍后重试',
              data: null,
            },
            statusCode: 502,
            header: {},
            cookies: [],
            errMsg: 'request:ok',
          }
        : {
            data: { ok: true, data: { value: 'recovered' } },
            statusCode: 200,
            header: {},
            cookies: [],
            errMsg: 'request:ok',
          },
    )
    options.complete?.({ errMsg: 'request:ok' })
    return {} as UniApp.RequestTask
  })
  vi.stubGlobal('uni', {
    getStorageSync: vi.fn(() => 'stored-token'),
    request: requestMock,
    showLoading: vi.fn(),
    hideLoading: vi.fn(),
    showToast: vi.fn(),
    navigateTo: vi.fn(),
  })

  await expect(
    request<{ value: string }>({
      url: '/api/v1/daily/history?days=90',
      loading: false,
    }),
  ).resolves.toEqual({ value: 'recovered' })
  expect(requestMock).toHaveBeenCalledTimes(2)
})

it('does not retry a POST that already reached the server', async () => {
  const requestMock = vi.fn((options: UniApp.RequestOptions) => {
    options.success?.({
      data: {
        ok: false,
        code: 'DATABASE_ERROR',
        message: '数据服务请求失败，请稍后重试',
        data: null,
      },
      statusCode: 502,
      header: {},
      cookies: [],
      errMsg: 'request:ok',
    })
    options.complete?.({ errMsg: 'request:ok' })
    return {} as UniApp.RequestTask
  })
  vi.stubGlobal('uni', {
    getStorageSync: vi.fn(() => 'stored-token'),
    request: requestMock,
    showLoading: vi.fn(),
    hideLoading: vi.fn(),
    showToast: vi.fn(),
    navigateTo: vi.fn(),
  })

  await expect(
    request({
      url: '/api/v1/daily/logs/manual',
      method: 'POST',
      data: { logDate: '2026-09-02', mealSlot: 'lunch', dishes: [] },
      loading: false,
    }),
  ).rejects.toMatchObject({ statusCode: 502, code: 'DATABASE_ERROR' })
  expect(requestMock).toHaveBeenCalledTimes(1)
})
})
