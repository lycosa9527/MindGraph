/**
 * Dify Query Composables
 *
 * Vue Query composables for fetching Dify API data with automatic caching.
 */
import { useQuery } from '@tanstack/vue-query'

import { useAuthStore } from '@/stores'

import { difyKeys } from './difyKeys'

// ============================================================================
// Types
// ============================================================================

export interface DifyAppParameters {
  opening_statement?: string
  suggested_questions?: string[]
}

export interface DifyConversation {
  id: string
  name: string
  created_at: number
  updated_at: number
}

export interface DifyMessage {
  id: string
  query: string
  answer: string
  created_at: number
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Handle 401 response by triggering session expired modal
 */
function handle401Response(authStore: ReturnType<typeof useAuthStore>, message?: string): void {
  authStore.handleTokenExpired(message || '您的登录已过期，请重新登录')
}

async function fetchAppParameters(): Promise<DifyAppParameters> {
  // Use credentials (token in httpOnly cookie)
  const response = await fetch('/api/dify/app/parameters', {
    credentials: 'same-origin',
  })

  if (!response.ok) {
    if (response.status === 401) {
      const authStore = useAuthStore()
      handle401Response(authStore)
    }
    throw new Error('Failed to fetch app parameters')
  }

  return await response.json()
}

async function fetchConversations(): Promise<DifyConversation[]> {
  const response = await fetch('/api/dify/conversations?limit=50', {
    credentials: 'same-origin',
  })

  if (!response.ok) {
    if (response.status === 401) {
      const authStore = useAuthStore()
      handle401Response(authStore)
    }
    throw new Error('Failed to fetch conversations')
  }

  const result = await response.json()
  return result.data || []
}

async function fetchPinnedConversations(): Promise<Set<string>> {
  const response = await fetch('/api/dify/pinned', {
    credentials: 'same-origin',
  })

  if (!response.ok) {
    if (response.status === 401) {
      const authStore = useAuthStore()
      handle401Response(authStore)
    }
    throw new Error('Failed to fetch pinned conversations')
  }

  const result = await response.json()
  return new Set(result.data || [])
}

async function fetchConversationMessages(convId: string): Promise<DifyMessage[]> {
  const response = await fetch(`/api/dify/conversations/${convId}/messages?limit=100`, {
    credentials: 'same-origin',
  })

  if (!response.ok) {
    if (response.status === 401) {
      const authStore = useAuthStore()
      handle401Response(authStore)
    }
    throw new Error('Failed to fetch conversation messages')
  }

  const result = await response.json()
  const messages = result.data || []

  // Sort by created_at ascending (chronological order)
  return messages.sort((a: DifyMessage, b: DifyMessage) => a.created_at - b.created_at)
}

// ============================================================================
// Query Composables
// ============================================================================

/**
 * Fetch Dify app parameters (opening statement, suggested questions)
 * Stale time: 30 minutes (rarely changes)
 */
export function useAppParameters() {
  const authStore = useAuthStore()

  return useQuery({
    queryKey: difyKeys.appParams(),
    queryFn: fetchAppParameters,
    staleTime: 30 * 60 * 1000, // 30 minutes
    enabled: !!authStore.user, // Use user presence, not token (token is in httpOnly cookie)
  })
}

/**
 * Fetch user's conversations list
 * Stale time: 1 minute (changes more often)
 */
export function useConversations() {
  const authStore = useAuthStore()

  return useQuery({
    queryKey: difyKeys.conversations(),
    queryFn: fetchConversations,
    staleTime: 60 * 1000, // 1 minute
    enabled: !!authStore.user,
  })
}

/**
 * Fetch pinned conversation IDs
 * Stale time: 2 minutes
 */
export function usePinnedConversations() {
  const authStore = useAuthStore()

  return useQuery({
    queryKey: difyKeys.pinned(),
    queryFn: fetchPinnedConversations,
    staleTime: 2 * 60 * 1000, // 2 minutes
    enabled: !!authStore.user,
  })
}

/**
 * Fetch messages for a specific conversation
 * Stale time: 5 minutes
 */
export function useConversationMessages(convId: string | null) {
  const authStore = useAuthStore()

  return useQuery({
    queryKey: difyKeys.messages(convId || ''),
    queryFn: () => fetchConversationMessages(convId!),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: !!authStore.user && !!convId,
  })
}
