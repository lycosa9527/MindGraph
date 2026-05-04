import { describe, expect, it } from 'vitest'

import {
  WORKSHOP_RECONNECT,
  WORKSHOP_RESYNC_WATCHDOG,
  applySnapshotFrame,
  computeReconnectDelayMs,
  evaluateLiveSpecGap,
  netPresenceAfterCancellingPairs,
  nextPendingResyncBackoffMs,
  shouldScheduleReconnect,
} from '@/composables/workshop/useWorkshopReconnect'

describe('computeReconnectDelayMs', () => {
  it('returns 1s on the first attempt', () => {
    expect(computeReconnectDelayMs(0)).toBe(1000)
  })

  it('doubles per attempt', () => {
    expect(computeReconnectDelayMs(1)).toBe(2000)
    expect(computeReconnectDelayMs(2)).toBe(4000)
    expect(computeReconnectDelayMs(3)).toBe(8000)
  })

  it('caps at 30s', () => {
    expect(computeReconnectDelayMs(10)).toBe(WORKSHOP_RECONNECT.MAX_DELAY_MS)
  })

  it('treats negative attempts as the base delay', () => {
    expect(computeReconnectDelayMs(-1)).toBe(WORKSHOP_RECONNECT.BASE_DELAY_MS)
  })
})

describe('shouldScheduleReconnect', () => {
  it('schedules when attempts < max and code is retryable', () => {
    expect(shouldScheduleReconnect(0, 1006)).toBe(true)
    expect(shouldScheduleReconnect(2, 1011)).toBe(true)
    expect(shouldScheduleReconnect(WORKSHOP_RECONNECT.MAX_ATTEMPTS - 1, 1006)).toBe(true)
  })

  it('stops once max attempts reached', () => {
    expect(shouldScheduleReconnect(WORKSHOP_RECONNECT.MAX_ATTEMPTS, 1006)).toBe(false)
    expect(shouldScheduleReconnect(WORKSHOP_RECONNECT.MAX_ATTEMPTS + 1, 1006)).toBe(false)
  })

  it('does not reconnect on normal close (1000)', () => {
    expect(shouldScheduleReconnect(0, 1000)).toBe(false)
  })

  it('does not reconnect on auth failure (4002)', () => {
    expect(shouldScheduleReconnect(0, 4002)).toBe(false)
  })

  it('does not reconnect on room closed by server (4010)', () => {
    expect(shouldScheduleReconnect(0, 4010)).toBe(false)
  })

  it('does not reconnect on session ended by host (4011)', () => {
    expect(shouldScheduleReconnect(0, 4011)).toBe(false)
  })
})

describe('evaluateLiveSpecGap - pendingResync decision', () => {
  it('ignores non-numeric versions as stale', () => {
    const d = evaluateLiveSpecGap(5, undefined)
    expect(d).toEqual({ gap: false, nextSequential: 5, stale: true })
  })

  it('seeds lastSequential when not yet set', () => {
    const d = evaluateLiveSpecGap(null, 10)
    expect(d).toEqual({ gap: false, nextSequential: 10, stale: false })
  })

  it('marks stale when incoming <= lastSequential', () => {
    expect(evaluateLiveSpecGap(5, 5)).toEqual({
      gap: false,
      nextSequential: 5,
      stale: true,
    })
    expect(evaluateLiveSpecGap(5, 3)).toEqual({
      gap: false,
      nextSequential: 5,
      stale: true,
    })
  })

  it('accepts sequential increments', () => {
    expect(evaluateLiveSpecGap(5, 6)).toEqual({
      gap: false,
      nextSequential: 6,
      stale: false,
    })
  })

  it('flags a gap when incoming skips versions', () => {
    expect(evaluateLiveSpecGap(5, 7)).toEqual({
      gap: true,
      nextSequential: 5,
      stale: false,
    })
    expect(evaluateLiveSpecGap(5, 100)).toEqual({
      gap: true,
      nextSequential: 5,
      stale: false,
    })
  })

  it('ignores NaN / Infinity as stale', () => {
    expect(evaluateLiveSpecGap(5, NaN).stale).toBe(true)
    expect(evaluateLiveSpecGap(5, Infinity).stale).toBe(true)
  })
})

