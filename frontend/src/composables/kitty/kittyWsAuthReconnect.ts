/**
 * Kitty WS reconnect auth recovery — 401-stampede via shared refresh epoch.
 *
 * Auth is rejected before websocket.accept(), so the browser typically sees
 * HTTP 403 / close 1006 rather than close code 4001. Recovery uses the same
 * ensureFreshSessionAfterAuthFailure helper as apiClient: if a peer already
 * refreshed since connect start, retry without rotating again.
 */

import {
  awaitSessionRefreshIdle,
  ensureFreshSessionAfterAuthFailure,
  getSessionRefreshEpoch,
} from '@/utils/sessionRefresh'

/** Outcome of one Kitty connect attempt (before any auth refresh). */
export type KittyConnectAttemptResult = 'connected' | 'aborted' | 'failed'

export function isKittyConnectAbortError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false
  }
  const msg = error.message
  return (
    msg.includes('superseded') ||
    msg.includes('Cleanup started') ||
    msg.includes('Conversation stopped') ||
    msg.includes('has been destroyed')
  )
}

/**
 * Connect once; on failure use shared stampede helper + one retry.
 * Hard-stop when refresh fails (session expired).
 */
export async function runKittyConnectWithAuthRecovery(deps: {
  isHardStopped: () => boolean
  markHardStopped: () => void
  hasAuthenticatedUser: () => boolean
  onSessionExpired: () => void
  connectOnce: () => Promise<KittyConnectAttemptResult>
}): Promise<boolean> {
  if (deps.isHardStopped()) {
    return false
  }
  if (!deps.hasAuthenticatedUser()) {
    return false
  }

  await awaitSessionRefreshIdle()
  if (deps.isHardStopped() || !deps.hasAuthenticatedUser()) {
    return false
  }

  const epochAtStart = getSessionRefreshEpoch()
  const first = await deps.connectOnce()
  if (first === 'connected') {
    return true
  }
  if (first === 'aborted' || deps.isHardStopped()) {
    return false
  }

  const refreshed = await ensureFreshSessionAfterAuthFailure(epochAtStart)
  if (!refreshed) {
    deps.markHardStopped()
    deps.onSessionExpired()
    return false
  }

  await awaitSessionRefreshIdle()
  if (deps.isHardStopped() || !deps.hasAuthenticatedUser()) {
    return false
  }
  return (await deps.connectOnce()) === 'connected'
}

/** Per-agent gate so concurrent voice:ws_closed handlers share one hard-stop flag. */
export function createKittyWsAuthReconnectGate(): {
  isHardStopped: () => boolean
  markHardStopped: () => void
  reset: () => void
} {
  let hardStopped = false
  return {
    isHardStopped: () => hardStopped,
    markHardStopped: () => {
      hardStopped = true
    },
    reset: () => {
      hardStopped = false
    },
  }
}
