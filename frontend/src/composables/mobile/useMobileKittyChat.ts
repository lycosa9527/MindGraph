/**
 * Mobile Kitty conversation — ASR + history + edit pipeline (protocol-managed).
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useKittyAsrSession } from '@/composables/kitty/asr/useKittyAsrSession'
import { useKittyConversationHistory } from '@/composables/kitty/conversation/useKittyConversationHistory'
import type { KittyAgentContext } from '@/composables/kitty/kittyAgentTypes'
import { resolveKittyEditFailureMessage } from '@/composables/kitty/kittyDiagramEditFeedback'
import {
  markKittyEditTurnCompleted,
  markKittyServerStepOk,
  runKittyEditTurn,
} from '@/composables/kitty/pipeline/editTurn'
import { messageForKittyFail } from '@/composables/kitty/pipeline/trace'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import type { useKittyFunAsrMic } from '@/composables/kitty/useKittyFunAsrMic'
import { useDiagramStore } from '@/stores/diagram'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'
import type {
  OneSentenceClarifyChoice,
  OneSentencePhase,
} from '@/stores/oneSentence'
import type { OneSentenceReplyPayload } from '@/composables/canvasToolbar/oneSentenceReplyState'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

const OWNER_ID = 'MobileKittyChat'

export type UseMobileKittyChatOptions = {
  kitty: ReturnType<typeof useKittyAgent>
  funAsr: ReturnType<typeof useKittyFunAsrMic>
  diagramScope: ComputedRef<string>
  ephemeralSessionId: ComputedRef<string> | Ref<string>
  phase: ComputedRef<OneSentencePhase>
  draft: Ref<string>
  ensureConnected: () => Promise<boolean>
  buildContext: () => KittyAgentContext
  /** Prefer store-backed flag; kept for page wiring compat. */
  editPipelineActive: Ref<boolean>
  onDebugLine?: (prefix: string, detail: string) => void
}

