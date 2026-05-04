/**
 * Centralised version / sequencing state for the canvas-collab WebSocket session.
 *
 * Extracted from the scattered ``sessionMutable.*`` fields in ``useWorkshop`` so
 * that all version cursors are:
 *   - Reactive (Pinia / Vue devtools can observe them)
 *   - Owned in one place (single reset site, no forgotten cursor)
 *   - Testable without a full WebSocket + component tree
 *
 * The pure math helpers (``evaluateLiveSpecGap``, ``applySnapshotFrame``) from
 * ``useWorkshopReconnect`` are reused here; this composable only adds the
 * reactive state container and the record* API.
 */
import { type ComputedRef, type Ref, computed, readonly, ref } from 'vue'

import { WORKSHOP_STALE_RESYNC_THRESHOLD } from './useWorkshopMessageHandlers'
import { applySnapshotFrame, evaluateLiveSpecGap } from './useWorkshopReconnect'

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

export interface RecordUpdateResult {
  /** Frame was a duplicate / older than last seen — should be dropped. */
  stale: boolean
  /** Seq / version gap detected — caller should request a resync. */
  gap: boolean
  /** Stale burst threshold hit — caller should also request a resync. */
  consecutiveStaleHit: boolean
}

export interface RecordAckResult {
  /**
   * The ack seq / version jumped by more than 1, meaning there are peer
   * broadcasts we never received.  Caller should request a resync.
   */
  peerGap: boolean
}

export interface CollabSyncVersion {
  // ── Reactive state (read-only refs) ────────────────────────────────────
  /** Latest accepted live-spec version from ``update`` / ``snapshot`` / ``update_ack``. */
  liveVersion: Readonly<Ref<number | null>>
  /** Latest accepted ``seq`` counter (primary ordering cursor). */
  liveSeq: Readonly<Ref<number | null>>
  /** True while waiting for a ``snapshot`` reply to recover from a gap / error. */
  pendingResync: Readonly<Ref<boolean>>
  /** Number of consecutive stale ``update`` frames since last accepted frame. */
  consecutiveStale: Readonly<Ref<number>>
  /** ``Date.now()`` of the last accepted ``update`` or ``snapshot`` frame. */
  lastFrameAt: Readonly<Ref<number | null>>

  // ── Derived ────────────────────────────────────────────────────────────
  /** True when not waiting for a resync and at least one frame has been processed. */
  isSynced: ComputedRef<boolean>
  /** True when ``pendingResync`` is on or at least one consecutive stale frame has been received. */
  isStale: ComputedRef<boolean>

  // ── Mutation API ───────────────────────────────────────────────────────
  /**
   * Apply a ``snapshot`` frame.  Resets pendingResync, advances both cursors.
   */
  recordSnapshot(version: number | null | undefined, seq?: number | null): void

  /**
   * Evaluate an incoming ``update`` frame.
   * Returns a result object that the caller uses to decide whether to drop,
   * resync, or apply the update.  Advances internal cursors on acceptance.
   */
  recordUpdate(
    version: number | null | undefined,
    seq?: number | null,
  ): RecordUpdateResult

  /**
   * Evaluate an ``update_ack`` frame.
   * Returns whether a peer-gap was detected that requires a resync.
   */
  recordAck(version: number | null | undefined, seq?: number | null): RecordAckResult

  /** Handle an ``error`` frame — sets pendingResync for ``update_rejected``. */
  recordError(code?: string): void

  /** Write ``pendingResync`` — called by the watchdog / message handlers. */
  setPendingResync(value: boolean): void

