/**
 * useMindMate - Composable for AI assistant conversation
 *
 * Handles:
 * - SSE streaming for AI responses
 * - Conversation management (userId, conversationId)
 * - Message state (user/assistant messages)
 * - Panel integration via EventBus
 * - Message markdown (see `MessageBubble` + `renderRichMarkdownHtml`)
 *
 * Conversation history list is managed by useMindMateStore (Pinia).
 * This composable handles messages for a single conversation.
 *
 * Migrated from archive/static/js/managers/mindmate-manager.js
 */
import { computed, onUnmounted, ref, shallowRef, watch } from 'vue'

import { useQueryClient } from '@tanstack/vue-query'

import { useAuthStore, useMindMateStore } from '@/stores'
import type { ModelLoadPhase } from '@/stores/llmResults'
import type {
  DifyHistoryMessage,
  FeedbackRating,
  MindMateFile,
  MindMateMessage,
} from '@/stores/mindmateActiveThread'
import {
  mapDifyMessagesToMindMate,
  threadsContentEqual,
} from '@/stores/mindmateActiveThread'
import { consumeSseDataLines } from '@/utils/mindMateSseStream'
import { mindmateDifyUserIdFromSession } from '@/utils/mindmateDifyUserId'

import { eventBus } from '../core/useEventBus'
import { difyKeys, useAppParameters, useGenerateTitle } from '../queries'
import {
  mindMateLoadPhaseOnAbort,
  mindMateLoadPhaseOnComplete,
  mindMateLoadPhaseOnError,
  mindMateLoadPhaseOnFirstToken,
  mindMateLoadPhaseOnSendStart,
  mindMateLoadPhaseOnStreamOpen,
} from './mindMateLoadPhase'

// ============================================================================
// Types
// ============================================================================

export type { FeedbackRating, MindMateFile, MindMateMessage } from '@/stores/mindmateActiveThread'

export interface MindMateConversation {
  id: string
  name: string
  created_at: number
  updated_at: number
}

export interface MindMateOptions {
  ownerId?: string
  language?: string
  onMessageChunk?: (chunk: string) => void
  onMessageComplete?: () => void
  onError?: (error: string) => void
  onTitleChanged?: (title: string, oldTitle?: string) => void
}

export type MindMateState = 'idle' | 'loading' | 'streaming' | 'error'

interface SSEData {
  event: string
  answer?: string
  conversation_id?: string
  message_id?: string // Dify message ID for feedback
  error?: string
  error_type?: string
  message?: string
  // message_file event fields
  id?: string
  type?: string
  url?: string
  belongs_to?: string
  // workflow event fields
  workflow_run_id?: string
  task_id?: string
  data?: Record<string, unknown>
}

interface DifyMessage extends DifyHistoryMessage {}

