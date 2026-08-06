/**
 * Shared mutex + 401-stampede coordinator for POST /api/auth/refresh
 * (httpOnly cookie rotation).
 *
 * Concurrent callers share one in-flight refresh. After a successful rotation,
 * callers that failed under the previous epoch retry without starting another
 * refresh — so stale in-flight cookie requests do not delete the new session.
 *
 * HTTP 401 storms (apiClient / auth store) also respect a short grace window
 * after a successful refresh. Kitty WS must not refresh on transport failures;
 * it only calls ensureFresh on close code 4001 (see kittyWsAuthReconnect).
 *
 * Kitty / desktop_focus must also await idle so a WebSocket handshake or PUT
 * does not leave with a cookie that Redis just deleted mid-rotation.
 */
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

const API_BASE = '/api'

/**
 * After a successful refresh, treat the session as fresh for this long.
 * Guards HTTP 401 stampede peers that retry after the mutex releases.
 */
const REFRESH_SUCCESS_GRACE_MS = 20_000

let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null
/** Bumped only after a successful /api/auth/refresh. */
let refreshEpoch = 0
let lastSuccessfulRefreshAt = 0
/** Last non-OK refresh outcome (cleared on success). */
let lastRefreshFailure: 'auth' | 'rate_limit' | 'network' | null = null

/** Monotonic epoch; use as epochAtStart before a cookie-auth request/WS open. */
export function getSessionRefreshEpoch(): number {
  return refreshEpoch
}

/** True while a refresh request is in flight (not merely “recently refreshed”). */
export function isSessionRefreshInFlight(): boolean {
  return isRefreshing
}

/** True when the last refresh attempt hit HTTP 429 (not session death). */
export function isSessionRefreshRateLimited(): boolean {
  return lastRefreshFailure === 'rate_limit'
}

/**
 * Wait until any in-flight refresh finishes (no-op when idle).
 * Callers that open cookie-auth WebSockets or fire cookie-auth PUTs should
 * await this so they do not race Redis session deletion.
 */
export async function awaitSessionRefreshIdle(): Promise<void> {
  if (refreshPromise != null) {
    await refreshPromise.catch(() => false)
  }
}

function withinSuccessfulRefreshGrace(): boolean {
  return (
    lastSuccessfulRefreshAt > 0 && Date.now() - lastSuccessfulRefreshAt < REFRESH_SUCCESS_GRACE_MS
  )
}

/**
 * After an auth failure: wait for idle; if a peer already refreshed since
 * ``epochAtFailure`` (or a successful refresh is still within grace), return
 * true without rotating again; else refresh once.
 */
export async function ensureFreshSessionAfterAuthFailure(
  epochAtFailure: number
): Promise<boolean> {
  if (isMindgraphHeadlessExportSession()) {
    return false
  }
  await awaitSessionRefreshIdle()
  if (getSessionRefreshEpoch() > epochAtFailure) {
    return true
  }
  if (withinSuccessfulRefreshGrace()) {
    return true
  }
  return refreshSessionAccessToken()
}

export async function refreshSessionAccessToken(): Promise<boolean> {
  if (isMindgraphHeadlessExportSession()) {
    return false
  }
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'same-origin',
      })
      if (response.ok) {
        refreshEpoch += 1
        lastSuccessfulRefreshAt = Date.now()
        lastRefreshFailure = null
        return true
      }
      if (response.status === 429) {
        lastRefreshFailure = 'rate_limit'
      } else {
        lastRefreshFailure = 'auth'
      }
      return false
    } catch {
      lastRefreshFailure = 'network'
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}
