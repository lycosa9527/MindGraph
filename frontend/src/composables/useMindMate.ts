/**
 * useMindMate - Composable for AI assistant conversation
 *
 * Handles:
 * - SSE streaming for AI responses
 * - Conversation management (userId, conversationId)
 * - Message state (user/assistant messages)
 * - Panel integration via EventBus
 * - Markdown rendering
 *
 * Migrated from archive/static/js/managers/mindmate-manager.js
 */
import { computed, onUnmounted, ref, shallowRef } from 'vue'

import { eventBus } from './useEventBus'

// ============================================================================
// Types
// ============================================================================

export interface MindMateMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  isStreaming?: boolean
}

export interface MindMateOptions {
  ownerId?: string
  language?: 'en' | 'zh'
  onMessageChunk?: (chunk: string) => void
  onMessageComplete?: () => void
  onError?: (error: string) => void
}

export type MindMateState = 'idle' | 'loading' | 'streaming' | 'error'

interface SSEData {
  event: string
  answer?: string
  conversation_id?: string
  error?: string
  error_type?: string
  message?: string
}

// ============================================================================
// Composable
// ============================================================================

export function useMindMate(options: MindMateOptions = {}) {
  const {
    ownerId = `MindMate_${Date.now()}`,
    language = 'en',
    onMessageChunk,
    onMessageComplete,
    onError,
  } = options

  // =========================================================================
  // State
  // =========================================================================

  const state = ref<MindMateState>('idle')
  const messages = ref<MindMateMessage[]>([])
  const conversationId = ref<string | null>(null)
  const diagramSessionId = ref<string | null>(null)
  const hasGreeted = ref(false)
  const currentLang = ref(language)

  // Streaming state
  const streamingBuffer = ref('')
  const currentStreamingId = ref<string | null>(null)

  // User ID (persisted)
  const userId = shallowRef(getUserId())

  // =========================================================================
  // Computed
  // =========================================================================

  const isStreaming = computed(() => state.value === 'streaming')
  const isLoading = computed(() => state.value === 'loading')
  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() => messages.value[messages.value.length - 1] || null)

  // =========================================================================
  // Helpers
  // =========================================================================

  function getUserId(): string {
    let id = localStorage.getItem('mindgraph_user_id')
    if (!id) {
      id = `user_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`
      localStorage.setItem('mindgraph_user_id', id)
    }
    return id
  }

  function generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
  }

  function addMessage(role: MindMateMessage['role'], content: string, isStreaming = false): string {
    const id = generateMessageId()
    messages.value.push({
      id,
      role,
      content,
      timestamp: Date.now(),
      isStreaming,
    })
    return id
  }

  function updateMessage(id: string, content: string, isStreaming = false): void {
    const msg = messages.value.find((m) => m.id === id)
    if (msg) {
      msg.content = content
      msg.isStreaming = isStreaming
    }
  }

  // =========================================================================
  // SSE Streaming
  // =========================================================================

  async function sendMessage(
    message: string,
    showUserMessage = true
  ): Promise<void> {
    if (!message.trim()) return

    // Add user message
    if (showUserMessage) {
      addMessage('user', message)
    }

    state.value = 'loading'
    streamingBuffer.value = ''
    currentStreamingId.value = null

    // Emit event
    eventBus.emit('mindmate:message_sending', { message })

    try {
      const token = localStorage.getItem('access_token')
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const response = await fetch('/api/ai_assistant/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message,
          user_id: userId.value,
          conversation_id: conversationId.value,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      state.value = 'streaming'

      // Create streaming message placeholder
      currentStreamingId.value = addMessage('assistant', '', true)

      // Recursive read function
      const readChunk = async (): Promise<void> => {
        const { done, value } = await reader.read()

        if (done) {
          // Stream complete
          if (currentStreamingId.value) {
            updateMessage(currentStreamingId.value, streamingBuffer.value, false)
          }

          state.value = 'idle'
          currentStreamingId.value = null
          streamingBuffer.value = ''

          eventBus.emit('mindmate:message_completed', {
            conversationId: conversationId.value,
          })
          onMessageComplete?.()
          return
        }

        // Decode chunk
        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: SSEData = JSON.parse(line.slice(6))
              handleStreamEvent(data)
            } catch {
              // Skip malformed JSON
            }
          }
        }

        // Continue reading
        await readChunk()
      }

      await readChunk()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      state.value = 'error'

      // Remove streaming message if exists
      if (currentStreamingId.value) {
        messages.value = messages.value.filter((m) => m.id !== currentStreamingId.value)
      }

      currentStreamingId.value = null
      streamingBuffer.value = ''

      eventBus.emit('mindmate:error', { error: errorMsg })
      onError?.(errorMsg)
    }
  }

  function handleStreamEvent(data: SSEData): void {
    switch (data.event) {
      case 'message':
        if (data.answer) {
          streamingBuffer.value += data.answer

          if (currentStreamingId.value) {
            updateMessage(currentStreamingId.value, streamingBuffer.value, true)
          }

          eventBus.emit('mindmate:message_chunk', { chunk: data.answer })
          onMessageChunk?.(data.answer)
        }

        // Save conversation ID
        if (data.conversation_id && !conversationId.value) {
          conversationId.value = data.conversation_id
        }
        break

      case 'message_end':
        if (currentStreamingId.value) {
          updateMessage(currentStreamingId.value, streamingBuffer.value, false)
        }

        if (data.conversation_id) {
          conversationId.value = data.conversation_id
        }

        streamingBuffer.value = ''
        currentStreamingId.value = null
        break

      case 'error':
        const errorMsg = data.message || data.error || 'An error occurred'

        if (currentStreamingId.value) {
          messages.value = messages.value.filter((m) => m.id !== currentStreamingId.value)
        }

        addMessage('assistant', errorMsg)

        streamingBuffer.value = ''
        currentStreamingId.value = null
        state.value = 'error'

        eventBus.emit('mindmate:stream_error', {
          error: data.error,
          error_type: data.error_type,
          message: errorMsg,
        })
        onError?.(errorMsg)
        break
    }
  }

  // =========================================================================
  // Conversation Management
  // =========================================================================

  async function sendGreeting(): Promise<void> {
    if (hasGreeted.value) return

    hasGreeted.value = true

    try {
      await sendMessage('start', false)
    } catch {
      // Show fallback welcome
      const welcomeText =
        currentLang.value === 'zh'
          ? '✨ MindMate AI 已就绪\n有什么可以帮助您的吗？'
          : '✨ MindMate AI is ready\nHow can I help you today?'
      addMessage('assistant', welcomeText)
    }
  }

  function startNewSession(sessionId: string): void {
    // Check if new session
    if (diagramSessionId.value !== sessionId) {
      diagramSessionId.value = sessionId
      conversationId.value = null
      hasGreeted.value = false
      messages.value = []
    }
  }

  function clearMessages(): void {
    messages.value = []
    streamingBuffer.value = ''
    currentStreamingId.value = null
    state.value = 'idle'
  }

  function resetConversation(): void {
    conversationId.value = null
    hasGreeted.value = false
    clearMessages()
  }

  // =========================================================================
  // Panel Integration
  // =========================================================================

  function openPanel(): void {
    eventBus.emit('panel:open_requested', { panel: 'mindmate', source: 'mindmate_composable' })
  }

  function closePanel(): void {
    eventBus.emit('panel:close_requested', { panel: 'mindmate', source: 'mindmate_composable' })
  }

  // =========================================================================
  // EventBus Subscriptions
  // =========================================================================

  // Listen for send message requests (from voice agent)
  eventBus.onWithOwner(
    'mindmate:send_message',
    (data) => {
      if (data.message) {
        sendMessage(data.message as string)
      }
    },
    ownerId
  )

  // Listen for panel open to send greeting
  eventBus.onWithOwner(
    'panel:opened',
    (data) => {
      if (data.panel === 'mindmate' && !hasGreeted.value) {
        setTimeout(() => sendGreeting(), 300)
      }
    },
    ownerId
  )

  // Listen for session changes
  eventBus.onWithOwner(
    'lifecycle:session_starting',
    (data) => {
      if (data.sessionId) {
        startNewSession(data.sessionId as string)
      }
    },
    ownerId
  )

  // =========================================================================
  // Cleanup
  // =========================================================================

  function destroy(): void {
    eventBus.removeAllListenersForOwner(ownerId)

    // Clear state
    conversationId.value = null
    diagramSessionId.value = null
    hasGreeted.value = false
    messages.value = []
    streamingBuffer.value = ''
    currentStreamingId.value = null
  }

  onUnmounted(() => {
    destroy()
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    state,
    messages,
    conversationId,
    diagramSessionId,
    hasGreeted,
    userId,
    currentLang,

    // Computed
    isStreaming,
    isLoading,
    hasMessages,
    lastMessage,

    // Actions
    sendMessage,
    sendGreeting,
    startNewSession,
    clearMessages,
    resetConversation,
    openPanel,
    closePanel,

    // Cleanup
    destroy,
  }
}

// ============================================================================
// Markdown Utilities (for components)
// ============================================================================

/**
 * Simple markdown to HTML converter for MindMate messages
 * For full markdown support, use markdown-it in the component
 */
export function simpleMarkdown(text: string): string {
  return text
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
    // Inline code
    .replace(/`(.+?)`/g, '<code>$1</code>')
    // Links
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // Line breaks
    .replace(/\n/g, '<br>')
}
