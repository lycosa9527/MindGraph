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
    autoReconnect: { retries: 6, delay: 2500 },
    heartbeat: {
      message: JSON.stringify({ type: 'ping' }),
      interval: 30000,
      pongTimeout: 10000,
    },
    onConnected() {
      connected.value = true
      sendSubscribePresence(send)
      const userId = Number(authStore.user?.id)
      if (userId) {
        updatePresence(userId, 'active')
      }
    },
    onDisconnected() {
      connected.value = false
      const userId = Number(authStore.user?.id)
      if (userId) {
        updatePresence(userId, 'offline')
      }
    },
    onMessage(_ws, event) {
      handleFrame(event.data)
    },
  })

  usePresenceActivity((status) => {
    if (connected.value) {
      send(JSON.stringify({ type: 'presence', status }))
    }
    const userId = Number(authStore.user?.id)
    if (userId) {
      updatePresence(userId, status)
    }
  })

  function disconnectNotify(): void {
    if (status.value === 'CLOSED') {
      connected.value = false
      return
    }
    close()
    connected.value = false
  }

  function connectNotify(): void {
    if (!shouldConnect.value) {
      disconnectNotify()
      return
    }
    if (status.value === 'OPEN' || status.value === 'CONNECTING') {
      return
    }
    wsUrl.value = buildWsUrl()
    open()
  }

  watch(
    shouldConnect,
    (ok) => {
      if (ok) {
        connectNotify()
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
