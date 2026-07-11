/**
 * Single FE diagram mutation apply path — inbound emits bus events only.
 */
import { eventBus } from '@/composables/core/useEventBus'
import { applyVerifiedDiagramUpdate } from '@/composables/kitty/diagramEditApply'
import { applyKittyDiagramUpdate } from '@/composables/kitty/kittyAgentActions'
import { reportKittyDiagramEditFailure } from '@/composables/kitty/kittyDiagramEditFeedback'
import { formatKittyDiagramUpdateDebug } from '@/composables/kitty/kittyAgentDebug'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import type { DiagramEditExpectedEffect } from '@/utils/diagramEditVerify'
import type { Connection, DiagramNode } from '@/types'
import { useKittySessionStore } from '@/stores/kittySession'

export type KittyDiagramMutationRequest = {
  action: string
  updates: Record<string, unknown>
  mutationId?: string
  userSummary?: string
  expectedEffect?: DiagramEditExpectedEffect
  beforeFingerprint?: { nodes: DiagramNode[]; connections: Connection[] }
  sendAck?: (payload: Record<string, unknown>) => void
  hubPersist?: {
    buildContext: () => import('@/composables/kitty/kittyAgentTypes').KittyAgentContext
    updateContext: (
      context: import('@/composables/kitty/kittyAgentTypes').KittyAgentContext,
      options?: import('@/composables/kitty/kittyAgentTypes').KittyContextUpdateOptions
    ) => void
    scope?: string | null
  }
  lane?: 'mobile' | 'desktop'
}

function onKittyDiagramMutationRequested(
  payload: KittyDiagramMutationRequest
): void {
  void applyKittyDiagramMutationRequest(payload)
}

/** Idempotent: safe under Vite HMR (off then on with stable handler ref). */
export function registerKittyDiagramMutationBus(): void {
  eventBus.off('kitty:diagram_mutation_requested', onKittyDiagramMutationRequested)
  eventBus.on('kitty:diagram_mutation_requested', onKittyDiagramMutationRequested)
}

async function applyKittyDiagramMutationRequest(
  payload: KittyDiagramMutationRequest
): Promise<void> {
  const diagramAction = payload.action
  const diagramUpdates = payload.updates
  const mutationId = payload.mutationId?.trim() ?? ''
  const userSummary = payload.userSummary?.trim() ?? ''
  const summary =
    userSummary !== ''
      ? userSummary
      : formatKittyDiagramUpdateDebug(diagramAction, diagramUpdates)
  const kittySession = useKittySessionStore()
  const lane = payload.lane ?? 'mobile'

    if (mutationId !== '') {
      const sendAck =
        payload.sendAck ??
        ((_ackPayload: Record<string, unknown>) => {
          /* verified mutation without WS ack sink — still apply Pinia */
        })
      const applyResult = await applyVerifiedDiagramUpdate(diagramAction, diagramUpdates, {
        mutationId,
        expectedEffect: payload.expectedEffect,
        beforeFingerprint: payload.beforeFingerprint,
        sendAck,
        hubRevision: kittySession.hubScopeRevision,
        hubPersist: payload.hubPersist
          ? {
              buildContext: payload.hubPersist.buildContext,
              updateContext: payload.hubPersist.updateContext,
              hubScopeRevision: kittySession.hubScopeRevision,
              scope: payload.hubPersist.scope ?? null,
            }
          : undefined,
      })

      if (applyResult.verified) {
        eventBus.emit('voice:diagram_update_executed', {
          action: diagramAction,
          updates: diagramUpdates,
          summary,
          userSummary: userSummary !== '' ? userSummary : summary,
          verified: true,
        })
      } else {
        const errorCode = applyResult.verificationError ?? 'verify_failed'
        eventBus.emit('voice:diagram_update_executed', {
          action: diagramAction,
          updates: diagramUpdates,
          summary: errorCode,
          verified: false,
          errorCode,
        })
        reportKittyDiagramEditFailure({
          action: diagramAction,
          errorCode,
          message: applyResult.verificationError,
          scope: payload.hubPersist?.scope ?? null,
          lane,
        })
      }
      traceKittyWorkflow(lane, 'diagram_ws', summary, {
        action: diagramAction,
        verified: applyResult.verified,
        hubPersistOk: applyResult.hubPersistOk,
      })
      return
    }

  eventBus.emit('voice:diagram_update_executed', {
    action: diagramAction,
    updates: diagramUpdates,
    summary,
    userSummary: userSummary !== '' ? userSummary : undefined,
  })
  traceKittyWorkflow(lane, 'diagram_ws', summary, { action: diagramAction })
  applyKittyDiagramUpdate(diagramAction, diagramUpdates)
}
