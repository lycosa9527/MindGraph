/**
 * useWorkshop - Composable for presentation-mode WebSocket collaboration
 * Handles real-time diagram updates via WebSocket
 */
import { type Ref, computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useAuthStore } from '@/stores'

import { collectNodeIdsFromOutboundPayload, useCollabOutboundQueue } from './useCollabOutboundQueue'
import { useCollabSyncVersion } from './useCollabSyncVersion'
import { useWorkshopHeartbeat } from './useWorkshopHeartbeat'
import { useWorkshopJoin } from './useWorkshopJoin'
import { dispatchWorkshopMessage } from './useWorkshopMessageHandlers'
import type {
  WorkshopAuthContext,
  WorkshopMessageDispatchDeps,
  WorkshopMutableSessionState,
} from './useWorkshopMessageHandlers'
import { useWorkshopOutboundDispatcher } from './useWorkshopOutboundDispatcher'
import { useWorkshopPresence } from './useWorkshopPresence'
import {
  WORKSHOP_RECONNECT,
  WORKSHOP_RESYNC_WATCHDOG,
  computeReconnectDelayMs,
  nextPendingResyncBackoffMs,
  shouldScheduleReconnect,
} from './useWorkshopReconnect'
import type {
  ActiveEditor,
  ConnectionStatus,
  ParticipantInfo,
  RemoteNodeSelection,
  WorkshopRole,
} from './useWorkshopTypes'
import { isWorkshopUpdate } from './useWorkshopTypes'

export type {
  ActiveEditor,
  ConnectionStatus,
  NodeEditingEvent,
  ParticipantInfo,
  RemoteNodeSelection,
  WorkshopRole,
  WorkshopUpdate,
} from './useWorkshopTypes'

