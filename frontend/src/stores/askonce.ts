/**
 * AskOnce Store - Pinia store for multi-LLM chat state
 *
 * Manages conversation history, system prompt, and token tracking
 * with localStorage persistence and 24-hour TTL.
 *
 * Chinese name: 多应
 * English name: AskOnce
 */
import { computed, ref, watch } from 'vue'

import { defineStore } from 'pinia'

import { useAuthStore } from './auth'

// ============================================================================
// Types
// ============================================================================

export interface AskOnceMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

// Persisted response with content and thinking
export interface PersistedResponse {
  content: string
  thinking: string
}

export interface AskOnceConversation {
  id: string
  name: string
  userMessages: string[] // Shared user messages
  modelResponses: Record<ModelId, PersistedResponse[]> // Per-model response history with thinking
  systemPrompt: string
  createdAt: number
  updatedAt: number
}

export interface ModelResponse {
  content: string
  thinking: string
  tokens: number
  status: 'idle' | 'streaming' | 'done' | 'error'
  error?: string
}

export type ModelId = 'qwen' | 'deepseek' | 'kimi'

interface LocalStorageData {
  currentConversationId: string | null
  conversations: AskOnceConversation[]
  sessionTokens: Record<ModelId, number>
  savedAt: number
}

// ============================================================================
// Constants
// ============================================================================

const STORAGE_KEY = 'askonce_session'
const TTL_MS = 7 * 24 * 60 * 60 * 1000 // 7 days for conversation history
const MAX_CONVERSATIONS = 50 // Maximum saved conversations

const MODEL_IDS: ModelId[] = ['qwen', 'deepseek', 'kimi']

