/**
 * MindMate notify WebSocket — org presence + collab poke toasts.
 * Uses /api/ws/mindmate-notify (no workshop chat access required).
 */
import { computed, onUnmounted, ref, watch } from 'vue'

import { useWebSocket } from '@vueuse/core'

import { useLanguage, useNotifications } from '@/composables'
import { useSchoolTierFeatures } from '@/composables/auth/useSchoolTierFeatures'
import { useMindmateCollabPresenceBridge } from '@/composables/mindmate/mindmateCollabPresenceBridge'
import { usePresenceActivity } from '@/composables/workshop/usePresenceActivity'
import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { handleMindmateCollabPokeFrame } from '@/utils/mindmateCollabPokeNotify'

const CONNECT_DEBOUNCE_MS = 200
const PING_MESSAGE = JSON.stringify({ type: 'ping' })
const PONG_MESSAGE = JSON.stringify({ type: 'pong' })

function buildWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/api/ws/mindmate-notify`
}

export function useMindmateCollabNotify(): void {
  const authStore = useAuthStore()
  const featureFlagsStore = useFeatureFlagsStore()
  const { canUseOnlineCollab } = useSchoolTierFeatures()
  const notify = useNotifications()
  const { t } = useLanguage()
  const { applyPresenceSnapshot, updatePresence } = useMindmateCollabPresenceBridge()
  const wsUrl = ref('')
  const connected = ref(false)
  /** Bumped on every intentional disconnect; stale handshakes must not stay open. */
  let connectGeneration = 0
  let connectTimer: ReturnType<typeof setTimeout> | null = null
  /** True when we wanted to drop a socket that was still handshaking. */
  let cancelConnecting = false

  const shouldConnect = computed(
    () =>
      authStore.isAuthenticated &&
      authStore.isAuthSessionVerified &&
      featureFlagsStore.flags !== null &&
      featureFlagsStore.getFeatureMindmateCollab() &&
      canUseOnlineCollab.value
  )

  function resolveOrgId(): number | null {
    const raw = authStore.user?.schoolId
    if (!raw) {
      return null
    }
    const id = parseInt(raw, 10)
    return Number.isNaN(id) ? null : id
  }

  function sendSubscribePresence(sendFn: (payload: string) => void): void {
    const orgId = resolveOrgId()
    if (orgId == null) {
      return
    }
    sendFn(JSON.stringify({ type: 'subscribe_presence', org_id: orgId }))
  }

  function handleFrame(raw: string): void {
    let data: Record<string, unknown>
    try {
      data = JSON.parse(raw) as Record<string, unknown>
    } catch {
      return
    }
    if (handleMindmateCollabPokeFrame(data, t, notify)) {
      return
    }
    const msgType = String(data.type || '')
    const selfId = Number(authStore.user?.id) || 0
    if (msgType === 'presence') {
      updatePresence(Number(data.user_id), String(data.status || 'offline'))
      return
    }
    if (msgType === 'presence_snapshot') {
      const ids = data.user_ids
      if (!Array.isArray(ids)) {
        return
      }
      const parsed: number[] = []
      for (const uid of ids) {
        const n = typeof uid === 'number' ? uid : Number(uid)
        if (Number.isFinite(n)) {
          parsed.push(n)
        }
      }
      applyPresenceSnapshot(parsed, selfId || undefined)
    }
  }

  const { send, close, open, status } = useWebSocket(wsUrl, {
    immediate: false,
    // URL is set manually before open(); default autoConnect watches url and would
    // call open() again → close() on the still-CONNECTING socket (Chrome console noise).
    autoConnect: false,
    // Own lifecycle in onUnmounted — VueUse autoClose would close() mid-handshake on dispose.
    autoClose: false,
    autoReconnect: { retries: 6, delay: 2500 },
    heartbeat: {
      message: PING_MESSAGE,
      responseMessage: PONG_MESSAGE,
      interval: 30000,
      pongTimeout: 10000,
    },
    onConnected() {
      if (cancelConnecting || !shouldConnect.value) {
        cancelConnecting = false
        close()
        connected.value = false
        return
      }
      connected.value = true
      sendSubscribePresence(send)
      const userId = Number(authStore.user?.id)
      if (userId) {
        updatePresence(userId, 'active')
      }
    },
    onDisconnected() {
      connected.value = false
      // close() sets VueUse explicitlyClosed so autoReconnect does not revive a cancelled session.
      if (cancelConnecting || !shouldConnect.value) {
        close()
      }
      const userId = Number(authStore.user?.id)
      if (userId) {
        updatePresence(userId, 'offline')
      }
    },
    onMessage(_ws, event) {
      handleFrame(event.data)
    },
  })

  usePresenceActivity((presenceStatus) => {
    if (connected.value) {
      send(JSON.stringify({ type: 'presence', status: presenceStatus }))
    }
    const userId = Number(authStore.user?.id)
    if (userId) {
      updatePresence(userId, presenceStatus)
    }
  })

  function clearConnectTimer(): void {
    if (connectTimer != null) {
      clearTimeout(connectTimer)
      connectTimer = null
    }
  }

  /**
   * Avoid Chrome "WebSocket is closed before the connection is established"
   * by never calling close() while status is CONNECTING.
   */
  function disconnectNotify(): void {
    clearConnectTimer()
    connectGeneration += 1
    cancelConnecting = true
    if (status.value === 'CLOSED') {
      connected.value = false
      return
    }
    if (status.value === 'CONNECTING') {
      connected.value = false
      return
    }
    close()
    connected.value = false
  }

  function connectNotifyNow(): void {
    if (!shouldConnect.value) {
      disconnectNotify()
      return
    }
    cancelConnecting = false
    if (status.value === 'OPEN' || status.value === 'CONNECTING') {
      return
    }
    wsUrl.value = buildWsUrl()
    open()
  }

  function scheduleConnectNotify(): void {
    clearConnectTimer()
    const generation = connectGeneration
    connectTimer = setTimeout(() => {
      connectTimer = null
      if (generation !== connectGeneration || !shouldConnect.value) {
        return
      }
      connectNotifyNow()
    }, CONNECT_DEBOUNCE_MS)
  }

  watch(
    shouldConnect,
    (ok) => {
      if (ok) {
        scheduleConnectNotify()
      } else {
        disconnectNotify()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    disconnectNotify()
  })
}

/** @deprecated Use useMindmateCollabNotify */
export function useOrgPresenceWs(): void {
  useMindmateCollabNotify()
}
