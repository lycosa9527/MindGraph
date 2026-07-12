/**
 * Hub sync worker — Redis live_spec via syncKittyHubContext (S07 / S12).
 */
import { getActivePinia } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import type {
  KittyAgentContext,
  KittyContextUpdateOptions,
} from '@/composables/kitty/kittyAgentTypes'
import {
  KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS,
  KITTY_HUB_EDIT_GATE_TIMEOUT_MS,
  syncKittyHubContext,
} from '@/composables/kitty/syncKittyHubContext'
import { failKittyTurn, recordPipelineEvent } from '@/composables/kitty/pipeline/trace'
import type { KittyStep, KittyTurnContext } from '@/composables/kitty/pipeline/types'
import { resolveKittyErrorCode } from '@/composables/kitty/pipeline/errorCatalog'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'
import { useKittySessionStore } from '@/stores/kittySession'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { useDiagramStore } from '@/stores/diagram'

export type KittyHubSyncWorkerDeps = {
  buildContext: () => KittyAgentContext
  updateContext: (context: KittyAgentContext, options?: KittyContextUpdateOptions) => void
  getScope: () => string | null | undefined
  isConnected: () => boolean
  lane: 'mobile' | 'desktop'
}

let fingerprintDebounce: ReturnType<typeof setTimeout> | null = null
let lastHubFingerprint = ''

export async function runKittyHubSync(options: {
  deps: KittyHubSyncWorkerDeps
  ctx: KittyTurnContext
  reason: 'edit_gate' | 'background' | 'post_mutation'
  step?: KittyStep
  timeoutMs?: number
}): Promise<{ ok: boolean; revision?: number; errorCode?: string }> {
  const step: KittyStep =
    options.step ??
    (options.reason === 'post_mutation' ? 'S12_post_hub_persist' : 'S07_hub_sync')
  const timeoutMs =
    options.timeoutMs ??
    (options.reason === 'edit_gate'
      ? KITTY_HUB_EDIT_GATE_TIMEOUT_MS
      : KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS)
  const pipeline = getActivePinia() ? useKittyPipelineStore() : null
  const kittySession = useKittySessionStore()

  if (options.reason === 'background' && pipeline?.editPipelineActive) {
    recordPipelineEvent({
      ctx: options.ctx,
      module: 'hub_sync',
      step,
      status: 'skip',
      detail: 'deferred editPipelineActive',
    })
    return { ok: false, errorCode: 'hub_persist_skipped' }
  }

  if (options.reason === 'edit_gate') {
    pipeline?.setPhase('hub_syncing')
  }

  recordPipelineEvent({
    ctx: options.ctx,
    module: 'hub_sync',
    step,
    status: 'started',
    detail: options.reason,
  })
  eventBus.emit('kitty:hub_sync_requested', {
    ctx: options.ctx,
    reason: options.reason,
  })

  const result = await syncKittyHubContext({
    buildContext: options.deps.buildContext,
    updateContext: options.deps.updateContext,
    hubScopeRevision: kittySession.hubScopeRevision,
    setHubScopeRevision: (rev) => kittySession.setHubScopeRevision(rev),
    scope: options.deps.getScope(),
    isConnected: options.deps.isConnected(),
    timeoutMs,
    debugLabel: options.reason,
  })

  if (result.ok) {
    recordPipelineEvent({
      ctx: options.ctx,
      module: 'hub_sync',
      step,
      status: 'ok',
      detail: `rev=${result.revision ?? '?'}`,
    })
    return { ok: true, revision: result.revision }
  }

  const errorCode = resolveKittyErrorCode(result.error)
  if (options.reason === 'edit_gate') {
    failKittyTurn({
      ctx: options.ctx,
      module: 'hub_sync',
      step,
      errorCode,
      detail: result.error,
    })
  } else {
    recordPipelineEvent({
      ctx: options.ctx,
      module: 'hub_sync',
      step,
      status: 'fail',
      errorCode,
      detail: result.error,
    })
  }
  return { ok: false, errorCode }
}

export function scheduleKittyHubContextSync(
  deps: KittyHubSyncWorkerDeps,
  options?: { debounceMs?: number; ctx?: KittyTurnContext }
): void {
  const debounceMs = options?.debounceMs ?? 500
  if (fingerprintDebounce != null) {
    clearTimeout(fingerprintDebounce)
  }
  fingerprintDebounce = setTimeout(() => {
    fingerprintDebounce = null
    if (getActivePinia() && useKittyPipelineStore().editPipelineActive) {
      return
    }
    if (!deps.isConnected()) {
      return
    }
    const diagramStore = useDiagramStore()
    const fingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
    if (!fingerprint || fingerprint === lastHubFingerprint) {
      return
    }
    const ctx =
      options?.ctx ??
      ({
        requestId: `hub-bg-${Date.now()}`,
        scope: deps.getScope()?.trim() || 'scope',
        lane: deps.lane,
      } satisfies KittyTurnContext)
    void runKittyHubSync({
      deps,
      ctx,
      reason: 'background',
    }).then((r) => {
      if (r.ok) {
        lastHubFingerprint = fingerprint
      }
    })
  }, debounceMs)
}

export function resetKittyHubSyncFingerprint(): void {
  lastHubFingerprint = ''
}

export function markKittyHubSyncFingerprint(fingerprint: string): void {
  lastHubFingerprint = fingerprint
}
