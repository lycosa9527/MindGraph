/**
 * MindMate collab room WebSocket client.
 */
import { computed, ref, shallowRef } from 'vue'

import { useWebSocket } from '@vueuse/core'

import { useLanguage, useNotifications } from '@/composables'
import { createCollabSocketHeartbeat } from '@/composables/mindmate/mindmateCollabHeartbeat'
import {
  loadOlderSeminarPage,
  pullMindmateCollabHistory,
} from '@/composables/mindmate/pullMindmateCollabHistory'
import { useMindmateCollabRead } from '@/composables/mindmate/useMindmateCollabRead'
import { showSeminarFaces } from '@/composables/mindmate/useMindmateSeminarFaces'
import { useAuthStore } from '@/stores/auth'
import {
  mergeMindmateCollabSnapshot,
  resolveCollabAssistantEndContent,
} from '@/utils/mindmateCollabDisplay'
import {
  collabChainNeedsFill,
  collabGapAfterId,
  collabMaxSavedId,
  collabPrevId,
  collabSnapshotBackfillAfterId,
  collabTranscriptBehind,
  insertMissingCollabMessages,
  streamingCoveredBySaved,
} from '@/utils/mindmateCollabGap'
import { collabFrameCreatedAt } from '@/utils/mindmateCollabRead'
import {
  MINDMATE_COLLAB_RECONNECT,
  computeMindmateCollabReconnectDelayMs,
  mindmateCollabPermanentFailureLocaleKey,
  shouldScheduleMindmateCollabReconnect,
} from '@/utils/mindmateCollabReconnect'
import { shouldReconnectMindmateCollab } from '@/utils/mindmateCollabSessions'
import {
  type MindmateCollabConnectionStatus,
  mindmateCollabDisconnectShouldNotify,
  mindmateCollabWsErrorLocaleKey,
  mindmateCollabWsErrorRollsBackSend,
} from '@/utils/mindmateCollabWsErrors'
import {
  type SeminarFace,
  removeSeminarFace,
  seminarFaceFromPayload,
  seminarFacesFromJoined,
  upsertSeminarFace,
} from '@/utils/mindmateSeminarFaces'

export interface MindmateCollabMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  sender_user_id?: number | null
  username?: string | null
  streaming?: boolean
  clientKey?: string
  created_at?: string
}

export interface MindmateCollabRoomInfo {
  sessionId: string
  code: string
  title: string
  visibility: string
  ownerId: number
}

function buildWsUrl(code: string, resumeToken?: string | null): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  const enc = encodeURIComponent(code)
  const base = `${proto}://${host}/api/ws/mindmate-collab/${enc}`
  if (resumeToken) {
    return `${base}?resume=${encodeURIComponent(resumeToken)}`
  }
  return base
}

export interface UseMindmateCollabOptions {
  onSessionEnded?: (reason: 'idle' | 'host') => void
  embedded?: boolean
  seedMessages?: () => MindmateCollabMessage[]
  /** When false, face updates stay on this room and do not replace the header. */
  isForeground?: () => boolean
}

