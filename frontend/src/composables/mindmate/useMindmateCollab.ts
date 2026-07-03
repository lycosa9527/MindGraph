/**
 * MindMate collab room WebSocket client.
 */
import { computed, onUnmounted, ref, shallowRef } from 'vue'

import { useWebSocket } from '@vueuse/core'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores/auth'
import { shouldReconnectMindmateCollab } from '@/utils/mindmateCollabSessions'

export interface MindmateCollabMessage {
  id?: number
  role: 'user' | 'assistant'
  content: string
  sender_user_id?: number | null
  username?: string | null
  streaming?: boolean
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
  const isStreaming = ref(false)
  const idleWarningSeconds = ref<number | null>(null)
  const resumeToken = ref<string | null>(null)
  const wsUrl = ref('')
  const suppressReconnect = ref(false)

  let streamingAssistant: MindmateCollabMessage | null = null
  let idleDeadlineUnix: number | null = null
  let idleTickInterval: ReturnType<typeof setInterval> | null = null

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

  const { open, close, send } = useWebSocket(wsUrl, {
    immediate: false,
    autoReconnect: {
      retries: (retried) => !suppressReconnect.value && retried < 8,
      delay: 2000,
    },
    onConnected() {
      connected.value = true
    },
    onDisconnected(_ws, event) {
      connected.value = false
      if (!shouldReconnectMindmateCollab(event.code)) {
        suppressReconnect.value = true
      }
      if (event.code === 4010) {
        notify.warning(t('mindmate.collabRoomEndedIdle'))
        if (options.onSessionEnded) {
          options.onSessionEnded('idle')
        } else if (!options.embedded) {
          window.location.href = '/mindmate'
        }
      } else if (event.code === 4011) {
        notify.info(t('mindmate.collabRoomEndedHost'))
        if (options.onSessionEnded) {
          options.onSessionEnded('host')
        } else if (!options.embedded) {
          window.location.href = '/mindmate'
        }
      }
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

  function finalizeAssistant(endContent?: string, aborted?: boolean) {
    if (streamingAssistant) {
      if (endContent && !streamingAssistant.content) {
        streamingAssistant.content = endContent
      }
      streamingAssistant.streaming = false
      if (aborted) {
        streamingAssistant.content += `\n\n_${t('mindmate.collabStreamAborted')}_`
      }
      streamingAssistant = null
      messages.value = [...messages.value]
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
      const seed = readSeedMessages()
      messages.value = [...seed, ...rows.map((m) => ({ ...m }))]
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
      const senderId = Number(parsed.sender_user_id || 0)
      if (senderId === Number(authStore.user?.id)) {
        return
      }
      messages.value = [
        ...messages.value,
        {
          role: 'user',
          content: String(parsed.content || ''),
          sender_user_id: senderId,
          username: (parsed.username as string) || null,
        },
      ]
      return
    }
    if (type === 'ai_message_chunk') {
      appendAssistantChunk(String(parsed.content || ''))
      return
    }
    if (type === 'ai_message_end') {
      finalizeAssistant(String(parsed.content || ''), Boolean(parsed.aborted))
      return
    }
    if (type === 'room_idle_warning') {
      applyIdleWarning(Number(parsed.grace_seconds || 120))
      return
    }
    if (type === 'session_closing' || type === 'room_idle_shutdown' || type === 'session_ended_shutdown') {
      suppressReconnect.value = true
      connected.value = false
      clearIdleCountdown()
      close()
    }
    if (type === 'error' && parsed.code === 'mindmate_responding') {
      notify.warning(t('mindmate.collabMindmateResponding'))
    }
  }

  function connect() {
    const code = roomCode()
    if (!code) {
      return
    }
    suppressReconnect.value = false
    applySeedMessages()
    wsUrl.value = buildWsUrl(code, resumeToken.value)
    open()
  }

  function disconnect() {
    close()
    connected.value = false
    clearIdleCountdown()
  }

  function sendChat(content: string, options?: { toMindmate?: boolean }) {
    const trimmed = content.trim()
    if (!trimmed || isStreaming.value) {
      return
    }
    messages.value = [
      ...messages.value,
      {
        role: 'user',
        content: trimmed,
        sender_user_id: Number(authStore.user?.id) || null,
        username: authStore.user?.username ?? null,
      },
    ]
    send(
      JSON.stringify({
        type: 'chat',
        content: trimmed,
        to_mindmate: Boolean(options?.toMindmate),
      }),
    )
  }

  const isHost = computed(() => room.value?.ownerId === Number(authStore.user?.id))

  onUnmounted(() => {
    disconnect()
  })

  return {
    messages,
    room,
    connected,
    isStreaming,
    idleWarningSeconds,
    isHost,
    connect,
    disconnect,
    sendChat,
    seedRoom,
  }
}