function generateId(): string {
  return `askonce_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
}

// ============================================================================
// Store
// ============================================================================

export const useAskOnceStore = defineStore('askonce', () => {
  // =========================================================================
  // State
  // =========================================================================

  const conversations = ref<AskOnceConversation[]>([])
  const currentConversationId = ref<string | null>(null)
  const sessionTokens = ref<Record<ModelId, number>>({
    qwen: 0,
    deepseek: 0,
    kimi: 0,
  })

  // Current responses from each model
  const responses = ref<Record<ModelId, ModelResponse>>({
    qwen: { content: '', thinking: '', tokens: 0, status: 'idle' },
    deepseek: { content: '', thinking: '', tokens: 0, status: 'idle' },
    kimi: { content: '', thinking: '', tokens: 0, status: 'idle' },
  })

  // Abort controllers for cancelling streams
  const abortControllers = ref<Record<ModelId, AbortController | null>>({
    qwen: null,
    deepseek: null,
    kimi: null,
  })

  const isStreaming = ref(false)

  // =========================================================================
  // Computed
  // =========================================================================

  const currentConversation = computed(() => {
    if (!currentConversationId.value) return null
    return conversations.value.find((c) => c.id === currentConversationId.value) || null
  })

  // Get user messages from current conversation
  const userMessages = computed(() => currentConversation.value?.userMessages || [])

  // Build messages array for a specific model (interleaves user messages with model responses)
  function getMessagesForModel(modelId: ModelId): AskOnceMessage[] {
    const conv = currentConversation.value
    if (!conv) return []

    const messages: AskOnceMessage[] = []
    const userMsgs = conv.userMessages || []
    const modelResponses = conv.modelResponses?.[modelId] || []

    // Interleave user messages and model responses
    for (let i = 0; i < userMsgs.length; i++) {
      messages.push({ role: 'user', content: userMsgs[i] })
      if (i < modelResponses.length) {
        // Extract content from PersistedResponse (handle legacy string format)
        const response = modelResponses[i]
        const content = typeof response === 'string' ? response : response.content
        messages.push({ role: 'assistant', content })
      }
    }

    return messages
  }

  // Legacy computed for backward compatibility
  const conversationHistory = computed(() => {
    // Returns interleaved messages using first model (qwen) for display purposes
    return getMessagesForModel('qwen')
  })

  const systemPrompt = computed(() => currentConversation.value?.systemPrompt || '')

  const totalSessionTokens = computed(() => {
    return sessionTokens.value.qwen + sessionTokens.value.deepseek + sessionTokens.value.kimi
  })

  const hasConversation = computed(() => userMessages.value.length > 0)

  const hasSystemPrompt = computed(() => systemPrompt.value.trim().length > 0)

  // Sorted conversations for display (most recent first)
  const sortedConversations = computed(() => {
    return [...conversations.value].sort((a, b) => b.updatedAt - a.updatedAt)
  })

  // =========================================================================
  // LocalStorage Persistence
  // =========================================================================

  function saveToStorage(): void {
    try {
      const data: LocalStorageData = {
        currentConversationId: currentConversationId.value,
        conversations: conversations.value,
        sessionTokens: sessionTokens.value,
        savedAt: Date.now(),
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch (error) {
      console.warn('[AskOnceStore] Failed to save to localStorage:', error)
    }
  }

  // Migrate old conversation format to new format
  function migrateConversation(conv: AskOnceConversation): AskOnceConversation {
    // Check if this is old format (has 'messages' array instead of 'userMessages')
    const oldConv = conv as AskOnceConversation & { messages?: AskOnceMessage[] }

    if (oldConv.messages && !conv.userMessages) {
      // Migrate from oldest format (single messages array)
      const userMessages: string[] = []
      const modelResponses: Record<ModelId, PersistedResponse[]> = {
        qwen: [],
        deepseek: [],
        kimi: [],
      }

      // Extract user messages and use assistant messages as responses for all models
      for (const msg of oldConv.messages) {
        if (msg.role === 'user') {
          userMessages.push(msg.content)
        } else if (msg.role === 'assistant') {
          // Put old assistant messages in all models with empty thinking
          const response: PersistedResponse = { content: msg.content, thinking: '' }
          modelResponses.qwen.push(response)
          modelResponses.deepseek.push(response)
          modelResponses.kimi.push(response)
        }
      }

      return {
        id: conv.id,
        name: conv.name,
        userMessages,
        modelResponses,
        systemPrompt: conv.systemPrompt,
        createdAt: conv.createdAt,
        updatedAt: conv.updatedAt,
      }
    }

    // Ensure modelResponses exists
    if (!conv.modelResponses) {
      conv.modelResponses = { qwen: [], deepseek: [], kimi: [] }
    }
    if (!conv.userMessages) {
      conv.userMessages = []
    }

    // Migrate string[] to PersistedResponse[] if needed (intermediate format)
    MODEL_IDS.forEach((modelId) => {
      if (conv.modelResponses[modelId]) {
        conv.modelResponses[modelId] = conv.modelResponses[modelId].map((response) => {
          // If it's already a PersistedResponse object, keep it
          if (typeof response === 'object' && response !== null && 'content' in response) {
            return response as PersistedResponse
          }
          // If it's a string (old format), convert to PersistedResponse
          return { content: response as unknown as string, thinking: '' }
        })
      }
    })

    return conv
  }

  function loadFromStorage(): boolean {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return false

      const data: LocalStorageData = JSON.parse(raw)

      // Check TTL - remove old conversations
      const now = Date.now()
      const validConversations = (data.conversations || []).filter(
        (conv) => now - conv.updatedAt < TTL_MS
      )

      // Migrate and restore state
      conversations.value = validConversations
        .slice(0, MAX_CONVERSATIONS)
        .map((conv) => migrateConversation(conv))

      currentConversationId.value = data.currentConversationId
      sessionTokens.value = data.sessionTokens || { qwen: 0, deepseek: 0, kimi: 0 }

      // Verify current conversation still exists
      if (currentConversationId.value) {
        const exists = conversations.value.some((c) => c.id === currentConversationId.value)
        if (!exists) {
          currentConversationId.value = null
        }
      }

      console.debug(
        `[AskOnceStore] Loaded ${conversations.value.length} conversations from localStorage`
      )
      return true
    } catch (error) {
      console.warn('[AskOnceStore] Failed to load from localStorage:', error)
      localStorage.removeItem(STORAGE_KEY)
      return false
    }
  }

  function clearStorage(): void {
    localStorage.removeItem(STORAGE_KEY)
  }

  // Auto-save on changes
  watch(
    [conversations, currentConversationId, sessionTokens],
    () => {
      saveToStorage()
    },
    { deep: true }
  )

  // =========================================================================
  // Actions - Conversation Management
  // =========================================================================

  function createNewConversation(name?: string): string {
    const now = Date.now()
    const newConv: AskOnceConversation = {
      id: generateId(),
      name: name || '',
      userMessages: [],
      modelResponses: {
        qwen: [],
        deepseek: [],
        kimi: [],
      },
      systemPrompt: '',
      createdAt: now,
      updatedAt: now,
    }
    conversations.value.unshift(newConv)

    // Limit total conversations
    if (conversations.value.length > MAX_CONVERSATIONS) {
      conversations.value = conversations.value.slice(0, MAX_CONVERSATIONS)
    }

    currentConversationId.value = newConv.id
    return newConv.id
  }

  function startNewConversation(): void {
    abortAllStreams()
    resetAllResponses()
    createNewConversation()
  }

  function setCurrentConversation(convId: string): void {
    const conv = conversations.value.find((c) => c.id === convId)
    if (conv) {
      abortAllStreams()
      currentConversationId.value = convId
      // Load last responses from conversation history into the panels
      loadResponsesFromHistory(conv)
    }
  }

  // Load the last response from each model's history into the responses state
  function loadResponsesFromHistory(conv: AskOnceConversation): void {
    MODEL_IDS.forEach((modelId) => {
      const modelHistory = conv.modelResponses?.[modelId] || []
      if (modelHistory.length > 0) {
        // Load the last response from this model's history
        const lastResponse = modelHistory[modelHistory.length - 1]
        // Handle both new PersistedResponse format and legacy string format
        const content = typeof lastResponse === 'string' ? lastResponse : lastResponse.content
        const thinking = typeof lastResponse === 'string' ? '' : lastResponse.thinking || ''
        responses.value[modelId] = {
          content,
          thinking,
          tokens: 0, // Token count is not persisted per-response
          status: 'done',
        }
      } else {
        // No history for this model, reset to idle
        responses.value[modelId] = {
          content: '',
          thinking: '',
          tokens: 0,
          status: 'idle',
        }
      }
    })
  }

  function deleteConversation(convId: string): void {
    const index = conversations.value.findIndex((c) => c.id === convId)
    if (index !== -1) {
      conversations.value.splice(index, 1)
      // If deleted the current conversation, clear selection
      if (currentConversationId.value === convId) {
        currentConversationId.value = null
        resetAllResponses()
      }
    }
  }

  function renameConversation(convId: string, newName: string): void {
    const conv = conversations.value.find((c) => c.id === convId)
    if (conv) {
      conv.name = newName
      conv.updatedAt = Date.now()
    }
  }

  // =========================================================================
  // Actions - Messages
  // =========================================================================

  function setSystemPrompt(prompt: string): void {
    if (!currentConversationId.value) {
      createNewConversation()
    }
    const conv = conversations.value.find((c) => c.id === currentConversationId.value)
    if (conv) {
      conv.systemPrompt = prompt
      conv.updatedAt = Date.now()
    }
  }

  function addUserMessage(content: string): void {
    if (!currentConversationId.value) {
      createNewConversation()
    }
    const conv = conversations.value.find((c) => c.id === currentConversationId.value)
    if (conv) {
      // Initialize userMessages array if needed (for migrated conversations)
      if (!conv.userMessages) {
        conv.userMessages = []
      }
      conv.userMessages.push(content)
      conv.updatedAt = Date.now()
      // Auto-name conversation from first message if unnamed
      if (!conv.name && conv.userMessages.length === 1) {
        conv.name = content.slice(0, 50) + (content.length > 50 ? '...' : '')
      }
    }
  }

  function addAssistantMessage(modelId: ModelId, content: string, thinking: string = ''): void {
    const conv = conversations.value.find((c) => c.id === currentConversationId.value)
    if (conv) {
      // Initialize modelResponses object if needed (for migrated conversations)
      if (!conv.modelResponses) {
        conv.modelResponses = { qwen: [], deepseek: [], kimi: [] }
      }
      // Initialize model responses array if needed
      if (!conv.modelResponses[modelId]) {
        conv.modelResponses[modelId] = []
      }
      // Save both content and thinking
      conv.modelResponses[modelId].push({ content, thinking })
      conv.updatedAt = Date.now()
    }
  }

  // =========================================================================
  // Actions - Model Responses
  // =========================================================================

  function updateModelResponse(modelId: ModelId, update: Partial<ModelResponse>): void {
    responses.value[modelId] = { ...responses.value[modelId], ...update }
  }

  function appendContent(modelId: ModelId, content: string): void {
    responses.value[modelId].content += content
  }

  function appendThinking(modelId: ModelId, content: string): void {
    responses.value[modelId].thinking += content
  }

  function setTokens(modelId: ModelId, tokens: number): void {
    responses.value[modelId].tokens = tokens
    sessionTokens.value[modelId] += tokens
  }

  function resetResponse(modelId: ModelId): void {
    responses.value[modelId] = {
      content: '',
      thinking: '',
      tokens: 0,
      status: 'idle',
    }
  }

  function resetAllResponses(): void {
    MODEL_IDS.forEach((id) => resetResponse(id))
  }

  function setAbortController(modelId: ModelId, controller: AbortController | null): void {
    abortControllers.value[modelId] = controller
  }

  function abortStream(modelId: ModelId): void {
    const controller = abortControllers.value[modelId]
    if (controller) {
      controller.abort()
      abortControllers.value[modelId] = null
    }
  }

  function abortAllStreams(): void {
    MODEL_IDS.forEach((id) => abortStream(id))
    isStreaming.value = false
  }

  // =========================================================================
  // Actions - Clear/Reset
  // =========================================================================

  function clearConversation(): void {
    if (currentConversationId.value) {
      deleteConversation(currentConversationId.value)
    }
    resetAllResponses()
  }

  function clearAll(): void {
    conversations.value = []
    currentConversationId.value = null
    resetAllResponses()
    sessionTokens.value = { qwen: 0, deepseek: 0, kimi: 0 }
    clearStorage()
  }

  // =========================================================================
  // Auth Integration - Clear on logout
  // =========================================================================

  const authStore = useAuthStore()
  watch(
    () => authStore.isAuthenticated,
    (isAuth, wasAuth) => {
      // Clear when user logs out
      if (wasAuth && !isAuth) {
        console.debug('[AskOnceStore] User logged out, clearing session')
        clearAll()
      }
    }
  )

  // =========================================================================
  // Initialization
  // =========================================================================

  function initialize(): void {
    loadFromStorage()
    // If there's a current conversation, load its responses into the panels
    if (currentConversation.value) {
      loadResponsesFromHistory(currentConversation.value)
    }
  }

  // Initialize on store creation
  initialize()

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    conversations,
    currentConversationId,
    sessionTokens,
    responses,
    abortControllers,
    isStreaming,

    // Computed
    currentConversation,
    conversationHistory,
    userMessages,
    systemPrompt,
    sortedConversations,
    totalSessionTokens,
    hasConversation,
    hasSystemPrompt,

    // Functions
    getMessagesForModel,

    // Actions - Conversation Management
    createNewConversation,
    startNewConversation,
    setCurrentConversation,
    deleteConversation,
    renameConversation,

    // Actions - Messages
    setSystemPrompt,
    addUserMessage,
    addAssistantMessage,

    // Actions - Model Responses
    updateModelResponse,
    appendContent,
    appendThinking,
    setTokens,
    resetResponse,
    resetAllResponses,
    setAbortController,
    abortStream,
    abortAllStreams,

    // Actions - Clear/Reset
    clearConversation,
    clearAll,
    initialize,
  }
})
