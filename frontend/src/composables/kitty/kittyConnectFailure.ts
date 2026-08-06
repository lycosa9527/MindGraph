/**
 * Kitty WS handshake failure classification from WebSocket close codes.
 *
 * Server (`reject_kitty_websocket`) accepts then closes so browsers receive
 * these codes instead of opaque HTTP 403 → close 1006.
 */

/** Close codes Kitty auth/policy uses after accept-then-close. */
export const KITTY_WS_CLOSE_AUTH = 4001
export const KITTY_WS_CLOSE_ACCESS = 4003
export const KITTY_WS_CLOSE_BAD_SCOPE = 4400
export const KITTY_WS_CLOSE_SCOPE_DENIED = 4403
/** Client/server intentional supersede, cleanup, or peer replace. */
export const KITTY_WS_CLOSE_GOING_AWAY = 1001

export class KittyConnectCloseError extends Error {
  readonly code: number
  readonly closeReason: string

  constructor(code: number, reason: string) {
    const trimmed = reason.trim()
    super(trimmed || `WebSocket closed (${code})`)
    this.name = 'KittyConnectCloseError'
    this.code = code
    this.closeReason = reason
  }
}

export function isKittyConnectCloseError(error: unknown): error is KittyConnectCloseError {
  return error instanceof KittyConnectCloseError
}

/** Map a close code to a connect-attempt outcome, or null if unclassified. */
export function classifyKittyWsCloseCode(
  code: number
): 'auth_failed' | 'access_denied' | 'scope_denied' | null {
  if (code === KITTY_WS_CLOSE_AUTH) {
    return 'auth_failed'
  }
  if (code === KITTY_WS_CLOSE_ACCESS) {
    return 'access_denied'
  }
  if (code === KITTY_WS_CLOSE_BAD_SCOPE || code === KITTY_WS_CLOSE_SCOPE_DENIED) {
    return 'scope_denied'
  }
  return null
}

/** Preempt / cleanup / local reconnect — do not treat as transport loss. */
export function isKittyWsIntentionalClose(
  code: number | undefined,
  wasClean?: boolean
): boolean {
  return code === KITTY_WS_CLOSE_GOING_AWAY || wasClean === true
}

/** Feature/scope policy denial — hard-stop reconnect, never refresh cookies. */
export function isKittyWsPolicyDenyClose(code: number | undefined): boolean {
  return (
    code === KITTY_WS_CLOSE_ACCESS ||
    code === KITTY_WS_CLOSE_BAD_SCOPE ||
    code === KITTY_WS_CLOSE_SCOPE_DENIED
  )
}