export function useMindmateCollab(
  roomCode: () => string | null,
  options: UseMindmateCollabOptions = {}
) {
  const authStore = useAuthStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  const messages = shallowRef<MindmateCollabMessage[]>([])
  const hasOlder = ref(false)
  const room = ref<MindmateCollabRoomInfo | null>(null)
  const connected = ref(false)
  const connectionStatus = ref<MindmateCollabConnectionStatus>('idle')
  const isStreaming = ref(false)
  const idleWarningSeconds = ref<number | null>(null)
  const resumeToken = ref<string | null>(null)
  /** Mutated before each `open()`; VueUse reads this array reference at connect time. */
  const wsProtocolList: string[] = []
  const suppressReconnect = ref(false)
  const shutdownPending = ref(false)

  /** Set only at connect/reconnect time — not reactive to resumeToken while open. */
  const wsUrl = ref('')

  function refreshWsUrlForConnect(): void {
    const code = roomCode()
    if (!code) {
      wsUrl.value = ''
      return
    }
    wsUrl.value = buildWsUrl(code, resumeToken.value)
  }

  let streamingAssistant: MindmateCollabMessage | null = null
  let idleDeadlineUnix: number | null = null
  let idleTickInterval: ReturnType<typeof setInterval> | null = null
  let pendingReconnectFailedNotify = false
  let lastOptimisticSendContent: string | null = null
  let lastCloseCode = 1006
  const gapFill = { current: null as Promise<void> | null }
  let gapGeneration = 0
  const disposed = false
  let socketSend: (data: string) => boolean = () => false
  let openSocket: () => void = () => {}
  let ignoreNextClose = false

  const heartbeat = createCollabSocketHeartbeat({
    sendPing: () => socketSend(JSON.stringify({ type: 'socket_ping' })),
    reopen: () => {
      heartbeat.stop()
      ignoreNextClose = true
      suppressReconnect.value = false
      shutdownPending.value = false
      connectionStatus.value = 'reconnecting'
      openSocket()
    },
    isActive: () => connected.value && !suppressReconnect.value,
  })

  const { readCursors, noteReadCursorFrame, noteReadCursorList, resetReadCursors } =
    useMindmateCollabRead({
      messages,
      connected,
      isDisposed: () => disposed,
      send: (body) => socketSend(body),
    })

  async function pullMessagesAfter(startAfter: number): Promise<boolean> {
    const sessionId = room.value?.sessionId ?? ''
    const generation = gapGeneration
    return pullMindmateCollabHistory<MindmateCollabMessage>({
      sessionId,
      startAfter,
      stillCurrent: () => Boolean(sessionId) && !disposed && generation === gapGeneration,
      gapFill,
      applyRows: (rows) => {
        messages.value = insertMissingCollabMessages(messages.value, rows)
        if (streamingAssistant && streamingCoveredBySaved(streamingAssistant.content, rows)) {
          messages.value = messages.value.filter((row) => row !== streamingAssistant)
          streamingAssistant = null
          isStreaming.value = false
        }
      },
    })
  }

  async function pullMissingMessages(targetId: number): Promise<void> {
    if (!collabChainNeedsFill(messages.value, targetId)) {
      return
    }
    await pullMessagesAfter(collabGapAfterId(messages.value, targetId))
  }

  function noteMessageChain(prevId: number | null): void {
    if (prevId == null || !collabChainNeedsFill(messages.value, prevId)) {
      return
    }
    void pullMissingMessages(prevId)
  }

  function stopIdleCountdownTick(): void {
    if (idleTickInterval) {
      clearInterval(idleTickInterval)
      idleTickInterval = null
    }
  }

  function syncIdleSecondsFromDeadline(): void {
    if (idleDeadlineUnix == null) {
      idleWarningSeconds.value = null
      return
    }
    idleWarningSeconds.value = Math.max(0, idleDeadlineUnix - Math.floor(Date.now() / 1000))
  }

  function clearIdleCountdown(): void {
    idleDeadlineUnix = null
    idleWarningSeconds.value = null
    stopIdleCountdownTick()
  }

  function applyIdleWarning(graceSeconds: number): void {
    clearIdleCountdown()
    idleDeadlineUnix = Math.floor(Date.now() / 1000) + Math.max(1, graceSeconds)
    syncIdleSecondsFromDeadline()
    stopIdleCountdownTick()
    idleTickInterval = setInterval(() => syncIdleSecondsFromDeadline(), 1000)
  }

  function removeLastOptimisticUserMessage(content: string): void {
    const selfId = Number(authStore.user?.id)
    const next = [...messages.value]
    for (let index = next.length - 1; index >= 0; index -= 1) {
      const candidate = next[index]
      if (
        candidate.role === 'user' &&
        candidate.sender_user_id === selfId &&
        candidate.id == null &&
        candidate.content === content
      ) {
        next.splice(index, 1)
        messages.value = next
        return
      }
    }
  }

  function handleServerErrorFrame(parsed: Record<string, unknown>): void {
    const errorCode = String(parsed.code || '')
    const localeKey = mindmateCollabWsErrorLocaleKey(errorCode)
    if (localeKey) {
      const serverMessage = String(parsed.message || '').trim()
      if (errorCode === 'dify_error' && serverMessage) {
        notify.error(serverMessage)
      } else {
        notify.warningKey(localeKey)
      }
    } else {
      const fallback = String(parsed.message || '').trim()
      if (fallback) {
        notify.warning(fallback)
      } else {
        notify.warningKey('mindmate.collabErrorUnknown')
      }
    }
    if (mindmateCollabWsErrorRollsBackSend(errorCode) && lastOptimisticSendContent) {
      removeLastOptimisticUserMessage(lastOptimisticSendContent)
      lastOptimisticSendContent = null
    }
    if (errorCode === 'room_closed') {
      suppressReconnect.value = true
      connectionStatus.value = 'failed'
    }
  }

  function notifyDisconnect(closeCode: number, reason: string): void {
    const action = mindmateCollabDisconnectShouldNotify(
      closeCode,
      suppressReconnect.value,
      pendingReconnectFailedNotify
    )
    pendingReconnectFailedNotify = false

    if (action === 'none') {
      return
    }
    if (action === 'reconnect_failed') {
      connectionStatus.value = 'failed'
      if (isForegroundRoom()) {
        notify.errorKey('mindmate.collabReconnectFailed')
      }
      return
    }
    if (action === 'closed_reason') {
      connectionStatus.value = 'failed'
      if (!isForegroundRoom()) {
        return
      }
      const label = reason.trim() || t('mindmate.collabConnectionClosed')
      notify.warningKey('mindmate.collabConnectionClosedReason', { reason: label })
      return
    }
    connectionStatus.value = 'reconnecting'
  }

  const { open, close, send } = useWebSocket(wsUrl, {
    immediate: false,
    autoConnect: false,
    protocols: wsProtocolList,
    autoReconnect: {
      retries: (retried) => {
        if (suppressReconnect.value || shutdownPending.value) {
          return false
        }
        if (!shouldScheduleMindmateCollabReconnect(retried, lastCloseCode)) {
          pendingReconnectFailedNotify = true
          return false
        }
        connectionStatus.value = 'reconnecting'
        syncWsResumeProtocols()
        refreshWsUrlForConnect()
        return true
      },
      delay: (retried) => {
        const base = computeMindmateCollabReconnectDelayMs(retried)
        return base + Math.floor(Math.random() * MINDMATE_COLLAB_RECONNECT.JITTER_MS)
      },
    },
    onConnected() {
      connected.value = true
      connectionStatus.value = 'connected'
      pendingReconnectFailedNotify = false
      heartbeat.start()
    },
    onDisconnected(_ws, event) {
      if (ignoreNextClose) {
        ignoreNextClose = false
        connected.value = false
        return
      }
      heartbeat.stop()
      connected.value = false
      lastCloseCode = event.code
      if (!shouldReconnectMindmateCollab(event.code)) {
        suppressReconnect.value = true
      }
      if (event.code === 4010) {
        shutdownPending.value = false
        connectionStatus.value = 'failed'
        notify.warningKey('mindmate.collabRoomEndedIdle')
        if (options.onSessionEnded) {
          options.onSessionEnded('idle')
        } else if (!options.embedded) {
          window.location.href = '/mindmate'
        }
        return
      }
      if (event.code === 4011) {
        shutdownPending.value = false
        connectionStatus.value = 'failed'
        notify.infoKey('mindmate.collabRoomEndedHost')
        if (options.onSessionEnded) {
          options.onSessionEnded('host')
        } else if (!options.embedded) {
          window.location.href = '/mindmate'
        }
        return
      }
      if (event.code === 4003) {
        shutdownPending.value = false
        connectionStatus.value = 'failed'
        if (isForegroundRoom()) {
          notify.infoKey('mindmate.collabDuplicateTab')
        }
        return
      }
      if (event.code === 1008 || event.code === 4029) {
        shutdownPending.value = false
        connectionStatus.value = 'failed'
        if (!isForegroundRoom()) {
          return
        }
        const localeKey = mindmateCollabPermanentFailureLocaleKey(event.code, event.reason || '')
        if (localeKey) {
          notify.warningKey(localeKey)
        } else {
          notify.warningKey('mindmate.collabConnectionDenied')
        }
        return
      }
      if (shutdownPending.value) {
        return
      }
      notifyDisconnect(event.code, event.reason || '')
    },
    onMessage(_ws, event) {
      heartbeat.noteInbound()
      handleFrame(event.data)
    },
  })

  openSocket = open
  socketSend = (data: string) => send(data, false)

  function readSeedMessages(): MindmateCollabMessage[] {
    const seed = options.seedMessages?.() ?? []
    return seed.map((m) => ({ ...m }))
  }

  function applySeedMessages(): void {
    const seed = readSeedMessages()
    if (seed.length > 0) {
      messages.value = seed
    }
  }

  function seedRoom(info: MindmateCollabRoomInfo): void {
    room.value = info
  }

  let olderLoad: Promise<void> | null = null

  async function loadOlderMessages(): Promise<void> {
    if (olderLoad) {
      await olderLoad
      return
    }
    const sessionId = room.value?.sessionId ?? ''
    if (!sessionId || !hasOlder.value) {
      return
    }
    const run = (async () => {
      const page = await loadOlderSeminarPage(sessionId, messages.value)
      if (!page) {
        return
      }
      hasOlder.value = page.hasMore
      messages.value = page.messages
    })()
    olderLoad = run
    try {
      await run
    } finally {
      if (olderLoad === run) {
        olderLoad = null
      }
    }
  }

  function appendAssistantChunk(chunk: string) {
    if (!streamingAssistant) {
      streamingAssistant = { role: 'assistant', content: chunk, streaming: true }
      messages.value = [...messages.value, streamingAssistant]
    } else {
      streamingAssistant.content += chunk
      messages.value = [...messages.value]
    }
    isStreaming.value = true
  }

  function applyUserMessageFrame(parsed: Record<string, unknown>): void {
    noteMessageChain(collabPrevId(parsed.prev_id))
    const msgId = collabPrevId(parsed.id)
    if (msgId == null) {
      return
    }
    const senderId = Number(parsed.sender_user_id || 0)
    const selfId = Number(authStore.user?.id)
    messages.value = insertMissingCollabMessages(messages.value, [
      {
        id: msgId,
        role: 'user',
        content: String(parsed.content || ''),
        sender_user_id: senderId > 0 ? senderId : null,
        username: typeof parsed.username === 'string' ? parsed.username : null,
        created_at: collabFrameCreatedAt(parsed.created_at),
      },
    ])
    if (senderId === selfId) {
      lastOptimisticSendContent = null
    }
  }

  function finalizeAssistant(
    endContent?: string,
    aborted?: boolean,
    messageId?: number,
    prevId?: number | null,
    createdAt?: string
  ) {
    noteMessageChain(prevId ?? null)
    if (streamingAssistant) {
      streamingAssistant.content = resolveCollabAssistantEndContent(
        streamingAssistant.content,
        endContent || ''
      )
      streamingAssistant.streaming = false
      if (messageId != null) {
        streamingAssistant.id = messageId
      }
      if (createdAt) {
        streamingAssistant.created_at = createdAt
      }
      if (aborted) {
        streamingAssistant.content += `\n\n_${t('mindmate.collabStreamAborted')}_`
      }
      streamingAssistant = null
      messages.value = [...messages.value]
    } else if (
      messageId != null &&
      endContent &&
      !messages.value.some((item) => item.id === messageId)
    ) {
      messages.value = insertMissingCollabMessages(messages.value, [
        {
          id: messageId,
          role: 'assistant',
          content: endContent,
          created_at: createdAt,
        },
      ])
    }
    isStreaming.value = false
  }

  function handleFrame(raw: string) {
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(raw) as Record<string, unknown>
    } catch {
      return
    }
    const type = String(parsed.type || '')
    if (type === 'snapshot') {
      const rows = (parsed.messages as MindmateCollabMessage[]) || []
      const priorMax = collabMaxSavedId(messages.value)
      messages.value = mergeMindmateCollabSnapshot(messages.value, rows)
      hasOlder.value = parsed.has_older === true
      streamingAssistant = null
      isStreaming.value = false
      const backfillAfter = collabSnapshotBackfillAfterId(priorMax, rows)
      if (backfillAfter != null) {
        void pullMessagesAfter(backfillAfter)
      }
      return
    }
    if (type === 'read_cursors') {
      noteReadCursorList(parsed.cursors)
      return
    }
    if (type === 'read_cursor') {
      noteReadCursorFrame(parsed)
      return
    }
    if (type === 'resync') {
      void pullMessagesAfter(collabMaxSavedId(messages.value))
      return
    }
    if (type === 'socket_pong') {
      const latest = collabPrevId(parsed.latest_id)
      if (collabTranscriptBehind(messages.value, latest)) {
        void pullMessagesAfter(collabMaxSavedId(messages.value))
      }
      return
    }
    if (type === 'joined') {
      room.value = {
        sessionId: String(parsed.session_id || ''),
        code: String(parsed.code || roomCode() || ''),
        title: String(parsed.title || 'MindMate Collab'),
        visibility: String(parsed.visibility || 'organization'),
        ownerId: Number(parsed.owner_id || 0),
      }
      resumeToken.value = String(parsed.resume_token || '') || null
      replaceLocalFaces(parsed.faces)
      return
    }
    if (type === 'user_joined') {
      const face = seminarFaceFromPayload(parsed)
      if (face) {
        addLocalFace(face)
      }
      return
    }
    if (type === 'user_left') {
      dropLocalFace(Number(parsed.user_id || 0))
      return
    }
    if (type === 'user_message') {
      applyUserMessageFrame(parsed)
      return
    }
    if (type === 'ai_message_chunk') {
      appendAssistantChunk(String(parsed.content || ''))
      return
    }
    if (type === 'ai_message_end') {
      const messageId = parsed.id as number | undefined
      finalizeAssistant(
        String(parsed.content || ''),
        Boolean(parsed.aborted),
        messageId,
        collabPrevId(parsed.prev_id),
        collabFrameCreatedAt(parsed.created_at)
      )
      return
    }
    if (type === 'room_idle_warning') {
      applyIdleWarning(Number(parsed.grace_seconds || 120))
      return
    }
    if (type === 'session_closing') {
      suppressReconnect.value = true
      shutdownPending.value = true
      connected.value = false
      connectionStatus.value = 'failed'
      clearIdleCountdown()
      notify.infoKey('mindmate.collabRoomClosing')
      return
    }
    if (type === 'error') {
      handleServerErrorFrame(parsed)
    }
  }

  function syncWsResumeProtocols(): void {
    wsProtocolList.length = 0
    const token = resumeToken.value?.trim()
    if (token) {
      wsProtocolList.push(`mg-resume.${token}`)
    }
  }

  function resetForRoomChange(): void {
    gapGeneration += 1
    resumeToken.value = null
    wsUrl.value = ''
    wsProtocolList.length = 0
    messages.value = []
    hasOlder.value = false
    room.value = null
    streamingAssistant = null
    isStreaming.value = false
    lastOptimisticSendContent = null
    pendingReconnectFailedNotify = false
    shutdownPending.value = false
    lastCloseCode = 1006
    connectionStatus.value = 'idle'
    clearIdleCountdown()
    clearLocalFaces()
    resetReadCursors()
  }

  const localFaces = ref<SeminarFace[]>([])

  function isForegroundRoom(): boolean {
    return options.isForeground ? options.isForeground() : true
  }

  function publishSeminarFaces(): void {
    if (!isForegroundRoom()) {
      return
    }
    showSeminarFaces(localFaces.value)
  }

  function replaceLocalFaces(raw: unknown): void {
    localFaces.value = seminarFacesFromJoined(raw, currentSelfFace())
    publishSeminarFaces()
  }

  function addLocalFace(face: SeminarFace): void {
    localFaces.value = upsertSeminarFace(localFaces.value, face)
    publishSeminarFaces()
  }

  function dropLocalFace(userId: number): void {
    localFaces.value = removeSeminarFace(localFaces.value, userId)
    publishSeminarFaces()
  }

  function clearLocalFaces(): void {
    localFaces.value = []
    publishSeminarFaces()
  }

  function currentSelfFace(): SeminarFace | null {
    const user = authStore.user
    if (!user) {
      return null
    }
    const userId = Number(user.id)
    if (!Number.isFinite(userId) || userId <= 0) {
      return null
    }
    return {
      userId,
      name: user.username?.trim() || `User ${userId}`,
      avatar: user.avatar ?? null,
    }
  }

  function connect() {
    const code = roomCode()
    if (!code) {
      return
    }
    suppressReconnect.value = false
    pendingReconnectFailedNotify = false
    shutdownPending.value = false
    connectionStatus.value = 'connecting'
    syncWsResumeProtocols()
    refreshWsUrlForConnect()
    applySeedMessages()
    open()
  }

  function disconnect() {
    heartbeat.stop()
    suppressReconnect.value = true
    close()
    connected.value = false
    connectionStatus.value = 'idle'
    clearIdleCountdown()
    clearLocalFaces()
  }

  function sendChat(content: string, sendOptions?: { toMindmate?: boolean }) {
    const trimmed = content.trim()
    if (!trimmed || isStreaming.value) {
      return
    }
    if (!connected.value) {
      notify.warningKey('mindmate.collabNotConnected')
      return
    }
    lastOptimisticSendContent = trimmed
    const clientKey = `local-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
    messages.value = [
      ...messages.value,
      {
        role: 'user',
        content: trimmed,
        sender_user_id: Number(authStore.user?.id) || null,
        username: authStore.user?.username ?? null,
        clientKey,
        created_at: new Date().toISOString(),
      },
    ]
    send(
      JSON.stringify({
        type: 'chat',
        content: trimmed,
        to_mindmate: Boolean(sendOptions?.toMindmate),
      })
    )
  }

  function retryConnection(): void {
    if (!roomCode()) {
      return
    }
    suppressReconnect.value = false
    pendingReconnectFailedNotify = false
    shutdownPending.value = false
    connectionStatus.value = 'connecting'
    syncWsResumeProtocols()
    refreshWsUrlForConnect()
    open()
  }

  const isHost = computed(() => room.value?.ownerId === Number(authStore.user?.id))

  const canSend = computed(
    () => connected.value && connectionStatus.value === 'connected' && !isStreaming.value
  )

  const canRetryConnection = computed(
    () => connectionStatus.value === 'failed' && !shutdownPending.value
  )

  return {
    messages,
    hasOlder,
    room,
    connected,
    connectionStatus,
    isStreaming,
    idleWarningSeconds,
    isHost,
    canSend,
    canRetryConnection,
    connect,
    disconnect,
    sendChat,
    seedRoom,
    loadOlderMessages,
    resetForRoomChange,
    retryConnection,
    readCursors,
    publishSeminarFaces,
  }
}
