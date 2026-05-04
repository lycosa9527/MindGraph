/**
 * Pure helpers for the ``useWorkshop`` collab composable.
 *
 * Extracted so that the reconnect / pendingResync / idle-countdown primitives
 * can be unit-tested with Vitest without standing up a full WebSocket +
 * Vue component tree.
 *
 * These helpers deliberately have no Vue / DOM / router dependencies so they
 * can run under jsdom or node with no mocks.
 */

/** Constants shared between the composable and its unit tests. */
export const WORKSHOP_RECONNECT = {
  /** Maximum number of WS reconnect attempts before we give up. */
  MAX_ATTEMPTS: 5,
  /** Minimum base delay (ms). */
  BASE_DELAY_MS: 1000,
  /** Upper bound for the exponential delay (ms) before jitter. */
  MAX_DELAY_MS: 30000,
  /** Uniform-random jitter added on top of the exponential delay (ms). */
  JITTER_MS: 1000,
  /** WS close codes that should *not* trigger a reconnect attempt. */
  NO_RECONNECT_CLOSE_CODES: new Set<number>([
    1000, // normal close
    1008, // policy violation (e.g. collaboration session ended / invalid)
    4001, // JWT expired mid-session — user must re-login, not reconnect
    4002, // auth failure (not retryable)
    4003, // superseded by another tab / session
    4010, // room closed by server
    4011, // session ended by host (explicit stop)
    4012,
    4013,
    4014,
    4015,
  ]),
} as const

/**
 * Decide the next reconnect delay in ms (without jitter) given how many
 * attempts have already run.  Matches the production formula
 * ``min(30000, 1000 * 2^attempts)``.
 */
export function computeReconnectDelayMs(attempt: number): number {
  if (attempt < 0) {
    return WORKSHOP_RECONNECT.BASE_DELAY_MS
  }
  const raw = WORKSHOP_RECONNECT.BASE_DELAY_MS * Math.pow(2, attempt)
  return Math.min(WORKSHOP_RECONNECT.MAX_DELAY_MS, raw)
}

/**
 * Given the current number of attempts and the close code from the WebSocket,
 * return ``true`` if we should schedule another reconnect attempt.
 *
 * The composable also requires ``workshopCode`` to be non-null at call-time;
 * that check is left to the caller since it depends on Vue reactivity.
 */
export function shouldScheduleReconnect(attempts: number, closeCode: number): boolean {
  if (attempts >= WORKSHOP_RECONNECT.MAX_ATTEMPTS) {
    return false
  }
  if (WORKSHOP_RECONNECT.NO_RECONNECT_CLOSE_CODES.has(closeCode)) {
    return false
  }
  return true
}

/**
 * Version-gap detector: returns ``{ gap: true }`` when the incoming live-spec
 * ``v`` skipped one or more versions, i.e. ``incoming > lastSequential + 1``.
 *
 * Used by the ``update`` WS handler to decide whether to set
 * ``pendingResync = true`` and send ``{"type":"resync"}``.
 *
 * Ignores out-of-order / duplicate / stale messages (``incoming <= last``).
 */
export interface LiveSpecGapDecision {
  /** True iff client should request a server snapshot to recover. */
  gap: boolean
  /** What the new ``lastSequentialLiveVersion`` should be after this frame. */
  nextSequential: number | null
  /** True iff the frame is a stale/duplicate and should be ignored. */
  stale: boolean
}

export function evaluateLiveSpecGap(
  lastSequential: number | null,
  incoming: number | null | undefined
): LiveSpecGapDecision {
  if (typeof incoming !== 'number' || !Number.isFinite(incoming)) {
    return { gap: false, nextSequential: lastSequential, stale: true }
  }
  if (lastSequential === null) {
    return { gap: false, nextSequential: incoming, stale: false }
  }
  if (incoming <= lastSequential) {
    return { gap: false, nextSequential: lastSequential, stale: true }
  }
  if (incoming > lastSequential + 1) {
    return { gap: true, nextSequential: lastSequential, stale: false }
  }
  return { gap: false, nextSequential: incoming, stale: false }
}

/**
 * Apply a ``snapshot`` WS frame to the pendingResync / version book-keeping.
 *
 * Returns the new ``(lastSequentialLiveVersion, lastLiveSpecVersion,
 * pendingResync)`` tuple.
 */
export interface SnapshotApply {
  lastSequential: number | null
  lastLiveSpec: number | null
  pendingResync: boolean
}

export function applySnapshotFrame(incomingVersion: number | null | undefined): SnapshotApply {
  if (typeof incomingVersion !== 'number' || !Number.isFinite(incomingVersion)) {
    return { lastSequential: null, lastLiveSpec: null, pendingResync: false }
  }
  return {
    lastSequential: incomingVersion,
    lastLiveSpec: incomingVersion,
    pendingResync: false,
  }
}

/** After a coalesce window, drop names that appear in both joined and left. */
export function netPresenceAfterCancellingPairs(
  joined: string[],
  left: string[]
): { joined: string[]; left: string[] } {
  const leftSet = new Set(left)
  const joinedSet = new Set(joined)
  return {
    joined: joined.filter((u) => !leftSet.has(u)),
    left: left.filter((u) => !joinedSet.has(u)),
  }
}

/** One participant row for join/leave coalescing (stable ``userId`` for pairing). */
export interface PresenceDeltaRow {
  userId: number
  displayName: string
}

/**
 * Same as ``netPresenceAfterCancellingPairs`` but keyed by ``userId`` so a
 * reconnect cannot produce mismatched display strings for the same person.
 */
export function netPresenceAfterCancellingPairsByUserId(
  joined: PresenceDeltaRow[],
  left: PresenceDeltaRow[]
): { joined: PresenceDeltaRow[]; left: PresenceDeltaRow[] } {
  const leftIds = new Set(left.map((r) => r.userId))
  const joinedIds = new Set(joined.map((r) => r.userId))
  return {
    joined: joined.filter((r) => !leftIds.has(r.userId)),
    left: left.filter((r) => !joinedIds.has(r.userId)),
  }
}

/** Timers for pendingResync resend / banner (mirrors useWorkshop). */
export const WORKSHOP_RESYNC_WATCHDOG = {
  INITIAL_WAIT_MS: 8000,
  MAX_RETRIES: 3,
  STEADY_INTERVAL_MS: 30000,
} as const

/**
 * Delay before the next watchdog ``resync`` send after ``stepAfterSend``
 * completed watchdog sends (1 => 16 s, 2 => 32 s). The first watchdog fire
 * uses ``WORKSHOP_RESYNC_WATCHDOG.INITIAL_WAIT_MS`` only.
 */
export function nextPendingResyncBackoffMs(stepAfterSend: number): number {
  const base = WORKSHOP_RESYNC_WATCHDOG.INITIAL_WAIT_MS
  return base * Math.pow(2, stepAfterSend)
}
