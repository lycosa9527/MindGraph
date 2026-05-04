/**
 * useCollabOutboundQueue
 *
 * Per-session FIFO queue of outgoing collab `update` payloads with
 * `client_op_id` tracking, ack-based dedupe, and replay-on-reconnect support.
 *
 * Design goals
 * ------------
 *   - Never silently drop an edit because the WebSocket was closed at the
 *     instant `sendUpdate` was called or because `pendingResync` was active.
 *   - Be replayable in order on reconnect / after snapshot.
 *   - Be deduplicated by the server using `client_op_id` so the receiver can
 *     ignore duplicates from a retry.
 *   - Cap memory: the queue is bounded; if the cap is exceeded the oldest
 *     unacked op is dropped and a warning is emitted (graceful degradation).
 *
 * Usage
 * -----
 *   const queue = useCollabOutboundQueue({
 *     send: (payload) => sock.send(JSON.stringify(payload)),
 *     canFlush: () => sock.readyState === WebSocket.OPEN && !pendingResync.value,
 *   })
 *   queue.enqueue({ type: 'update', nodes: [...] })
 *   // on receiving update_ack
 *   queue.acknowledge(message.client_op_id)
 *   // on socket open or pendingResync clear
 *   queue.tryFlush()
 */
import { type Ref, computed, ref } from 'vue'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Maximum number of unacked outbound ops the queue will hold before it
 * starts dropping the oldest entry.  Sized for ~30 minutes of disconnect
 * at typical edit rates (~1 op/s).  Memory cost: roughly 2 KB / op.
 */
export const COLLAB_OUTBOUND_QUEUE_MAX_SIZE = 2000

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape of an outbound message expected by the queue. */
export interface CollabOutboundPayload {
  type: string
  [key: string]: unknown
}

/** A queued op with its assigned client_op_id and creation timestamp. */
export interface CollabQueuedOp {
  id: string
  payload: CollabOutboundPayload
  enqueuedAt: number
}

export interface CollabOutboundQueueOptions {
  /** Caller-provided send function — invoked once per flushed op. */
  send: (payload: CollabOutboundPayload & { client_op_id: string }) => void
  /** Returns true when the queue is allowed to flush (e.g. WS open + !pendingResync). */
  canFlush: () => boolean
  /** Optional override for client_op_id generator. */
  generateId?: () => string
  /** Optional max size override. */
  maxSize?: number
  /** Called when the queue must evict because coalescing cannot preserve intent. */
  onOverflow?: (dropped: CollabQueuedOp, maxSize: number) => void
}

/** Extract node IDs referenced by an outbound ``update`` payload (nodes + deletions). */
export function collectNodeIdsFromOutboundPayload(payload: CollabOutboundPayload): string[] {
  const ids: string[] = []
  const nodesRaw = payload.nodes
  if (Array.isArray(nodesRaw)) {
    for (const n of nodesRaw) {
      if (n && typeof n === 'object' && typeof (n as { id?: unknown }).id === 'string') {
        const id = (n as { id: string }).id
        if (id) {
          ids.push(id)
        }
      }
    }
  }
  const delRaw = payload.deleted_node_ids
  if (Array.isArray(delRaw)) {
    for (const x of delRaw) {
      if (typeof x === 'string' && x) {
        ids.push(x)
      }
    }
  }
  return ids
}

export interface CollabOutboundQueue {
  /** Reactive count of unacked queued ops. */
  size: Readonly<Ref<number>>
  /** True when there is at least one queued op. */
  hasPending: Readonly<Ref<boolean>>
  /**
   * Enqueue an outbound payload.  Returns the assigned client_op_id so the
   * caller can correlate with a future ack if it wants to surface UI state
   * (e.g. dim a node until ack arrives).
   *
   * If `canFlush()` is true at enqueue time the op is sent immediately
   * (it is still tracked in the queue until acked).
   */
  enqueue(payload: CollabOutboundPayload): string
  /**
   * Drop a queued op by `client_op_id`.  Called when an `update_ack` is
   * received from the server.  Returns true if the id was found and dropped.
   */
  acknowledge(id: string | null | undefined): boolean
  /** Flush as many pending ops as possible while `canFlush()` stays true. */
  tryFlush(): number
  /** Drop everything (called on hard disconnect / room teardown). */
  clear(): void
  /**
   * Reset all in-flight markers so the next `tryFlush()` re-sends every
   * still-queued op.  Called from the parent on socket reconnect because the
   * server has lost the previous send context.
   */
  resetInFlight(): void
  /** Inspect current contents (for tests / debug). */
  snapshot(): readonly CollabQueuedOp[]
}

// ---------------------------------------------------------------------------
// ID generator
// ---------------------------------------------------------------------------

function defaultGenerateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback for environments without crypto.randomUUID.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

// ---------------------------------------------------------------------------
// Implementation
// ---------------------------------------------------------------------------

