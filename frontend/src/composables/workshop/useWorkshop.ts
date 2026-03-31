/**
 * useWorkshop - Composable for presentation-mode WebSocket collaboration
 * Handles real-time diagram updates via WebSocket
 */
import { type Ref, computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { eventBus } from '@/composables/core/useEventBus'
import { useAuthStore } from '@/stores'

export interface ParticipantInfo {
  user_id: number
  username: string
}

export interface WorkshopUpdate {
  type:
    | 'update'
    | 'user_joined'
    | 'user_left'
    | 'joined'
    | 'snapshot'
    | 'error'
    | 'pong'
    | 'node_editing'
    | 'node_selected'
  diagram_id?: string
  spec?: Record<string, unknown>
  nodes?: Array<Record<string, unknown>> // Granular: only changed nodes
  connections?: Array<Record<string, unknown>> // Granular: only changed connections
  user_id?: number
  username?: string
  timestamp?: string
  participants?: number[] // Backward compatibility
  participants_with_names?: ParticipantInfo[] // New: includes usernames
  message?: string
  node_id?: string
  editing?: boolean
  color?: string
  emoji?: string
  selected?: boolean
  owner_id?: number
  version?: number
}

export interface RemoteNodeSelection {
  nodeId: string
  username: string
  color: string
}

export interface ActiveEditor {
  user_id: number
  username: string
  color: string
  emoji: string
}

export function useWorkshop(
  workshopCode: Ref<string | null>,
  diagramId: Ref<string | null>,
  onUpdate?: (spec: Record<string, unknown>) => void,
  onGranularUpdate?: (
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>
  ) => void,
  onNodeEditing?: (nodeId: string, editor: ActiveEditor | null) => void,
  onServerSnapshot?: (spec: Record<string, unknown>, version: number) => void
) {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const participants = ref<number[]>([]) // Backward compatibility
  const participantsWithNames = ref<ParticipantInfo[]>([]) // New: includes usernames
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000
  const activeEditors = ref<Map<string, ActiveEditor>>(new Map()) // node_id -> ActiveEditor
  /** Remote users' selected node (for dashed outline); excludes current user. */
  const remoteSelectionsByUser = ref<Map<number, RemoteNodeSelection>>(new Map())
  const diagramOwnerId = ref<number | null>(null)
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  const authStore = useAuthStore()
  const notify = useNotifications()
  const { t } = useLanguage()
  const router = useRouter()

  const isDiagramOwner = computed(() => {
    if (!workshopCode.value) {
      return true
    }
    if (diagramOwnerId.value == null) {
      return false
    }
    return String(diagramOwnerId.value) === String(authStore.user?.id ?? '')
  })

  // Get WebSocket URL
  function getWebSocketUrl(code: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/api/ws/canvas-collab/${code}`
  }

  // Connect to presentation-mode WebSocket
  function connect() {
    if (!workshopCode.value || !diagramId.value) {
      return
    }

    if (ws.value?.readyState === WebSocket.OPEN) {
      return // Already connected
    }

    try {
      const url = getWebSocketUrl(workshopCode.value)
      const socket = new WebSocket(url)

      socket.onopen = () => {
        isConnected.value = true
        reconnectAttempts.value = 0

        // Send join message
        socket.send(
          JSON.stringify({
            type: 'join',
            diagram_id: diagramId.value,
          })
        )
      }

      socket.onmessage = (event) => {
        try {
          const message: WorkshopUpdate = JSON.parse(event.data)

          switch (message.type) {
            case 'joined':
              participants.value = message.participants || []
              participantsWithNames.value = message.participants_with_names || []
              if (message.owner_id !== undefined && message.owner_id !== null) {
                diagramOwnerId.value = Number(message.owner_id)
              }
              break

            case 'snapshot':
              if (message.spec && onServerSnapshot) {
                onServerSnapshot(message.spec, message.version ?? 1)
              }
              break

            case 'update':
              // Handle granular updates (preferred) or full spec (backward compatibility)
              if (message.nodes !== undefined || message.connections !== undefined) {
                // Granular update: merge only changed nodes/connections
                if (onGranularUpdate) {
                  onGranularUpdate(message.nodes, message.connections)
                } else if (onUpdate) {
                  // Fallback: if no granular handler, use full update handler
                  if (import.meta.env.DEV) {
                    console.warn(
                      '[WorkshopWS] Granular update received but no onGranularUpdate handler'
                    )
                  }
                }
              } else if (message.spec && onUpdate) {
                // Full spec update (backward compatibility)
                onUpdate(message.spec)
              }
              break

            case 'node_editing':
              if (message.node_id) {
                if (message.editing && message.user_id && message.color && message.emoji) {
                  // User started editing
                  const editor: ActiveEditor = {
                    user_id: message.user_id,
                    username: message.username || `User ${message.user_id}`,
                    color: message.color,
                    emoji: message.emoji,
                  }
                  activeEditors.value.set(message.node_id, editor)

                  // Show notification if not current user
                  if (
                    message.user_id !== undefined &&
                    String(message.user_id) !== authStore.user?.id
                  ) {
                    notify.info(
                      t('workshopCanvas.editingNode', {
                        username: editor.username,
                        emoji: editor.emoji,
                      })
                    )
                  }

                  if (onNodeEditing) {
                    onNodeEditing(message.node_id, editor)
                  }
                } else {
                  // User stopped editing
                  activeEditors.value.delete(message.node_id)

                  if (onNodeEditing) {
                    onNodeEditing(message.node_id, null)
                  }
                }
              }
              break

            case 'user_joined': {
              const joinedId = message.user_id
              if (joinedId == null) {
                break
              }
              participants.value = [...(participants.value || []), joinedId]
              notify.info(t('workshopCanvas.userJoined', { userId: String(message.user_id) }))
              break
            }

            case 'user_left': {
              const leftId = message.user_id
              participants.value = (participants.value || []).filter((id) => id !== leftId)
              if (leftId != null) {
                remoteSelectionsByUser.value.delete(leftId)
                remoteSelectionsByUser.value = new Map(remoteSelectionsByUser.value)
              }
              notify.info(t('workshopCanvas.userLeft', { userId: String(message.user_id) }))
              break
            }

            case 'node_selected': {
              const uid = message.user_id
              const nid = message.node_id
              if (uid == null || !nid) {
                break
              }
              if (String(uid) === String(authStore.user?.id ?? '')) {
                break
              }
              if (message.selected === false) {
                remoteSelectionsByUser.value.delete(uid)
              } else {
                remoteSelectionsByUser.value.set(uid, {
                  nodeId: nid,
                  username: message.username || `User ${uid}`,
                  color: message.color || '#f97316',
                })
              }
              remoteSelectionsByUser.value = new Map(remoteSelectionsByUser.value)
              break
            }

            case 'error':
              notify.error(message.message || t('workshopCanvas.errorGeneric'))
              break

            case 'pong':
              // Heartbeat response
              break
          }
        } catch (error) {
          if (import.meta.env.DEV) {
            console.error('[WorkshopWS] Failed to parse message:', error)
          }
        }
      }

      socket.onerror = (error) => {
        if (import.meta.env.DEV) {
          console.error('[WorkshopWS] WebSocket error:', error)
        }
        isConnected.value = false
        notify.error(t('workshopCanvas.wsError'))
      }

      socket.onclose = (event) => {
        isConnected.value = false

        if (event.code === 4002) {
          disconnect()
          eventBus.emit('workshop:code-changed', { code: null })
          notify.info(t('workshopCanvas.returnedHomeIdle'))
          void router.push('/mindgraph')
          return
        }

        // Show error notification if not a normal closure
        if (event.code !== 1000 && event.code !== 1001) {
          const reason = event.reason || t('workshopCanvas.connectionClosed')
          notify.warning(t('workshopCanvas.connectionClosedReason', { reason }))
        }

        // Attempt to reconnect
        if (
          reconnectAttempts.value < maxReconnectAttempts &&
          workshopCode.value &&
          event.code !== 1000
        ) {
          reconnectAttempts.value++
          reconnectTimeout = setTimeout(() => {
            connect()
          }, reconnectDelay)
        } else if (reconnectAttempts.value >= maxReconnectAttempts) {
          notify.error(t('workshopCanvas.reconnectFailed'))
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

  // Disconnect from presentation mode
  function disconnect() {
    // Clear reconnect timeout
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }

    // Reset reconnect attempts
    reconnectAttempts.value = 0

    // Close WebSocket
    if (ws.value) {
      try {
        ws.value.close()
      } catch (error) {
        console.error('[WorkshopWS] Error closing WebSocket:', error)
      }
      ws.value = null
    }

    // Clear state
    isConnected.value = false
    participants.value = []
    participantsWithNames.value = []
    activeEditors.value.clear()
    remoteSelectionsByUser.value.clear()
    diagramOwnerId.value = null

    // Stop heartbeat
    stopHeartbeat()
  }

  // Send diagram update (granular or full spec)
  function sendUpdate(
    spec?: Record<string, unknown>,
    nodes?: Array<Record<string, unknown>>,
    connections?: Array<Record<string, unknown>>
  ) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return
    }

    try {
      const message: Record<string, unknown> = {
        type: 'update',
        diagram_id: diagramId.value,
        timestamp: new Date().toISOString(),
      }

      // Prefer granular updates
      if (nodes !== undefined || connections !== undefined) {
        if (nodes !== undefined) {
          message.nodes = nodes
        }
        if (connections !== undefined) {
          message.connections = connections
        }
      } else if (spec) {
        // Fallback to full spec
        message.spec = spec
      } else {
        if (import.meta.env.DEV) {
          console.warn('[WorkshopWS] sendUpdate called without spec, nodes, or connections')
        }
        return
      }

      ws.value.send(JSON.stringify(message))
    } catch (error) {
      if (import.meta.env.DEV) {
        console.error('[WorkshopWS] Failed to send update:', error)
      }
    }
  }

  function sendNodeSelected(nodeId: string | null, selected: boolean) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return
    }
    if (!nodeId) {
      return
    }
    try {
      ws.value.send(
        JSON.stringify({
          type: 'node_selected',
          node_id: nodeId,
          selected,
        })
      )
    } catch (error) {
      console.error('[WorkshopWS] Failed to send node_selected:', error)
    }
  }

  // Notify when user starts/stops editing a node
  function notifyNodeEditing(nodeId: string, editing: boolean) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return
    }

    try {
      ws.value.send(
        JSON.stringify({
          type: 'node_editing',
          node_id: nodeId,
          editing,
        })
      )
    } catch (error) {
      console.error('[WorkshopWS] Failed to send node_editing:', error)
    }
  }

  // Send ping (heartbeat)
  function ping() {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      return
    }

    try {
      ws.value.send(JSON.stringify({ type: 'ping' }))
    } catch (error) {
      console.error('[WorkshopWS] Failed to send ping:', error)
    }
  }

  // Setup heartbeat
  let heartbeatInterval: ReturnType<typeof setInterval> | null = null
  function startHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
    }
    heartbeatInterval = setInterval(() => {
      if (isConnected.value) {
        ping()
      }
    }, 30000) // Ping every 30 seconds
  }

  function stopHeartbeat() {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }
  }

  // Watch for code changes and connect/disconnect
  let codeWatcher: (() => void) | null = null

  function watchCode() {
    // Stop existing watcher
    if (codeWatcher) {
      codeWatcher()
      codeWatcher = null
    }

    // Create new watcher for code/diagram changes
    codeWatcher = watch(
      [workshopCode, diagramId],
      ([code, id]) => {
        if (code && id) {
          connect()
          startHeartbeat()
        } else {
          disconnect()
        }
      },
      { immediate: true }
    )
  }

  // Cleanup on unmount
  onUnmounted(() => {
    // Stop watcher
    if (codeWatcher) {
      codeWatcher()
      codeWatcher = null
    }

    // Disconnect and cleanup
    disconnect()
    stopHeartbeat()
  })

  return {
    isConnected,
    participants,
    participantsWithNames: computed(() => participantsWithNames.value),
    activeEditors: computed(() => activeEditors.value),
    remoteSelectionsByUser: computed(() => remoteSelectionsByUser.value),
    diagramOwnerId: computed(() => diagramOwnerId.value),
    isDiagramOwner,
    connect,
    disconnect,
    sendUpdate,
    sendNodeSelected,
    notifyNodeEditing,
    watchCode,
  }
}
