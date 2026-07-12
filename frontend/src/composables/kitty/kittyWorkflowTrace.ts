/**
 * Kitty workflow trace — compat bus for non-pipeline debug lines.
 * Pipeline status must use recordPipelineEvent / failKittyTurn only.
 * This shim must not write the pipeline store (avoids polluting mid-turn status).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { normalizeKittyDebugText } from '@/composables/kitty/kittyAgentDebug'
import { kittyPipelineTraceEnabled } from '@/composables/kitty/pipeline/trace'

export type KittyWorkflowLane = 'mobile' | 'desktop' | 'hub'

export interface KittyWorkflowTracePayload {
  lane: KittyWorkflowLane
  stage: string
  detail: string
  scope?: string
  action?: string
  at: number
}

export function kittyWorkflowTraceEnabled(): boolean {
  return kittyPipelineTraceEnabled()
}

/**
 * @deprecated Prefer recordPipelineEvent / failKittyTurn from pipeline protocol.
 * Emits kitty:workflow_trace only — does not append pipeline steps.
 */
export function traceKittyWorkflow(
  lane: KittyWorkflowLane,
  stage: string,
  detail: string,
  options?: {
    scope?: string
    action?: string
    verified?: boolean
    hubPersistOk?: boolean
  }
): void {
  const at = Date.now()
  const row: KittyWorkflowTracePayload = {
    lane,
    stage,
    detail: normalizeKittyDebugText(detail, 240),
    scope: options?.scope,
    action: options?.action,
    at,
  }
  eventBus.emit('kitty:workflow_trace', row)

  if (kittyPipelineTraceEnabled()) {
    const scope = options?.scope ? ` scope=${options.scope.slice(0, 12)}` : ''
    const action = options?.action ? ` action=${options.action}` : ''
    console.debug(
      `[KittyWF:legacy] lane=${lane} stage=${stage}${scope}${action} | ${row.detail}`
    )
  }
}
