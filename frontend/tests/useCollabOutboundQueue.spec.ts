import { describe, expect, it, vi } from 'vitest'

import {
  COLLAB_OUTBOUND_QUEUE_MAX_SIZE,
  collectNodeIdsFromOutboundPayload,
  useCollabOutboundQueue,
} from '@/composables/workshop/useCollabOutboundQueue'

describe('collectNodeIdsFromOutboundPayload', () => {
  it('collects node ids and deleted ids', () => {
    expect(
      collectNodeIdsFromOutboundPayload({
        type: 'update',
        nodes: [{ id: 'a' }, { id: 'b' }],
        deleted_node_ids: ['c'],
      }),
    ).toEqual(['a', 'b', 'c'])
  })
})

describe('useCollabOutboundQueue', () => {
  it('sends head only until ack, then next op', () => {
    const sent: string[] = []
    const q = useCollabOutboundQueue({
      send: (p) => {
        sent.push(String(p.client_op_id))
      },
      canFlush: () => true,
    })
    const id1 = q.enqueue({ type: 'update', nodes: [] })
    const id2 = q.enqueue({ type: 'update', nodes: [] })
    expect(sent).toEqual([id1])
    q.acknowledge(id1)
    expect(sent).toEqual([id1, id2])
  })

  it('replays after resetInFlight', () => {
    const payloads: string[] = []
    const q = useCollabOutboundQueue({
      send: (p) => payloads.push(p.client_op_id as string),
      canFlush: () => true,
    })
    const id1 = q.enqueue({ type: 'update', nodes: [] })
    q.resetInFlight()
    q.tryFlush()
    expect(payloads.filter((x) => x === id1).length).toBe(2)
  })

  it('legacy ack without id dequeues head when in flight', () => {
    const q = useCollabOutboundQueue({
      send: () => {},
      canFlush: () => true,
    })
    q.enqueue({ type: 'update', nodes: [] })
    q.acknowledge(null)
    expect(q.size.value).toBe(0)
  })

  it('evicts oldest at max cap', () => {
    const q = useCollabOutboundQueue({
      send: () => {},
      canFlush: () => false,
      maxSize: 3,
    })
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    for (let i = 0; i < 5; i++) {
      q.enqueue({ type: 'update', i })
    }
    expect(q.size.value).toBe(3)
    warn.mockRestore()
  })

  it('respects max export constant', () => {
    expect(COLLAB_OUTBOUND_QUEUE_MAX_SIZE).toBeGreaterThan(100)
  })
})
