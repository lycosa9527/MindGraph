/**
 * Kitty pipeline protocol recorder — single write path for status, logs, bus, fails.
 */
import { getActivePinia } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import {
  getKittyErrorCatalogEntry,
  resolveKittyErrorCode,
  resolveKittyFailMessage,
} from '@/composables/kitty/pipeline/errorCatalog'
import type {
  KittyErrorCode,
  KittyModule,
  KittyPipelineEvent,
  KittyPipelineEventStatus,
  KittyStep,
  KittyTurnContext,
  KittyTurnFail,
  KittyTurnStatus,
} from '@/composables/kitty/pipeline/types'
import { normalizeKittyDebugText } from '@/composables/kitty/kittyAgentDebug'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'

const STORAGE_KEY = 'kitty_workflow_trace'

export function kittyPipelineTraceEnabled(): boolean {
  if (typeof window === 'undefined') {
    return false
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw === '1' || raw === 'verbose'
  } catch {
    return false
  }
}

function formatPipelineLogLine(event: KittyPipelineEvent): string {
  const req = event.ctx.requestId.slice(0, 8)
  const utt = event.ctx.utteranceId ? ` utt=${event.ctx.utteranceId.slice(0, 12)}` : ''
  const scope = event.ctx.scope ? ` scope=${event.ctx.scope.slice(0, 12)}` : ''
  const code = event.errorCode ? ` code=${event.errorCode}` : ''
  const dur =
    typeof event.durationMs === 'number' && event.durationMs >= 0
      ? ` dur=${event.durationMs}ms`
      : ''
  const detail = event.detail ? ` | ${normalizeKittyDebugText(event.detail, 200)}` : ''
  return (
    `[KittyWF] lane=${event.ctx.lane} module=${event.module} step=${event.step}` +
    ` status=${event.status}${code} request=${req}${utt}${scope}${dur}${detail}`
  )
}

export function recordPipelineEvent(input: {
  ctx: KittyTurnContext
  module: KittyModule
  step: KittyStep
  status: KittyPipelineEventStatus
  errorCode?: KittyErrorCode | string
  detail?: string
  at?: number
  durationMs?: number
}): KittyPipelineEvent {
  const at = input.at ?? Date.now()
  let durationMs = input.durationMs
  let store: ReturnType<typeof useKittyPipelineStore> | null = null
  if (getActivePinia()) {
    store = useKittyPipelineStore()
  }
  if (durationMs == null && input.status !== 'started' && store) {
    const started = store.getStepStartedAt(input.step)
    if (started != null) {
      durationMs = Math.max(0, at - started)
    }
  }
  const errorCode =
    input.status === 'fail'
      ? resolveKittyErrorCode(
          typeof input.errorCode === 'string' ? input.errorCode : input.errorCode
        )
      : undefined

  const event: KittyPipelineEvent = {
    ctx: { ...input.ctx },
    module: input.module,
    step: input.step,
    status: input.status,
    errorCode,
    detail: input.detail ? normalizeKittyDebugText(input.detail, 240) : undefined,
    at,
    durationMs,
  }

  store?.appendStepEvent(event)
  eventBus.emit('kitty:pipeline_step', event)

  if (kittyPipelineTraceEnabled()) {
    console.debug(formatPipelineLogLine(event))
  }

  return event
}

export function failKittyTurn(input: {
  ctx: KittyTurnContext
  module: KittyModule
  step: KittyStep
  errorCode: KittyErrorCode | string
  detail?: string
}): KittyTurnFail {
  const errorCode = resolveKittyErrorCode(input.errorCode)
  const event = recordPipelineEvent({
    ctx: input.ctx,
    module: input.module,
    step: input.step,
    status: 'fail',
    errorCode,
    detail: input.detail,
  })
  const fail: KittyTurnFail = {
    requestId: input.ctx.requestId,
    module: input.module,
    step: input.step,
    errorCode,
    detail: event.detail,
    at: event.at,
  }
  eventBus.emit('kitty:turn_failed', {
    ctx: input.ctx,
    module: input.module,
    step: input.step,
    errorCode,
    detail: event.detail,
  })
  return fail
}

export function completeKittyTurn(ctx: KittyTurnContext, lastStep: KittyStep): void {
  recordPipelineEvent({
    ctx,
    module: 'edit_pipeline',
    step: lastStep,
    status: 'ok',
    detail: 'turn completed',
  })
  eventBus.emit('kitty:turn_completed', { ctx, lastStep })
  if (!getActivePinia()) {
    return
  }
  const store = useKittyPipelineStore()
  store.completeTurn(lastStep)
  window.setTimeout(() => {
    if (store.activeTurn?.requestId === ctx.requestId && store.pipelinePhase === 'completed') {
      store.resetToIdle()
    }
  }, 50)
}

export function beginKittyTurn(ctx: KittyTurnContext): void {
  if (!getActivePinia()) {
    return
  }
  useKittyPipelineStore().beginTurn(ctx)
}

export function getTurnStatus(requestId?: string): KittyTurnStatus {
  if (!getActivePinia()) {
    return {
      phase: 'idle',
      module: null,
      step: null,
      completedSteps: [],
    }
  }
  return useKittyPipelineStore().getTurnStatus(requestId)
}

export function getLastFail(): KittyTurnFail | null {
  if (!getActivePinia()) {
    return null
  }
  return useKittyPipelineStore().getLastFail()
}

export function dumpTurnTrace(requestId: string): KittyPipelineEvent[] {
  if (!getActivePinia()) {
    return []
  }
  return useKittyPipelineStore().dumpTurnTrace(requestId)
}

export function messageForKittyFail(
  fail: KittyTurnFail,
  t: (key: string, fallbackOrParams?: string | Record<string, string>) => string
): string {
  return resolveKittyFailMessage(fail.errorCode, t, fail.detail)
}

export function catalogEntryForCode(errorCode: KittyErrorCode) {
  return getKittyErrorCatalogEntry(errorCode)
}
