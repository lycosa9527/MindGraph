/**
 * Mobile Kitty conversation — ASR + shared history + edit pipeline (protocol-managed).
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useKittyAsrSession } from '@/composables/kitty/asr/useKittyAsrSession'
import { useKittyConversationHistory } from '@/composables/kitty/conversation/useKittyConversationHistory'
import { useKittyEditReplyBus } from '@/composables/kitty/conversation/useKittyEditReplyBus'
import type { KittyAgentContext } from '@/composables/kitty/kittyAgentTypes'
import {
  runKittyEditTurn,
} from '@/composables/kitty/pipeline/editTurn'
import { adaptKittyTranslate } from '@/composables/kitty/pipeline/errorCatalog'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import type { useKittyFunAsrMic } from '@/composables/kitty/useKittyFunAsrMic'
import { reportKittySessionIngress } from '@/composables/kitty/useKittySessionManager'
import { useDiagramStore } from '@/stores/diagram'
import { useKittyPipelineStore } from '@/stores/kittyPipeline'
import { useOneSentenceStore } from '@/stores/oneSentence'
import type {
  OneSentenceClarifyChoice,
  OneSentencePhase,
} from '@/stores/oneSentence'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

const OWNER_ID = 'MobileKittyChat'
const PEER_HISTORY_POLL_MS = 4000

export type UseMobileKittyChatOptions = {
  kitty: ReturnType<typeof useKittyAgent>
  funAsr: ReturnType<typeof useKittyFunAsrMic>
  diagramScope: ComputedRef<string>
  ephemeralSessionId: ComputedRef<string> | Ref<string>
  phase: ComputedRef<OneSentencePhase>
  draft: Ref<string>
  ensureConnected: () => Promise<boolean>
  buildContext: () => KittyAgentContext
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
    onDebugLine,
  } = options

  const { t } = useLanguage()
  const kittyT = adaptKittyTranslate(t)
  const diagramStore = useDiagramStore()
  const pipelineStore = useKittyPipelineStore()
  const oneSentence = useOneSentenceStore()
  const { messages: oneSentenceMessages } = storeToRefs(oneSentence)

  const history = useKittyConversationHistory({
    diagramScope,
    phase,
    messages: oneSentenceMessages,
  })

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
    utteranceId?: string,
    source?: 'asr' | 'text' | 'clarify_choice'
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

    const ingressSource: 'asr' | 'text' | 'clarify_choice' =
      source ?? (utteranceId || requestId ? 'asr' : 'text')

    if (phase.value === 'create') {
      history.replyState.showFinalReply(
        t(
          'mobile.kittyPickDiagramToEdit',
          'Open or pick a saved diagram first, then hold to speak or type to edit it.'
        )
      )
      history.markActiveRequest('failed', rid)
      void reportKittySessionIngress(diagramScope.value, {
        requestId: rid,
        source: ingressSource === 'clarify_choice' ? 'clarify_choice' : ingressSource,
        text,
        lane: 'mobile',
        utteranceId,
        rejected: true,
        reason: 'phase_create',
      })
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
        t: kittyT,
      },
      {
        text,
        source: ingressSource,
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
    await sendUserText(String(choice.index), undefined, undefined, 'clarify_choice')
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

  const replyBus = useKittyEditReplyBus(OWNER_ID, {
    showFinalReply: (text) => history.replyState.showFinalReply(text),
    handleReplyPayload: (payload) => history.replyState.handleReplyPayload(payload),
    markActiveRequest: (status, requestId) => history.markActiveRequest(status, requestId),
    activeRequestId: history.activeRequestId,
    finalizeConversationalStream: () => history.replyState.finalizeConversationalStream(),
    t,
    kittyT,
  })

  const onPipelineStep = (event: {
    module: string
    step: string
    status: string
    errorCode?: string
  }) => {
    onDebugLine?.(
      '#trace',
      `${event.module} ${event.step} ${event.status}${event.errorCode ? ` ${event.errorCode}` : ''}`
    )
  }
  eventBus.onWithOwner('kitty:pipeline_step', onPipelineStep, `${OWNER_ID}:trace`)

  // Peer history refresh — desktop may append replies while phone waits.
  let peerPollTimer: ReturnType<typeof setInterval> | null = null
  function startPeerHistoryPoll(): void {
    stopPeerHistoryPoll()
    peerPollTimer = setInterval(() => {
      if (pipelineStore.editPipelineActive) {
        return
      }
      void history.bootstrapHistory()
    }, PEER_HISTORY_POLL_MS)
  }
  function stopPeerHistoryPoll(): void {
    if (peerPollTimer != null) {
      clearInterval(peerPollTimer)
      peerPollTimer = null
    }
  }
  startPeerHistoryPoll()

  onUnmounted(() => {
    stopPeerHistoryPoll()
    replyBus.dispose()
    eventBus.removeAllListenersForOwner(`${OWNER_ID}:trace`)
    funAsr.stopListening()
  })

  return {
    messages: history.messages,
    sessionHydrated: history.sessionHydrated,
    sendDraft,
    sendUserText,
    selectClarifyChoice,
    bindChatScroll: history.bindChatScroll,
  }
}
