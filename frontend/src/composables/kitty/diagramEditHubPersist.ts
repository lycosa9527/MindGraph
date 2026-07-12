/**
 * After verified canvas apply: persist Pinia truth to Agent Hub via context_update.
 */
import { eventBus } from '@/composables/core/useEventBus'
import type {
  KittyAgentContext,
  KittyContextUpdateOptions,
} from '@/composables/kitty/kittyAgentTypes'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type HubPersistResult = {
  ok: boolean
  revision?: number
  error?: string
}

export type DiagramHubPersistDeps = {
  buildContext: () => KittyAgentContext
  updateContext: (context: KittyAgentContext, options?: KittyContextUpdateOptions) => void
  hubScopeRevision: number | null
  scope?: string | null
  timeoutMs?: number
}

const DEFAULT_HUB_PERSIST_TIMEOUT_MS = 3000
/** Must stay below BE diagram_edit ack timeout (8s) so the client can still send diagram_mutation_ack. */

export function waitForContextMutationAck(options: {
  expectedRevision?: number
  idempotencyKey?: string
  timeoutMs?: number
}): Promise<HubPersistResult> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_HUB_PERSIST_TIMEOUT_MS
  const syncKey = options.idempotencyKey?.trim() ?? ''

  return new Promise((resolve) => {
    let settled = false
    const settle = (result: HubPersistResult): void => {
      if (settled) {
        return
      }
      settled = true
      eventBus.off('voice:context_mutation_ack', onAck)
      clearTimeout(timer)
      resolve(result)
    }

    const ackKeyMatches = (data: { idempotency_key?: string }): boolean => {
      if (!syncKey) {
        return true
      }
      const ackKey = typeof data.idempotency_key === 'string' ? data.idempotency_key.trim() : ''
      return ackKey === syncKey || ackKey === `${syncKey}-retry`
    }

    const onAck = (data: {
      ok?: boolean
      revision?: number
      error?: string
      library_snapshot_error?: string
      idempotency_key?: string
    }): void => {
      if (syncKey && !ackKeyMatches(data)) {
        return
      }
      if (data.ok === false) {
        settle({
          ok: false,
          error: data.error ?? data.library_snapshot_error ?? 'context_mutation_rejected',
        })
        return
      }
      const revision = typeof data.revision === 'number' ? data.revision : undefined
      if (syncKey) {
        settle({ ok: true, revision })
        return
      }
      // Ignore duplicate acks at the same known revision. Accept a *lower*
      // revision as a Hub/session reset (e.g. Kitty WS reconnected → rev=1
      // while the FE still held a stale expectedRevision from before).
      if (
        options.expectedRevision != null &&
        revision != null &&
        revision === options.expectedRevision
      ) {
        return
      }
      settle({ ok: true, revision })
    }

    const timer = setTimeout(() => {
      settle({ ok: false, error: 'hub_persist_timeout' })
    }, timeoutMs)

    eventBus.on('voice:context_mutation_ack', onAck)
  })
}

export async function persistVerifiedDiagramToHub(
  deps: DiagramHubPersistDeps
): Promise<HubPersistResult> {
  const ctx = deps.buildContext()
  const expectedRevision = deps.hubScopeRevision ?? undefined
  const scopeHint = deps.scope?.trim() || 'scope'
  const idempotencyKey = `kitty-hub-sync-${scopeHint}-${safeRandomUUID()}`
  const waitPromise = waitForContextMutationAck({
    expectedRevision,
    idempotencyKey,
    timeoutMs: deps.timeoutMs,
  })

  deps.updateContext(ctx, {
    expectedRevision: deps.hubScopeRevision ?? undefined,
    idempotencyKey,
  })

  const result = await waitPromise
  if (result.ok && deps.scope?.trim()) {
    // Owning tab already holds Pinia SoT — observers recover; owner must not reload.
    eventBus.emit('kitty:hub_diagram_persisted', {
      scope: deps.scope.trim(),
      revision: result.revision,
      source: 'owning_tab',
    })
  }
  return result
}