export function useWorkshop(
  workshopCode: Ref<string | null>,
  diagramId: Ref<string | null>,
  onUpdate?: (spec: Record<string, unknown>) => void,
  onGranularUpdate?: (
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>,
    deletedNodeIds?: string[],
    deletedConnectionIds?: string[]
  ) => void,
  onNodeEditing?: (nodeId: string, editor: ActiveEditor | null) => void,
  onServerSnapshot?: (spec: Record<string, unknown>, version: number) => void
) {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const connectionStatus = ref<ConnectionStatus>('connected')
  const participants = ref<number[]>([])
  const participantsWithNames = ref<ParticipantInfo[]>([])
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = WORKSHOP_RECONNECT.MAX_ATTEMPTS
  const activeEditors = ref<Map<string, ActiveEditor>>(new Map())
  const remoteSelectionsByUser = ref<Map<number, RemoteNodeSelection>>(new Map())
  const diagramOwnerId = ref<number | null>(null)
  const workshopRole = ref<WorkshopRole>('editor')
  const serverBaselineReady = ref(false)

  let _sessionDiagramIdValue: string | null = null
  const sessionMutable: WorkshopMutableSessionState = {
    get sessionDiagramId() {
      return _sessionDiagramIdValue
    },
    set sessionDiagramId(v: string | null) {
      _sessionDiagramIdValue = v
      sessionDiagramIdRef.value = v
    },
  }

  /** Reactive version/sequencing state — single source of truth for all cursors. */
  const version = useCollabSyncVersion()

  /**
   * Outbound queue: holds every `update` payload until the server acks it.
   *   - Held while WS is not OPEN or `pendingResync` is true.
   *   - Replayed in order on reconnect / after snapshot lands.
   *   - Each op carries a `client_op_id` so the server can dedupe.
   */
  const outboundQueue = useCollabOutboundQueue({
    send: (payload) => {
      const sock = ws.value
      if (!sock || sock.readyState !== WebSocket.OPEN) {
        throw new Error('socket_not_open')
      }
      sock.send(JSON.stringify(payload))
    },
    canFlush: () => {
      const sock = ws.value
      if (!sock || sock.readyState !== WebSocket.OPEN) {
        return false
      }
      // Hold all outbound traffic while the client is recovering from a gap;
      // the snapshot reply will reset state and tryFlush() will be invoked.
      if (version.pendingResync.value) {
        return false
      }
      if (!serverBaselineReady.value) {
        return false
      }
      return true
    },
    onOverflow: () => {
      notify.warning(t('workshopCanvas.outboundQueueDegraded'))
    },
  })
  watch(
    () => version.pendingResync.value,
    (pending) => {
      if (!pending) {
        outboundQueue.tryFlush()
      }
    }
  )
  const joinResumeToken = ref<string | null>(null)
  const sessionDiagramTitleRef = ref<string | null>(null)
  // Reactive mirror of sessionMutable.sessionDiagramId so callers can use it
  // as the authoritative diagram ID for stop/resync even when activeDiagramId
  // differs (e.g., host navigated to a different diagram mid-session).
  const sessionDiagramIdRef = ref<string | null>(null)

  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  let pendingResyncTimer: ReturnType<typeof setTimeout> | null = null
  let pendingResyncInterval: ReturnType<typeof setInterval> | null = null
  let pendingResyncRetryStep = 0

  function clearPendingResyncWatchdog(): void {
    if (pendingResyncTimer) {
      clearTimeout(pendingResyncTimer)
      pendingResyncTimer = null
    }
    if (pendingResyncInterval) {
      clearInterval(pendingResyncInterval)
      pendingResyncInterval = null
    }
    pendingResyncRetryStep = 0
  }

  const authStore = useAuthStore()
  const notify = useNotifications()
  const { t } = useLanguage()
  const router = useRouter()

  const presence = useWorkshopPresence()
  const { startHeartbeat, stopHeartbeat, recordPong } = useWorkshopHeartbeat(ws, isConnected)

  function schedulePendingResyncWatchdog(sock: WebSocket): void {
    clearPendingResyncWatchdog()
    const runStep = (): void => {
      if (!version.pendingResync.value) {
        clearPendingResyncWatchdog()
        return
      }
      if (sock.readyState !== WebSocket.OPEN) {
        clearPendingResyncWatchdog()
        return
      }
      const diagram = sessionMutable.sessionDiagramId ?? diagramId.value
      if (!diagram) {
        pendingResyncTimer = setTimeout(runStep, WORKSHOP_RESYNC_WATCHDOG.INITIAL_WAIT_MS)
        return
      }
      sock.send(JSON.stringify({ type: 'resync', diagram_id: diagram }))
      pendingResyncRetryStep += 1
      if (pendingResyncRetryStep < WORKSHOP_RESYNC_WATCHDOG.MAX_RETRIES) {
        const delay = nextPendingResyncBackoffMs(pendingResyncRetryStep)
        pendingResyncTimer = setTimeout(runStep, delay)
      } else {
        notify.warning(t('workshopCanvas.resyncWaiting'))
        let steadyFires = 0
        pendingResyncInterval = setInterval(() => {
          if (!version.pendingResync.value || sock.readyState !== WebSocket.OPEN) {
            clearPendingResyncWatchdog()
            return
          }
          steadyFires += 1
          // After 2 steady-state resync sends with no snapshot reply, the server
          // or network is stuck — force a full reconnect to clear the stale state.
          if (steadyFires > 2) {
            clearPendingResyncWatchdog()
            if (import.meta.env.DEV) {
              console.warn('[CollabSync] pendingResync stuck after retries — forcing reconnect')
            }
            reconnect()
            return
          }
          const d = sessionMutable.sessionDiagramId ?? diagramId.value
          if (d) {
            sock.send(JSON.stringify({ type: 'resync', diagram_id: d }))
          }
        }, WORKSHOP_RESYNC_WATCHDOG.STEADY_INTERVAL_MS)
        pendingResyncTimer = null
      }
    }
    pendingResyncTimer = setTimeout(runStep, WORKSHOP_RESYNC_WATCHDOG.INITIAL_WAIT_MS)
  }

  const isDiagramOwner = computed(() => {
    if (!workshopCode.value) {
      return true
    }
    if (diagramOwnerId.value == null) {
      return false
    }
    return String(diagramOwnerId.value) === String(authStore.user?.id ?? '')
  })

  const { getWebSocketUrl, clearAuthRefreshReconnect, scheduleAuthRefreshReconnect } =
    useWorkshopJoin({
      workshopCode,
      joinResumeToken,
      ws,
      authStore,
      notify,
      t,
      connect,
    })

  const authContext: WorkshopAuthContext = {
    getCurrentUserIdString: () => String(authStore.user?.id ?? ''),
  }

  /** True when joined as a collaborator who is not the diagram owner (host). */
  function collaborationParticipantIsGuest(): boolean {
    if (!workshopCode.value || diagramOwnerId.value == null || authStore.user?.id == null) {
      return false
    }
    return String(authStore.user.id) !== String(diagramOwnerId.value)
  }

  let guestForcedExitHandled = false

  function performGuestForcedExit(reason?: string): void {
    if (guestForcedExitHandled) {
      return
    }
    guestForcedExitHandled = true
    // Room-idle kicks do not show a toast in the ``kicked`` handler; mirror close ``4010``.
    if (reason === 'room_idle') {
      notify.info(t('workshopCanvas.returnedHomeRoomIdle'))
    }
    eventBus.emit('workshop:code-changed', { code: null, visibility: null })
    void router.replace({ name: 'MindGraph' }).catch(() => {})
  }

  const messageDeps: WorkshopMessageDispatchDeps = {
    workshopCode,
    diagramId,
    mutable: sessionMutable,
    version,
    participants,
    participantsWithNames,
    workshopRole,
    diagramOwnerId,
    activeEditors,
    remoteSelectionsByUser,
    joinResumeToken,
    sessionDiagramTitle: sessionDiagramTitleRef,
    auth: authContext,
    onUpdate,
    onGranularUpdate,
    onNodeEditing,
    onServerSnapshot,
    clearRoomIdleCountdownUi: presence.clearRoomIdleCountdownUi,
    applyRoomIdleWarningFromServer: presence.applyRoomIdleWarningFromServer,
    schedulePresenceNotification: presence.schedulePresenceNotification,
    clearPendingResyncWatchdog,
    schedulePendingResyncWatchdog,
    flushOutboundQueue: () => {
      outboundQueue.tryFlush()
    },
    markServerBaselineReady: () => {
      serverBaselineReady.value = true
    },
    acknowledgeOutboundUpdate: (id) => {
      outboundQueue.acknowledge(id)
    },
    collectAcknowledgedNodeIds: (clientOpId) => {
      const ops = outboundQueue.snapshot()
      const op =
        typeof clientOpId === 'string' && clientOpId ? ops.find((o) => o.id === clientOpId) : ops[0]
      if (!op) {
        return []
      }
      return collectNodeIdsFromOutboundPayload(op.payload)
    },
    recordTransportPong: recordPong,
    notify: {
      error: (m) => notify.error(m),
      warning: (m) => notify.warning(m),
      info: (m) => notify.info(m),
    },
    t,
    onGuestForcedExit: ({ reason }) => performGuestForcedExit(reason),
  }

  const {
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    sendClaimNodeEdit,
    clearNodeEditingThrottles,
  } = useWorkshopOutboundDispatcher({
    ws,
    diagramId,
    pendingResync: version.pendingResync,
    queueSize: outboundQueue.size,
    getSessionDiagramId: () => sessionMutable.sessionDiagramId,
    canSendRealtimeControl: () => {
      const sock = ws.value
      return Boolean(
        sock &&
          sock.readyState === WebSocket.OPEN &&
          !version.pendingResync.value &&
          serverBaselineReady.value
      )
    },
    clearRoomIdleCountdownUi: presence.clearRoomIdleCountdownUi,
    enqueueUpdatePayload: (payload) => outboundQueue.enqueue(payload),
  })

  function connect() {
    if (!workshopCode.value) {
      return
    }

    if (
      ws.value &&
      (ws.value.readyState === WebSocket.CONNECTING || ws.value.readyState === WebSocket.OPEN)
    ) {
      // OPEN (1) or CONNECTING (0): socket is live or mid-handshake.
      return
    }

    if (ws.value && ws.value.readyState === WebSocket.CLOSING) {
      // CLOSING (2): the previous socket is tearing down.
      // Wait for its onclose to fire, then reconnect once it completes.
      ws.value.addEventListener('close', () => connect(), { once: true })
      return
    }

    try {
      const url = getWebSocketUrl(workshopCode.value)
      const socket = new WebSocket(url)
      socket.binaryType = 'arraybuffer'
      let errorNotified = false

      socket.onopen = () => {
        guestForcedExitHandled = false
        isConnected.value = true
        connectionStatus.value = 'connected'
        reconnectAttempts.value = 0
        clearPendingResyncWatchdog()
        scheduleAuthRefreshReconnect()
        version.reset()
        serverBaselineReady.value = false

        const joinMsg: Record<string, unknown> = { type: 'join' }
        if (diagramId.value) {
          joinMsg.diagram_id = diagramId.value
        }
        socket.send(JSON.stringify(joinMsg))

        // Server has lost prior socket context; mark every still-queued op as
        // not-in-flight so it gets re-sent.  We do NOT flush yet — the queue is
        // gated until the server snapshot baseline lands for this socket.
        outboundQueue.resetInFlight()
      }

      socket.onmessage = (event) => {
        try {
          let rawData: string
          if (typeof event.data === 'string') {
            rawData = event.data
          } else if (event.data instanceof ArrayBuffer) {
            rawData = new TextDecoder().decode(event.data)
          } else {
            return
          }
          const parsed = JSON.parse(rawData) as unknown
          if (!isWorkshopUpdate(parsed)) {
            if (import.meta.env.DEV) {
              console.warn('[WorkshopWS] Ignoring malformed message', parsed)
            }
            return
          }
          const message = parsed
          dispatchWorkshopMessage(message, socket, messageDeps)
        } catch {
          notify.warning(t('workshopCanvas.wsError'))
        }
      }

      socket.onerror = (error) => {
        if (import.meta.env.DEV) {
          console.error('[WorkshopWS] WebSocket error:', error)
        }
        isConnected.value = false
        errorNotified = true
        notify.error(t('workshopCanvas.wsError'))
      }

      socket.onclose = (event) => {
        isConnected.value = false

        if (
          guestForcedExitHandled &&
          (event.code === 4002 || event.code === 4010 || event.code === 4011)
        ) {
          disconnect()
          guestForcedExitHandled = false
          return
        }

        if (event.code === 4001) {
          // JWT expired mid-session — cannot reconnect with the same token.
          // Clear session state and show a warning so the user knows to re-login.
          disconnect()
          sessionStorage.removeItem('mg_workshop_code')
          sessionStorage.removeItem('mg_workshop_diagram_id')
          eventBus.emit('workshop:code-changed', { code: null, visibility: null })
          notify.warning(t('workshopCanvas.sessionExpiredReconnect'))
          return
        }

        if (event.code === 4002) {
          disconnect()
          eventBus.emit('workshop:code-changed', { code: null, visibility: null })
          notify.info(t('workshopCanvas.returnedHomeIdle'))
          void router.replace({ name: 'MindGraph' }).catch(() => {})
          return
        }

        if (event.code === 4010) {
          disconnect()
          eventBus.emit('workshop:code-changed', { code: null, visibility: null })
          notify.info(t('workshopCanvas.returnedHomeRoomIdle'))
          void router.replace({ name: 'MindGraph' }).catch(() => {})
          return
        }

        if (event.code === 4011) {
          const sendGuestHome = collaborationParticipantIsGuest()
          disconnect()
          eventBus.emit('workshop:code-changed', { code: null, visibility: null })
          if (sendGuestHome) {
            void router.replace({ name: 'MindGraph' }).catch(() => {})
          }
          return
        }

        if (event.code === 4003) {
          notify.info(event.reason || t('workshopCanvas.otherTabCollaborationActive'))
          disconnect()
          return
        }

        if (event.code === 4014) {
          notify.warning(t('workshopCanvas.connectionClosedSlow'))
          disconnect()
          return
        }

        if (!errorNotified && event.code !== 1000 && event.code !== 1001) {
          const reason = event.reason || t('workshopCanvas.connectionClosed')
          notify.warning(t('workshopCanvas.connectionClosedReason', { reason }))
        }

        if (shouldScheduleReconnect(reconnectAttempts.value, event.code) && workshopCode.value) {
          activeEditors.value.clear()
          remoteSelectionsByUser.value.clear()
          clearPendingResyncWatchdog()
          version.reset()
          connectionStatus.value = 'reconnecting'
          const delay =
            computeReconnectDelayMs(reconnectAttempts.value) +
            Math.random() * WORKSHOP_RECONNECT.JITTER_MS
          reconnectAttempts.value++
          reconnectTimeout = setTimeout(() => {
            connect()
          }, delay)
        } else {
          // reconnect() deliberately closes the old socket with code 1000 and
          // reason 'manual_reconnect', then immediately calls connect() to open
          // a fresh socket.  By the time onclose fires here, ws.value already
          // holds the new socket.  Skip teardown so we do not kill it.
          if (event.reason === 'manual_reconnect') {
            return
          }
          if (reconnectAttempts.value >= maxReconnectAttempts) {
            notify.error(t('workshopCanvas.reconnectFailed'))
            connectionStatus.value = 'failed'
          }
          disconnect()
          sessionStorage.removeItem('mg_workshop_code')
          sessionStorage.removeItem('mg_workshop_diagram_id')
          eventBus.emit('workshop:code-changed', { code: null, visibility: null })
        }
      }

      ws.value = socket
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('[WorkshopWS] Failed to connect:', error)
      }
      notify.error(t('workshopCanvas.connectFailed'))
    }
  }

  function disconnect() {
    presence.clearRoomIdleCountdownUi()
    presence.clearPresenceCoalescer()
    clearNodeEditingThrottles()
    clearAuthRefreshReconnect()
    clearPendingResyncWatchdog()
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }

    reconnectAttempts.value = 0

    if (ws.value) {
      try {
        ws.value.close()
      } catch (error) {
        if (import.meta.env.DEV) {
          console.error('[WorkshopWS] Error closing WebSocket:', error)
        }
      }
      ws.value = null
    }

    isConnected.value = false
    connectionStatus.value = 'connected'
    participants.value = []
    participantsWithNames.value = []
    activeEditors.value.clear()
    remoteSelectionsByUser.value.clear()
    diagramOwnerId.value = null
    sessionMutable.sessionDiagramId = null
    sessionDiagramIdRef.value = null
    serverBaselineReady.value = false
    version.reset()
    outboundQueue.clear()
    joinResumeToken.value = null
    sessionDiagramTitleRef.value = null

    stopHeartbeat()
  }

  let codeWatcher: (() => void) | null = null

  function watchCode() {
    if (codeWatcher) {
      codeWatcher()
      codeWatcher = null
    }

    codeWatcher = watch(
      [workshopCode, diagramId],
      ([code]) => {
        if (code) {
          connect()
          startHeartbeat()
        } else {
          disconnect()
        }
      },
      { immediate: true }
    )
  }

  onUnmounted(() => {
    if (codeWatcher) {
      codeWatcher()
      codeWatcher = null
    }

    disconnect()
    stopHeartbeat()
  })

  function reconnect() {
    reconnectAttempts.value = 0
    connectionStatus.value = 'connected'
    if (ws.value && ws.value.readyState !== WebSocket.CLOSED) {
      ws.value.close(1000, 'manual_reconnect')
    }
    connect()
  }

  /**
   * Optimistically mark the current user as the diagram owner before the WS
   * `joined` message arrives.  Called by checkAndReconnectWorkshop when the
   * REST status endpoint already confirms is_owner=true, so isDiagramOwner is
   * immediately true during the WS handshake window instead of flickering to
   * false (guest) until the server echoes owner_id back.
   */
  function setOwnerIdOptimistic(userId: number): void {
    diagramOwnerId.value = userId
  }

  function refreshActiveEditorsRef(): void {
    activeEditors.value = new Map(activeEditors.value)
  }

  return {
    isConnected,
    connectionStatus: computed(() => connectionStatus.value),
    participants,
    participantsWithNames: computed(() => participantsWithNames.value),
    activeEditors: computed(() => activeEditors.value),
    remoteSelectionsByUser: computed(() => remoteSelectionsByUser.value),
    diagramOwnerId: computed(() => diagramOwnerId.value),
    lastLiveSpecVersion: version.liveVersion,
    collabSyncVersion: version,
    roomIdleSecondsRemaining: computed(() => presence.roomIdleSecondsRemaining.value),
    workshopRole: computed(() => workshopRole.value),
    isDiagramOwner,
    sessionDiagramId: computed(() => sessionDiagramIdRef.value),
    sessionDiagramTitle: computed(() => sessionDiagramTitleRef.value),
    connect,
    disconnect,
    reconnect,
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    sendClaimNodeEdit,
    setOwnerIdOptimistic,
    refreshActiveEditorsRef,
    watchCode,
  }
}