  /** Reset all cursors (called on socket open / close / disconnect). */
  reset(): void
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

export function useCollabSyncVersion(): CollabSyncVersion {
  const _liveVersion = ref<number | null>(null)
  const _liveSeq = ref<number | null>(null)
  const _pendingResync = ref(false)
  const _consecutiveStale = ref(0)
  const _lastFrameAt = ref<number | null>(null)

  const isSynced = computed(
    () => !_pendingResync.value && _liveVersion.value !== null,
  )
  const isStale = computed(
    () => _pendingResync.value || _consecutiveStale.value > 0,
  )

  function recordSnapshot(
    version: number | null | undefined,
    seq?: number | null,
  ): void {
    _consecutiveStale.value = 0
    const snap = applySnapshotFrame(version)
    _pendingResync.value = snap.pendingResync
    if (snap.lastLiveSpec !== null) {
      _liveVersion.value = snap.lastLiveSpec
    }
    if (snap.lastSequential !== null) {
      _liveVersion.value = snap.lastSequential
    }
    if (typeof seq === 'number' && Number.isFinite(seq)) {
      if (_liveSeq.value === null || seq >= _liveSeq.value) {
        _liveSeq.value = seq
      }
    }
    _lastFrameAt.value = Date.now()
  }

  function recordUpdate(
    version: number | null | undefined,
    seq?: number | null,
  ): RecordUpdateResult {
    const hasSeq = typeof seq === 'number' && Number.isFinite(seq)
    const gapDecision = hasSeq
      ? evaluateLiveSpecGap(_liveSeq.value, seq!)
      : evaluateLiveSpecGap(_liveVersion.value, version)

    if (gapDecision.gap) {
      return { stale: false, gap: true, consecutiveStaleHit: false }
    }

    if (gapDecision.stale) {
      const newCount = _consecutiveStale.value + 1
      _consecutiveStale.value = newCount
      const hit = newCount >= WORKSHOP_STALE_RESYNC_THRESHOLD
      if (hit) {
        _consecutiveStale.value = 0
      }
      return { stale: true, gap: false, consecutiveStaleHit: hit }
    }

    // ── Frame accepted — advance cursors ──────────────────────────────────
    _consecutiveStale.value = 0

    if (gapDecision.nextSequential !== null) {
      if (hasSeq) {
        _liveSeq.value = gapDecision.nextSequential
      } else {
        _liveVersion.value = gapDecision.nextSequential
      }
    }
    // Always advance seq tracker when seq is present.
    if (hasSeq && typeof seq === 'number') {
      if (_liveSeq.value === null || seq > _liveSeq.value) {
        _liveSeq.value = seq
      }
    }
    // Always advance version tracker (informational + version-fallback path).
    if (typeof version === 'number' && Number.isFinite(version)) {
      if (_liveVersion.value === null || version > _liveVersion.value) {
        _liveVersion.value = version
      }
    }
    _lastFrameAt.value = Date.now()

    return { stale: false, gap: false, consecutiveStaleHit: false }
  }

  function recordAck(
    version: number | null | undefined,
    seq?: number | null,
  ): RecordAckResult {
    const hasSeq = typeof seq === 'number' && Number.isFinite(seq)
    const hasVer = typeof version === 'number' && Number.isFinite(version)
    let peerGap = false

    if (hasSeq) {
      const prevSeq = _liveSeq.value
      if (prevSeq === null || seq! > prevSeq) {
        peerGap = prevSeq !== null && seq! > prevSeq + 1
        _liveSeq.value = seq!
      }
    } else if (hasVer) {
      const prev = _liveVersion.value
      if (prev === null || version! > prev) {
        peerGap = prev !== null && version! > prev + 1
      }
    }

    // Advance version cursor for UI display and version-fallback path.
    if (hasVer) {
      if (_liveVersion.value === null || version! > _liveVersion.value) {
        _liveVersion.value = version!
      }
    }

    _lastFrameAt.value = Date.now()

    return { peerGap }
  }

  function recordError(code?: string): void {
    if (code === 'update_rejected') {
      _pendingResync.value = true
    }
  }

  function setPendingResync(value: boolean): void {
    _pendingResync.value = value
  }

  function reset(): void {
    _liveVersion.value = null
    _liveSeq.value = null
    _pendingResync.value = false
    _consecutiveStale.value = 0
    _lastFrameAt.value = null
  }

  return {
    liveVersion: readonly(_liveVersion),
    liveSeq: readonly(_liveSeq),
    pendingResync: readonly(_pendingResync),
    consecutiveStale: readonly(_consecutiveStale),
    lastFrameAt: readonly(_lastFrameAt),
    isSynced,
    isStale,
    recordSnapshot,
    recordUpdate,
    recordAck,
    recordError,
    setPendingResync,
    reset,
  }
}
