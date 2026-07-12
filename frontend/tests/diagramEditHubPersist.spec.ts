import { afterEach, describe, expect, it, vi } from 'vitest'

import { eventBus } from '@/composables/core/useEventBus'
import {
  persistVerifiedDiagramToHub,
  waitForContextMutationAck,
} from '@/composables/kitty/diagramEditHubPersist'

describe('diagramEditHubPersist', () => {
  afterEach(() => {
    eventBus.off('voice:context_mutation_ack')
  })

  it('waitForContextMutationAck resolves on matching ack', async () => {
    const promise = waitForContextMutationAck({ expectedRevision: 2, timeoutMs: 500 })
    eventBus.emit('voice:context_mutation_ack', { ok: true, revision: 3 })
    const result = await promise
    expect(result.ok).toBe(true)
    expect(result.revision).toBe(3)
  })

  it('waitForContextMutationAck ignores duplicate same-revision ack', async () => {
    const promise = waitForContextMutationAck({ expectedRevision: 2, timeoutMs: 80 })
    eventBus.emit('voice:context_mutation_ack', { ok: true, revision: 2 })
    const result = await promise
    expect(result.ok).toBe(false)
    expect(result.error).toBe('hub_persist_timeout')
  })

  it('waitForContextMutationAck accepts same-revision ack when idempotency key matches', async () => {
    const promise = waitForContextMutationAck({
      expectedRevision: 12,
      idempotencyKey: 'kitty-hub-sync-scope-abc',
      timeoutMs: 500,
    })
    eventBus.emit('voice:context_mutation_ack', {
      ok: true,
      revision: 12,
      idempotency_key: 'kitty-hub-sync-scope-abc',
    })
    const result = await promise
    expect(result.ok).toBe(true)
    expect(result.revision).toBe(12)
  })

  it('waitForContextMutationAck accepts hub stale-revision retry suffix on idempotency key', async () => {
    const promise = waitForContextMutationAck({
      idempotencyKey: 'kitty-hub-sync-scope-abc',
      timeoutMs: 500,
    })
    eventBus.emit('voice:context_mutation_ack', {
      ok: true,
      revision: 4,
      idempotency_key: 'kitty-hub-sync-scope-abc-retry',
    })
    const result = await promise
    expect(result.ok).toBe(true)
    expect(result.revision).toBe(4)
  })

  it('waitForContextMutationAck ignores ack with mismatched idempotency key', async () => {
    const promise = waitForContextMutationAck({
      idempotencyKey: 'kitty-hub-sync-scope-abc',
      timeoutMs: 80,
    })
    eventBus.emit('voice:context_mutation_ack', {
      ok: true,
      revision: 9,
      idempotency_key: 'kitty-mobile-persist-other',
    })
    const result = await promise
    expect(result.ok).toBe(false)
    expect(result.error).toBe('hub_persist_timeout')
  })

  it('waitForContextMutationAck accepts Hub revision reset below expected', async () => {
    const promise = waitForContextMutationAck({ expectedRevision: 5, timeoutMs: 500 })
    eventBus.emit('voice:context_mutation_ack', { ok: true, revision: 1 })
    const result = await promise
    expect(result.ok).toBe(true)
    expect(result.revision).toBe(1)
  })

  it('waitForContextMutationAck times out when no ack', async () => {
    const result = await waitForContextMutationAck({ timeoutMs: 30 })
    expect(result.ok).toBe(false)
    expect(result.error).toBe('hub_persist_timeout')
  })

  it('persistVerifiedDiagramToHub sends context_update then awaits ack', async () => {
    const updateContext = vi.fn()
    const buildContext = vi.fn(() => ({
      diagram_type: 'mindmap',
      active_panel: 'none',
      selected_nodes: [],
      diagram_data: { children: [] },
    }))

    const promise = persistVerifiedDiagramToHub({
      buildContext,
      updateContext,
      hubScopeRevision: 1,
      scope: 'scope-abc',
      timeoutMs: 500,
    })

    expect(updateContext).toHaveBeenCalledTimes(1)
    const syncOpts = updateContext.mock.calls[0]?.[1] as { idempotencyKey?: string }
    expect(syncOpts?.idempotencyKey).toMatch(/^kitty-hub-sync-scope-abc-/)
    eventBus.emit('voice:context_mutation_ack', {
      ok: true,
      revision: 2,
      idempotency_key: syncOpts?.idempotencyKey,
    })

    const result = await promise
    expect(result.ok).toBe(true)
    expect(result.revision).toBe(2)
  })
})
