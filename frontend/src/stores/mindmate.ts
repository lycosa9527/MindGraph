/**
 * MindMate Store - Pinia store for shared MindMate conversation state
 *
 * Conversation list, title, and LLM load phase (avatar ring) live here.
 * Message handling and SSE streaming remain in the useMindMate composable.
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import { eventBus } from '@/composables/core/useEventBus'
import type { ModelLoadPhase } from '@/stores/llmResults'
import {
  cloneMindMateMessages,
  type ActiveThreadSnapshot,
  type MindMateMessage,
} from '@/stores/mindmateActiveThread'
import { isLlmGenerating } from '@/utils/llmLoadPhase'

// ============================================================================
// Types
// ============================================================================

export interface MindMateConversation {
  id: string
  name: string
  created_at: number
  updated_at: number
  is_pinned?: boolean
  channel?: 'web' | 'mindbot'
  dify_user?: string
}

// Cached message structure (raw Dify format)
export interface CachedDifyMessage {
  id: string
  query: string
  answer: string
  created_at: number
}

// localStorage cache entry with TTL
interface CacheEntry {
  messages: CachedDifyMessage[]
  cachedAt: number // Unix timestamp in milliseconds
}

// Cache TTL: 1 hour
const CACHE_TTL_MS = 60 * 60 * 1000

// ============================================================================
// Store
// ============================================================================

export const useMindMateStore = defineStore('mindmate', () => {
  // =========================================================================
  // State
  // =========================================================================

  const conversations = ref<MindMateConversation[]>([])
  const pinnedConversationIds = ref<Set<string>>(new Set())
  const currentConversationId = ref<string | null>(null)
  const conversationTitle = ref<string>('MindMate')
  const isLoadingConversations = ref(false)
  const messageCount = ref(0)

  /** Avatar / status ring phase (sending → waiting → streaming → idle). */
  const loadPhase = ref<ModelLoadPhase>('idle')

  // Message cache for prefetched conversations (convId -> messages).
  // Legacy prefetch path; navigation restore uses activeThread* below.
  const messageCache = ref<Map<string, CachedDifyMessage[]>>(new Map())
  const prefetchingConversations = ref<Set<string>>(new Set())

  /** In-memory active conversation thread (survives route unmount). */
  const activeThreadConversationId = ref<string | null>(null)
  const activeThreadMessages = ref<MindMateMessage[]>([])
  const activeThreadHasGreeted = ref(false)
  const activeThreadUpdatedAt = ref(0)

  // =========================================================================
  // Computed
  // =========================================================================

  const hasConversations = computed(() => conversations.value.length > 0)

  const currentConversation = computed(() => {
    if (!currentConversationId.value) return null
    return conversations.value.find((c) => c.id === currentConversationId.value) || null
  })

  const isGenerating = computed(() => isLlmGenerating(loadPhase.value))

  // =========================================================================
  // Load phase (LLM avatar ring)
  // =========================================================================

  function setLoadPhase(phase: ModelLoadPhase): void {
    loadPhase.value = phase
    eventBus.emit('mindmate:load_phase', { phase })
  }

  function resetLoadPhase(): void {
    setLoadPhase('idle')
  }

  // =========================================================================
  // Helpers
  // =========================================================================

  /**
   * sessionStorage key for message cache (cleared when browser session ends)
   */
  function getCacheKey(convId: string): string {
    return `mindmate_msg_cache_${convId}`
  }

  function purgeLegacyMindmateLocalStorage(): void {
    try {
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('mindmate_msg_cache_')) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach((key) => localStorage.removeItem(key))
    } catch {
      void 0
    }
  }

  purgeLegacyMindmateLocalStorage()

  /**
   * Save messages to sessionStorage with timestamp for TTL
   */
  function _saveMessagesToStorage(convId: string, messages: CachedDifyMessage[]): void {
    try {
      const key = getCacheKey(convId)
      const entry: CacheEntry = {
        messages,
        cachedAt: Date.now(),
      }
      sessionStorage.setItem(key, JSON.stringify(entry))
    } catch {
      // sessionStorage might be full or disabled - continue without error
    }
  }

  /**
   * Load messages from sessionStorage (with TTL check)
   */
  function loadMessagesFromStorage(convId: string): CachedDifyMessage[] | null {
    try {
      const key = getCacheKey(convId)
      const stored = sessionStorage.getItem(key)
      if (!stored) return null

      const parsed = JSON.parse(stored)

      // Handle legacy format (direct array) vs new format (CacheEntry)
      if (Array.isArray(parsed)) {
        // Legacy format without TTL - treat as valid but migrate on next save
        return parsed as CachedDifyMessage[]
      }

      const entry = parsed as CacheEntry

      // Check TTL - if cache is stale, remove it and return null
      if (Date.now() - entry.cachedAt > CACHE_TTL_MS) {
        sessionStorage.removeItem(key)
        return null
      }

      return entry.messages
    } catch {
      return null
    }
  }

  /**
   * Clear messages from sessionStorage
   */
  function clearMessagesFromStorage(convId: string): void {
    try {
      const key = getCacheKey(convId)
      sessionStorage.removeItem(key)
    } catch {
      void 0
    }
  }

  /**
   * Clear all message caches from sessionStorage
   */
  function clearAllMessagesFromStorage(): void {
    try {
      const keysToRemove: string[] = []
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i)
        if (key && key.startsWith('mindmate_msg_cache_')) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach((key) => sessionStorage.removeItem(key))
    } catch {
      void 0
    }
  }

  /**
   * Prune old sessionStorage entries that are not in top 3 conversations
   */
  function _pruneOldCacheEntries(): void {
    try {
      const top3Ids = new Set(conversations.value.slice(0, 3).map((c) => c.id))
      const keysToRemove: string[] = []

      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i)
        if (key && key.startsWith('mindmate_msg_cache_')) {
          const convId = key.replace('mindmate_msg_cache_', '')
          if (!top3Ids.has(convId)) {
            keysToRemove.push(key)
          }
        }
      }

      keysToRemove.forEach((key) => sessionStorage.removeItem(key))
    } catch {
      void 0
    }
  }

  // =========================================================================
  // Actions
  // =========================================================================

  /**
   * Sync conversations from Vue Query data
   * Called by components that use useConversations() query
   */
  function syncConversationsFromQuery(convs: MindMateConversation[], pinnedIds: Set<string>): void {
    pinnedConversationIds.value = pinnedIds
    conversations.value = convs.map((conv) => ({
      ...conv,
      is_pinned: pinnedIds.has(conv.id),
    }))
    sortConversations()
  }

  /**
   * Resolve Dify user key for a conversation (web or bound DingTalk MindBot).
   */
  function getConversationDifyUser(convId: string): string | undefined {
    const conv = conversations.value.find((item) => item.id === convId)
    return conv?.dify_user?.trim() || undefined
  }

  /**
   * Sort conversations: pinned first, then by updated_at descending
   */
  function sortConversations(): void {
    conversations.value.sort((a, b) => {
      // Pinned items first
      if (a.is_pinned && !b.is_pinned) return -1
      if (!a.is_pinned && b.is_pinned) return 1
      // Then by updated_at (most recent first)
      return b.updated_at - a.updated_at
    })
  }

  /**
   * Toggle pin status for a conversation
   * Thin wrapper - actual mutation handled by Vue Query
   * This function is kept for backward compatibility but should use usePinConversation() mutation
   */
  async function pinConversation(_convId: string): Promise<boolean> {
    // This is now a no-op - mutations handle the API call
    // Components should use usePinConversation() mutation directly
    return false
  }

  /**
   * Get cached messages for a conversation (returns null if not cached)
   * Checks memory cache first, then localStorage
   */
  function getCachedMessages(convId: string): CachedDifyMessage[] | null {
    // Check memory cache first
    const memoryCache = messageCache.value.get(convId)
    if (memoryCache) {
      return memoryCache
    }

    // Check localStorage if not in memory
    const storageCache = loadMessagesFromStorage(convId)
    if (storageCache) {
      // Load into memory cache for faster subsequent access
      messageCache.value.set(convId, storageCache)
      return storageCache
    }

    return null
  }

  /**
   * Clear message cache for a conversation (e.g., after new message)
   */
  function clearMessageCache(convId: string): void {
    messageCache.value.delete(convId)
    clearMessagesFromStorage(convId)
  }

  function setActiveThread(convId: string, messages: MindMateMessage[], hasGreeted: boolean): void {
    activeThreadConversationId.value = convId
    activeThreadMessages.value = cloneMindMateMessages(messages)
    activeThreadHasGreeted.value = hasGreeted
    activeThreadUpdatedAt.value = Date.now()
  }

  function clearActiveThread(): void {
    activeThreadConversationId.value = null
    activeThreadMessages.value = []
    activeThreadHasGreeted.value = false
    activeThreadUpdatedAt.value = 0
  }

  function getActiveThread(convId: string): ActiveThreadSnapshot | null {
    if (activeThreadConversationId.value !== convId) {
      return null
    }
    if (activeThreadMessages.value.length === 0) {
      return null
    }
    return {
      conversationId: convId,
      messages: cloneMindMateMessages(activeThreadMessages.value),
      hasGreeted: activeThreadHasGreeted.value,
      updatedAt: activeThreadUpdatedAt.value,
    }
  }

  /**
   * Set the current conversation (when loading from history)
   */
  function setCurrentConversation(convId: string | null, title?: string): void {
    const hasChanged = currentConversationId.value !== convId
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

    // Only emit event if conversation actually changed
    if (hasChanged) {
      eventBus.emit('mindmate:conversation_changed', {
        conversationId: convId,
        title: conversationTitle.value,
      })
    }
  }

  /**
   * Delete a conversation
   * Thin wrapper - actual mutation handled by Vue Query
   * This function handles local state cleanup after deletion
   */
  async function deleteConversation(convId: string): Promise<boolean> {
    // Remove from local list (optimistic update)
    conversations.value = conversations.value.filter((c) => c.id !== convId)

    // Remove from pinned set if it was pinned
    pinnedConversationIds.value.delete(convId)

    // Clear cached messages for this conversation (memory and localStorage)
    messageCache.value.delete(convId)
    clearMessagesFromStorage(convId)

    // If deleted current conversation, emit event to start new one
    if (currentConversationId.value === convId) {
      currentConversationId.value = null
      conversationTitle.value = 'MindMate'
      messageCount.value = 0
      clearActiveThread()
      eventBus.emit('mindmate:start_new_conversation', {})
    }

    // Actual API call should be handled by useDeleteConversation() mutation
    return true
  }

  /**
   * Rename a conversation
   * Thin wrapper - actual mutation handled by Vue Query
   * This function handles local state updates
   */
  async function renameConversation(convId: string, newName: string): Promise<boolean> {
    // Update in local list (optimistic update)
    const conv = conversations.value.find((c) => c.id === convId)
    if (conv) {
      conv.name = newName
    }

    // Update title if this is the current conversation
    if (currentConversationId.value === convId) {
      conversationTitle.value = newName
    }

    // Actual API call should be handled by useRenameConversation() mutation
    return true
  }

  /**
   * Start a new conversation (reset current state)
   */
  function startNewConversation(): void {
    currentConversationId.value = null
    conversationTitle.value = 'MindMate'
    messageCount.value = 0
    clearActiveThread()
    eventBus.emit('mindmate:start_new_conversation', {})
  }

  /**
   * Update conversation title (after Dify generates it)
   */
  function updateConversationTitle(title: string): void {
    const oldTitle = conversationTitle.value // Capture BEFORE updating
    conversationTitle.value = title

    // Update in conversations list if exists
    if (currentConversationId.value) {
      const conv = conversations.value.find((c) => c.id === currentConversationId.value)
      if (conv) {
        conv.name = title
        conv.updated_at = Math.floor(Date.now() / 1000) // Use seconds like Dify
      }
    }

    // Emit event for components that need to react to title changes
    eventBus.emit('mindmate:title_updated', {
      conversationId: currentConversationId.value,
      title,
      oldTitle, // Pass old title for animation
    })
  }

  /**
   * Increment message count and set initial title from first message
   */
  function trackMessage(userMessage: string, files?: { name: string }[]): void {
    messageCount.value++

    // First message: use truncated message as immediate title
    if (messageCount.value === 1) {
      if (userMessage.trim()) {
        const truncated = userMessage.trim().substring(0, 30)
        conversationTitle.value = truncated + (userMessage.length > 30 ? '...' : '')
      } else if (files && files.length > 0) {
        // File-only message: use first file name as title
        const fileName = files[0].name
        const truncated = fileName.length > 25 ? fileName.substring(0, 25) + '...' : fileName
        conversationTitle.value = truncated
      }
    }
  }

  /**
   * Fetch Dify's auto-generated title
   * Thin wrapper - actual mutation handled by Vue Query
   * This function handles local state updates after title generation
   */
  async function fetchDifyTitle(): Promise<void> {
    if (!currentConversationId.value) return

    // Actual API call should be handled by useGenerateTitle() mutation
    // This function is kept for backward compatibility
    // The mutation's onSuccess will trigger cache invalidation
  }

  /**
   * Add a new conversation to the list (after first message creates it)
   * Used for optimistic updates when SSE creates a new conversation
   */
  function addConversation(conv: MindMateConversation): void {
    // Add to beginning of list (optimistic update)
    conversations.value.unshift(conv)
    sortConversations()
  }

  /**
   * Reset store state
   */
  function reset(): void {
    conversations.value = []
    pinnedConversationIds.value.clear()
    currentConversationId.value = null
    conversationTitle.value = 'MindMate'
    isLoadingConversations.value = false
    messageCount.value = 0
    resetLoadPhase()
    messageCache.value.clear()
    prefetchingConversations.value.clear()
    clearAllMessagesFromStorage()
    clearActiveThread()
  }

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    conversations,
    pinnedConversationIds,
    currentConversationId,
    conversationTitle,
    isLoadingConversations,
    messageCount,
    activeThreadConversationId,
    activeThreadMessages,
    activeThreadHasGreeted,
    activeThreadUpdatedAt,

    // LLM load phase (avatar ring)
    loadPhase,
    isGenerating,

    // Computed
    hasConversations,
    currentConversation,

    // Actions
    setLoadPhase,
    resetLoadPhase,
    syncConversationsFromQuery,
    setCurrentConversation,
    deleteConversation,
    renameConversation,
    pinConversation,
    startNewConversation,
    updateConversationTitle,
    trackMessage,
    fetchDifyTitle,
    addConversation,
    reset,

    // Message cache actions
    getCachedMessages,
    clearMessageCache,
    getConversationDifyUser,
    setActiveThread,
    clearActiveThread,
    getActiveThread,
  }
})

export type { MindMateMessage, MindMateFile, FeedbackRating } from '@/stores/mindmateActiveThread'
