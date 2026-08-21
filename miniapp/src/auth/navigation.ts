export type PostLoginNavigation = {
  method: 'switchTab' | 'redirectTo'
  url: string
}

const DEFAULT_TAB = '/pages/today/today'
const TAB_BAR_ROUTES = new Set([
  DEFAULT_TAB,
  '/pages/profile/profile',
  '/pages/constitution/constitution',
  '/pages/history/history',
  '/pages/mine/mine',
])

export function resolvePostLoginNavigation(
  encodedRedirect?: string,
): PostLoginNavigation {
  let url = DEFAULT_TAB
  if (encodedRedirect) {
    try {
      const decoded = decodeURIComponent(encodedRedirect)
      if (decoded.startsWith('/pages/')) url = decoded
    } catch {
      url = DEFAULT_TAB
    }
  }
  const path = url.split('?')[0]
  return {
    method: TAB_BAR_ROUTES.has(path) ? 'switchTab' : 'redirectTo',
    url,
  }
}
