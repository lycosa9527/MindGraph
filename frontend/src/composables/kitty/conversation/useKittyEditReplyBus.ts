/**
 * Shared Kitty edit reply / mutation outcome handlers for mobile + desktop chat UIs.
 */
import type { OneSentenceReplyPayload } from '@/composables/canvasToolbar/oneSentenceReplyState'
import { eventBus } from '@/composables/core/useEventBus'
import { resolveKittyEditFailureMessage } from '@/composables/kitty/kittyDiagramEditFeedback'
import {
  markKittyEditTurnCompleted,
  markKittyServerStepOk,
} from '@/composables/kitty/pipeline/editTurn'
import type { KittyTranslateFn } from '@/composables/kitty/pipeline/errorCatalog'
import { messageForKittyFail } from '@/composables/kitty/pipeline/trace'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'

export type KittyEditReplyBusHandlers = {
  showFinalReply: (text: string) => void
  handleReplyPayload: (payload: OneSentenceReplyPayload) => void
  markActiveRequest: (status: 'done' | 'failed', requestId?: string | null) => void
  activeRequestId: { value: string | null }
  onBusyLlm?: (errorCode?: string) => boolean
  finalizeConversationalStream?: () => void
  t: (key: string, fallback?: string) => string
  kittyT: KittyTranslateFn
  /** After verified apply on desktop — optional hub post-mutation hook. */
  onVerifiedApplyOk?: (payload: {
    userSummary?: string
    action: string
  }) => void
}

export function useKittyEditReplyBus(
  ownerId: string,
  handlers: KittyEditReplyBusHandlers
): { dispose: () => void } {
  const pipelineStore = useKittyPipelineStore()

  const onOneSentenceReply = (payload: OneSentenceReplyPayload) => {
    handlers.handleReplyPayload(payload)
    if (payload.kind === 'final') {
      if (!payload.requestId || handlers.activeRequestId.value === payload.requestId) {
        handlers.markActiveRequest('done')
      }
      const ctx = pipelineStore.activeTurn
      if (ctx) {
        markKittyServerStepOk(ctx, 'reply')
        markKittyEditTurnCompleted(ctx)
      }
    }
  }

  const onDiagramUpdate = (payload: {
    verified?: boolean
    errorCode?: string
    action?: string
    userSummary?: string
  }) => {
    const ctx = pipelineStore.activeTurn
    if (ctx) {
      markKittyServerStepOk(ctx, payload.action)
    }
    if (payload.verified === true) {
      const summary = payload.userSummary?.trim()
      if (summary) {
        handlers.showFinalReply(summary)
      }
      handlers.markActiveRequest('done')
      if (ctx) {
        markKittyEditTurnCompleted(ctx)
      }
      return
    }
    if (payload.verified === false) {
      if (handlers.onBusyLlm?.(payload.errorCode)) {
        return
      }
      handlers.showFinalReply(
        resolveKittyEditFailureMessage(payload.errorCode, handlers.t, payload.action)
      )
      handlers.markActiveRequest('failed')
      if (ctx) {
        const fail = pipelineStore.getLastFail()
        if (fail) {
          handlers.showFinalReply(messageForKittyFail(fail, handlers.kittyT))
        }
      }
    }
  }

  const onDiagramActionCompleted = (payload: {
    ok: boolean
    userSummary?: string
    errorCode?: string
    action: string
  }) => {
    if (payload.ok) {
      handlers.onVerifiedApplyOk?.(payload)
      if (payload.userSummary?.trim()) {
        handlers.showFinalReply(payload.userSummary.trim())
      }
      handlers.markActiveRequest('done')
      const ctx = pipelineStore.activeTurn
      if (ctx) {
        markKittyEditTurnCompleted(ctx)
      }
      return
    }
    if (handlers.onBusyLlm?.(payload.errorCode)) {
      return
    }
    handlers.showFinalReply(
      resolveKittyEditFailureMessage(payload.errorCode, handlers.t, payload.action)
    )
    handlers.markActiveRequest('failed')
  }

  const onDiagramEditFailed = (payload: { action: string; errorCode: string }) => {
    handlers.showFinalReply(
      resolveKittyEditFailureMessage(payload.errorCode, handlers.t, payload.action)
    )
    handlers.markActiveRequest('failed')
  }

  const onAssistantTextDone = () => {
    handlers.finalizeConversationalStream?.()
  }

  eventBus.onWithOwner('kitty:one_sentence_reply', onOneSentenceReply, ownerId)
  eventBus.onWithOwner('voice:diagram_update_executed', onDiagramUpdate, ownerId)
  eventBus.onWithOwner('kitty:diagram_action_completed', onDiagramActionCompleted, ownerId)
  eventBus.onWithOwner('kitty:diagram_edit_failed', onDiagramEditFailed, ownerId)
  eventBus.onWithOwner('voice:assistant_text_done', onAssistantTextDone, ownerId)
  eventBus.onWithOwner('voice:response_done', onAssistantTextDone, ownerId)

  return {
    dispose: () => {
      eventBus.removeAllListenersForOwner(ownerId)
    },
  }
}
