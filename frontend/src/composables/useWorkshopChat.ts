/**
 * Workshop Chat WebSocket Composable
 *
 * Manages WebSocket connection lifecycle, message dispatching, and
 * real-time event handling for the workshop chat system.
 *
 * Uses @vueuse/core useWebSocket for auto-reconnect.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { useWebSocket } from '@vueuse/core'

import { ElMessage } from 'element-plus'

import {
  requestNotificationPermission,
  useChatNotifications,
} from '@/composables/useChatNotifications'
import { useLanguage } from '@/composables/useLanguage'
import { usePresenceActivity } from '@/composables/usePresenceActivity'
import { useAuthStore } from '@/stores/auth'
import { useWorkshopChatStore } from '@/stores/workshopChat'
import {
  registerWorkshopChatWsDisconnect,
  unregisterWorkshopChatWsDisconnect,
} from '@/utils/workshopChatWsRegistry'

function buildWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  return `${proto}://${host}/api/ws/chat`
}

export function useWorkshopChatComposable() {
  const store = useWorkshopChatStore()
  const authStore = useAuthStore()
  const { t } = useLanguage()
  const notifications = useChatNotifications()
  const connected = ref(false)
  const wsUrl = ref('')

  const { send, close, open, status } = useWebSocket(wsUrl, {
    immediate: false,
    autoReconnect: {
      retries: 10,
      delay: 2000,
      onFailed() {
        console.warn('[WorkshopChat] WebSocket reconnection failed after max retries')
      },
    },
    heartbeat: {
      message: JSON.stringify({ type: 'ping' }),
      interval: 30000,
      pongTimeout: 10000,
    },
    onConnected() {
      connected.value = true
      sendSubscribePresence()
      const channelIds = store.joinedChannels.map((c) => c.id)
      if (channelIds.length > 0) {
        send(JSON.stringify({ type: 'subscribe_channels', channel_ids: channelIds }))
      }
      const userId = Number(authStore.user?.id)
      if (userId) {
        store.updatePresence(userId, 'active')
      }
    },
    onDisconnected() {
      connected.value = false
      const userId = Number(authStore.user?.id)
      if (userId) {
        store.updatePresence(userId, 'offline')
      }
    },
    onMessage(_ws, event) {
      handleMessage(event.data)
    },
  })

  const isConnected = computed(() => status.value === 'OPEN')

  function resolveWorkshopPresenceOrgId(): number | null {
    if (store.adminOrgId != null) return store.adminOrgId
    const raw = authStore.user?.schoolId
    if (!raw) return null
    const id = parseInt(raw, 10)
    return Number.isNaN(id) ? null : id
  }

  function sendSubscribePresence(): void {
    const orgId = resolveWorkshopPresenceOrgId()
    if (orgId == null) return
    send(JSON.stringify({ type: 'subscribe_presence', org_id: orgId }))
  }

  function sendPresence(presenceStatus: 'active' | 'idle'): void {
    if (isConnected.value) {
      send(JSON.stringify({ type: 'presence', status: presenceStatus }))
    }
    const userId = Number(authStore.user?.id)
    if (userId) {
      store.updatePresence(userId, presenceStatus)
    }
  }

  usePresenceActivity((presenceStatus) => {
    sendPresence(presenceStatus)
  })

  function connect(): void {
    if (!authStore.isAuthenticated) return
    wsUrl.value = buildWsUrl()
    open()
  }

  function disconnect(): void {
    close()
    connected.value = false
  }

  function handleMessage(raw: string): void {
    let data: Record<string, unknown>
    try {
      data = JSON.parse(raw)
    } catch {
      return
    }

    const msgType = data.type as string

    switch (msgType) {
      case 'channel_message': {
        const msg = data.message as never
        store.addIncomingChannelMessage(msg)
        notifications.notifyChannelMessage(msg)
        break
      }
      case 'topic_message': {
        const msg = data.message as never
        store.addIncomingTopicMessage(msg)
        notifications.notifyTopicMessage(msg)
        break
      }
      case 'dm': {
        const msg = data.message as never
        store.addIncomingDM(msg)
        notifications.notifyDM(msg)
        break
      }
      case 'typing_channel':
      case 'typing_topic': {
        const key = `ch:${data.channel_id}:t:${data.topic_id ?? 'general'}:u:${data.user_id}`
        store.setTyping(key, data.username as string)
        break
      }
      case 'typing_dm': {
        const dmKey = `dm:${data.sender_id}`
        store.setTyping(dmKey, data.username as string)
        break
      }
      case 'presence':
        store.updatePresence(data.user_id as number, data.status as string)
        break
      case 'presence_snapshot': {
        const ids = data.user_ids
        if (!Array.isArray(ids)) break
        for (const uid of ids) {
          if (typeof uid === 'number') {
            store.updatePresence(uid, 'active')
          }
        }
        break
      }
      case 'topic_updated':
        store.updateTopic(data.topic as never)
        break
      case 'error': {
        const code = data.code as string | undefined
        if (code === 'invalid_mentions') {
          const unknown = data.unknown as string[] | undefined
          const ambiguous = data.ambiguous as string[] | undefined
          const parts: string[] = []
          if (unknown?.length) {
            parts.push(t('workshop.mentionUnknown').replace('{0}', unknown.join(', ')))
          }
          if (ambiguous?.length) {
            parts.push(t('workshop.mentionAmbiguous').replace('{0}', ambiguous.join(', ')))
          }
          ElMessage.warning(
            parts.join(' · ') || (data.message as string) || t('workshop.messageSendFailed')
          )
        }
        break
      }
      case 'pong':
        break
      case 'channel_invite': {
        void store.fetchChannels({ force: true })
        const name = typeof data.channel_name === 'string' ? data.channel_name : ''
        ElMessage.info(t('workshop.channelInviteReceived').replace('{name}', name))
        break
      }
      default:
        break
    }
  }

  function sendChannelMessage(channelId: number, content: string): void {
    send(
      JSON.stringify({
        type: 'channel_message',
        channel_id: channelId,
        content,
      })
    )
  }

  function sendTopicMessage(channelId: number, topicId: number, content: string): void {
    send(
      JSON.stringify({
        type: 'topic_message',
        channel_id: channelId,
        topic_id: topicId,
        content,
      })
    )
  }

  function sendDM(recipientId: number, content: string): void {
    send(
      JSON.stringify({
        type: 'dm',
        recipient_id: recipientId,
        content,
      })
    )
  }

  function sendTypingChannel(channelId: number): void {
    send(JSON.stringify({ type: 'typing_channel', channel_id: channelId }))
  }

  function sendTypingTopic(channelId: number, topicId: number): void {
    send(
      JSON.stringify({
        type: 'typing_topic',
        channel_id: channelId,
        topic_id: topicId,
      })
    )
  }

  function sendTypingDM(recipientId: number): void {
    send(JSON.stringify({ type: 'typing_dm', recipient_id: recipientId }))
  }

  function sendReadChannel(channelId: number, messageId: number): void {
    send(
      JSON.stringify({
        type: 'read_channel',
        channel_id: channelId,
        message_id: messageId,
      })
    )
  }

  function subscribeChannels(channelIds: number[]): void {
    send(JSON.stringify({ type: 'subscribe_channels', channel_ids: channelIds }))
  }

  watch(
    () => store.joinedChannels,
    (newChannels) => {
      if (isConnected.value && newChannels.length > 0) {
        subscribeChannels(newChannels.map((c) => c.id))
      }
    }
  )

  watch(
    () => store.adminOrgId,
    () => {
      if (isConnected.value) {
        sendSubscribePresence()
      }
    }
  )

  onMounted(() => {
    requestNotificationPermission()
    registerWorkshopChatWsDisconnect(disconnect)
  })

  onUnmounted(() => {
    unregisterWorkshopChatWsDisconnect(disconnect)
    disconnect()
  })

  return {
    connected,
    isConnected,
    connect,
    disconnect,
    sendChannelMessage,
    sendTopicMessage,
    sendDM,
    sendTypingChannel,
    sendTypingTopic,
    sendTypingDM,
    sendReadChannel,
    subscribeChannels,
    sendPresence,
  }
}
