/**
 * MindMate collab room WebSocket client.
 */
import { computed, onUnmounted, ref, shallowRef } from 'vue'

import { useWebSocket } from '@vueuse/core'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { shouldReconnectMindmateCollab } from '@/utils/mindmateCollabSessions'
import {
  computeMindmateCollabReconnectDelayMs,
  mindmateCollabPermanentFailureLocaleKey,
  shouldScheduleMindmateCollabReconnect,
} from '@/utils/mindmateCollabReconnect'
import {
  mindmateCollabDisconnectShouldNotify,
  mindmateCollabWsErrorLocaleKey,
  mindmateCollabWsErrorRollsBackSend,
  type MindmateCollabConnectionStatus,
} from '@/utils/mindmateCollabWsErrors'

export interface MindmateCollabMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  sender_user_id?: number | null
  username?: string | null
  streaming?: boolean
  clientKey?: string
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
}

export function useMindmateCollab(
  roomCode: () => string | null,
  options: UseMindmateCollabOptions = {},
) {
  const authStore = useAuthStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  const messages = shallowRef<MindmateCollabMessage[]>([])
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
  let reconnectAttempt = 0
  let lastCloseCode = 1006

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
        candidate.role === 'user'
        && candidate.sender_user_id === selfId
        && candidate.id == null
        && candidate.content === content
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
      } else if (errorCode === 'mindmate_responding') {
        notify.warning(t(localeKey))
      } else {
        notify.warning(t(localeKey))
      }
    } else {
      const fallback = String(parsed.message || '').trim()
      notify.warning(fallback || t('mindmate.collabErrorUnknown'))
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
      pendingReconnectFailedNotify,
    )
    pendingReconnectFailedNotify = false

    if (action === 'none') {
      return
    }
    if (action === 'reconnect_failed') {
      connectionStatus.value = 'failed'
      notify.error(t('mindmate.collabReconnectFailed'))
      return
    }
    if (action === 'closed_reason') {
      connectionStatus.value = 'failed'
      const label = reason.trim() || t('mindmate.collabConnectionClosed')
      notify.warning(t('mindmate.collabConnectionClosedReason', { reason: label }))
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
        reconnectAttempt = retried + 1
        connectionStatus.value = 'reconnecting'
        syncWsResumeProtocols()
        refreshWsUrlForConnect()
        return true
      },
      delay: (retried) => {
        const base = computeMindmateCollabReconnectDelayMs(retried)
        return base + Math.floor(Math.random() * 1000)
      },
    },
    onConnected() {
      connected.value = true
      connectionStatus.value = 'connected'
      pendingReconnectFailedNotify = false
    },
    onDisconnected(_ws, event) {
      connected.value = false
      lastCloseCode = event.code
      if (!shouldReconnectMindmateCollab(event.code)) {
        suppressReconnect.value = true
      }
      if (event.code === 4010) {
        shutdownPending.value = false
        connectionStatus.value = 'failed'
        notify.warning(t('mindmate.collabRoomEndedIdle'))
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
        notify.info(t('mindmate.collabRoomEndedHost'))
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
        notify.info(t('mindmate.collabDuplicateTab'))
        return
      }
      if (event.code === 1008 || event.code === 4029) {
        shutdownPending.value = false
        connectionStatus.value = 'failed'
        const localeKey = mindmateCollabPermanentFailureLocaleKey(
          event.code,
          event.reason || '',
        )
        if (localeKey) {
          notify.warning(t(localeKey))
        } else {
          notify.warning(t('mindmate.collabConnectionDenied'))
        }
        return
      }
      if (shutdownPending.value) {
        return
      }
      notifyDisconnect(event.code, event.reason || '')
    },
    onMessage(_ws, event) {
      handleFrame(event.data)
    },
  })

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
    const senderId = Number(parsed.sender_user_id || 0)
    const msgId = parsed.id as number | undefined
    const content = String(parsed.content || '')
    const username = (parsed.username as string) || null
    const selfId = Number(authStore.user?.id)

    if (senderId === selfId) {
      if (msgId == null) {
        return
      }
      const next = [...messages.value]
      for (let index = next.length - 1; index >= 0; index -= 1) {
        const candidate = next[index]
        if (
          candidate.role === 'user'
          && candidate.sender_user_id === selfId
          && candidate.id == null
          && candidate.content === content
        ) {
          next[index] = {
            ...candidate,
            id: msgId,
            username: username ?? candidate.username ?? null,
            clientKey: undefined,
          }
          messages.value = next
          lastOptimisticSendContent = null
          return
        }
      }
      if (messages.value.some((item) => item.id === msgId)) {
        return
      }
    } else if (msgId != null && messages.value.some((item) => item.id === msgId)) {
      return
    }

    messages.value = [
      ...messages.value,
      {
        id: msgId,
        role: 'user',
        content,
        sender_user_id: senderId,
        username,
      },
    ]
  }

  function finalizeAssistant(
    endContent?: string,
    aborted?: boolean,
    messageId?: number,
  ) {
    if (streamingAssistant) {
      if (endContent && !streamingAssistant.content) {
        streamingAssistant.content = endContent
      }
      streamingAssistant.streaming = false
      if (messageId != null) {
        streamingAssistant.id = messageId
      }
      if (aborted) {
        streamingAssistant.content += `\n\n_${t('mindmate.collabStreamAborted')}_`
      }
      streamingAssistant = null
      messages.value = [...messages.value]
    } else if (messageId != null && endContent && !messages.value.some((item) => item.id === messageId)) {
      messages.value = [
        ...messages.value,
        {
          id: messageId,
          role: 'assistant',
          content: endContent,
        },
      ]
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
      messages.value = rows.map((message) => ({ ...message }))
      streamingAssistant = null
      isStreaming.value = false
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
      finalizeAssistant(String(parsed.content || ''), Boolean(parsed.aborted), messageId)
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
      notify.info(t('mindmate.collabRoomClosing'))
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
    resumeToken.value = null
    wsUrl.value = ''
    wsProtocolList.length = 0
    messages.value = []
    room.value = null
    streamingAssistant = null
    isStreaming.value = false
    lastOptimisticSendContent = null
    pendingReconnectFailedNotify = false
    shutdownPending.value = false
    reconnectAttempt = 0
    lastCloseCode = 1006
    connectionStatus.value = 'idle'
    clearIdleCountdown()
  }

  function connect() {
    const code = roomCode()
    if (!code) {
      return
    }
    suppressReconnect.value = false
    pendingReconnectFailedNotify = false
    shutdownPending.value = false
    reconnectAttempt = 0
    connectionStatus.value = 'connecting'
    syncWsResumeProtocols()
    refreshWsUrlForConnect()
    applySeedMessages()
    open()
  }

  function disconnect() {
    suppressReconnect.value = true
    close()
    connected.value = false
    connectionStatus.value = 'idle'
    clearIdleCountdown()
  }

  function sendChat(content: string, sendOptions?: { toMindmate?: boolean }) {
    const trimmed = content.trim()
    if (!trimmed || isStreaming.value) {
      return
    }
    if (!connected.value) {
      notify.warning(t('mindmate.collabNotConnected'))
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
      },
    ]
    send(
      JSON.stringify({
        type: 'chat',
        content: trimmed,
        to_mindmate: Boolean(sendOptions?.toMindmate),
      }),
    )
  }

  function retryConnection(): void {
    if (!roomCode()) {
      return
    }
    suppressReconnect.value = false
    pendingReconnectFailedNotify = false
    shutdownPending.value = false
    reconnectAttempt = 0
    connectionStatus.value = 'connecting'
    syncWsResumeProtocols()
    refreshWsUrlForConnect()
    open()
  }

  const isHost = computed(() => room.value?.ownerId === Number(authStore.user?.id))

  const canSend = computed(
    () => connected.value && connectionStatus.value === 'connected' && !isStreaming.value,
  )

  const canRetryConnection = computed(
    () => connectionStatus.value === 'failed' && !shutdownPending.value,
  )

  onUnmounted(() => {
    disconnect()
  })

  return {
    messages,
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
    resetForRoomChange,
    retryConnection,
  }
}
