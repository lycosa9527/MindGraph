/**
 * useWorkshop - Composable for workshop WebSocket collaboration
 * Handles real-time diagram updates via WebSocket
 */
import { ref, computed, watch, onUnmounted, type Ref } from 'vue'

import { useAuthStore } from '@/stores'
import { useNotifications, useLanguage } from '@/composables'

export interface ParticipantInfo {
  user_id: number
  username: string
}

export interface WorkshopUpdate {
  type: 'update' | 'user_joined' | 'user_left' | 'joined' | 'error' | 'pong' | 'node_editing'
  diagram_id?: string
  spec?: Record<string, unknown>
  nodes?: Array<Record<string, unknown>>  // Granular: only changed nodes
  connections?: Array<Record<string, unknown>>  // Granular: only changed connections
  user_id?: number
  username?: string
  timestamp?: string
  participants?: number[]  // Backward compatibility
  participants_with_names?: ParticipantInfo[]  // New: includes usernames
  message?: string
  node_id?: string
  editing?: boolean
  color?: string
  emoji?: string
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
  onGranularUpdate?: (nodes?: Array<Record<string, unknown>>, connections?: Array<Record<string, unknown>>) => void,
  onNodeEditing?: (nodeId: string, editor: ActiveEditor | null) => void
) {
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const participants = ref<number[]>([])  // Backward compatibility
  const participantsWithNames = ref<ParticipantInfo[]>([])  // New: includes usernames
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000
  const activeEditors = ref<Map<string, ActiveEditor>>(new Map())  // node_id -> ActiveEditor
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  const authStore = useAuthStore()
  const notify = useNotifications()
  const { isZh } = useLanguage()

  // Get WebSocket URL
  function getWebSocketUrl(code: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/api/ws/workshop/${code}`
  }

  // Connect to workshop WebSocket
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
        console.log('[WorkshopWS] Connected')
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
              console.log('[WorkshopWS] Joined workshop', message)
              break

            case 'update':
              // Handle granular updates (preferred) or full spec (backward compatibility)
              if (message.nodes !== undefined || message.connections !== undefined) {
                // Granular update: merge only changed nodes/connections
                if (onGranularUpdate) {
                  onGranularUpdate(message.nodes, message.connections)
                } else if (onUpdate) {
                  // Fallback: if no granular handler, use full update handler
                  // This requires the frontend to merge manually
                  console.warn('[WorkshopWS] Granular update received but no onGranularUpdate handler')
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
                  if (message.user_id !== undefined && String(message.user_id) !== authStore.user?.id) {
                    notify.info(
                      isZh.value
                        ? `${editor.username} ${editor.emoji} 正在编辑此节点`
                        : `${editor.username} ${editor.emoji} is editing this node`
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

            case 'user_joined':
              participants.value = [
                ...(participants.value || []),
                message.user_id!,
              ]
              notify.info(
                isZh.value
                  ? `用户 ${message.user_id} 已加入`
                  : `User ${message.user_id} joined`
              )
              break

            case 'user_left':
              participants.value = (participants.value || []).filter(
                (id) => id !== message.user_id
              )
              notify.info(
                isZh.value
                  ? `用户 ${message.user_id} 已离开`
                  : `User ${message.user_id} left`
              )
              break

            case 'error':
              notify.error(
                message.message ||
                  (isZh.value ? '工作坊错误' : 'Workshop error')
              )
              break

            case 'pong':
              // Heartbeat response
              break
          }
        } catch (error) {
          console.error('[WorkshopWS] Failed to parse message:', error)
        }
      }

      socket.onerror = (error) => {
        console.error('[WorkshopWS] WebSocket error:', error)
        isConnected.value = false
        notify.error(
          isZh.value
            ? '工作坊连接错误，请检查网络连接'
            : 'Workshop connection error, please check your network'
        )
      }

      socket.onclose = (event) => {
        console.log('[WorkshopWS] Disconnected', event.code, event.reason)
        isConnected.value = false

        // Show error notification if not a normal closure
        if (event.code !== 1000 && event.code !== 1001) {
          const reason =
            event.reason ||
            (isZh.value ? '连接已断开' : 'Connection closed')
          notify.warning(
            isZh.value
              ? `工作坊连接已断开：${reason}`
              : `Workshop connection closed: ${reason}`
          )
        }

        // Attempt to reconnect
        if (
          reconnectAttempts.value < maxReconnectAttempts &&
          workshopCode.value &&
          event.code !== 1000
        ) {
          reconnectAttempts.value++
          reconnectTimeout = setTimeout(() => {
            console.log(
              `[WorkshopWS] Reconnecting (attempt ${reconnectAttempts.value})...`
            )
            connect()
          }, reconnectDelay)
        } else if (reconnectAttempts.value >= maxReconnectAttempts) {
          notify.error(
            isZh.value
              ? '工作坊重连失败，请刷新页面重试'
              : 'Failed to reconnect to workshop, please refresh the page'
          )
        }
      }

      ws.value = socket
    } catch (error) {
      console.error('[WorkshopWS] Failed to connect:', error)
      notify.error(
        isZh.value ? '连接工作坊失败' : 'Failed to connect to workshop'
      )
    }
  }

  // Disconnect from workshop
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
        console.warn('[WorkshopWS] sendUpdate called without spec, nodes, or connections')
        return
      }

      ws.value.send(JSON.stringify(message))
    } catch (error) {
      console.error('[WorkshopWS] Failed to send update:', error)
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
    connect,
    disconnect,
    sendUpdate,
    notifyNodeEditing,
    watchCode,
  }
}