export function useMindMate(options: MindMateOptions = {}) {
  const {
    ownerId = `MindMate_${Date.now()}`,
    language = 'en',
    onMessageChunk,
    onMessageComplete,
    onError,
    onTitleChanged,
  } = options

  // =========================================================================
  // Stores
  // =========================================================================

  const authStore = useAuthStore()
  const mindMateStore = useMindMateStore()
  const queryClient = useQueryClient()

  // =========================================================================
  // Vue Query
  // =========================================================================

  // Fetch app parameters (opening statement, suggested questions)
  const { data: appParams } = useAppParameters()
  const { mutate: generateTitle } = useGenerateTitle()

  // =========================================================================
  // State (local to this composable instance)
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
  const abortController = ref<AbortController | null>(null)
  let streamGeneration = 0

  // File upload state
  const pendingFiles = ref<MindMateFile[]>([])
  const isUploading = ref(false)

  // History loading state (distinct from isLoading which is for AI response)
  const isLoadingHistory = ref(false)

  const isRestoringThread = ref(false)
  const isLoadingFromServer = ref(false)

  // User ID - derived from authenticated user
  const userId = shallowRef(getDifyUserId())

  // =========================================================================
  // Computed (proxied from store for convenience)
  // =========================================================================

  const isStreaming = computed(() => state.value === 'streaming')
  const isLoading = computed(() => state.value === 'loading')
  const loadPhase = computed(() => mindMateStore.loadPhase)
  const isGenerating = computed(() => mindMateStore.isGenerating)

  function applyLoadPhase(phase: ModelLoadPhase): void {
    mindMateStore.setLoadPhase(phase)
  }

  function beginAssistantStreaming(): void {
    if (mindMateStore.loadPhase === 'streaming') {
      return
    }
    applyLoadPhase(mindMateLoadPhaseOnFirstToken())
    state.value = 'streaming'
  }

  function isActiveStreamGeneration(generation: number): boolean {
    return generation === streamGeneration
  }

  function finalizeStreamSuccess(generation: number): void {
    if (!isActiveStreamGeneration(generation)) {
      return
    }
    if (currentStreamingId.value) {
      updateMessage(currentStreamingId.value, streamingBuffer.value, false)
    }
    state.value = 'idle'
    applyLoadPhase(mindMateLoadPhaseOnComplete())
    currentStreamingId.value = null
    streamingBuffer.value = ''
    abortController.value = null
    eventBus.emit('mindmate:message_completed', {
      conversationId: conversationId.value ?? undefined,
    })
    onMessageComplete?.()
  }

  function finalizeStreamAbort(generation: number): void {
    if (!isActiveStreamGeneration(generation)) {
      return
    }
    if (currentStreamingId.value) {
      updateMessage(currentStreamingId.value, streamingBuffer.value, false)
    }
    state.value = 'idle'
    applyLoadPhase(mindMateLoadPhaseOnAbort())
    currentStreamingId.value = null
    streamingBuffer.value = ''
    abortController.value = null
  }

  function finalizeStreamError(generation: number, errorMsg: string, removePlaceholder: boolean): void {
    if (!isActiveStreamGeneration(generation)) {
      return
    }
    if (removePlaceholder && currentStreamingId.value) {
      messages.value = messages.value.filter((m) => m.id !== currentStreamingId.value)
    }
    state.value = 'error'
    applyLoadPhase(mindMateLoadPhaseOnError())
    currentStreamingId.value = null
    streamingBuffer.value = ''
    abortController.value = null
    eventBus.emit('mindmate:error', { error: errorMsg })
    onError?.(errorMsg)
  }
  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() => messages.value[messages.value.length - 1] || null)

  // Proxy store state for backward compatibility
  const conversations = computed(() => mindMateStore.conversations)
  const conversationTitle = computed(() => mindMateStore.conversationTitle)
  const isLoadingConversations = computed(() => mindMateStore.isLoadingConversations)
  const messageCount = computed(() => mindMateStore.messageCount)

  // =========================================================================
  // Helpers
  // =========================================================================

  function getDifyUserId(): string {
    if (authStore.user?.id) {
      return mindmateDifyUserIdFromSession(authStore.mode, authStore.user.id, authStore.user.phone)
    }
    let id = localStorage.getItem('mindgraph_guest_id')
    if (!id) {
      id = `guest_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`
      localStorage.setItem('mindgraph_guest_id', id)
    }
    return id
  }

  // Watch for auth changes and update userId
  watch(
    () => [authStore.user?.id, authStore.mode, authStore.user?.phone] as const,
    () => {
      userId.value = getDifyUserId()
    }
  )

  function generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
  }

  function syncActiveThreadToStore(): void {
    if (isRestoringThread.value || isLoadingFromServer.value) {
      return
    }
    const convId = conversationId.value ?? mindMateStore.currentConversationId
    if (!convId) {
      if (messages.value.length === 0) {
        mindMateStore.clearActiveThread()
      }
      return
    }
    mindMateStore.setActiveThread(convId, messages.value, hasGreeted.value)
  }

  function restoreActiveThread(): boolean {
    const convId = mindMateStore.currentConversationId
    if (!convId) {
      return false
    }
    const snapshot = mindMateStore.getActiveThread(convId)
    if (!snapshot) {
      return false
    }

    isRestoringThread.value = true
    messages.value = structuredClone(snapshot.messages)
    conversationId.value = convId
    hasGreeted.value = snapshot.hasGreeted
    isRestoringThread.value = false
    return true
  }

  watch(messages, () => syncActiveThreadToStore(), { deep: true })

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

  function updateMessage(
    id: string,
    content: string,
    isStreaming = false,
    difyMessageId?: string
  ): void {
    const index = messages.value.findIndex((m) => m.id === id)
    if (index !== -1) {
      // Replace the object to ensure Vue reactivity triggers properly
      messages.value[index] = {
        ...messages.value[index],
        content,
        isStreaming,
        ...(difyMessageId && { difyMessageId }),
      }
    }
  }

  // =========================================================================
  // File Upload
  // =========================================================================

  function getFileType(mimeType: string): MindMateFile['type'] {
    if (mimeType.startsWith('image/')) return 'image'
    if (mimeType.startsWith('audio/')) return 'audio'
    if (mimeType.startsWith('video/')) return 'video'
    if (
      mimeType.includes('pdf') ||
      mimeType.includes('document') ||
      mimeType.includes('text') ||
      mimeType.includes('spreadsheet') ||
      mimeType.includes('presentation')
    ) {
      return 'document'
    }
    return 'custom'
  }

  async function uploadFile(file: File): Promise<MindMateFile | null> {
    // Only allow image files
    if (!file.type.startsWith('image/')) {
      const errorMsg = 'Only image files are allowed'
      eventBus.emit('mindmate:error', { error: errorMsg })
      onError?.(errorMsg)
      return null
    }

    isUploading.value = true

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('user_id', userId.value)

      // Use fetch with credentials (token in httpOnly cookie)
      const response = await fetch('/api/dify/files/upload', {
        method: 'POST',
        credentials: 'same-origin',
        body: formData,
      })

      if (!response.ok) {
        // Handle token expiration - show login modal
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后上传文件')
          throw new Error('Session expired')
        }
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(error.detail || 'Upload failed')
      }

      const result = await response.json()
      const data = result.data

      // Validate response data exists
      if (!data || !data.id) {
        throw new Error('Invalid response from file upload API')
      }

      const uploadedFile: MindMateFile = {
        id: data.id,
        name: data.name || file.name,
        type: getFileType(data.mime_type || file.type),
        size: data.size || file.size,
        extension: data.extension || file.name.split('.').pop() || '',
        mime_type: data.mime_type || file.type,
        preview_url: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
      }

      pendingFiles.value.push(uploadedFile)
      eventBus.emit('mindmate:file_uploaded', { file: uploadedFile })

      return uploadedFile
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'File upload failed'
      eventBus.emit('mindmate:error', { error: errorMsg })
      onError?.(errorMsg)
      return null
    } finally {
      isUploading.value = false
    }
  }

  function removeFile(fileId: string): void {
    const file = pendingFiles.value.find((f) => f.id === fileId)
    if (file?.preview_url) {
      URL.revokeObjectURL(file.preview_url)
    }
    pendingFiles.value = pendingFiles.value.filter((f) => f.id !== fileId)
  }

  function clearPendingFiles(): void {
    pendingFiles.value.forEach((f) => {
      if (f.preview_url) URL.revokeObjectURL(f.preview_url)
    })
    pendingFiles.value = []
  }

  // =========================================================================
  // SSE Streaming
  // =========================================================================

  async function sendMessage(message: string, showUserMessage = true): Promise<void> {
    if (!message.trim() && pendingFiles.value.length === 0) return

    // Cancel any ongoing stream
    if (abortController.value) {
      abortController.value.abort()
    }

    streamGeneration += 1
    const activeGeneration = streamGeneration

    // Create new abort controller
    abortController.value = new AbortController()

    // Capture files to send
    const filesToSend = [...pendingFiles.value]

    // Add user message with files
    if (showUserMessage) {
      const msgId = addMessage('user', message)
      const msg = messages.value.find((m) => m.id === msgId)
      if (msg && filesToSend.length > 0) {
        msg.files = filesToSend
      }
      // Track user message for title generation (via store)
      mindMateStore.trackMessage(message, filesToSend)
    }

    // Clear message cache for this conversation (new message invalidates cache)
    // Note: Re-prefetch happens after stream completes (in message_end handler)
    if (conversationId.value) {
      mindMateStore.clearMessageCache(conversationId.value)
    }

    // Clear pending files
    pendingFiles.value = []

    state.value = 'loading'
    applyLoadPhase(mindMateLoadPhaseOnSendStart())
    streamingBuffer.value = ''
    currentStreamingId.value = null

    // Emit event
    eventBus.emit('mindmate:message_sending', { message, files: filesToSend })

    try {
      // Build request with files
      const requestBody: Record<string, unknown> = {
        message: message || (filesToSend.length > 0 ? 'Please analyze this file.' : ''),
        user_id: userId.value,
        conversation_id: conversationId.value,
      }

      // Add files in Dify format
      if (filesToSend.length > 0) {
        requestBody.files = filesToSend.map((f) => ({
          type: f.type,
          transfer_method: 'local_file',
          upload_file_id: f.id,
        }))
      }

      // Use fetch with credentials (token in httpOnly cookie)
      const response = await fetch('/api/ai_assistant/stream', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
        signal: abortController.value.signal,
      })

      if (!response.ok) {
        // Handle token expiration - show login modal
        if (response.status === 401) {
          authStore.handleTokenExpired('您的登录已过期，请重新登录后继续使用MindMate')
          throw new Error('Session expired')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      applyLoadPhase(mindMateLoadPhaseOnStreamOpen())

      // Placeholder bubble while waiting for first token (state stays loading until then)
      currentStreamingId.value = addMessage('assistant', '', true)

      await consumeSseDataLines(
        reader,
        (payload) => handleStreamEvent(payload as unknown as SSEData, activeGeneration),
        abortController.value.signal
      )

      if (
        isActiveStreamGeneration(activeGeneration) &&
        loadPhase.value !== 'error' &&
        loadPhase.value !== 'idle'
      ) {
        finalizeStreamSuccess(activeGeneration)
      }
    } catch (error) {
      // Ignore abort errors (user cancelled / stopGeneration already reset UI)
      if (error instanceof Error && error.name === 'AbortError') {
        if (isActiveStreamGeneration(activeGeneration)) {
          finalizeStreamAbort(activeGeneration)
        }
        return
      }

      const errorMsg = error instanceof Error ? error.message : 'Unknown error'
      finalizeStreamError(activeGeneration, errorMsg, true)
    }
  }

  function stopGeneration(): void {
    if (loadPhase.value === 'idle' && state.value === 'idle' && !abortController.value) {
      return
    }

    streamGeneration += 1

    if (currentStreamingId.value) {
      updateMessage(currentStreamingId.value, streamingBuffer.value, false)
    }

    applyLoadPhase(mindMateLoadPhaseOnComplete())
    state.value = 'idle'
    streamingBuffer.value = ''
    currentStreamingId.value = null

    const controller = abortController.value
    abortController.value = null
    if (controller) {
      controller.abort()
    }
  }

  function regenerateMessage(messageId: string): void {
    // Find the user message before this assistant message
    const msgIndex = messages.value.findIndex((m) => m.id === messageId)
    if (msgIndex <= 0) return

    // Find the previous user message
    let userMsgIndex = -1
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (messages.value[i].role === 'user') {
        userMsgIndex = i
        break
      }
    }

    if (userMsgIndex === -1) return

    // Remove this assistant message and any after it
    messages.value = messages.value.slice(0, msgIndex)

    // Resend the user message
    const userMessage = messages.value[userMsgIndex].content
    sendMessage(userMessage, false)
  }

  async function submitFeedback(localMessageId: string, rating: FeedbackRating): Promise<boolean> {
    // Find the message to get its Dify message ID
    const msg = messages.value.find((m) => m.id === localMessageId)
    if (!msg?.difyMessageId) {
      console.warn('[MindMate] Cannot submit feedback: no Dify message ID')
      return false
    }

    try {
      // Use fetch with credentials (token in httpOnly cookie)
      const response = await fetch(`/api/dify/messages/${msg.difyMessageId}/feedback`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rating }),
      })

      // Handle token expiration
      if (response.status === 401) {
        authStore.handleTokenExpired('您的登录已过期，请重新登录')
        return false
      }

      if (response.ok) {
        // Update local message state
        msg.feedback = rating
        eventBus.emit('mindmate:feedback_submitted', {
          messageId: localMessageId,
          difyMessageId: msg.difyMessageId,
          rating,
        })
        return true
      }

      return false
    } catch (error) {
      console.error('[MindMate] Failed to submit feedback:', error)
      return false
    }
  }

  function handleStreamEvent(data: SSEData, generation: number): boolean {
    if (!isActiveStreamGeneration(generation)) {
      return false
    }

    switch (data.event) {
      case 'message':
        if (data.answer) {
          beginAssistantStreaming()

          streamingBuffer.value += data.answer

          if (currentStreamingId.value) {
            updateMessage(currentStreamingId.value, streamingBuffer.value, true)
          }

          eventBus.emit('mindmate:message_chunk', { chunk: data.answer })
          onMessageChunk?.(data.answer)
        }

        // Save conversation ID and add to history immediately (first message creates conversation)
        if (data.conversation_id && !conversationId.value) {
          conversationId.value = data.conversation_id
          mindMateStore.setCurrentConversation(data.conversation_id)

          // Optimistic update: Add new conversation to Vue Query cache
          const now = Math.floor(Date.now() / 1000) // Use seconds like Dify
          const newConv = {
            id: data.conversation_id,
            name: mindMateStore.conversationTitle,
            created_at: now,
            updated_at: now,
          }

          // Update conversations cache optimistically
          queryClient.setQueryData(
            difyKeys.conversations(),
            (old: MindMateConversation[] | undefined) => {
              if (!old) return [newConv]
              return [newConv, ...old]
            }
          )

          // Also update store for backward compatibility
          mindMateStore.addConversation(newConv)
        }
        break

      case 'message_end':
        if (currentStreamingId.value) {
          // Capture the Dify message ID for feedback functionality
          updateMessage(currentStreamingId.value, streamingBuffer.value, false, data.message_id)
        }

        // Update conversation ID if needed (conversation was already added in 'message' event)
        if (data.conversation_id && !conversationId.value) {
          conversationId.value = data.conversation_id
          mindMateStore.setCurrentConversation(data.conversation_id)
        }

        streamingBuffer.value = ''
        currentStreamingId.value = null

        // Fetch Dify's auto-generated title after second message (with 1-second delay)
        if (mindMateStore.messageCount === 2 && conversationId.value) {
          const convId = conversationId.value
          setTimeout(() => {
            generateTitle({
              convId,
              difyUser: mindMateStore.getConversationDifyUser(convId),
            })
          }, 1000)
        }
        break

      case 'message_replace':
        // Replace entire message content (used by Dify for content edits)
        if (data.answer && currentStreamingId.value) {
          beginAssistantStreaming()
          streamingBuffer.value = data.answer
          updateMessage(currentStreamingId.value, streamingBuffer.value, true)
        }
        break

      case 'message_file':
        // File output from AI (images, documents generated by AI)
        eventBus.emit('mindmate:file_received', {
          id: data.id,
          type: data.type,
          url: data.url,
          belongs_to: data.belongs_to,
        })
        break

      case 'workflow_started':
      case 'node_started':
      case 'node_finished':
      case 'workflow_finished':
        // Workflow status events - emit for potential UI updates
        eventBus.emit('mindmate:workflow_event', {
          event: data.event,
          workflow_run_id: data.workflow_run_id,
          task_id: data.task_id,
          data: data.data,
        })
        break

      case 'tts_message':
        // TTS audio chunk - emit for audio playback
        eventBus.emit('mindmate:tts_chunk', { data: data.data })
        break

      case 'tts_message_end':
        // TTS complete
        eventBus.emit('mindmate:tts_complete', {})
        break

      case 'ping':
        // Keepalive - ignore
        break

      case 'error': {
        const errorMsg = data.message || data.error || 'An error occurred'

        if (currentStreamingId.value) {
          messages.value = messages.value.filter((m) => m.id !== currentStreamingId.value)
        }

        addMessage('assistant', errorMsg)

        streamingBuffer.value = ''
        currentStreamingId.value = null
        abortController.value = null
        state.value = 'error'
        applyLoadPhase(mindMateLoadPhaseOnError())

        eventBus.emit('mindmate:stream_error', {
          error: typeof data.error === 'string' ? data.error : undefined,
          error_type: typeof data.error_type === 'string' ? data.error_type : undefined,
          message: errorMsg,
        })
        onError?.(errorMsg)
        return false
      }

      default:
        break
    }

    return true
  }

  // =========================================================================
  // Conversation Management
  // =========================================================================

  async function sendGreeting(): Promise<void> {
    if (hasGreeted.value) return

    hasGreeted.value = true

    // Use cached app parameters from Vue Query
    // Watch for data in case it loads asynchronously
    const unwatch = watch(
      () => appParams.value,
      (params) => {
        if (params) {
          // Use opening_statement if configured
          if (params.opening_statement) {
            addMessage('assistant', params.opening_statement)

            // Store suggested questions if available
            if (params.suggested_questions && params.suggested_questions.length > 0) {
              eventBus.emit('mindmate:suggested_questions', {
                questions: params.suggested_questions,
              })
            }
          }
          // Stop watching once we have the data
          unwatch()
        }
      },
      { immediate: true }
    )
  }

  function startNewSession(sessionId: string): void {
    // Check if new session
    if (diagramSessionId.value !== sessionId) {
      stopGeneration()
      diagramSessionId.value = sessionId
      conversationId.value = null
      hasGreeted.value = false
      messages.value = []
      mindMateStore.clearActiveThread()
    }
  }

  function clearMessages(): void {
    messages.value = []
    streamingBuffer.value = ''
    currentStreamingId.value = null
    state.value = 'idle'
    applyLoadPhase(mindMateLoadPhaseOnComplete())
  }

  function resetConversation(): void {
    conversationId.value = null
    hasGreeted.value = false
    clearMessages()
  }

  // =========================================================================
  // Conversation History - Delegated to Store
  // =========================================================================

  /**
   * Fetch conversations from API (via Vue Query refetch)
   */
  async function fetchConversations(): Promise<void> {
    await queryClient.invalidateQueries({ queryKey: difyKeys.conversations() })
  }

  /**
   * Fetch messages for a conversation (shared by blocking load and background revalidate).
   */
  async function fetchDifyConversationMessages(convId: string): Promise<DifyHistoryMessage[]> {
    const difyUser = mindMateStore.getConversationDifyUser(convId)
    return queryClient.fetchQuery({
      queryKey: difyKeys.messages(convId, difyUser),
      queryFn: async () => {
        const query = difyUser
          ? `?limit=100&dify_user=${encodeURIComponent(difyUser)}`
          : '?limit=100'
        const response = await fetch(`/api/dify/conversations/${convId}/messages${query}`, {
          credentials: 'same-origin',
        })

        if (!response.ok) {
          if (response.status === 401) {
            authStore.handleTokenExpired('您的登录已过期，请重新登录后查看对话历史')
            throw new Error('Session expired')
          }
          throw new Error('Failed to fetch conversation messages')
        }

        const result = await response.json()
        const rows: DifyMessage[] = result.data || []
        return rows.sort((a, b) => a.created_at - b.created_at)
      },
    })
  }

  function applyMappedMessages(convId: string, mapped: MindMateMessage[]): void {
    isRestoringThread.value = true
    messages.value = mapped
    conversationId.value = convId
    hasGreeted.value = true
    isRestoringThread.value = false
    mindMateStore.setActiveThread(convId, mapped, true)
  }

  async function revalidateConversationInBackground(convId: string): Promise<void> {
    if (isGenerating.value) {
      return
    }

    try {
      const difyMessages = await fetchDifyConversationMessages(convId)
      const mapped = mapDifyMessagesToMindMate(difyMessages)

      if (conversationId.value !== convId) {
        return
      }
      if (threadsContentEqual(messages.value, mapped)) {
        return
      }

      applyMappedMessages(convId, mapped)
    } catch {
      // User already sees cached thread; ignore background failures.
    }
  }

  /**
   * Load a specific conversation's messages
   */
  async function loadConversation(convId: string): Promise<void> {
    stopGeneration()

    const cached = mindMateStore.getActiveThread(convId)
    if (cached) {
      isRestoringThread.value = true
      messages.value = structuredClone(cached.messages)
      conversationId.value = convId
      hasGreeted.value = cached.hasGreeted
      isRestoringThread.value = false
      mindMateStore.setCurrentConversation(convId)
      void revalidateConversationInBackground(convId)
      return
    }

    state.value = 'loading'
    isLoadingHistory.value = true
    isLoadingFromServer.value = true
    clearMessages()

    try {
      const difyMessages = await fetchDifyConversationMessages(convId)
      const mapped = mapDifyMessagesToMindMate(difyMessages)
      applyMappedMessages(convId, mapped)
      mindMateStore.setCurrentConversation(convId)
    } catch {
      onError?.('Failed to load conversation')
    } finally {
      isLoadingFromServer.value = false
      state.value = 'idle'
      applyLoadPhase(mindMateLoadPhaseOnComplete())
      isLoadingHistory.value = false
    }
  }

  /**
   * Delete a conversation (delegates to store)
   */
  async function deleteConversation(convId: string): Promise<boolean> {
    const result = await mindMateStore.deleteConversation(convId)

    // If deleted current conversation, reset local state
    // Welcome screen will show when no messages
    if (result && conversationId.value === convId) {
      resetConversation()
    }

    return result
  }

  /**
   * Start a new conversation (resets local state and notifies store)
   * Welcome screen will be shown instead of auto-greeting
   */
  function startNewConversation(): void {
    resetConversation()
    mindMateStore.startNewConversation()
    // Welcome screen shows automatically when no messages
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

  // Listen for panel open (welcome screen shows instead of auto-greeting)
  eventBus.onWithOwner(
    'panel:opened',
    (data) => {
      if (data.panel === 'mindmate') {
        // Welcome screen is now shown by default, no auto-greeting
        // User will see welcome screen until they send their first message
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

  // Listen for conversation changes from store (e.g., sidebar click)
  eventBus.onWithOwner(
    'mindmate:conversation_changed',
    (data) => {
      const newConvId = data.conversationId as string | null
      // Load the conversation if it's different from current
      // (store only emits when conversation actually changes)
      if (newConvId && newConvId !== conversationId.value) {
        loadConversation(newConvId)
      }
    },
    ownerId
  )

  // Listen for new conversation request from store (e.g., sidebar "New Chat")
  eventBus.onWithOwner(
    'mindmate:start_new_conversation',
    () => {
      resetConversation()
      // Welcome screen shows automatically when no messages
    },
    ownerId
  )

  // Listen for title updates from store (after Dify auto-generates title)
  eventBus.onWithOwner(
    'mindmate:title_updated',
    (data) => {
      if (data.title && onTitleChanged) {
        onTitleChanged(data.title as string, data.oldTitle as string | undefined)
      }
    },
    ownerId
  )

  // =========================================================================
  // Cleanup
  // =========================================================================

  function destroy(): void {
    stopGeneration()
    syncActiveThreadToStore()

    pendingFiles.value.forEach((f) => {
      if (f.preview_url) URL.revokeObjectURL(f.preview_url)
    })
    pendingFiles.value = []

    eventBus.removeAllListenersForOwner(ownerId)

    diagramSessionId.value = null
    streamingBuffer.value = ''
    currentStreamingId.value = null
    state.value = 'idle'
    applyLoadPhase(mindMateLoadPhaseOnComplete())
  }

  onUnmounted(() => {
    destroy()
  })

  function tryInitialConversationLoad(): void {
    if (restoreActiveThread()) {
      const convId = mindMateStore.currentConversationId
      if (convId) {
        void revalidateConversationInBackground(convId)
      }
      return
    }
    const convId = mindMateStore.currentConversationId
    if (convId && !hasMessages.value) {
      void loadConversation(convId)
    }
  }

  tryInitialConversationLoad()

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    state,
    loadPhase,
    messages,
    conversationId,
    diagramSessionId,
    hasGreeted,
    userId,
    currentLang,
    pendingFiles,
    isUploading,
    isLoadingHistory,

    // Conversation history state (proxied from store)
    conversations,
    conversationTitle,
    isLoadingConversations,
    messageCount,

    // Computed
    isStreaming,
    isLoading,
    isGenerating,
    hasMessages,
    lastMessage,

    // Actions
    sendMessage,
    sendGreeting,
    startNewSession,
    clearMessages,
    resetConversation,
    regenerateMessage,
    stopGeneration,
    submitFeedback,
    openPanel,
    closePanel,

    // Conversation history actions (delegated to store)
    fetchConversations,
    loadConversation,
    deleteConversation,
    startNewConversation,

    // File actions
    uploadFile,
    removeFile,
    clearPendingFiles,

    // Cleanup
    destroy,
  }
}

// ============================================================================
// Markdown Utilities (legacy; prefer `renderRichMarkdownHtml` in components)
// ============================================================================

/**
 * Tiny regex markdown approximator (unsafe for untrusted input as final HTML; not used by MindMate UI).
 * Message bubbles use `@/composables/core/useMarkdown` (`renderRichMarkdownHtml`).
 */
export function simpleMarkdown(text: string): string {
  return (
    text
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
  )
}
