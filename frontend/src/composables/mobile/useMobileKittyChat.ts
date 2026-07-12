/**
 * Mobile Kitty conversation — local message list + one-sentence turn REST + Kitty reply bus.
 */
import { type ComputedRef, type Ref, nextTick, onUnmounted, ref, watch } from 'vue'

import {
  pickOneSentenceGenerateDone,
  pickOneSentenceWelcome,
} from '@/composables/canvasToolbar/oneSentenceChatLines'
import {
  type OneSentenceReplyPayload,
  createOneSentenceReplyState,
} from '@/composables/canvasToolbar/oneSentenceReplyState'
import {
  appendOneSentenceTurn,
  fetchOneSentenceTurns,
  migrateOneSentenceScope,
} from '@/composables/canvasToolbar/useOneSentenceSessionTurns'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import type { HubPersistResult } from '@/composables/kitty/diagramEditHubPersist'
import type { KittyAgentContext } from '@/composables/kitty/kittyAgentTypes'
import { resolveKittyEditFailureMessage } from '@/composables/kitty/kittyDiagramEditFeedback'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import type { useKittyFunAsrMic } from '@/composables/kitty/useKittyFunAsrMic'
import { useDiagramStore } from '@/stores/diagram'
import { useKittySessionStore } from '@/stores/kittySession'
import type {
  OneSentenceChatMessage,
  OneSentenceClarifyChoice,
  OneSentencePhase,
} from '@/stores/oneSentence'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

const OWNER_ID = 'MobileKittyChat'

