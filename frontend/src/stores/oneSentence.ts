/**
 * One-sentence mini-chat SoT — messages, phase, scope, request lifecycle, FIFO busy queue.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type OneSentenceChatRole = 'user' | 'kitty'
export type OneSentencePhase = 'create' | 'edit'
export type OneSentenceRequestStatus = 'queued' | 'inflight' | 'done' | 'failed'

export type OneSentenceClarifyChoice = {
  /** 1-based index — matches backend ``classify_clarify_option_pick``. */
  index: number
  label: string
}

export type OneSentenceChatMessage = {
  id: string
  role: OneSentenceChatRole
  text: string
  streaming?: boolean
  choices?: OneSentenceClarifyChoice[]
  /** True after the user picks or a newer turn starts. */
  choicesConsumed?: boolean
  requestId?: string
  status?: OneSentenceRequestStatus
}

export type OneSentenceRequestState = {
  requestId: string
  text: string
  status: OneSentenceRequestStatus
  messageId: string
  createdAt: number
  errorCode?: string
}

export type OneSentenceTurnHydrateRow = {
  turn_id: string
  role: 'user' | 'kitty' | 'meta'
  content: string
  phase?: OneSentencePhase
  request_id?: string
  outcome?: string
}

let messageSeq = 0

function nextMessageId(): string {
  messageSeq += 1
  return `one-sentence-msg-${messageSeq}`
}

function emitRequestStatus(
  event:
    | 'oneSentence:request_queued'
    | 'oneSentence:request_inflight'
    | 'oneSentence:request_done'
    | 'oneSentence:request_failed',
  requestId: string,
  extras?: { text?: string; errorCode?: string; scope?: string }
): void {
  eventBus.emit(event, {
    requestId,
    status:
      event === 'oneSentence:request_queued'
        ? 'queued'
        : event === 'oneSentence:request_inflight'
          ? 'inflight'
          : event === 'oneSentence:request_done'
            ? 'done'
            : 'failed',
    text: extras?.text,
    errorCode: extras?.errorCode,
    scope: extras?.scope,
  })
}

