/** Shared Kitty REST poll intervals (pairing hints + recovery). */
export const KITTY_PAIR_POLL_MS = 4000
/** Slow poll while SSE is disconnected (desktop mobile_active / action fallback). */
export const KITTY_MOBILE_WATCH_MS = 12000
/**
 * Legacy long-poll BLPOP hold. Desktop SPA no longer chains ``wait_sec=25``;
 * actions drain via SSE ``desktop_action_pending`` + instant LPOP.
 */
export const KITTY_DESKTOP_PAIR_WAIT_SEC = 25
/** Mobile focus REST recovery while Kitty WS is connected (push is primary). */
export const KITTY_FOCUS_RECOVERY_POLL_MS = 30000
/** live_context recovery poll (SSE/WS carry hot path). */
export const KITTY_LIVE_CONTEXT_POLL_MS = 12000
