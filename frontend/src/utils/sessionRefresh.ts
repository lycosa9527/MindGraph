/**
 * Shared mutex + 401-stampede coordinator for POST /api/auth/refresh
 * (httpOnly cookie rotation).
 *
 * Concurrent callers share one in-flight refresh. After a successful rotation,
 * callers that failed under the previous epoch retry without starting another
 * refresh — so stale in-flight cookie requests do not delete the new session.
 *
 * Kitty / desktop_focus must also await idle so a WebSocket handshake or PUT
 * does not leave with a cookie that Redis just deleted mid-rotation.
 */
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'

const API_BASE = '/api'

let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null
/** Bumped only after a successful /api/auth/refresh. */
let refreshEpoch = 0

/** Monotonic epoch; use as epochAtStart before a cookie-auth request/WS open. */
export function getSessionRefreshEpoch(): number {
  return refreshEpoch
}

/** True while a refresh request is in flight (not merely “recently refreshed”). */
export function isSessionRefreshInFlight(): boolean {
  return isRefreshing
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

/**
 * After an auth failure: wait for idle; if a peer already refreshed since
 * ``epochAtFailure``, return true without rotating again; else refresh once.
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
        return true
      }
      return false
    } catch {
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}