export type UseMobileKittyChatOptions = {
  kitty: ReturnType<typeof useKittyAgent>
  funAsr: ReturnType<typeof useKittyFunAsrMic>
  diagramScope: ComputedRef<string>
  /** Ephemeral UUID for this mobile page visit — migrate to library when scope upgrades. */
  ephemeralSessionId: ComputedRef<string> | Ref<string>
  phase: ComputedRef<OneSentencePhase>
  draft: Ref<string>
  ensureConnected: () => Promise<boolean>
  buildContext: () => KittyAgentContext
  /** Shared with hub persist / context sync so PTT release cannot race the edit gate. */
  editPipelineActive: Ref<boolean>
  /** Await library persist ack — mobile edit gate (replaces duplicate pre-edit context sync). */
  awaitHubLibraryPersistBeforeEdit: (timeoutMs?: number) => Promise<HubPersistResult>
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
    awaitHubLibraryPersistBeforeEdit,
    onDebugLine,
  } = options

  const { t, currentLanguage } = useLanguage()
  const diagramStore = useDiagramStore()
  const kittySession = useKittySessionStore()
  const messages = ref<OneSentenceChatMessage[]>([])
  const activeRequestId = ref<string | null>(null)
  const chatScrollEl = ref<HTMLElement | null>(null)
  const sessionHydrated = ref(false)
  let bootstrapGeneration = 0
  let messageSeq = 0

  function seedOpeningKittyLine(): void {
    // Same rotating pools as desktop one-sentence panel.
    const seed =
      phase.value === 'edit'
        ? pickOneSentenceGenerateDone(currentLanguage.value)
        : pickOneSentenceWelcome(currentLanguage.value)
    if (seed.trim()) {
      pushKittyMessage(seed)
    }
  }

  function nextMessageId(): string {
    messageSeq += 1
    return `mobile-kitty-msg-${messageSeq}`
  }

  function scrollChatToBottom(): void {
    void nextTick(() => {
      const el = chatScrollEl.value
      if (el) {
        el.scrollTop = el.scrollHeight
      }
    })
  }

  function pushKittyMessage(
    text: string,
    streaming = false,
    extras?: { choices?: OneSentenceClarifyChoice[] }
  ): string {
    const id = nextMessageId()
    const row: OneSentenceChatMessage = {
      id,
      role: 'kitty',
      text,
      streaming,
    }
    if (extras?.choices?.length) {
      row.choices = extras.choices
    }
    messages.value = [...messages.value, row]
    scrollChatToBottom()
    return id
  }

  function replaceKittyMessage(messageId: string, text: string, streaming = false): void {
    const idx = messages.value.findIndex((m) => m.id === messageId)
    if (idx < 0) {
      pushKittyMessage(text, streaming)
      return
    }
    const next = [...messages.value]
    next[idx] = { ...next[idx], text, streaming }
    messages.value = next
    scrollChatToBottom()
  }

  const replyState = createOneSentenceReplyState({
    messages,
    pushKittyMessage,
    replaceKittyMessage,
    scrollChatToBottom,
  })

  function pushUserMessage(text: string, requestId: string): string {
    const id = nextMessageId()
    messages.value = [
      ...messages.value,
      {
        id,
        role: 'user',
        text,
        requestId,
        status: 'inflight',
      },
    ]
    scrollChatToBottom()
    return id
  }

  function markActiveRequest(status: 'done' | 'failed'): void {
    const id = activeRequestId.value
    if (!id) {
      return
    }
    const idx = messages.value.findIndex((m) => m.requestId === id && m.role === 'user')
    if (idx >= 0) {
      const next = [...messages.value]
      next[idx] = { ...next[idx], status }
      messages.value = next
    }
    activeRequestId.value = null
  }

  async function persistUserTurn(text: string, requestId: string): Promise<void> {
    const scope = diagramScope.value
    if (!scope) {
      return
    }
    await appendOneSentenceTurn(scope, {
      role: 'user',
      content: text,
      phase: phase.value,
      source: 'mobile_ui',
      diagram_type: diagramStore.type ?? undefined,
      request_id: requestId,
    })
  }

  async function sendUserText(raw: string): Promise<boolean> {
    const text = raw.trim()
    if (!text) {
      return false
    }
    editPipelineActive.value = true
    try {
      replyState.consumeOpenChoices()
      const requestId = safeRandomUUID()
      pushUserMessage(text, requestId)
      activeRequestId.value = requestId
      draft.value = ''
      await persistUserTurn(text, requestId)
      replyState.resetForNewTurn()

      // Create/empty canvas: desktop owns generate. Prompt to pick or open a diagram.
      if (phase.value === 'create') {
        replyState.showFinalReply(
          t(
            'mobile.kittyPickDiagramToEdit',
            'Open or pick a saved diagram first, then hold to speak or type to edit it.'
          )
        )
        markActiveRequest('failed')
        return false
      }

      const ok = await ensureConnected()
      if (!ok) {
        replyState.showFinalReply(t('canvas.mindMapOneSentence.kittyUnavailable'))
        markActiveRequest('failed')
        return false
      }

      let hubResult = await awaitHubLibraryPersistBeforeEdit()
      if (!hubResult.ok) {
        if (!kitty.isConnected.value) {
          const reconnected = await ensureConnected()
          if (reconnected) {
            hubResult = await awaitHubLibraryPersistBeforeEdit()
          }
        }
      }
      if (!hubResult.ok) {
        replyState.showFinalReply(t('canvas.mindMapOneSentence.kittyContextSyncFailed'))
        markActiveRequest('failed')
        return false
      }

      let sent = kitty.sendTextMessage(text, requestId)
      if (!sent) {
        const reconnected = await ensureConnected()
        if (reconnected) {
          sent = kitty.sendTextMessage(text, requestId)
        }
      }
      if (!sent) {
        replyState.showFinalReply(t('mobile.kittyConnectFailed', '连接失败，请检查网络后重试'))
        markActiveRequest('failed')
        return false
      }
      return true
    } finally {
      editPipelineActive.value = false
    }
  }

  async function sendDraft(): Promise<boolean> {
    return sendUserText(draft.value)
  }

  async function selectClarifyChoice(choice: OneSentenceClarifyChoice): Promise<void> {
    draft.value = String(choice.index)
    await sendDraft()
  }

  function bindChatScroll(el: HTMLElement | null): void {
    chatScrollEl.value = el
  }

  function hydrateFromTurns(
    turns: Array<{
      turn_id: string
      role: 'user' | 'kitty' | 'meta'
      content: string
      request_id?: string
      outcome?: string
    }>
  ): void {
    const rows: OneSentenceChatMessage[] = []
    for (const turn of turns) {
      if (turn.role !== 'user' && turn.role !== 'kitty') {
        continue
      }
      const content = turn.content?.trim()
      if (!content) {
        continue
      }
      const requestId = turn.request_id?.trim() || undefined
      let status: OneSentenceChatMessage['status']
      if (turn.role === 'user' && requestId) {
        const outcome = (turn.outcome || '').toLowerCase()
        if (outcome === 'failed' || outcome === 'error') {
          status = 'failed'
        } else if (outcome === 'queued') {
          status = 'queued'
        } else {
          status = 'done'
        }
      }
      rows.push({
        id: turn.turn_id || nextMessageId(),
        role: turn.role,
        text: content,
        requestId,
        status,
      })
    }
    messages.value = rows
    scrollChatToBottom()
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
    // Only migrate when leaving this page's ephemeral session toward a durable scope.
    if (prevScope !== ephemeral) {
      return
    }
    const ok = await migrateOneSentenceScope(ephemeral, nextScope)
    if (ok) {
      migratedFromEphemeral.value = true
    }
  }

  async function bootstrapChat(): Promise<void> {
    const gen = ++bootstrapGeneration
    const scope = diagramScope.value
    sessionHydrated.value = false
    if (!scope) {
      messages.value = []
      seedOpeningKittyLine()
      sessionHydrated.value = true
      return
    }
    const restored = await fetchOneSentenceTurns(scope)
    if (gen !== bootstrapGeneration) {
      return
    }
    if (restored.length > 0) {
      hydrateFromTurns(restored)
    } else {
      messages.value = []
      seedOpeningKittyLine()
    }
    sessionHydrated.value = true
  }

  let lastAsrCommitText = ''
  let lastAsrCommitAt = 0
  let asrFinalCommitted = false
  /** Latest hold correlation — ignore stale finals/stops from a prior utterance. */
  let activeAsrUtteranceId: string | null = null
  /** Buffered transcript while the button is still held (release-only submit). */
  let holdTranscript = ''
  let holdListening = false
  /** True once this hold received non-empty ASR text (partial or final). */
  let holdHadSpeech = false

  function normalizeAsrCommitKey(text: string): string {
    return text
      .trim()
      .replace(/[。．.！？!?，,、；;：:\s]+$/gu, '')
      .trim()
  }

  function utteranceMatches(utteranceId?: string): boolean {
    if (!utteranceId) {
      // Legacy servers without utterance_id — accept only while we have an open hold.
      return holdListening || funAsr.listening.value
    }
    if (activeAsrUtteranceId == null) {
      activeAsrUtteranceId = utteranceId
      return true
    }
    return utteranceId === activeAsrUtteranceId
  }

  function resetHoldCorrelation(): void {
    holdTranscript = ''
    holdListening = false
    holdHadSpeech = false
    activeAsrUtteranceId = null
  }

  function commitAsrTranscript(raw: string): void {
    const text = raw.trim()
    if (!text) {
      return
    }
    if (asrFinalCommitted) {
      return
    }
    const key = normalizeAsrCommitKey(text)
    const now = Date.now()
    if (key.length > 0 && key === lastAsrCommitText && now - lastAsrCommitAt < 2500) {
      return
    }
    if (key.length > 0) {
      lastAsrCommitText = key
    }
    lastAsrCommitAt = now
    asrFinalCommitted = true
    draft.value = text
    if (funAsr.listening.value) {
      funAsr.stopListening()
    }
    // Block debounced library persist / scheduled context sync before async sendUserText runs.
    editPipelineActive.value = true
    void sendUserText(text)
  }

  const onAsrPartial = (payload: { text: string; utteranceId?: string }) => {
    if (!utteranceMatches(payload.utteranceId)) {
      return
    }
    if (payload.utteranceId) {
      activeAsrUtteranceId = payload.utteranceId
    }
    if (payload.text.trim()) {
      asrFinalCommitted = false
      holdListening = true
      holdHadSpeech = true
      holdTranscript = payload.text.trim()
      draft.value = holdTranscript
    }
  }

  const onAsrFinal = (payload: { text: string; utteranceId?: string }) => {
    if (!utteranceMatches(payload.utteranceId)) {
      return
    }
    if (payload.utteranceId) {
      activeAsrUtteranceId = payload.utteranceId
    }
    const text = payload.text.trim()
    if (!text) {
      return
    }
    // Release-only: while holding, only buffer. Submit on asr_stopped / pointer release.
    holdListening = true
    holdHadSpeech = true
    holdTranscript = text
    draft.value = text
    asrFinalCommitted = false
  }

  /** PTT release → asr_stop → asr_stopped; flush buffered transcript once. */
  const onAsrStopped = (payload?: { utteranceId?: string; text?: string }) => {
    if (
      payload?.utteranceId &&
      activeAsrUtteranceId &&
      payload.utteranceId !== activeAsrUtteranceId
    ) {
      return
    }
    const payloadText = typeof payload?.text === 'string' ? payload.text.trim() : ''
    const text = (payloadText || holdTranscript).trim()
    // Only submit ASR-captured speech — never an unrelated keyboard draft.
    if (!holdHadSpeech || !text) {
      resetHoldCorrelation()
      window.setTimeout(() => {
        asrFinalCommitted = false
      }, 3000)
      return
    }
    commitAsrTranscript(text)
    resetHoldCorrelation()
    window.setTimeout(() => {
      asrFinalCommitted = false
    }, 3000)
  }

  const onOneSentenceReply = (payload: OneSentenceReplyPayload) => {
    replyState.handleReplyPayload(payload)
    if (payload.kind === 'final') {
      if (!payload.requestId || activeRequestId.value === payload.requestId) {
        markActiveRequest('done')
      }
    }
  }

  const onDiagramUpdate = (payload: {
    verified?: boolean
    errorCode?: string
    action?: string
    userSummary?: string
  }) => {
    if (payload.verified === true) {
      const summary = payload.userSummary?.trim()
      if (summary) {
        replyState.showFinalReply(summary)
      }
      markActiveRequest('done')
      return
    }
    if (payload.verified === false) {
      replyState.showFinalReply(
        resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
      )
      markActiveRequest('failed')
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
        replyState.showFinalReply(payload.userSummary.trim())
      }
      markActiveRequest('done')
      return
    }
    replyState.showFinalReply(resolveKittyEditFailureMessage(payload.errorCode, t, payload.action))
    markActiveRequest('failed')
  }

  const onDiagramEditFailed = (payload: { action: string; errorCode: string }) => {
    replyState.showFinalReply(resolveKittyEditFailureMessage(payload.errorCode, t, payload.action))
    markActiveRequest('failed')
  }

  const onAssistantTextDone = () => {
    replyState.finalizeConversationalStream()
  }

  const onContextMutationAck = (data: { ok?: boolean; revision?: number }) => {
    if (data.ok !== false && typeof data.revision === 'number') {
      kittySession.setHubScopeRevision(data.revision)
    }
  }

  watch(
    diagramScope,
    (scope, prevScope) => {
      void (async () => {
        if (scope && prevScope !== undefined && scope !== prevScope) {
          await maybeMigrateEphemeralToScope(scope, prevScope)
        }
        await bootstrapChat()
      })()
    },
    { immediate: true }
  )

  const bus = eventBus
  bus.onWithOwner('kitty:asr_partial', onAsrPartial, OWNER_ID)
  bus.onWithOwner('kitty:asr_final', onAsrFinal, OWNER_ID)
  bus.onWithOwner('kitty:asr_stopped', onAsrStopped, OWNER_ID)
  bus.onWithOwner('kitty:one_sentence_reply', onOneSentenceReply, OWNER_ID)
  bus.onWithOwner('voice:diagram_update_executed', onDiagramUpdate, OWNER_ID)
  bus.onWithOwner('kitty:diagram_action_completed', onDiagramActionCompleted, OWNER_ID)
  bus.onWithOwner('kitty:diagram_edit_failed', onDiagramEditFailed, OWNER_ID)
  bus.onWithOwner('voice:assistant_text_done', onAssistantTextDone, OWNER_ID)
  bus.onWithOwner('voice:response_done', onAssistantTextDone, OWNER_ID)
  bus.onWithOwner('voice:context_mutation_ack', onContextMutationAck, OWNER_ID)

  onUnmounted(() => {
    eventBus.removeAllListenersForOwner(OWNER_ID)
    funAsr.stopListening()
  })

  return {
    messages,
    sessionHydrated,
    editPipelineActive,
    sendDraft,
    sendUserText,
    selectClarifyChoice,
    bindChatScroll,
    bootstrapChat,
  }
}
