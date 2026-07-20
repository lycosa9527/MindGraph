/**
 * Single FE diagram mutation apply path — inbound emits bus events only.
 */
import { eventBus } from '@/composables/core/useEventBus'
import { applyVerifiedDiagramUpdate } from '@/composables/kitty/diagramEditApply'
import { applyKittyDiagramUpdate } from '@/composables/kitty/kittyAgentActions'
import { reportKittyDiagramEditFailure } from '@/composables/kitty/kittyDiagramEditFeedback'
import { formatKittyDiagramUpdateDebug } from '@/composables/kitty/kittyAgentDebug'
import {
  recordKittyMutationApply,
  resolveTurnCtxFromActive,
} from '@/composables/kitty/pipeline/actionJournal'
import { markKittyServerStepOk } from '@/composables/kitty/pipeline/editTurn'
import { traceKittyWorkflow } from '@/composables/kitty/kittyWorkflowTrace'
import type { DiagramEditExpectedEffect } from '@/utils/diagramEditVerify'
import type { Connection, DiagramNode } from '@/types'
import { useDiagramStore } from '@/stores/diagram'
import { useKittySessionStore } from '@/stores/kittySession'

function collabBlocksKittyDiagramEdits(): boolean {
  const diagramStore = useDiagramStore()
  return diagramStore.collabSessionActive === true && diagramStore.type !== 'concept_map'
}

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
  const ctx = resolveTurnCtxFromActive(payload.hubPersist?.scope?.trim() ?? 'scope', lane)
  markKittyServerStepOk(ctx, diagramAction)

    if (mutationId !== '') {
      const sendAck =
        payload.sendAck ??
        useKittySessionStore().getMutationAckSender() ??
        ((_ackPayload: Record<string, unknown>) => {
          /* verified mutation without WS ack sink — still apply Pinia */
        })
      if (!useKittySessionStore().claimMutationId(mutationId)) {
        return
      }
      if (collabBlocksKittyDiagramEdits()) {
        sendAck({
          type: 'diagram_mutation_ack',
          mutation_id: mutationId,
          verified: false,
          ok: false,
          error_code: 'collab_active',
          message: 'Kitty edits paused during live collaboration',
        })
        recordKittyMutationApply({
          ctx,
          action: diagramAction,
          ok: false,
          verified: false,
          ackOk: true,
          errorCode: 'collab_active',
          summary,
        })
        eventBus.emit('voice:diagram_update_executed', {
          action: diagramAction,
          updates: diagramUpdates,
          summary: 'collab_active',
          verified: false,
          errorCode: 'collab_active',
        })
        reportKittyDiagramEditFailure({
          action: diagramAction,
          errorCode: 'collab_active',
          scope: payload.hubPersist?.scope ?? null,
          lane,
        })
        traceKittyWorkflow(lane, 'diagram_ws', 'collab_active', {
          action: diagramAction,
          verified: false,
        })
        return
      }
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

      recordKittyMutationApply({
        ctx,
        action: diagramAction,
        ok: applyResult.verified,
        verified: applyResult.verified,
        hubPersistOk: applyResult.hubPersistOk,
        ackOk: true,
        errorCode: applyResult.verificationError,
        summary,
      })

      if (applyResult.verified) {
        // Do not fall back to debug ``summary`` for chat — multi-step chains omit
        // user_summary so coalesced progress/done acks own the conversation.
        eventBus.emit('voice:diagram_update_executed', {
          action: diagramAction,
          updates: diagramUpdates,
          summary,
          userSummary: userSummary !== '' ? userSummary : undefined,
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
  recordKittyMutationApply({
    ctx,
    action: diagramAction,
    ok: true,
    verified: true,
    summary,
  })
  traceKittyWorkflow(lane, 'diagram_ws', summary, { action: diagramAction })
  applyKittyDiagramUpdate(diagramAction, diagramUpdates)
}
