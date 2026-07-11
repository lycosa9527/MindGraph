/**
 * Kitty voice → hub → canvas workflow trace (console + event bus; no audio chunks).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { normalizeKittyDebugText } from '@/composables/kitty/kittyAgentDebug'

export type KittyWorkflowLane = 'mobile' | 'desktop' | 'hub'

export interface KittyWorkflowTracePayload {
  lane: KittyWorkflowLane
  stage: string
  detail: string
  scope?: string
  action?: string
  at: number
}

const STORAGE_KEY = 'kitty_workflow_trace'

export function kittyWorkflowTraceEnabled(): boolean {
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
  const row: KittyWorkflowTracePayload = {
    lane,
    stage,
    detail: normalizeKittyDebugText(detail, 240),
    scope: options?.scope,
    action: options?.action,
    at: Date.now(),
  }
  eventBus.emit('kitty:workflow_trace', row)
  if (!kittyWorkflowTraceEnabled()) {
    return
  }
  const scopePart = row.scope ? ` scope=${row.scope.slice(0, 12)}` : ''
  const actionPart = row.action ? ` action=${row.action}` : ''
  const verifiedPart =
    typeof options?.verified === 'boolean' ? ` verified=${String(options.verified)}` : ''
  const hubPart =
    typeof options?.hubPersistOk === 'boolean'
      ? ` hubPersistOk=${String(options.hubPersistOk)}`
      : ''
  const line = `[KittyWF:${lane}] ${stage}${actionPart}${scopePart}${verifiedPart}${hubPart} | ${row.detail}`
  console.debug(line)
}
