/**
 * Kitty WS reconnect auth recovery — refresh only on close code 4001.
 *
 * Server accepts then closes with real codes (see reject_kitty_websocket).
 * Browsers therefore receive 4001 (auth), 4003 (feature/access), 4400/4403
 * (scope) instead of opaque HTTP 403 → 1006. Transport failures reconnect
 * without rotating cookies.
 */

import {
  classifyKittyWsCloseCode,
  isKittyConnectCloseError,
} from '@/composables/kitty/kittyConnectFailure'
import {
  awaitSessionRefreshIdle,
  ensureFreshSessionAfterAuthFailure,
  getSessionRefreshEpoch,
  isSessionRefreshRateLimited,
} from '@/utils/sessionRefresh'

/** Outcome of one Kitty connect attempt (before any auth refresh). */
export type KittyConnectAttemptResult =
  | 'connected'
  | 'aborted'
  | 'auth_failed'
  | 'access_denied'
  | 'scope_denied'
  | 'failed'

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

/** Classify a thrown connect error into an attempt result. */
export function classifyKittyConnectError(error: unknown): KittyConnectAttemptResult {
  if (isKittyConnectAbortError(error)) {
    return 'aborted'
  }
  if (isKittyConnectCloseError(error)) {
    return classifyKittyWsCloseCode(error.code) ?? 'failed'
  }
  return 'failed'
}

export type KittyWsAuthReconnectGate = {
  isHardStopped: () => boolean
  markHardStopped: () => void
  reset: () => void
  /** True until one auth-assisted connect attempt has been consumed. */
  canAttemptAuthRefresh: () => boolean
  markAuthRefreshConsumed: () => void
}

/**
 * Connect once; refresh cookies only on auth_failed (4001), then retry once.
 * Access/scope denials hard-stop without session-expired UI.
 * Transport failures return false so the caller can backoff-reconnect.
 */
export async function runKittyConnectWithAuthRecovery(deps: {
  isHardStopped: () => boolean
  markHardStopped: () => void
  hasAuthenticatedUser: () => boolean
  onSessionExpired: () => void
  connectOnce: () => Promise<KittyConnectAttemptResult>
  canAttemptAuthRefresh?: () => boolean
  markAuthRefreshConsumed?: () => void
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

  if (first === 'access_denied' || first === 'scope_denied') {
    deps.markHardStopped()
    return false
  }

  if (first !== 'auth_failed') {
    // Transport / unclassified — reconnect without rotating cookies.
    return false
  }

  const canRefresh = deps.canAttemptAuthRefresh?.() ?? true
  if (!canRefresh) {
    return false
  }
  deps.markAuthRefreshConsumed?.()

  const refreshed = await ensureFreshSessionAfterAuthFailure(epochAtStart)
  if (!refreshed) {
    deps.markHardStopped()
    // Rate limit means we hammered refresh — stop the loop, keep the session.
    if (!isSessionRefreshRateLimited()) {
      deps.onSessionExpired()
    }
    return false
  }

  await awaitSessionRefreshIdle()
  if (deps.isHardStopped() || !deps.hasAuthenticatedUser()) {
    return false
  }
  const second = await deps.connectOnce()
  if (second === 'connected') {
    return true
  }
  // Refresh succeeded but policy still rejects — stop reconnect storms.
  if (second === 'access_denied' || second === 'scope_denied') {
    deps.markHardStopped()
  }
  return false
}

/** Per-agent gate so concurrent voice:ws_closed handlers share one hard-stop flag. */
export function createKittyWsAuthReconnectGate(): KittyWsAuthReconnectGate {
  let hardStopped = false
  let authRefreshConsumed = false
  return {
    isHardStopped: () => hardStopped,
    markHardStopped: () => {
      hardStopped = true
    },
    reset: () => {
      hardStopped = false
      authRefreshConsumed = false
    },
    canAttemptAuthRefresh: () => !authRefreshConsumed,
    markAuthRefreshConsumed: () => {
      authRefreshConsumed = true
    },
  }
}
