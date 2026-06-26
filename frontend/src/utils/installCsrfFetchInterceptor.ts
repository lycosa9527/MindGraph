/**
 * Global fetch interceptor that attaches the double-submit CSRF token to
 * same-origin, state-changing requests.
 *
 * The backend (services/infrastructure/http/middleware.py csrf_protection) requires
 * a matching `X-CSRF-Token` header + `csrf_token` cookie for cookie-authenticated
 * POST/PUT/PATCH/DELETE requests. Installing this wrapper once at app bootstrap means
 * raw `fetch` callers (sessionRefresh, logout, stores, composables) are covered without
 * editing every call site.
 *
 * The cookie is read fresh on every call so retries after a token refresh (which rotates
 * the cookie) pick up the new value.
 */
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
const CSRF_COOKIE_NAME = 'csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'

let installed = false
let originalFetchRef: typeof window.fetch | null = null

function readCsrfTokenFromCookie(): string | null {
  if (typeof document === 'undefined') {
    return null
  }
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

function resolveUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') {
    return input
  }
  if (input instanceof URL) {
    return input.href
  }
  return input.url
}

function isSameOrigin(url: string): boolean {
  if (typeof window === 'undefined') {
    return true
  }
  try {
    const resolved = new URL(url, window.location.href)
    return resolved.origin === window.location.origin
  } catch {
    // Relative or malformed URLs are treated as same-origin (the common case).
    return true
  }
}

function resolveMethod(input: RequestInfo | URL, init?: RequestInit): string {
  const fromInit = init?.method
  if (fromInit) {
    return fromInit.toUpperCase()
  }
  if (input instanceof Request) {
    return input.method.toUpperCase()
  }
  return 'GET'
}

export function installCsrfFetchInterceptor(): void {
  if (installed || typeof window === 'undefined' || typeof window.fetch !== 'function') {
    return
  }
  installed = true

  const originalFetch = window.fetch.bind(window)
  originalFetchRef = originalFetch

  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const method = resolveMethod(input, init)
    if (!MUTATING_METHODS.has(method)) {
      return originalFetch(input, init)
    }

    const url = resolveUrl(input)
    if (!isSameOrigin(url)) {
      return originalFetch(input, init)
    }

    const token = readCsrfTokenFromCookie()
    if (!token) {
      return originalFetch(input, init)
    }

    // Merge into a Headers instance so we always overwrite a stale token (the
    // cookie is the source of truth, including after a refresh rotates it).
    const headers = new Headers(
      init?.headers ?? (input instanceof Request ? input.headers : undefined)
    )
    headers.set(CSRF_HEADER_NAME, token)

    if (input instanceof Request && !init?.headers) {
      return originalFetch(new Request(input, { headers }))
    }
    return originalFetch(input, { ...init, headers })
  }
}

/** Test-only: restore the original fetch and allow re-installation. */
function resetForTests(): void {
  if (originalFetchRef && typeof window !== 'undefined') {
    window.fetch = originalFetchRef
  }
  originalFetchRef = null
  installed = false
}

export const __testing = {
  readCsrfTokenFromCookie,
  isSameOrigin,
  resolveMethod,
  resetForTests,
  CSRF_COOKIE_NAME,
}
