/**
 * One-sentence panel chat wiring — thin view layer over ``useOneSentenceStore``.
 * First message → prompt-to-diagram; follow-ups → Kitty text (tracked requests).
 */
import { computed, nextTick, onMounted, onUnmounted, watch } from 'vue'

import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

import { diagramTypeToChineseMap } from '@/composables/canvasPage/diagramTypeMaps'
import {
  canvasDiagramSlugsEquivalent,
  extractTopicSeedFromPrompt,
  resolveDiagramTypeFromPrompt,
} from '@/composables/canvasPage/diagramTypeFromPrompt'
import { isCanvasPristineForTypeSwitch } from '@/composables/canvasPage/isCanvasPristineForTypeSwitch'
import { switchCanvasDiagramType } from '@/composables/canvasPage/switchCanvasDiagramType'
import {
  pickOneSentenceGenerateDone,
  pickOneSentenceGenerating,
  pickOneSentenceWelcome,
} from '@/composables/canvasToolbar/oneSentenceChatLines'
import { shouldUseOneSentenceEditFlow } from '@/composables/canvasToolbar/mindMapOneSentencePhase'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import {
  appendOneSentenceTurn,
  fetchOneSentenceTurns,
  migrateOneSentenceScope,
  type OneSentenceTurnInput,
} from '@/composables/canvasToolbar/useOneSentenceSessionTurns'
import {
  createOneSentenceReplyState,
  type OneSentenceReplyPayload,
} from '@/composables/canvasToolbar/oneSentenceReplyState'
import { useEventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { buildKittyDiagramContext } from '@/composables/kitty/buildKittyDiagramContext'
import { persistVerifiedDiagramToHub } from '@/composables/kitty/diagramEditHubPersist'
import type { HubPersistResult } from '@/composables/kitty/diagramEditHubPersist'
import { getKittyDiagramContentFingerprint } from '@/composables/kitty/kittyDiagramFingerprint'
import { resolveKittyEditFailureMessage } from '@/composables/kitty/kittyDiagramEditFeedback'
import {
  buildKittyEditQueuedForLlmMessage,
  listInFlightAutocompleteDisplayNames,
} from '@/composables/kitty/kittyEditAfterLlmQueue'
import { setDiagramWriteLockHolder } from '@/composables/kitty/useDiagramWriteLock'
import { useKittyFunAsrMic } from '@/composables/kitty/useKittyFunAsrMic'
import { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import {
  useDiagramStore,
  useFeatureFlagsStore,
  useLLMResultsStore,
  useOneSentenceStore,
  useSavedDiagramsStore,
  type OneSentenceClarifyChoice,
} from '@/stores'
import { useKittySessionStore } from '@/stores/kittySession'

export type {
  OneSentenceChatMessage,
  OneSentenceChatRole,
  OneSentenceClarifyChoice,
} from '@/stores/oneSentence'

const PANEL_OWNER = 'MindMapOneSentencePanel'

export function useMindMapOneSentenceChat() {
  const { t, isZh, currentLanguage } = useLanguage()
  const route = useRoute()
  const router = useRouter()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const featureFlagsStore = useFeatureFlagsStore()
  const oneSentence = useOneSentenceStore()
  const { isAIGenerating, handleAIGenerate } = useCanvasToolbarApps()
  const bus = useEventBus(PANEL_OWNER)

  const {
    draft,
    messages,
    phase,
    connecting,
    ephemeralScope,
    scopeMigrated,
    diagramScope,
    activeRequestId,
  } = storeToRefs(oneSentence)

  const isWaitingForFirstResult = computed(
    () => isAIGenerating.value && !llmResultsStore.selectedModel
  )

  const isInputBlocked = computed(
    () =>
      !oneSentence.sessionReady ||
      isWaitingForFirstResult.value ||
      connecting.value ||
      diagramStore.collabSessionActive
  )

  const chatScrollEl = { value: null as HTMLElement | null }

  const kittyEnabled = computed(() => featureFlagsStore.getFeatureKittyAgent())

  let pendingGenerateReply = false
  let generateWatchReady = false
  let recordingCreatePhase = false
  let lastEditRequestId: string | null = null
  let hubSyncTimer: ReturnType<typeof setTimeout> | null = null
  let lastHubFingerprint = ''
  let bootstrapGeneration = 0

  function scrollChatToBottom(): void {
    void nextTick(() => {
      const el = chatScrollEl.value
      if (!el) return
      el.scrollTop = el.scrollHeight
    })
  }

  function pushKittyMessage(
    text: string,
    streaming = false,
    extras?: { choices?: OneSentenceClarifyChoice[] }
  ): string {
    const id = oneSentence.pushMessage('kitty', text, streaming, extras)
    if (!streaming) {
      void persistCreateTurn('kitty', text, 'ui_create')
    }
    return id
  }

  function replaceKittyMessage(messageId: string, text: string, streaming = false): void {
    oneSentence.replaceMessage(messageId, text, streaming)
  }

  async function persistCreateTurn(
    role: 'user' | 'kitty',
    text: string,
    source: string,
    requestId?: string
  ): Promise<void> {
    if (!recordingCreatePhase) return
    const trimmed = text.trim()
    if (trimmed === '') return
    const payload: OneSentenceTurnInput = {
      role,
      content: trimmed,
      phase: 'create',
      source,
      diagram_type: diagramStore.type ?? undefined,
      request_id: requestId,
    }
    await appendOneSentenceTurn(diagramScope.value, payload)
  }

  async function persistEditUserTurn(
    text: string,
    requestId: string,
    outcome?: string
  ): Promise<void> {
    const payload: OneSentenceTurnInput = {
      role: 'user',
      content: text.trim(),
      phase: 'edit',
      source: outcome === 'queued' ? 'ui_queued' : outcome === 'failed' ? 'ui_failed' : 'ui_edit',
      diagram_type: diagramStore.type ?? undefined,
      request_id: requestId,
      outcome,
    }
    const ok = await appendOneSentenceTurn(diagramScope.value, payload)
    if (!ok && import.meta.env.DEV) {
      console.warn(
        `[OneSentence] persist user turn failed request_id=${requestId.slice(0, 8)} outcome=${outcome ?? 'inflight'}`
      )
    }
  }

  async function persistKittyUiTurn(
    text: string,
    requestId: string | null | undefined,
    outcome: string,
    source = 'ui_reply'
  ): Promise<void> {
    const trimmed = text.trim()
    if (!trimmed) return
    const payload: OneSentenceTurnInput = {
      role: 'kitty',
      content: trimmed,
      phase: phase.value,
      source,
      diagram_type: diagramStore.type ?? undefined,
      request_id: requestId ?? undefined,
      outcome,
    }
    await appendOneSentenceTurn(diagramScope.value, payload)
  }

  const replyState = createOneSentenceReplyState({
    messages,
    pushKittyMessage,
    replaceKittyMessage,
    scrollChatToBottom,
  })

  const kitty = useKittyAgent({
    ownerId: PANEL_OWNER,
    textOnly: true,
    sampleRate: 22050,
    onError: (err) => {
      pushKittyMessage(err)
    },
  })

  const kittySession = useKittySessionStore()
  const { asrListening, asrPartialTranscript } = storeToRefs(kittySession)

  const funAsr = useKittyFunAsrMic({
    ws: kitty.ws,
    stopPlayback: kitty.stopAudioPlayback,
    ensureConnected: () => ensureKittyConnected(),
    onError: (code) => {
      if (code === 'mic_denied') {
        pushKittyMessage(t('canvas.mindMapOneSentence.micDenied'))
        return
      }
      pushKittyMessage(t('canvas.mindMapOneSentence.kittyUnavailable'))
    },
  })

  function buildKittyContext() {
    return buildKittyDiagramContext(diagramStore, 'one_sentence', {
      oneSentencePhase: phase.value,
    })
  }

  kitty.registerDiagramContextBuilder(buildKittyContext)

  const kittyAgentState = computed(() => kitty.state.value)

  function handleGenerateFailure(error?: string): void {
    if (!pendingGenerateReply) return
    pendingGenerateReply = false
    recordingCreatePhase = false
    const fallback = t('canvas.mindMapOneSentence.kittyGenerateFailed')
    const msg = error?.trim() || fallback
    pushKittyMessage(msg)
    if (activeRequestId.value) {
      oneSentence.markRequestFailed(activeRequestId.value, 'generate_failed')
    }
  }

  async function ensureKittyConnected(): Promise<boolean> {
    if (!kittyEnabled.value) {
      pushKittyMessage(t('canvas.mindMapOneSentence.kittyUnavailable'))
      return false
    }
    if (kitty.isConnected.value) return true

    oneSentence.setConnecting(true)
    try {
      await kitty.startConversation(diagramScope.value, buildKittyContext())
      return true
    } catch {
      pushKittyMessage(t('canvas.mindMapOneSentence.kittyUnavailable'))
      return false
    } finally {
      oneSentence.setConnecting(false)
    }
  }

  async function syncKittyContext(): Promise<HubPersistResult> {
    if (!kitty.isConnected.value) {
      return { ok: false, error: 'not_connected' }
    }
    const result = await persistVerifiedDiagramToHub({
      buildContext: buildKittyContext,
      updateContext: kitty.updateContext,
      hubScopeRevision: kittySession.hubScopeRevision,
      scope: diagramScope.value,
    })
    if (result.ok && typeof result.revision === 'number') {
      kittySession.setHubScopeRevision(result.revision)
    }
    return result
  }

  async function maybeMigrateScope(libraryId: string): Promise<void> {
    if (scopeMigrated.value) return
    const fromScope = ephemeralScope.value
    if (!fromScope || fromScope === libraryId) {
      oneSentence.setScopeMigrated(true)
      oneSentence.setLibraryScope(libraryId)
      return
    }
    const ok = await migrateOneSentenceScope(fromScope, libraryId)
    if (ok) {
      oneSentence.emitSessionMigrated(fromScope, libraryId)
      if (kitty.isConnected.value) {
        await kitty.stopConversation()
      }
    }
  }

  function maybeSwitchDiagramTypeForCreate(text: string): void {
    const requestedType = resolveDiagramTypeFromPrompt(text)
    if (!requestedType) return
    if (canvasDiagramSlugsEquivalent(diagramStore.type, requestedType)) return
    if (!isCanvasPristineForTypeSwitch(diagramStore, savedDiagramsStore, llmResultsStore)) {
      return
    }

    const topicSeed = extractTopicSeedFromPrompt(text, requestedType)
    const switched = switchCanvasDiagramType(requestedType, {
      topicSeed,
      router,
      route,
    })
    if (!switched) return

    const typeLabel =
      diagramTypeToChineseMap[requestedType] ??
      diagramTypeToChineseMap.mindmap ??
      requestedType
    pushKittyMessage(t('canvas.mindMapOneSentence.switchDiagramType', { type: typeLabel }))
  }

  async function runCreateFlow(text: string): Promise<void> {
    maybeSwitchDiagramTypeForCreate(text)
    pendingGenerateReply = true
    pushKittyMessage(pickOneSentenceGenerating(currentLanguage.value))
    await handleAIGenerate({ generationInstructions: text })
  }

  function buildBusyQueuedReply(): string {
    const names = listInFlightAutocompleteDisplayNames(
      llmResultsStore.modelStates,
      llmResultsStore.modelPhases
    )
    return buildKittyEditQueuedForLlmMessage(t, names, isZh.value ? 'zh' : 'en')
  }

  async function runEditFlow(text: string, requestId: string): Promise<boolean> {
    // Always log the user utterance to PG/Redis before attempting Kitty.
    if (llmResultsStore.isGenerating) {
      oneSentence.enqueueBusyEdit(requestId)
      lastEditRequestId = requestId
      await persistEditUserTurn(text, requestId, 'queued')
      replyState.showFinalReply(buildBusyQueuedReply())
      return true
    }
    await persistEditUserTurn(text, requestId)
    replyState.resetForNewTurn()
    const ok = await ensureKittyConnected()
    if (!ok) {
      oneSentence.markRequestFailed(requestId, 'kitty_unavailable')
      await persistKittyUiTurn(
        t('canvas.mindMapOneSentence.kittyUnavailable'),
        requestId,
        'failed',
        'ui_failed'
      )
      return false
    }
    const flushed = await syncKittyContext()
    if (!flushed.ok) {
      const detail = flushed.error?.trim() || 'unknown'
      console.warn(`[OneSentence] hub context sync failed detail=${detail}`)
      const msg = t('canvas.mindMapOneSentence.kittyContextSyncFailedDetail', { detail })
      replyState.showFinalReply(msg)
      oneSentence.markRequestFailed(requestId, 'context_sync_failed')
      await persistKittyUiTurn(msg, requestId, 'failed', 'ui_failed')
      return false
    }
    lastHubFingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
    lastEditRequestId = requestId
    oneSentence.markRequestInflight(requestId)
    kitty.sendTextMessage(text, requestId)
    return true
  }

  function handleBusyLlmEdit(errorCode: string | undefined): boolean {
    if (errorCode !== 'busy_llm_generating') {
      return false
    }
    const requestId = lastEditRequestId || activeRequestId.value
    if (requestId) {
      const req = oneSentence.getRequest(requestId)
      if (req) {
        oneSentence.enqueueBusyEdit(requestId)
        void persistEditUserTurn(req.text, requestId, 'queued')
      }
    }
    replyState.showFinalReply(buildBusyQueuedReply())
    return true
  }

  async function flushQueuedAfterGeneration(): Promise<void> {
    if (oneSentence.flushingBusyQueue || llmResultsStore.isGenerating) {
      return
    }
    if (activeRequestId.value) {
      const active = oneSentence.getRequest(activeRequestId.value)
      if (active?.status === 'inflight') {
        return
      }
    }
    const pending = oneSentence.dequeueBusyEdit()
    if (!pending) {
      return
    }
    oneSentence.setFlushingBusyQueue(true)
    try {
      replyState.showFinalReply(t('canvas.mindMapOneSentence.kittyEditBusyResuming'))
      const sent = await runEditFlow(pending.text, pending.requestId)
      if (!sent) {
        oneSentence.setDraft(pending.text)
      }
    } finally {
      oneSentence.setFlushingBusyQueue(false)
    }
  }

  function onRequestSettled(): void {
    void flushQueuedAfterGeneration()
  }

  async function sendDraft(): Promise<void> {
    const text = draft.value.trim()
    if (!text) return
    if (isInputBlocked.value) return
    if (diagramStore.collabSessionActive) return

    oneSentence.setDraft('')
    replyState.consumeOpenChoices()

    const useEditFlow = shouldUseOneSentenceEditFlow(
      diagramStore,
      savedDiagramsStore,
      llmResultsStore,
      phase.value
    )
    if (useEditFlow) {
      oneSentence.setPhase('edit')
      const req = oneSentence.registerUserRequest(text, 'inflight')
      const sent = await runEditFlow(text, req.requestId)
      if (!sent) {
        oneSentence.setDraft(text)
      }
      return
    }

    recordingCreatePhase = true
    // Stay in create until first generate result (phase 3).
    const req = oneSentence.registerUserRequest(text, 'inflight')
    await persistCreateTurn('user', text, 'ui_create', req.requestId)
    await runCreateFlow(text)
  }

  async function selectClarifyChoice(choice: OneSentenceClarifyChoice): Promise<void> {
    if (isInputBlocked.value || diagramStore.collabSessionActive) {
      return
    }
    oneSentence.setDraft(String(choice.index))
    await sendDraft()
  }

  function bindChatScroll(el: HTMLElement | null): void {
    chatScrollEl.value = el
  }

  async function bootstrapSession(): Promise<void> {
    const gen = ++bootstrapGeneration
    const libraryId = savedDiagramsStore.activeDiagramId
    if (libraryId) {
      oneSentence.setLibraryScope(libraryId)
      await maybeMigrateScope(libraryId)
    }
    if (gen !== bootstrapGeneration) return

    const restored = await fetchOneSentenceTurns(diagramScope.value)
    if (gen !== bootstrapGeneration) return

    if (restored.length > 0) {
      oneSentence.hydrateFromTurns(restored)
      oneSentence.setPhase('edit')
      if (libraryId) {
        oneSentence.setScopeMigrated(true)
      }
      scrollChatToBottom()
    } else if (
      shouldUseOneSentenceEditFlow(diagramStore, savedDiagramsStore, llmResultsStore, phase.value)
    ) {
      oneSentence.setPhase('edit')
      pushKittyMessage(pickOneSentenceGenerateDone(currentLanguage.value))
    } else {
      pushKittyMessage(pickOneSentenceWelcome(currentLanguage.value))
    }
    oneSentence.markSessionReady(diagramScope.value)
  }

  watch(
    () => llmResultsStore.selectedModel,
    (model) => {
      if (!generateWatchReady) return
      if (model && pendingGenerateReply) {
        pendingGenerateReply = false
        pushKittyMessage(pickOneSentenceGenerateDone(currentLanguage.value))
        recordingCreatePhase = false
        oneSentence.setPhase('edit')
        if (activeRequestId.value) {
          oneSentence.markRequestDone(activeRequestId.value)
        }
      }
    }
  )

  watch(isAIGenerating, (generating) => {
    setDiagramWriteLockHolder(generating ? 'llm' : null)
    if (kitty.isConnected.value && phase.value === 'edit') {
      kitty.updateContext(buildKittyContext())
    }
  })

  watch(phase, () => {
    if (kitty.isConnected.value) {
      void syncKittyContext()
    }
  })

  watch(isAIGenerating, (generating, wasGenerating) => {
    if (!generateWatchReady) return
    if (wasGenerating && !generating && pendingGenerateReply && !llmResultsStore.selectedModel) {
      handleGenerateFailure()
    }
  })

  watch(
    () => savedDiagramsStore.activeDiagramId,
    (libraryId) => {
      if (!libraryId) {
        oneSentence.setLibraryScope(null)
        return
      }
      oneSentence.setLibraryScope(libraryId)
      void (async () => {
        await maybeMigrateScope(libraryId)
        // Do not force create→edit here; wait for generate result or restored history.
      })()
    },
    { immediate: true }
  )

  function scheduleDebouncedHubSync(): void {
    if (!kitty.isConnected.value || phase.value !== 'edit') {
      return
    }
    if (hubSyncTimer != null) {
      clearTimeout(hubSyncTimer)
    }
    hubSyncTimer = setTimeout(() => {
      hubSyncTimer = null
      const fingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
      if (!fingerprint || fingerprint === lastHubFingerprint) {
        return
      }
      void syncKittyContext().then((result) => {
        if (result.ok) {
          lastHubFingerprint = fingerprint
        }
      })
    }, 500)
  }

  watch(
    () => getKittyDiagramContentFingerprint(diagramStore.data),
    () => {
      scheduleDebouncedHubSync()
    }
  )

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
      oneSentence.applyAckOutcome(activeRequestId.value, 'done')
      return
    }
    if (payload.verified === false) {
      if (handleBusyLlmEdit(payload.errorCode)) {
        return
      }
      replyState.showFinalReply(
        resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
      )
      oneSentence.applyAckOutcome(activeRequestId.value, 'failed', payload.errorCode)
    }
  }

  const onDiagramActionCompleted = (payload: {
    ok: boolean
    userSummary?: string
    errorCode?: string
    action: string
  }) => {
    if (payload.ok) {
      void syncKittyContext().then((result) => {
        if (result.ok) {
          lastHubFingerprint = getKittyDiagramContentFingerprint(diagramStore.data)
        }
      })
      if (payload.userSummary?.trim()) {
        replyState.showFinalReply(payload.userSummary.trim())
      }
      oneSentence.applyAckOutcome(activeRequestId.value, 'done')
      return
    }
    if (handleBusyLlmEdit(payload.errorCode)) {
      return
    }
    replyState.showFinalReply(
      resolveKittyEditFailureMessage(payload.errorCode, t, payload.action)
    )
    oneSentence.applyAckOutcome(activeRequestId.value, 'failed', payload.errorCode)
  }

  const onAsrPartial = (payload: { text: string }) => {
    if (payload.text.trim()) {
      oneSentence.setDraft(payload.text.trim())
    }
  }

  const onAsrFinal = (payload: { text: string }) => {
    const text = payload.text.trim()
    if (!text) {
      return
    }
    oneSentence.setDraft(text)
    funAsr.stopListening()
    void sendDraft()
  }

  const onDiagramEditFailed = (payload: { action: string; errorCode: string }) => {
    if (handleBusyLlmEdit(payload.errorCode)) {
      return
    }
    replyState.showFinalReply(resolveKittyEditFailureMessage(payload.errorCode, t, payload.action))
    oneSentence.applyAckOutcome(activeRequestId.value, 'failed', payload.errorCode)
  }

  const onOneSentenceReply = (payload: OneSentenceReplyPayload) => {
    if (phase.value !== 'edit' && phase.value !== 'create') {
      return
    }
    if (
      payload.kind === 'final' &&
      llmResultsStore.isGenerating &&
      lastEditRequestId &&
      (payload.text.trim() === t('canvas.mindMapOneSentence.kittyEditBusy') ||
        payload.text.includes('还在生成') ||
        payload.text.toLowerCase().includes('still streaming') ||
        payload.text.toLowerCase().includes('still generating'))
    ) {
      oneSentence.enqueueBusyEdit(lastEditRequestId)
      replyState.showFinalReply(buildBusyQueuedReply())
      return
    }
    replyState.handleReplyPayload(payload)
    if (payload.kind === 'final') {
      oneSentence.applyAckOutcome(payload.requestId || activeRequestId.value, 'done')
    }
  }

  const onAssistantDone = (payload: { text: string }) => {
    replyState.finalizeConversationalStream()
    const trimmed = payload.text.trim()
    if (trimmed === '') {
      return
    }
    if (
      oneSentence.peekBusyQueue().length > 0 &&
      (trimmed.includes('还在生成') ||
        trimmed.toLowerCase().includes('still streaming') ||
        trimmed.toLowerCase().includes('still generating') ||
        trimmed === t('canvas.mindMapOneSentence.kittyEditBusy'))
    ) {
      return
    }
    replyState.showFinalReply(trimmed)
  }

  const onResponseDone = () => {
    replyState.finalizeConversationalStream()
  }

  const onGenerationFailed = (payload: { error: string }) => {
    handleGenerateFailure(payload.error)
  }

  const onGenerationCompleted = () => {
    void flushQueuedAfterGeneration()
  }

  const onMessagesChanged = () => {
    scrollChatToBottom()
  }

  onMounted(() => {
    generateWatchReady = true
    void bootstrapSession()

    bus.on('kitty:one_sentence_reply', onOneSentenceReply)
    bus.on('voice:assistant_text_done', onAssistantDone)
    bus.on('voice:response_done', onResponseDone)
    bus.on('voice:diagram_update_executed', onDiagramUpdate)
    bus.on('kitty:diagram_action_completed', onDiagramActionCompleted)
    bus.on('kitty:diagram_edit_failed', onDiagramEditFailed)
    bus.on('llm:generation_failed', onGenerationFailed)
    bus.on('llm:generation_completed', onGenerationCompleted)
    bus.on('oneSentence:request_done', onRequestSettled)
    bus.on('oneSentence:request_failed', onRequestSettled)
    bus.on('kitty:asr_partial', onAsrPartial)
    bus.on('kitty:asr_final', onAsrFinal)
    bus.on('oneSentence:messages_changed', onMessagesChanged)
    bus.on('oneSentence:session_reset', () => {
      void bootstrapSession()
    })
  })

  onUnmounted(() => {
    bootstrapGeneration += 1
    if (hubSyncTimer != null) {
      clearTimeout(hubSyncTimer)
      hubSyncTimer = null
    }
    funAsr.stopListening()
    void kitty.stopConversation()
  })

  return {
    draft,
    messages,
    phase,
    connecting,
    isInputBlocked,
    kittyAgentState,
    kittyEnabled,
    asrListening,
    asrPartialTranscript,
    toggleMic: funAsr.toggleListening,
    sendDraft,
    selectClarifyChoice,
    bindChatScroll,
  }
}
