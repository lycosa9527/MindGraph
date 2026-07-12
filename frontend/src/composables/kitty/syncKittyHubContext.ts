/**
 * Push Pinia canvas truth to Agent Hub (Redis live_spec) via Kitty WS context_update.
 * Used by desktop edit-gate / background hub sync. Mobile edit turns skip this gate.
 * Pipeline Eruda/status comes from hubSyncWorker → recordPipelineEvent (#trace), not #hub.
 */
import type {
  KittyAgentContext,
  KittyContextUpdateOptions,
} from '@/composables/kitty/kittyAgentTypes'
import {
  type HubPersistResult,
  persistVerifiedDiagramToHub,
} from '@/composables/kitty/diagramEditHubPersist'

/** Pre-edit gate: must finish before sendTextMessage; matches BE diagram_edit budget. */
export const KITTY_HUB_EDIT_GATE_TIMEOUT_MS = 8000

/** Debounced / background sync while connected. */
export const KITTY_HUB_BACKGROUND_SYNC_TIMEOUT_MS = 3000

export type KittyHubContextSyncDeps = {
  buildContext: () => KittyAgentContext
  updateContext: (context: KittyAgentContext, options?: KittyContextUpdateOptions) => void
  hubScopeRevision: number | null
  setHubScopeRevision: (revision: number) => void
  scope?: string | null
  isConnected: boolean
  timeoutMs?: number
  /** Label retained for callers/tests; protocol worker owns user-visible tracing. */
  debugLabel?: string
}

/**
 * Sync current diagram context to Agent Hub and wait for context_mutation_ack.
 * Writes Redis live_spec only; Postgres library snapshot persist is owned by
 * desktop canvas mutation apply (diagramEditApply hubPersist), not mobile.
 */
export async function syncKittyHubContext(
  deps: KittyHubContextSyncDeps
): Promise<HubPersistResult> {
  if (!deps.isConnected) {
    return { ok: false, error: 'not_connected' }
  }

  const result = await persistVerifiedDiagramToHub({
    buildContext: deps.buildContext,
    updateContext: deps.updateContext,
    hubScopeRevision: deps.hubScopeRevision,
    scope: deps.scope,
    timeoutMs: deps.timeoutMs,
  })

  if (result.ok && typeof result.revision === 'number') {
    deps.setHubScopeRevision(result.revision)
  }

  return result
}
