import { describe, expect, it } from 'vitest'

import { resolvePostLoginNavigation } from './navigation'

describe('post-login navigation', () => {
  it.each([
    '/pages/today/today',
    '/pages/profile/profile',
    '/pages/constitution/constitution',
    '/pages/history/history',
    '/pages/mine/mine',
  ])('uses switchTab for tabBar target %s', (url) => {
    expect(resolvePostLoginNavigation(encodeURIComponent(url))).toEqual({
      method: 'switchTab',
      url,
    })
  })

  it('uses redirectTo for an ordinary page and keeps its query string', () => {
    const url = '/pages/recipe/recipe?foodId=17'

    expect(resolvePostLoginNavigation(encodeURIComponent(url))).toEqual({
      method: 'redirectTo',
      url,
    })
  })

  it.each([undefined, '', 'https%3A%2F%2Fevil.example', '%E0%A4%A'])(
    'falls back to the today tab for missing or unsafe redirect %s',
    (redirect) => {
      expect(resolvePostLoginNavigation(redirect)).toEqual({
        method: 'switchTab',
        url: '/pages/today/today',
      })
    },
  )
})
