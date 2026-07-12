/**
 * Action journal + mutation step protocol helpers (S10–S13, S15).
 */
import { recordPipelineEvent, failKittyTurn } from '@/composables/kitty/pipeline/trace'
import type { KittyTurnContext } from '@/composables/kitty/pipeline/types'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'
import { resolveKittyErrorCode } from '@/composables/kitty/pipeline/errorCatalog'

export function recordKittyMutationApply(options: {
  ctx: KittyTurnContext
  action: string
  ok: boolean
  errorCode?: string
  summary?: string
  nodeIds?: string[]
  verified?: boolean
  hubPersistOk?: boolean
  ackOk?: boolean
}): void {
  const store = useKittyPipelineStore()
  recordPipelineEvent({
    ctx: options.ctx,
    module: 'mutation',
    step: 'S10_mutation_apply',
    status: options.ok ? 'ok' : 'fail',
    errorCode: options.ok ? undefined : resolveKittyErrorCode(options.errorCode ?? 'apply_failed'),
    detail: options.action,
  })

  if (options.ok && options.verified !== false) {
    recordPipelineEvent({
      ctx: options.ctx,
      module: 'mutation',
      step: 'S11_mutation_verify',
      status: 'ok',
      detail: options.summary?.slice(0, 80),
    })
  } else if (options.verified === false) {
    failKittyTurn({
      ctx: options.ctx,
      module: 'mutation',
      step: 'S11_mutation_verify',
      errorCode: resolveKittyErrorCode(options.errorCode ?? 'verify_failed'),
      detail: options.summary,
    })
  }

  if (options.hubPersistOk === true) {
    recordPipelineEvent({
      ctx: options.ctx,
      module: 'hub_sync',
      step: 'S12_post_hub_persist',
      status: 'ok',
    })
  } else if (options.hubPersistOk === false) {
    failKittyTurn({
      ctx: options.ctx,
      module: 'hub_sync',
      step: 'S12_post_hub_persist',
      errorCode: 'post_hub_persist_failed',
    })
  }

  if (options.ackOk === true) {
    recordPipelineEvent({
      ctx: options.ctx,
      module: 'mutation',
      step: 'S13_mutation_ack',
      status: 'ok',
    })
  } else if (options.ackOk === false) {
    recordPipelineEvent({
      ctx: options.ctx,
      module: 'mutation',
      step: 'S13_mutation_ack',
      status: 'fail',
      errorCode: 'ack_send_failed',
    })
  }

  store.appendActionJournal({
    requestId: options.ctx.requestId,
    scope: options.ctx.scope,
    action: options.action,
    ok: options.ok && options.verified !== false,
    summary: options.summary,
    errorCode: options.errorCode,
    nodeIds: options.nodeIds,
    at: Date.now(),
  })
}

export function resolveTurnCtxFromActive(fallbackScope: string, lane: 'mobile' | 'desktop'): KittyTurnContext {
  const store = useKittyPipelineStore()
  if (store.activeTurn) {
    return { ...store.activeTurn }
  }
  return {
    requestId: `mutation-${Date.now()}`,
    scope: fallbackScope || 'scope',
    lane,
  }
}
