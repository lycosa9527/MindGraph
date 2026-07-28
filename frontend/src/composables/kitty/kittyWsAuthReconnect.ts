/**
 * Kitty WS reconnect auth recovery — refresh once, then hard-stop.
 *
 * Auth is rejected before websocket.accept(), so the browser typically sees
 * HTTP 403 / close 1006 rather than close code 4001. Reconnect loops must
 * therefore recover via POST /api/auth/refresh (same as apiClient 401), not
 * via workshop-style close-code lists alone.
 */

export type KittyWsAuthRecoverResult = 'recovered' | 'hard_stop'

export async function recoverKittyWsAuthOrHardStop(deps: {
  hasAuthenticatedUser: boolean
  refreshAccessToken: () => Promise<{ success: boolean }>
  onSessionExpired: () => void
}): Promise<KittyWsAuthRecoverResult> {
  if (!deps.hasAuthenticatedUser) {
    return 'hard_stop'
  }
  const refreshed = await deps.refreshAccessToken()
  if (refreshed.success) {
    return 'recovered'
  }
  deps.onSessionExpired()
  return 'hard_stop'
}

/**
 * Connect once; on failure try silent refresh + one retry; hard-stop on refresh failure.
 */
export async function runKittyConnectWithAuthRecovery(deps: {
  isHardStopped: () => boolean
  markHardStopped: () => void
  hasAuthenticatedUser: () => boolean
  refreshAccessToken: () => Promise<{ success: boolean }>
  onSessionExpired: () => void
  connectOnce: () => Promise<boolean>
}): Promise<boolean> {
  if (deps.isHardStopped()) {
    return false
  }
  if (!deps.hasAuthenticatedUser()) {
    return false
  }
  if (await deps.connectOnce()) {
    return true
  }
  if (deps.isHardStopped()) {
    return false
  }
  const result = await recoverKittyWsAuthOrHardStop({
    hasAuthenticatedUser: deps.hasAuthenticatedUser(),
    refreshAccessToken: deps.refreshAccessToken,
    onSessionExpired: deps.onSessionExpired,
  })
  if (result === 'hard_stop') {
    deps.markHardStopped()
    return false
  }
  return deps.connectOnce()
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
