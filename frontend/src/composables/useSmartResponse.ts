import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'

export interface SmartResponseWebSocketMessage {
  type: string
  session_id?: string
  watch_id?: string
  text?: string
  is_final?: boolean
  [key: string]: any
}

export function useSmartResponseWebSocket(sessionId: Ref<string | null>) {
  const ws: Ref<WebSocket | null> = ref(null)
  const connected = ref(false)
  const error = ref<string | null>(null)

  const connect = () => {
    if (!sessionId.value) {
      error.value = 'No session ID'
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/smart-response/${sessionId.value}`

    try {
      ws.value = new WebSocket(wsUrl)
      
      ws.value.onopen = () => {
        connected.value = true
        error.value = null
        console.log('Smart Response WebSocket connected')
      }

      ws.value.onmessage = (event) => {
        const message: SmartResponseWebSocketMessage = JSON.parse(event.data)
        handleMessage(message)
      }

      ws.value.onerror = (err) => {
        error.value = 'WebSocket error'
        console.error('WebSocket error:', err)
      }

      ws.value.onclose = () => {
        connected.value = false
        console.log('Smart Response WebSocket disconnected')
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Connection failed'
    }
  }

  const disconnect = () => {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
  }

  const send = (message: SmartResponseWebSocketMessage) => {
    if (ws.value && connected.value) {
      ws.value.send(JSON.stringify(message))
    }
  }

  const startLearningMode = (diagramId: string, watchIds?: string[]) => {
    send({
      type: 'start_learning_mode',
      diagram_id: diagramId,
      watch_ids: watchIds || [],
    })
  }

  const stopLearningMode = () => {
    if (sessionId.value) {
      send({
        type: 'stop_learning_mode',
        session_id: sessionId.value,
      })
    }
  }

  const handleFillRequestResponse = (
    nodeId: string,
    requestId: string,
    action: 'approve' | 'reject',
    finalText?: string
  ) => {
    if (sessionId.value) {
      send({
        type: 'fill_request_response',
        session_id: sessionId.value,
        node_id: nodeId,
        request_id: requestId,
        action,
        final_text: finalText,
      })
    }
  }

  const handleMessage = (message: SmartResponseWebSocketMessage) => {
    switch (message.type) {
      case 'learning_mode_started':
        console.log('Learning mode started:', message)
        break
      case 'watch_ready':
        console.log('Watch ready:', message.watch_id)
        break
      case 'transcription_notification':
        console.log('Transcription:', message.text)
        break
      default:
        console.log('Unknown message type:', message.type)
    }
  }

  onMounted(() => {
    if (sessionId.value) {
      connect()
    }
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    error,
    connect,
    disconnect,
    send,
    startLearningMode,
    stopLearningMode,
    handleFillRequestResponse,
  }
}