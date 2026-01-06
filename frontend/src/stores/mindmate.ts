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
  const currentConversationId = ref<string | null>(null)
  const conversationTitle = ref<string>('MindMate')
  const isLoadingConversations = ref(false)
  const messageCount = ref(0)

  // Message cache for prefetched conversations (convId -> messages)
  const messageCache = ref<Map<string, CachedDifyMessage[]>>(new Map())
  const prefetchingConversations = ref<Set<string>>(new Set())

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

  /**
   * localStorage key for message cache
   */
  function getCacheKey(convId: string): string {
    return `mindmate_msg_cache_${convId}`
  }

  /**
   * Save messages to localStorage with timestamp for TTL
   */
  function saveMessagesToStorage(convId: string, messages: CachedDifyMessage[]): void {
    try {
      const key = getCacheKey(convId)
      const entry: CacheEntry = {
        messages,
        cachedAt: Date.now(),
      }
      localStorage.setItem(key, JSON.stringify(entry))
      console.debug(`[MindMateStore] Saved ${messages.length} messages to localStorage for ${convId}`)
    } catch (error) {
      console.debug(`[MindMateStore] Failed to save messages to localStorage:`, error)
      // localStorage might be full or disabled - continue without error
    }
  }

  /**
   * Load messages from localStorage (with TTL check)
   */
  function loadMessagesFromStorage(convId: string): CachedDifyMessage[] | null {
    try {
      const key = getCacheKey(convId)
      const stored = localStorage.getItem(key)
      if (!stored) return null

      const parsed = JSON.parse(stored)

      // Handle legacy format (direct array) vs new format (CacheEntry)
      if (Array.isArray(parsed)) {
        // Legacy format without TTL - treat as valid but migrate on next save
        console.debug(`[MindMateStore] Loaded ${parsed.length} messages from localStorage (legacy format) for ${convId}`)
        return parsed as CachedDifyMessage[]
      }

      const entry = parsed as CacheEntry

      // Check TTL - if cache is stale, remove it and return null
      if (Date.now() - entry.cachedAt > CACHE_TTL_MS) {
        console.debug(`[MindMateStore] Cache expired for ${convId} (age: ${Math.round((Date.now() - entry.cachedAt) / 60000)}min)`)
        localStorage.removeItem(key)
        return null
      }

      console.debug(`[MindMateStore] Loaded ${entry.messages.length} messages from localStorage for ${convId}`)
      return entry.messages
    } catch (error) {
      console.debug(`[MindMateStore] Failed to load messages from localStorage:`, error)
      return null
    }
  }

  /**
   * Clear messages from localStorage
   */
  function clearMessagesFromStorage(convId: string): void {
    try {
      const key = getCacheKey(convId)
      localStorage.removeItem(key)
      console.debug(`[MindMateStore] Cleared localStorage cache for ${convId}`)
    } catch (error) {
      console.debug(`[MindMateStore] Failed to clear localStorage cache:`, error)
    }
  }

  /**
   * Clear all message caches from localStorage
   */
  function clearAllMessagesFromStorage(): void {
    try {
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('mindmate_msg_cache_')) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach((key) => localStorage.removeItem(key))
      console.debug(`[MindMateStore] Cleared ${keysToRemove.length} cached conversations from localStorage`)
    } catch (error) {
      console.debug(`[MindMateStore] Failed to clear all localStorage cache:`, error)
    }
  }

  /**
   * Prune old localStorage entries that are not in top 3 conversations
   * Keeps localStorage clean and within size limits
   */
  function pruneOldCacheEntries(): void {
    try {
      const top3Ids = new Set(conversations.value.slice(0, 3).map((c) => c.id))
      const keysToRemove: string[] = []

      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('mindmate_msg_cache_')) {
          const convId = key.replace('mindmate_msg_cache_', '')
          if (!top3Ids.has(convId)) {
            keysToRemove.push(key)
          }
        }
      }

      keysToRemove.forEach((key) => localStorage.removeItem(key))
      if (keysToRemove.length > 0) {
        console.debug(`[MindMateStore] Pruned ${keysToRemove.length} old cache entries from localStorage`)
      }
    } catch (error) {
      console.debug(`[MindMateStore] Failed to prune old cache entries:`, error)
    }
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

    // Prefetch messages for the 3 most recent conversations
    prefetchRecentConversations(3)

    // Clean up old cache entries that are no longer in top 3
    pruneOldCacheEntries()
  }

  /**
   * Prefetch messages for the N most recent conversations
   * Loads from localStorage first if available, otherwise fetches from API
   */
  async function prefetchRecentConversations(count: number = 3): Promise<void> {
    const recentConvs = conversations.value.slice(0, count)

    for (const conv of recentConvs) {
      // Skip if already in memory cache or currently prefetching
      if (messageCache.value.has(conv.id) || prefetchingConversations.value.has(conv.id)) {
        continue
      }

      // Check localStorage first
      const storageCache = loadMessagesFromStorage(conv.id)
      if (storageCache) {
        // Load into memory cache for faster access
        messageCache.value.set(conv.id, storageCache)
        console.debug(`[MindMateStore] Loaded ${storageCache.length} messages from localStorage for ${conv.id}`)
        continue
      }

      // Not in localStorage - fetch from API in background (don't await)
      prefetchConversationMessages(conv.id)
    }
  }

  /**
   * Re-prefetch a conversation if it's in the top 3 (after cache was cleared)
   */
  function rePrefetchIfInTop3(convId: string): void {
    const top3Ids = conversations.value.slice(0, 3).map((c) => c.id)
    if (top3Ids.includes(convId)) {
      // Conversation is in top 3, prefetch in background
      prefetchConversationMessages(convId)
    }
  }

  /**
   * Prefetch messages for a specific conversation (background)
   */
  async function prefetchConversationMessages(convId: string): Promise<void> {
    // Mark as prefetching to avoid duplicate requests
    prefetchingConversations.value.add(convId)

    try {
      const response = await fetch(`/api/dify/conversations/${convId}/messages?limit=100`, {
        headers: getAuthHeaders(),
      })

      if (response.ok) {
        const result = await response.json()
        const difyMessages = result.data || []

        // Sort by created_at and cache
        const sortedMessages = [...difyMessages].sort(
          (a: CachedDifyMessage, b: CachedDifyMessage) => a.created_at - b.created_at
        )
        messageCache.value.set(convId, sortedMessages)

        // Save to localStorage for persistence across page refreshes
        saveMessagesToStorage(convId, sortedMessages)

        console.debug(`[MindMateStore] Prefetched ${sortedMessages.length} messages for conversation ${convId}`)
      }
    } catch (error) {
      console.debug(`[MindMateStore] Failed to prefetch conversation ${convId}:`, error)
    } finally {
      prefetchingConversations.value.delete(convId)
    }
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

        // Clear cached messages for this conversation (memory and localStorage)
        messageCache.value.delete(convId)
        clearMessagesFromStorage(convId)

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

    // New conversation is now #1, so top 3 might have changed
    // Re-prefetch top 3 to ensure cache is up to date
    // (New conversation doesn't need prefetch - it only has 1 message already in memory)
    prefetchRecentConversations(3)
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
    messageCache.value.clear()
    prefetchingConversations.value.clear()
    clearAllMessagesFromStorage()
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

    // Message cache actions
    getCachedMessages,
    clearMessageCache,
    prefetchRecentConversations,
    rePrefetchIfInTop3,
  }
})