describe('applySnapshotFrame', () => {
  it('clears pendingResync and sets both version trackers', () => {
    expect(applySnapshotFrame(42)).toEqual({
      lastSequential: 42,
      lastLiveSpec: 42,
      pendingResync: false,
    })
  })

  it('returns nulls for non-numeric versions', () => {
    expect(applySnapshotFrame(undefined)).toEqual({
      lastSequential: null,
      lastLiveSpec: null,
      pendingResync: false,
    })
  })
})

describe('netPresenceAfterCancellingPairs', () => {
  it('drops users who joined and left inside the coalesce window', () => {
    const raw = netPresenceAfterCancellingPairs(['alice', 'bob'], ['alice'])
    expect(raw.joined).toEqual(['bob'])
    expect(raw.left).toEqual([])
  })

  it('keeps asymmetric deltas', () => {
    const raw = netPresenceAfterCancellingPairs(['alice'], ['bob'])
    expect(raw.joined).toEqual(['alice'])
    expect(raw.left).toEqual(['bob'])
  })
})

describe('nextPendingResyncBackoffMs', () => {
  it('exponential gap between watchdog resync sends', () => {
    expect(nextPendingResyncBackoffMs(1)).toBe(WORKSHOP_RESYNC_WATCHDOG.INITIAL_WAIT_MS * 2)
    expect(nextPendingResyncBackoffMs(2)).toBe(WORKSHOP_RESYNC_WATCHDOG.INITIAL_WAIT_MS * 4)
  })
})

describe('stale frame should not trigger updates', () => {
  /**
   * Verifies the Section-1 fix: when ``evaluateLiveSpecGap`` returns
   * ``stale: true``, the composable should ``break`` and NOT call
   * ``onGranularUpdate`` or ``onUpdate``.
   * This test drives the pure helper and asserts stale frames are skipped.
   */
  it('stale duplicate frame is detected and skipped', () => {
    const last = 5
    const staleFrame = evaluateLiveSpecGap(last, 5)
    expect(staleFrame.stale).toBe(true)
    expect(staleFrame.gap).toBe(false)
    expect(staleFrame.nextSequential).toBe(last)

    const olderFrame = evaluateLiveSpecGap(last, 3)
    expect(olderFrame.stale).toBe(true)
  })

  it('non-numeric version is treated as stale', () => {
    expect(evaluateLiveSpecGap(5, null as unknown as undefined).stale).toBe(true)
    expect(evaluateLiveSpecGap(5, 'v5' as unknown as undefined).stale).toBe(true)
  })
})

describe('pendingResync round-trip simulation', () => {
  /**
   * Models the ``useWorkshop`` state machine:
   *   update(v=1) → update(v=2) → update(v=5)  ← gap, triggers resync
   *   snapshot(v=5)                            ← clears pendingResync
   *   update(v=6)                              ← accepted again
   */
  it('flags gap, snapshot clears, then continues', () => {
    let last: number | null = null
    let pending = false

    {
      const d = evaluateLiveSpecGap(last, 1)
      expect(d.gap).toBe(false)
      if (!d.stale) last = d.nextSequential
    }
    {
      const d = evaluateLiveSpecGap(last, 2)
      expect(d.gap).toBe(false)
      last = d.nextSequential
    }
    {
      const d = evaluateLiveSpecGap(last, 5)
      expect(d.gap).toBe(true)
      pending = true
    }
    expect(pending).toBe(true)

    const snap = applySnapshotFrame(5)
    pending = snap.pendingResync
    last = snap.lastSequential
    expect(pending).toBe(false)
    expect(last).toBe(5)

    {
      const d = evaluateLiveSpecGap(last, 6)
      expect(d.gap).toBe(false)
      expect(d.nextSequential).toBe(6)
    }
  })
})

describe('viewer seq trackers after reconnect (useWorkshop onopen)', () => {
  /**
   * On each WebSocket open, lastSequential / seq trackers clear so stale
   * lastSeenSeq from a prior socket cannot suppress resync vs a new session.
   */
  it('re-seeding null lastSequential aligns with incoming post-reconnect snapshot', () => {
    expect(evaluateLiveSpecGap(null, 10)).toEqual({
      gap: false,
      nextSequential: 10,
      stale: false,
    })
  })

  it('without reset, leftover lastSequential falsely treats lower seq as stale', () => {
    const staleAfterRoomRecreate = evaluateLiveSpecGap(42, 10)
    expect(staleAfterRoomRecreate.stale).toBe(true)
    expect(staleAfterRoomRecreate.nextSequential).toBe(42)
  })
})
