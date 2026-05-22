/** Shared Kitty REST poll intervals (pairing hints + desktop action consume/watch). */
export const KITTY_PAIR_POLL_MS = 4000
/** Slow poll while waiting for mobile Kitty to connect (desktop action gate). */
export const KITTY_MOBILE_WATCH_MS = 12000
/** Server BLPOP hold while consuming mobile-initiated desktop actions (long-poll chain). */
export const KITTY_DESKTOP_PAIR_WAIT_SEC = 25