export function useMobileKittyChat(options: UseMobileKittyChatOptions) {
  const {
    kitty,
    funAsr,
    diagramScope,
    ephemeralSessionId,
    phase,
    draft,
    ensureConnected,
    buildContext,
    editPipelineActive,
    onDebugLine,
  } = options

  const { t } = useLanguage()
  const diagramStore = useDiagramStore()
  const pipelineStore = useKittyPipelineStore()

  const history = useKittyConversationHistory({
    diagramScope,
    phase,
  })

  // Mirror store pipeline activity onto the page-owned ref (pairing/poll/persist).
  watch(
    () => pipelineStore.editPipelineActive,
    (active) => {
      editPipelineActive.value = active
    },
    { immediate: true }
  )

  const asr = useKittyAsrSession({
    mode: 'release_only',
    lane: 'mobile',
    getScope: () => diagramScope.value,
    draft,
    ownerId: `${OWNER_ID}:asr`,
    onCommit: (text, ctx) => {
      if (funAsr.listening.value) {
        funAsr.stopListening()
      }
      void sendUserText(text, ctx.requestId, ctx.utteranceId)
    },
  })
  asr.bindBus()

  async function sendUserText(
    raw: string,
    requestId?: string,
    utteranceId?: string
  ): Promise<boolean> {
    const text = raw.trim()
    if (!text) {
      return false
    }
    history.replyState.consumeOpenChoices()
    const rid = requestId ?? safeRandomUUID()
    history.pushUserMessage(text, rid)
    history.activeRequestId.value = rid
    draft.value = ''

    if (phase.value === 'create') {
      history.replyState.showFinalReply(
        t(
          'mobile.kittyPickDiagramToEdit',
          'Open or pick a saved diagram first, then hold to speak or type to edit it.'
        )
      )
      history.markActiveRequest('failed', rid)
      return false
    }

    const result = await runKittyEditTurn(
      {
        kitty,
        buildContext,
        updateContext: kitty.updateContext,
        getScope: () => diagramScope.value,
        lane: 'mobile',
        ensureConnected,
        appendUserTurn: async (turnText, turnId, ctx) =>
          history.appendUserTurn(turnText, turnId, {
            ctx,
            diagramType: diagramStore.type ?? undefined,
          }),
        onFailMessage: (msg) => {
          history.replyState.showFinalReply(msg)
          history.markActiveRequest('failed')
          onDebugLine?.('#trace', msg.slice(0, 80))
        },
        t: (key, fallback) => t(key, fallback),
      },
      {
        text,
        source: utteranceId || requestId ? 'asr' : 'text',
        requestId: rid,
        utteranceId,
      }
    )

    if (!result.ok) {
      return false
    }
    return true
  }

  async function sendDraft(): Promise<boolean> {
    return sendUserText(draft.value)
  }

  async function selectClarifyChoice(choice: OneSentenceClarifyChoice): Promise<void> {
    draft.value = String(choice.index)
    await sendDraft()
  }

  const migratedFromEphemeral = ref(false)

  async function maybeMigrateEphemeralToScope(
    nextScope: string,
    prevScope: string | undefined
  ): Promise<void> {
    if (migratedFromEphemeral.value) {
      return
    }
    const ephemeral = ephemeralSessionId.value?.trim()
    if (!ephemeral || !nextScope || nextScope === ephemeral) {
      return
    }
    if (prevScope !== ephemeral) {
      return
    }
    const ok = await history.migrateScope(ephemeral, nextScope)
    if (ok) {
      migratedFromEphemeral.value = true
    }
  }

  watch(
    diagramScope,
    (scope, prevScope) => {
      void (async () => {
        if (scope && prevScope !== undefined && scope !== prevScope) {
          await maybeMigrateEphemeralToScope(scope, prevScope)
        }
        await history.bootstrapHistory()
      })()
    },
    { immediate: true, flush: 'post' }
  )

  const onOneSentenceReply = (payload: OneSentenceReplyPayload) => {
    history.replyState.handleReplyPayload(payload)
    if (payload.kind === 'final') {
      if (!payload.requestId || history.activeRequestId.value === payload.requestId) {
        history.markActiveRequest('done')
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
        history.replyState.showFinalReply(summary)
      }
      history.markActiveRequest('done')
      if (ctx) {
        markKittyEditTurnCompleted(ctx)
      }
      return
    }
    if (payload.verified === false) {
      history.replyState.showFinalReply(
        resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
      )
      history.markActiveRequest('failed')
      if (ctx) {
        const fail = pipelineStore.getLastFail()
        if (fail) {
          history.replyState.showFinalReply(messageForKittyFail(fail, t))
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
      if (payload.userSummary?.trim()) {
        history.replyState.showFinalReply(payload.userSummary.trim())
      }
      history.markActiveRequest('done')
      const ctx = pipelineStore.activeTurn
      if (ctx) {
        markKittyEditTurnCompleted(ctx)
      }
      return
    }
    history.replyState.showFinalReply(
      resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
    )
    history.markActiveRequest('failed')
  }

  const onDiagramEditFailed = (payload: { action: string; errorCode: string }) => {
    history.replyState.showFinalReply(
      resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
    )
    history.markActiveRequest('failed')
  }

  const onAssistantTextDone = () => {
    history.replyState.finalizeConversationalStream()
  }

  const onPipelineStep = (event: { module: string; step: string; status: string; errorCode?: string }) => {
    onDebugLine?.(
      '#trace',
      `${event.module} ${event.step} ${event.status}${event.errorCode ? ` ${event.errorCode}` : ''}`
    )
  }

  const bus = eventBus
  bus.onWithOwner('kitty:one_sentence_reply', onOneSentenceReply, OWNER_ID)
  bus.onWithOwner('voice:diagram_update_executed', onDiagramUpdate, OWNER_ID)
  bus.onWithOwner('kitty:diagram_action_completed', onDiagramActionCompleted, OWNER_ID)
  bus.onWithOwner('kitty:diagram_edit_failed', onDiagramEditFailed, OWNER_ID)
  bus.onWithOwner('voice:assistant_text_done', onAssistantTextDone, OWNER_ID)
  bus.onWithOwner('voice:response_done', onAssistantTextDone, OWNER_ID)
  bus.onWithOwner('kitty:pipeline_step', onPipelineStep, OWNER_ID)

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(OWNER_ID)
    funAsr.stopListening()
  })

  return {
    messages: history.messages,
    sessionHydrated: history.sessionHydrated,
    editPipelineActive,
    sendDraft,
    sendUserText,
    selectClarifyChoice,
    bindChatScroll: history.bindChatScroll,
    bootstrapChat: history.bootstrapHistory,
  }
}
