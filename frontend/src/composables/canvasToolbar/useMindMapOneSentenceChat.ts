/**
 * One-sentence panel chat: first message → prompt-to-diagram; follow-ups → Kitty text (no voice).
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { useRoute, useRouter } from 'vue-router'

import { diagramTypeToChineseMap } from '@/composables/canvasPage/diagramTypeMaps'
import {
  canvasDiagramSlugsEquivalent,
  extractTopicSeedFromPrompt,
  resolveDiagramTypeFromPrompt,
} from '@/composables/canvasPage/diagramTypeFromPrompt'
import { isCanvasPristineForTypeSwitch } from '@/composables/canvasPage/isCanvasPristineForTypeSwitch'
import { switchCanvasDiagramType } from '@/composables/canvasPage/switchCanvasDiagramType'
import { useCanvasToolbarApps } from '@/composables/canvasToolbar/useCanvasToolbarApps'
import {
  appendOneSentenceTurn,
  fetchOneSentenceTurns,
  migrateOneSentenceScope,
  type OneSentenceTurnInput,
} from '@/composables/canvasToolbar/useOneSentenceSessionTurns'
import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { buildKittyDiagramContext } from '@/composables/kitty/buildKittyDiagramContext'
import { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import {
  useDiagramStore,
  useFeatureFlagsStore,
  useLLMResultsStore,
  useSavedDiagramsStore,
} from '@/stores'

export type OneSentenceChatRole = 'user' | 'kitty'

export type OneSentenceChatMessage = {
  id: string
  role: OneSentenceChatRole
  text: string
  streaming?: boolean
}

let messageSeq = 0

function nextMessageId(): string {
  messageSeq += 1
  return `one-sentence-msg-${messageSeq}`
}

export function useMindMapOneSentenceChat() {
  const { t } = useLanguage()
  const route = useRoute()
  const router = useRouter()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const featureFlagsStore = useFeatureFlagsStore()
  const { isAIGenerating, handleAIGenerate } = useCanvasToolbarApps()

  const isWaitingForFirstResult = computed(
    () => isAIGenerating.value && !llmResultsStore.selectedModel
  )

  const connecting = ref(false)

  const isInputBlocked = computed(
    () =>
      isWaitingForFirstResult.value ||
      connecting.value ||
      diagramStore.collabSessionActive
  )

  const inputBlockReason = computed(() => {
    if (diagramStore.collabSessionActive) {
      return t('canvas.toolbar.collabLiveAiDisabled')
    }
    if (isWaitingForFirstResult.value) {
      return t('canvas.mindMapOneSentence.inputBlockedGenerating')
    }
    if (connecting.value) {
      return t('canvas.mindMapOneSentence.kittyWorking')
    }
    return null
  })

  const draft = ref('')
  const messages = ref<OneSentenceChatMessage[]>([])
  const phase = ref<'create' | 'edit'>('create')
  const chatScrollEl = ref<HTMLElement | null>(null)

  const ephemeralScope = ref(crypto.randomUUID())
  const scopeMigrated = ref(false)
  const kittyScope = computed(
    () => savedDiagramsStore.activeDiagramId ?? ephemeralScope.value
  )

  const kittyEnabled = computed(() => featureFlagsStore.getFeatureKittyAgent())

  let streamingMessageId: string | null = null
  let lastAckText = ''
  let pendingGenerateReply = false
  let generateWatchReady = false
  let recordingCreatePhase = false

  const kitty = useKittyAgent({
    ownerId: 'MindMapOneSentencePanel',
    textOnly: true,
    onTextChunk: (chunk) => {
      appendKittyStream(chunk)
    },
    onError: (err) => {
      pushKittyMessage(err)
    },
  })

  const kittyAgentState = computed(() => kitty.state.value)

  function scrollChatToBottom(): void {
    void nextTick(() => {
      const el = chatScrollEl.value
      if (!el) return
      el.scrollTop = el.scrollHeight
    })
  }

  function pushMessage(role: OneSentenceChatRole, text: string, streaming = false): string {
    const id = nextMessageId()
    messages.value = [...messages.value, { id, role, text, streaming }]
    scrollChatToBottom()
    return id
  }

  function persistCreateTurn(role: OneSentenceChatRole, text: string, source: string): void {
    if (!recordingCreatePhase) return
    const trimmed = text.trim()
    if (trimmed === '') return
    const payload: OneSentenceTurnInput = {
      role,
      content: trimmed,
      phase: 'create',
      source,
      diagram_type: diagramStore.type ?? undefined,
    }
    void appendOneSentenceTurn(kittyScope.value, payload)
  }

  function pushKittyMessage(text: string, streaming = false): string {
    const id = pushMessage('kitty', text, streaming)
    if (!streaming) {
      persistCreateTurn('kitty', text, 'ui_create')
    }
    return id
  }

  function appendKittyStream(chunk: string): void {
    const piece = chunk.trim()
    if (piece === '') return

    if (!streamingMessageId) {
      streamingMessageId = pushKittyMessage(piece, true)
      lastAckText = piece
      return
    }

    const idx = messages.value.findIndex((m) => m.id === streamingMessageId)
    if (idx < 0) {
      streamingMessageId = pushKittyMessage(piece, true)
      return
    }

    const row = messages.value[idx]
    const merged = `${row.text}${chunk}`
    const next = [...messages.value]
    next[idx] = { ...row, text: merged, streaming: true }
    messages.value = next
    scrollChatToBottom()
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

  function applyKittyAck(text: string): void {
    const trimmed = text.trim()
    if (trimmed === '' || trimmed === lastAckText) return

    const last = messages.value[messages.value.length - 1]
    if (last?.role === 'kitty' && last.text === trimmed) return

    if (
      last?.role === 'kitty' &&
      lastAckText !== '' &&
      last.text === lastAckText &&
      trimmed !== lastAckText
    ) {
      replaceKittyMessage(last.id, trimmed, false)
      lastAckText = trimmed
      return
    }

    pushKittyMessage(trimmed)
    lastAckText = trimmed
  }

  function finalizeKittyStream(): void {
    if (!streamingMessageId) return
    const idx = messages.value.findIndex((m) => m.id === streamingMessageId)
    if (idx >= 0) {
      const next = [...messages.value]
      next[idx] = { ...next[idx], streaming: false }
      messages.value = next
    }
    streamingMessageId = null
  }

  function handleGenerateFailure(error?: string): void {
    if (!pendingGenerateReply) return
    pendingGenerateReply = false
    recordingCreatePhase = false
    const fallback = t('canvas.mindMapOneSentence.kittyGenerateFailed')
    const msg = error?.trim() || fallback
    pushKittyMessage(msg)
  }

  function buildKittyContext() {
    return buildKittyDiagramContext(diagramStore, 'one_sentence')
  }

  async function ensureKittyConnected(): Promise<boolean> {
    if (!kittyEnabled.value) {
      pushKittyMessage(t('canvas.mindMapOneSentence.kittyUnavailable'))
      return false
    }
    if (kitty.isConnected.value) return true

    connecting.value = true
    try {
      await kitty.startConversation(kittyScope.value, buildKittyContext())
      return true
    } catch {
      pushKittyMessage(t('canvas.mindMapOneSentence.kittyUnavailable'))
      return false
    } finally {
      connecting.value = false
    }
  }

  async function syncKittyContext(): Promise<void> {
    if (!kitty.isConnected.value) return
    kitty.updateContext(buildKittyContext())
  }

  async function maybeMigrateScope(libraryId: string): Promise<void> {
    if (scopeMigrated.value) return
    const fromScope = ephemeralScope.value
    if (!fromScope || fromScope === libraryId) {
      scopeMigrated.value = true
      return
    }
    const ok = await migrateOneSentenceScope(fromScope, libraryId)
    if (ok) {
      scopeMigrated.value = true
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
    pushKittyMessage(t('canvas.mindMapOneSentence.kittyGenerating'))
    await handleAIGenerate({ generationInstructions: text })
  }

  async function runEditFlow(text: string): Promise<void> {
    lastAckText = ''
    const ok = await ensureKittyConnected()
    if (!ok) {
      return
    }
    await syncKittyContext()
    kitty.sendTextMessage(text)
  }

  async function sendDraft(): Promise<void> {
    const text = draft.value.trim()
    if (!text) return
    if (isInputBlocked.value) return
    if (diagramStore.collabSessionActive) return

    draft.value = ''
    pushMessage('user', text)

    if (phase.value === 'create') {
      recordingCreatePhase = true
      phase.value = 'edit'
      persistCreateTurn('user', text, 'ui_create')
      await runCreateFlow(text)
      return
    }

    await runEditFlow(text)
  }

  function bindChatScroll(el: HTMLElement | null): void {
    chatScrollEl.value = el
  }

  watch(
    () => llmResultsStore.selectedModel,
    (model) => {
      if (!generateWatchReady) return
      if (model && pendingGenerateReply) {
        pendingGenerateReply = false
        pushKittyMessage(t('canvas.mindMapOneSentence.kittyGenerateDone'))
        recordingCreatePhase = false
      }
    }
  )

  watch(isAIGenerating, (generating, wasGenerating) => {
    if (!generateWatchReady) return
    if (wasGenerating && !generating && pendingGenerateReply && !llmResultsStore.selectedModel) {
      handleGenerateFailure()
    }
  })

  watch(
    () => savedDiagramsStore.activeDiagramId,
    (libraryId) => {
      if (!libraryId) return
      void maybeMigrateScope(libraryId)
    },
    { immediate: true }
  )

  const onAssistantDone = (payload: { text: string }) => {
    finalizeKittyStream()
    const trimmed = payload.text.trim()
    if (trimmed !== '' && !streamingMessageId) {
      applyKittyAck(trimmed)
    }
  }

  const onResponseDone = () => {
    finalizeKittyStream()
  }

  const onGenerationFailed = (payload: { error: string }) => {
    handleGenerateFailure(payload.error)
  }

  const onDiagramUpdate = (payload: { summary?: string; userSummary?: string }) => {
    const userSummary = String(payload.userSummary ?? '').trim()
    const summary = userSummary !== '' ? userSummary : String(payload.summary ?? '').trim()
    if (summary === '') return
    if (summary === lastAckText) return
    if (
      userSummary === '' &&
      (summary.startsWith('add_node {') ||
        summary.startsWith('update_nodes') ||
        summary.startsWith('remove_nodes'))
    ) {
      return
    }

    if (streamingMessageId) {
      replaceKittyMessage(streamingMessageId, summary, false)
      streamingMessageId = null
      lastAckText = summary
      return
    }

    applyKittyAck(summary)
  }

  onMounted(async () => {
    generateWatchReady = true
    const restored = await fetchOneSentenceTurns(kittyScope.value)
    if (restored.length > 0) {
      messages.value = restored.map((row) => ({
        id: row.turn_id || nextMessageId(),
        role: row.role === 'kitty' ? 'kitty' : 'user',
        text: row.content,
      }))
      phase.value = 'edit'
      scopeMigrated.value = Boolean(savedDiagramsStore.activeDiagramId)
      scrollChatToBottom()
    } else {
      pushKittyMessage(t('canvas.mindMapOneSentence.kittyWelcome'))
    }
    eventBus.on('voice:assistant_text_done', onAssistantDone)
    eventBus.on('voice:response_done', onResponseDone)
    eventBus.on('voice:diagram_update_executed', onDiagramUpdate)
    eventBus.on('llm:generation_failed', onGenerationFailed)
  })

  onUnmounted(() => {
    eventBus.off('voice:assistant_text_done', onAssistantDone)
    eventBus.off('voice:response_done', onResponseDone)
    eventBus.off('voice:diagram_update_executed', onDiagramUpdate)
    eventBus.off('llm:generation_failed', onGenerationFailed)
    void kitty.stopConversation()
  })

  return {
    draft,
    messages,
    phase,
    connecting,
    isInputBlocked,
    inputBlockReason,
    kittyAgentState,
    kittyEnabled,
    sendDraft,
    bindChatScroll,
  }
}
