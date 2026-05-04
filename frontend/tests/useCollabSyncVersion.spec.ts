import { describe, expect, it } from 'vitest'

import { WORKSHOP_STALE_RESYNC_THRESHOLD } from '@/composables/workshop/useWorkshopMessageHandlers'
import { useCollabSyncVersion } from '@/composables/workshop/useCollabSyncVersion'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function make() {
  return useCollabSyncVersion()
}

// ---------------------------------------------------------------------------
// reset
// ---------------------------------------------------------------------------

describe('reset', () => {
  it('clears all cursors', () => {
    const v = make()
    v.recordSnapshot(10, 5)
    v.reset()
    expect(v.liveVersion.value).toBeNull()
    expect(v.liveSeq.value).toBeNull()
    expect(v.pendingResync.value).toBe(false)
    expect(v.consecutiveStale.value).toBe(0)
    expect(v.lastFrameAt.value).toBeNull()
  })

  it('is idempotent', () => {
    const v = make()
    v.reset()
    v.reset()
    expect(v.liveVersion.value).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// recordSnapshot
// ---------------------------------------------------------------------------

describe('recordSnapshot', () => {
  it('sets liveVersion and clears pendingResync', () => {
    const v = make()
    v.setPendingResync(true)
    v.recordSnapshot(5, 3)
    expect(v.liveVersion.value).toBe(5)
    expect(v.liveSeq.value).toBe(3)
    expect(v.pendingResync.value).toBe(false)
  })

  it('resets consecutiveStale', () => {
    const v = make()
    // Force consecutive stale
    v.recordSnapshot(1)
    for (let i = 0; i < 3; i++) {
      v.recordUpdate(1) // stale — same version
    }
    expect(v.consecutiveStale.value).toBe(3)
    v.recordSnapshot(10)
    expect(v.consecutiveStale.value).toBe(0)
  })

  it('advances lastFrameAt', () => {
    const v = make()
    v.recordSnapshot(1)
    expect(v.lastFrameAt.value).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// recordUpdate — accepted frames
// ---------------------------------------------------------------------------

describe('recordUpdate (accepted)', () => {
  it('returns {stale:false, gap:false} and advances version', () => {
    const v = make()
    v.recordSnapshot(5)
    const r = v.recordUpdate(6)
    expect(r).toEqual({ stale: false, gap: false, consecutiveStaleHit: false })
    expect(v.liveVersion.value).toBe(6)
  })

  it('advances liveSeq when seq provided', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    const r = v.recordUpdate(6, 11)
    expect(r.stale).toBe(false)
    expect(r.gap).toBe(false)
    expect(v.liveSeq.value).toBe(11)
    expect(v.liveVersion.value).toBe(6)
  })

  it('resets consecutiveStale on acceptance', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    // One stale frame
    v.recordUpdate(5, 10)
    expect(v.consecutiveStale.value).toBe(1)
    // Accepted frame resets it
    v.recordUpdate(6, 11)
    expect(v.consecutiveStale.value).toBe(0)
  })

  it('updates lastFrameAt on acceptance', () => {
    const v = make()
    v.recordSnapshot(1, 1)
    const before = v.lastFrameAt.value!
    v.recordUpdate(2, 2)
    expect(v.lastFrameAt.value).toBeGreaterThanOrEqual(before)
  })

  it('accepts first frame without snapshot (null start)', () => {
    const v = make()
    const r = v.recordUpdate(1, 1)
    expect(r.stale).toBe(false)
    expect(r.gap).toBe(false)
    expect(v.liveVersion.value).toBe(1)
    expect(v.liveSeq.value).toBe(1)
  })
})

// ---------------------------------------------------------------------------
// recordUpdate — stale frames
// ---------------------------------------------------------------------------

describe('recordUpdate (stale)', () => {
  it('detects duplicate seq as stale', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    v.recordUpdate(6, 11) // accepted
    const r = v.recordUpdate(6, 11) // duplicate
    expect(r.stale).toBe(true)
    expect(r.gap).toBe(false)
  })

  it('detects older seq as stale', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    v.recordUpdate(6, 11)
    const r = v.recordUpdate(5, 9)
    expect(r.stale).toBe(true)
  })

  it('increments consecutiveStale and returns hit when threshold reached', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    let hit = false
    for (let i = 0; i < WORKSHOP_STALE_RESYNC_THRESHOLD; i++) {
      const r = v.recordUpdate(5, 10) // same frame every time = stale
      expect(r.stale).toBe(true)
      if (r.consecutiveStaleHit) {
        hit = true
      }
    }
    expect(hit).toBe(true)
  })

  it('resets consecutiveStale to 0 after threshold hit', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    for (let i = 0; i < WORKSHOP_STALE_RESYNC_THRESHOLD; i++) {
      v.recordUpdate(5, 10)
    }
    expect(v.consecutiveStale.value).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// recordUpdate — gap detection
// ---------------------------------------------------------------------------

describe('recordUpdate (gap)', () => {
  it('detects seq gap > 1', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    v.recordUpdate(6, 11) // accepted
    const r = v.recordUpdate(8, 13) // skipped seq 12
    expect(r.gap).toBe(true)
    expect(r.stale).toBe(false)
    // liveSeq should NOT advance on gap
    expect(v.liveSeq.value).toBe(11)
  })

  it('detects version gap > 1 when no seq', () => {
    const v = make()
    v.recordSnapshot(5)
    v.recordUpdate(6)
    const r = v.recordUpdate(8) // gap of 1
    expect(r.gap).toBe(true)
    expect(v.liveVersion.value).toBe(6)
  })
})

// ---------------------------------------------------------------------------
// recordAck
// ---------------------------------------------------------------------------

describe('recordAck', () => {
  it('advances liveSeq on normal ack', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    const r = v.recordAck(6, 11)
    expect(r.peerGap).toBe(false)
    expect(v.liveSeq.value).toBe(11)
    expect(v.liveVersion.value).toBe(6)
  })

  it('reports peerGap when ack seq jumps by more than 1', () => {
    const v = make()
    v.recordSnapshot(5, 10)
    v.recordUpdate(6, 11)
    const r = v.recordAck(8, 13) // skipped 12
    expect(r.peerGap).toBe(true)
  })

  it('does not report peerGap on first ack from null', () => {
    const v = make()
    const r = v.recordAck(5, 10)
    expect(r.peerGap).toBe(false)
    expect(v.liveSeq.value).toBe(10)
  })

  it('falls back to version gap detection when no seq in ack', () => {
    const v = make()
    v.recordSnapshot(5)
    v.recordUpdate(6)
    const r = v.recordAck(8) // version gap
    expect(r.peerGap).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// recordError
// ---------------------------------------------------------------------------

describe('recordError', () => {
  it('sets pendingResync for update_rejected', () => {
    const v = make()
    v.recordError('update_rejected')
    expect(v.pendingResync.value).toBe(true)
  })

  it('does not change pendingResync for unrecognised codes', () => {
    const v = make()
    v.recordError('some_other_error')
    expect(v.pendingResync.value).toBe(false)
  })

  it('does not change pendingResync when called without code', () => {
    const v = make()
    v.recordError()
    expect(v.pendingResync.value).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// setPendingResync
// ---------------------------------------------------------------------------

describe('setPendingResync', () => {
  it('sets to true', () => {
    const v = make()
    v.setPendingResync(true)
    expect(v.pendingResync.value).toBe(true)
  })

  it('clears back to false', () => {
    const v = make()
    v.setPendingResync(true)
    v.setPendingResync(false)
    expect(v.pendingResync.value).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// isSynced / isStale
// ---------------------------------------------------------------------------

describe('isSynced', () => {
  it('is false initially', () => {
    const v = make()
    expect(v.isSynced.value).toBe(false)
  })

  it('is true after snapshot is applied', () => {
    const v = make()
    v.recordSnapshot(1)
    expect(v.isSynced.value).toBe(true)
  })

  it('is false while pendingResync', () => {
    const v = make()
    v.recordSnapshot(1)
    v.setPendingResync(true)
    expect(v.isSynced.value).toBe(false)
  })
})

describe('isStale', () => {
  it('is false initially', () => {
    const v = make()
    expect(v.isStale.value).toBe(false)
  })

  it('is true when pendingResync', () => {
    const v = make()
    v.setPendingResync(true)
    expect(v.isStale.value).toBe(true)
  })

  it('is true as soon as the first consecutive stale frame arrives', () => {
    const v = make()
    v.recordSnapshot(1, 1)
    // One stale frame — consecutiveStale becomes 1, which is > 0.
    v.recordUpdate(1, 1)
    expect(v.consecutiveStale.value).toBe(1)
    expect(v.isStale.value).toBe(true)
  })
})