export const useOneSentenceStore = defineStore('oneSentence', () => {
  const draft = ref('')
  const messages = ref<OneSentenceChatMessage[]>([])
  const phase = ref<OneSentencePhase>('create')
  const connecting = ref(false)
  const sessionReady = ref(false)
  const ephemeralScope = ref(safeRandomUUID())
  const scopeMigrated = ref(false)
  const libraryScope = ref<string | null>(null)
  const requests = ref<Record<string, OneSentenceRequestState>>({})
  /** FIFO of request ids waiting for multi-LLM generation to finish. */
  const busyQueue = ref<string[]>([])
  const activeRequestId = ref<string | null>(null)
  const flushingBusyQueue = ref(false)

  const diagramScope = computed(
    () => libraryScope.value ?? ephemeralScope.value
  )

  function getRequest(requestId: string): OneSentenceRequestState | null {
    return requests.value[requestId] ?? null
  }

  function setDraft(text: string): void {
    draft.value = text
  }

  function setPhase(next: OneSentencePhase): void {
    phase.value = next
  }

  function setConnecting(value: boolean): void {
    connecting.value = value
  }

  function setLibraryScope(scope: string | null): void {
    libraryScope.value = scope
  }

  function setScopeMigrated(value: boolean): void {
    scopeMigrated.value = value
  }

  function scrollHint(): void {
    eventBus.emit('oneSentence:messages_changed', { scope: diagramScope.value })
  }

  function pushMessage(
    role: OneSentenceChatRole,
    text: string,
    streaming = false,
    extras?: {
      choices?: OneSentenceClarifyChoice[]
      requestId?: string
      status?: OneSentenceRequestStatus
    }
  ): string {
    const id = nextMessageId()
    const row: OneSentenceChatMessage = { id, role, text, streaming }
    if (extras?.choices?.length) {
      row.choices = extras.choices
    }
    if (extras?.requestId) {
      row.requestId = extras.requestId
    }
    if (extras?.status) {
      row.status = extras.status
    }
    messages.value = [...messages.value, row]
    scrollHint()
    return id
  }

  function replaceMessage(
    messageId: string,
    text: string,
    streaming = false,
    extras?: { choices?: OneSentenceClarifyChoice[]; status?: OneSentenceRequestStatus }
  ): void {
    const idx = messages.value.findIndex((m) => m.id === messageId)
    if (idx < 0) {
      pushMessage('kitty', text, streaming, {
        choices: extras?.choices,
        status: extras?.status,
      })
      return
    }
    const next = [...messages.value]
    const prev = next[idx]
    next[idx] = {
      ...prev,
      text,
      streaming,
      ...(extras?.choices !== undefined ? { choices: extras.choices } : {}),
      ...(extras?.status !== undefined ? { status: extras.status } : {}),
    }
    messages.value = next
    scrollHint()
  }

  function updateMessageStatus(messageId: string, status: OneSentenceRequestStatus): void {
    const idx = messages.value.findIndex((m) => m.id === messageId)
    if (idx < 0) {
      return
    }
    const next = [...messages.value]
    next[idx] = { ...next[idx], status }
    messages.value = next
  }

  function setMessages(rows: OneSentenceChatMessage[]): void {
    messages.value = rows
    scrollHint()
  }

  function _setRequestStatus(
    requestId: string,
    status: OneSentenceRequestStatus,
    extras?: { errorCode?: string }
  ): void {
    const current = requests.value[requestId]
    if (!current) {
      return
    }
    const updated: OneSentenceRequestState = {
      ...current,
      status,
      errorCode: extras?.errorCode,
    }
    requests.value = { ...requests.value, [requestId]: updated }
    updateMessageStatus(current.messageId, status)
    const scope = diagramScope.value
    if (import.meta.env.DEV) {
      console.info(
        `[OneSentence] request ${status} id=${requestId.slice(0, 8)} scope=${scope.slice(0, 8)}` +
          (extras?.errorCode ? ` error=${extras.errorCode}` : '')
      )
    }
    if (status === 'queued') {
      emitRequestStatus('oneSentence:request_queued', requestId, {
        text: current.text,
        scope,
      })
    } else if (status === 'inflight') {
      emitRequestStatus('oneSentence:request_inflight', requestId, {
        text: current.text,
        scope,
      })
    } else if (status === 'done') {
      emitRequestStatus('oneSentence:request_done', requestId, {
        text: current.text,
        scope,
      })
    } else {
      emitRequestStatus('oneSentence:request_failed', requestId, {
        text: current.text,
        errorCode: extras?.errorCode,
        scope,
      })
    }
  }

  function registerUserRequest(
    text: string,
    status: OneSentenceRequestStatus = 'inflight',
    preferredRequestId?: string
  ): OneSentenceRequestState {
    const requestId = preferredRequestId?.trim() || safeRandomUUID()
    const messageId = pushMessage('user', text, false, { requestId, status })
    const state: OneSentenceRequestState = {
      requestId,
      text,
      status,
      messageId,
      createdAt: Date.now(),
    }
    requests.value = { ...requests.value, [requestId]: state }
    if (status === 'inflight') {
      activeRequestId.value = requestId
    }
    _setRequestStatus(requestId, status)
    return state
  }

  function markRequestInflight(requestId: string): void {
    activeRequestId.value = requestId
    _setRequestStatus(requestId, 'inflight')
  }

  function markRequestDone(requestId: string): void {
    _setRequestStatus(requestId, 'done')
    if (activeRequestId.value === requestId) {
      activeRequestId.value = null
    }
  }

  function markRequestFailed(requestId: string, errorCode?: string): void {
    _setRequestStatus(requestId, 'failed', { errorCode })
    if (activeRequestId.value === requestId) {
      activeRequestId.value = null
    }
  }

  function applyAckOutcome(
    requestId: string | null | undefined,
    outcome: 'done' | 'failed',
    errorCode?: string
  ): void {
    const id = (requestId || activeRequestId.value || '').trim()
    if (!id || !requests.value[id]) {
      return
    }
    if (outcome === 'done') {
      markRequestDone(id)
      return
    }
    markRequestFailed(id, errorCode)
  }

  function enqueueBusyEdit(requestId: string): void {
    if (!requests.value[requestId]) {
      return
    }
    if (!busyQueue.value.includes(requestId)) {
      busyQueue.value = [...busyQueue.value, requestId]
    }
    _setRequestStatus(requestId, 'queued')
  }

  function dequeueBusyEdit(): OneSentenceRequestState | null {
    while (busyQueue.value.length > 0) {
      const [nextId, ...rest] = busyQueue.value
      busyQueue.value = rest
      const state = requests.value[nextId]
      if (state && (state.status === 'queued' || state.status === 'inflight')) {
        return state
      }
    }
    return null
  }

  function peekBusyQueue(): string[] {
    return [...busyQueue.value]
  }

  function clearBusyQueue(): void {
    busyQueue.value = []
  }

  function setFlushingBusyQueue(value: boolean): void {
    flushingBusyQueue.value = value
  }

  function hydrateFromTurns(turns: OneSentenceTurnHydrateRow[]): void {
    const rows: OneSentenceChatMessage[] = []
    const nextRequests: Record<string, OneSentenceRequestState> = {}
    for (const turn of turns) {
      if (turn.role !== 'user' && turn.role !== 'kitty') {
        continue
      }
      const requestId = turn.request_id?.trim() || undefined
      let status: OneSentenceRequestStatus | undefined
      if (turn.role === 'user' && requestId) {
        const outcome = (turn.outcome || '').toLowerCase()
        if (outcome === 'failed' || outcome === 'error') {
          status = 'failed'
        } else if (outcome === 'queued') {
          status = 'queued'
        } else {
          status = 'done'
        }
        nextRequests[requestId] = {
          requestId,
          text: turn.content,
          status,
          messageId: turn.turn_id || nextMessageId(),
          createdAt: Date.now(),
        }
      }
      rows.push({
        id: turn.turn_id || nextMessageId(),
        role: turn.role,
        text: turn.content,
        requestId,
        status: turn.role === 'user' ? status : undefined,
      })
    }

    // Prefer kitty outcome rows when present for the same request_id.
    for (const turn of turns) {
      if (turn.role !== 'kitty' || !turn.request_id) {
        continue
      }
      const req = nextRequests[turn.request_id]
      if (!req) {
        continue
      }
      const outcome = (turn.outcome || '').toLowerCase()
      if (outcome === 'failed' || outcome === 'error') {
        req.status = 'failed'
      } else if (outcome === 'success' || outcome === 'ok' || outcome === 'done' || !outcome) {
        req.status = 'done'
      }
      const msg = rows.find((r) => r.requestId === turn.request_id && r.role === 'user')
      if (msg) {
        msg.status = req.status
      }
    }

    messages.value = rows
    requests.value = nextRequests
    busyQueue.value = []
    activeRequestId.value = null
    scrollHint()
  }

  function markSessionReady(scope?: string): void {
    sessionReady.value = true
    eventBus.emit('oneSentence:session_ready', {
      scope: scope ?? diagramScope.value,
    })
  }

  function emitSessionMigrated(fromScope: string, toScope: string): void {
    scopeMigrated.value = true
    libraryScope.value = toScope
    eventBus.emit('oneSentence:session_migrated', { fromScope, toScope })
  }

  /**
   * Canvas reset: durable library history stays in Redis/PG; UI clears and
   * ephemeral scope rotates so a blank canvas does not reuse the old thread.
   */
  function onCanvasReset(): void {
    messages.value = []
    requests.value = {}
    busyQueue.value = []
    activeRequestId.value = null
    draft.value = ''
    phase.value = 'create'
    connecting.value = false
    sessionReady.value = false
    scopeMigrated.value = false
    libraryScope.value = null
    ephemeralScope.value = safeRandomUUID()
    eventBus.emit('oneSentence:session_reset', { scope: ephemeralScope.value })
  }

  /**
   * Adopt a shared Kitty session scope (mobile open_canvas → desktop).
   * Clears UI chat and binds ephemeral scope to the mobile-issued id so
   * canvas-owner WS and one-sentence turns share one SoT.
   */
  function adoptEphemeralScope(scope: string): void {
    const normalized = scope.trim()
    if (!normalized) {
      return
    }
    messages.value = []
    requests.value = {}
    busyQueue.value = []
    activeRequestId.value = null
    draft.value = ''
    phase.value = 'create'
    connecting.value = false
    sessionReady.value = false
    scopeMigrated.value = false
    libraryScope.value = null
    ephemeralScope.value = normalized
    eventBus.emit('oneSentence:session_reset', { scope: normalized })
  }

  /**
   * Clear in-memory chat for a fresh welcome seed. Does not rotate ephemeral
   * scope (use ``onCanvasReset`` when leaving a diagram entirely).
   */
  function resetChatUiForWelcome(): void {
    messages.value = []
    requests.value = {}
    busyQueue.value = []
    activeRequestId.value = null
    draft.value = ''
    phase.value = 'create'
    connecting.value = false
    sessionReady.value = false
  }

  return {
    draft,
    messages,
    phase,
    connecting,
    sessionReady,
    ephemeralScope,
    scopeMigrated,
    libraryScope,
    diagramScope,
    requests,
    busyQueue,
    activeRequestId,
    flushingBusyQueue,
    getRequest,
    setDraft,
    setPhase,
    setConnecting,
    setLibraryScope,
    setScopeMigrated,
    pushMessage,
    replaceMessage,
    updateMessageStatus,
    setMessages,
    registerUserRequest,
    markRequestInflight,
    markRequestDone,
    markRequestFailed,
    applyAckOutcome,
    enqueueBusyEdit,
    dequeueBusyEdit,
    peekBusyQueue,
    clearBusyQueue,
    setFlushingBusyQueue,
    hydrateFromTurns,
    markSessionReady,
    emitSessionMigrated,
    onCanvasReset,
    adoptEphemeralScope,
    resetChatUiForWelcome,
  }
})