export function useCollabOutboundQueue(options: CollabOutboundQueueOptions): CollabOutboundQueue {
  const queue = ref<CollabQueuedOp[]>([])
  // Set of ids that are currently considered "in flight" — i.e. handed off
  // to the WebSocket but not yet acknowledged.  We do not currently distinguish
  // sent-vs-pending in the public API but the set is useful for dedupe and
  // for future "retry timed-out ops" logic.
  const inFlight = new Set<string>()

  const generateId = options.generateId ?? defaultGenerateId
  const maxSize = options.maxSize ?? COLLAB_OUTBOUND_QUEUE_MAX_SIZE

  const size = computed(() => queue.value.length)
  const hasPending = computed(() => queue.value.length > 0)

  function canCoalesceGranularNodeUpdate(payload: CollabOutboundPayload): boolean {
    return (
      payload.type === 'update' &&
      Array.isArray(payload.nodes) &&
      payload.nodes.length === 1 &&
      payload.connections === undefined &&
      payload.deleted_node_ids === undefined &&
      payload.deleted_connection_ids === undefined
    )
  }

  function singleNodeId(payload: CollabOutboundPayload): string | null {
    if (!canCoalesceGranularNodeUpdate(payload)) {
      return null
    }
    const node = (payload.nodes as unknown[])[0]
    if (!node || typeof node !== 'object') {
      return null
    }
    const id = (node as { id?: unknown }).id
    return typeof id === 'string' && id ? id : null
  }

  function coalesceQueuedUpdate(payload: CollabOutboundPayload): string | null {
    const nodeId = singleNodeId(payload)
    if (!nodeId) {
      return null
    }
    for (let i = queue.value.length - 1; i >= 0; i -= 1) {
      const op = queue.value[i]
      if (inFlight.has(op.id)) {
        continue
      }
      if (singleNodeId(op.payload) === nodeId) {
        queue.value.splice(i, 1, {
          ...op,
          payload,
          enqueuedAt: Date.now(),
        })
        return op.id
      }
    }
    return null
  }

  function evictOldestIfFull(): void {
    while (queue.value.length >= maxSize) {
      const dropped = queue.value.shift()
      if (dropped) {
        inFlight.delete(dropped.id)
        options.onOverflow?.(dropped, maxSize)
        if (import.meta.env.DEV) {
          console.warn(
            '[CollabOutboundQueue] queue at cap (%d) — dropping oldest op id=%s',
            maxSize,
            dropped.id
          )
        }
      }
    }
  }

  function enqueue(payload: CollabOutboundPayload): string {
    const coalescedId = coalesceQueuedUpdate(payload)
    if (coalescedId) {
      tryFlush()
      return coalescedId
    }
    evictOldestIfFull()
    const id = generateId()
    queue.value.push({
      id,
      payload,
      enqueuedAt: Date.now(),
    })
    if (import.meta.env.DEV) {
      console.debug('[CollabOutboundQueue] enqueue id=%s size=%d', id, queue.value.length)
    }
    tryFlush()
    return id
  }

  function acknowledge(id: string | null | undefined): boolean {
    let targetId: string | undefined
    if (typeof id === 'string' && id.length > 0) {
      targetId = id
    } else if (queue.value.length > 0) {
      // Legacy server: no ``client_op_id`` on ack — assume FIFO for the one
      // in-flight op at the head (or the first queued op if nothing marked).
      const head = queue.value[0]
      if (inFlight.has(head.id)) {
        targetId = head.id
      }
    }
    if (!targetId) {
      tryFlush()
      return false
    }
    const idx = queue.value.findIndex((op) => op.id === targetId)
    if (idx < 0) {
      tryFlush()
      return false
    }
    queue.value.splice(idx, 1)
    inFlight.delete(targetId)
    if (import.meta.env.DEV) {
      console.debug('[CollabOutboundQueue] ack id=%s remaining=%d', targetId, queue.value.length)
    }
    tryFlush()
    return true
  }

  function tryFlush(): number {
    let flushed = 0
    // Strict FIFO: only the queue head may be sent.  If it is already in
    // flight we wait for `acknowledge` before sending the next op.
    while (queue.value.length > 0 && options.canFlush()) {
      const head = queue.value[0]
      if (inFlight.has(head.id)) {
        break
      }
      try {
        options.send({ ...head.payload, client_op_id: head.id })
        inFlight.add(head.id)
        flushed += 1
        break
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn(
            '[CollabOutboundQueue] send threw for id=%s — leaving in queue',
            head.id,
            err
          )
        }
        break
      }
    }
    return flushed
  }

  function clear(): void {
    if (import.meta.env.DEV && queue.value.length > 0) {
      console.debug('[CollabOutboundQueue] clear (dropping %d queued op(s))', queue.value.length)
    }
    queue.value = []
    inFlight.clear()
  }

  function snapshot(): readonly CollabQueuedOp[] {
    return queue.value.slice()
  }

  function resetInFlight(): void {
    inFlight.clear()
  }

  return {
    size,
    hasPending,
    enqueue,
    acknowledge,
    tryFlush,
    clear,
    resetInFlight,
    snapshot,
  }
}
