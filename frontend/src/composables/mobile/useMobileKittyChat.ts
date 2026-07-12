/**
 * Mobile Kitty conversation — local message list + one-sentence turn REST + Kitty reply bus.
 */
import {
  type ComputedRef,
  type Ref,
  nextTick,
  onUnmounted,
  ref,
  watch,
} from 'vue'

import {
  type OneSentenceReplyPayload,
  createOneSentenceReplyState,
} from '@/composables/canvasToolbar/oneSentenceReplyState'
import {
  pickOneSentenceGenerateDone,
  pickOneSentenceWelcome,
} from '@/composables/canvasToolbar/oneSentenceChatLines'
import {
  appendOneSentenceTurn,
  fetchOneSentenceTurns,
  migrateOneSentenceScope,
} from '@/composables/canvasToolbar/useOneSentenceSessionTurns'
import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'
import { persistVerifiedDiagramToHub } from '@/composables/kitty/diagramEditHubPersist'
import { resolveKittyEditFailureMessage } from '@/composables/kitty/kittyDiagramEditFeedback'
import type { KittyAgentContext } from '@/composables/kitty/kittyAgentTypes'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import type { useKittyFunAsrMic } from '@/composables/kitty/useKittyFunAsrMic'
import type {
  OneSentenceChatMessage,
  OneSentenceClarifyChoice,
  OneSentencePhase,
} from '@/stores/oneSentence'
import { useDiagramStore } from '@/stores/diagram'
import { useKittySessionStore } from '@/stores/kittySession'
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
  } = options

  const { t, currentLanguage } = useLanguage()
  const diagramStore = useDiagramStore()
  const kittySession = useKittySessionStore()
  const messages = ref<OneSentenceChatMessage[]>([])
  const activeRequestId = ref<string | null>(null)
  const chatScrollEl = ref<HTMLElement | null>(null)
  const sessionHydrated = ref(false)
  /** True while ASR→hub-sync→sendText is running; blocks scope-watch WS reconnect. */
  const editPipelineActive = ref(false)
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

  async function syncHubBeforeEdit(): Promise<boolean> {
    if (!kitty.isConnected.value) {
      return false
    }
    const attempt = async (): Promise<boolean> => {
      const result = await persistVerifiedDiagramToHub({
        buildContext,
        updateContext: kitty.updateContext,
        hubScopeRevision: kittySession.hubScopeRevision,
        scope: diagramScope.value,
      })
      if (result.ok && typeof result.revision === 'number') {
        kittySession.setHubScopeRevision(result.revision)
        return true
      }
      return false
    }

    if (await attempt()) {
      return true
    }
    // One retry after a brief settle — covers transient WS preempt during context_update.
    if (!kitty.isConnected.value) {
      const reconnected = await ensureConnected()
      if (!reconnected) {
        return false
      }
    }
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, 200)
    })
    return attempt()
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

      const hubOk = await syncHubBeforeEdit()
      if (!hubOk) {
        replyState.showFinalReply(t('canvas.mindMapOneSentence.kittyContextSyncFailed'))
        markActiveRequest('failed')
        return false
      }

      kitty.sendTextMessage(text, requestId)
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

  async function maybeMigrateEphemeralToScope(nextScope: string, prevScope: string | undefined): Promise<void> {
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

  function normalizeAsrCommitKey(text: string): string {
    return text
      .trim()
      .replace(/[。．.！？!?，,、；;：:\s]+$/gu, '')
      .trim()
  }

  function commitAsrTranscript(raw: string, source: 'final' | 'stopped'): void {
    const text = raw.trim()
    if (!text) {
      return
    }
    if (source === 'stopped' && asrFinalCommitted) {
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
    if (source === 'final') {
      asrFinalCommitted = true
    }
    draft.value = text
    funAsr.stopListening()
    void sendUserText(text)
  }

  const onAsrPartial = (payload: { text: string }) => {
    if (payload.text.trim()) {
      // New utterance started — allow a later final after a prior hold.
      asrFinalCommitted = false
      draft.value = payload.text.trim()
    }
  }

  const onAsrFinal = (payload: { text: string }) => {
    commitAsrTranscript(payload.text, 'final')
  }

  /** PTT release may get asr_stopped before asr_final if DashScope is slow — flush draft. */
  const onAsrStopped = () => {
    commitAsrTranscript(draft.value, 'stopped')
    // Allow a later final in the same hold only if stopped flushed nothing useful.
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
    replyState.showFinalReply(
      resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
    )
    markActiveRequest('failed')
  }

  const onDiagramEditFailed = (payload: { action: string; errorCode: string }) => {
    replyState.showFinalReply(
      resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
    )
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
