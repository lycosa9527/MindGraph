/**
 * MindMate Store - Pinia store for shared MindMate conversation state
 *
 * This store manages conversation list and current conversation state
 * that is shared between ChatHistory sidebar and MindmatePanel.
 *
 * Message handling and SSE streaming remain in the useMindMate composable.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/useEventBus'

// ============================================================================
// Types
// ============================================================================

export interface MindMateConversation {
  id: string
  name: string
  created_at: number
  updated_at: number
}

// ============================================================================
// Store
// ============================================================================

export const useMindMateStore = defineStore('mindmate', () => {
  // =========================================================================
  // State
  // =========================================================================

  const conversations = ref<MindMateConversation[]>([])
  const currentConversationId = ref<string | null>(null)
  const conversationTitle = ref<string>('MindMate')
  const isLoadingConversations = ref(false)
  const messageCount = ref(0)

  // =========================================================================
  // Computed
  // =========================================================================

  const hasConversations = computed(() => conversations.value.length > 0)

  const currentConversation = computed(() => {
    if (!currentConversationId.value) return null
    return conversations.value.find((c) => c.id === currentConversationId.value) || null
  })

  // =========================================================================
  // Helpers
  // =========================================================================

  function getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('access_token')
    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    return headers
  }

  // =========================================================================
  // Actions
  // =========================================================================

  /**
   * Fetch all conversations from the API
   */
  async function fetchConversations(): Promise<void> {
    if (isLoadingConversations.value) return

    isLoadingConversations.value = true

    try {
      const response = await fetch('/api/dify/conversations?limit=50', {
        headers: getAuthHeaders(),
      })

      if (response.ok) {
        const result = await response.json()
        conversations.value = result.data || []
      }
    } catch (error) {
      console.debug('[MindMateStore] Failed to fetch conversations:', error)
    } finally {
      isLoadingConversations.value = false
    }
  }

  /**
   * Set the current conversation (when loading from history)
   */
  function setCurrentConversation(convId: string | null, title?: string): void {
    currentConversationId.value = convId

    if (convId && title) {
      conversationTitle.value = title
    } else if (convId) {
      const conv = conversations.value.find((c) => c.id === convId)
      if (conv?.name) {
        conversationTitle.value = conv.name
      }
    } else {
      conversationTitle.value = 'MindMate'
    }

    // Emit event for other components to react
    eventBus.emit('mindmate:conversation_changed', {
      conversationId: convId,
      title: conversationTitle.value,
    })
  }

  /**
   * Delete a conversation
   */
  async function deleteConversation(convId: string): Promise<boolean> {
    try {
      const response = await fetch(`/api/dify/conversations/${convId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      })

      if (response.ok) {
        // Remove from local list
        conversations.value = conversations.value.filter((c) => c.id !== convId)

        // If deleted current conversation, emit event to start new one
        if (currentConversationId.value === convId) {
          currentConversationId.value = null
          conversationTitle.value = 'MindMate'
          messageCount.value = 0
          eventBus.emit('mindmate:start_new_conversation', {})
        }

        return true
      }
    } catch (error) {
      console.debug('[MindMateStore] Failed to delete conversation:', error)
    }

    return false
  }

  /**
   * Rename a conversation
   */
  async function renameConversation(convId: string, newName: string): Promise<boolean> {
    try {
      const response = await fetch(`/api/dify/conversations/${convId}/name`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, auto_generate: false }),
      })

      if (response.ok) {
        // Update in local list
        const conv = conversations.value.find((c) => c.id === convId)
        if (conv) {
          conv.name = newName
        }

        // Update title if this is the current conversation
        if (currentConversationId.value === convId) {
          conversationTitle.value = newName
        }

        return true
      }
    } catch (error) {
      console.debug('[MindMateStore] Failed to rename conversation:', error)
    }

    return false
  }

  /**
   * Start a new conversation (reset current state)
   */
  function startNewConversation(): void {
    currentConversationId.value = null
    conversationTitle.value = 'MindMate'
    messageCount.value = 0
    eventBus.emit('mindmate:start_new_conversation', {})
  }

  /**
   * Update conversation title (after Dify generates it)
   */
  function updateConversationTitle(title: string): void {
    conversationTitle.value = title

    // Update in conversations list if exists
    if (currentConversationId.value) {
      const conv = conversations.value.find((c) => c.id === currentConversationId.value)
      if (conv) {
        conv.name = title
      }
    }
  }

  /**
   * Increment message count and set initial title from first message
   */
  function trackMessage(userMessage: string): void {
    messageCount.value++

    // First message: use truncated message as immediate title
    if (messageCount.value === 1 && userMessage.trim()) {
      const truncated = userMessage.trim().substring(0, 30)
      conversationTitle.value = truncated + (userMessage.length > 30 ? '...' : '')
    }
  }

  /**
   * Fetch Dify's auto-generated title
   */
  async function fetchDifyTitle(): Promise<void> {
    if (!currentConversationId.value) return

    try {
      const response = await fetch(`/api/dify/conversations/${currentConversationId.value}/name`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_generate: true }),
      })

      if (response.ok) {
        const result = await response.json()
        const newTitle = result.data?.name || result.data?.title
        if (newTitle && newTitle !== conversationTitle.value) {
          updateConversationTitle(newTitle)
        }
      }
    } catch (error) {
      console.debug('[MindMateStore] Failed to fetch Dify title:', error)
    }
  }

  /**
   * Add a new conversation to the list (after first message creates it)
   */
  function addConversation(conv: MindMateConversation): void {
    // Add to beginning of list
    conversations.value.unshift(conv)
  }

  /**
   * Reset store state
   */
  function reset(): void {
    conversations.value = []
    currentConversationId.value = null
    conversationTitle.value = 'MindMate'
    isLoadingConversations.value = false
    messageCount.value = 0
  }

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    conversations,
    currentConversationId,
    conversationTitle,
    isLoadingConversations,
    messageCount,

    // Computed
    hasConversations,
    currentConversation,

    // Actions
    fetchConversations,
    setCurrentConversation,
    deleteConversation,
    renameConversation,
    startNewConversation,
    updateConversationTitle,
    trackMessage,
    fetchDifyTitle,
    addConversation,
    reset,
  }
})
