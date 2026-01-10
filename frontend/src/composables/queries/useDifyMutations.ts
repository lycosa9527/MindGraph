/**
 * Dify Mutation Composables
 *
 * Vue Query mutations for modifying Dify data with automatic cache invalidation.
 */
import { useMutation, useQueryClient } from '@tanstack/vue-query'

import { useAuthStore } from '@/stores'

import { difyKeys } from './difyKeys'

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Handle 401 response by triggering session expired modal
 */
function handle401Response(): void {
  const authStore = useAuthStore()
  authStore.handleTokenExpired('您的登录已过期，请重新登录')
}

async function pinConversationAPI(convId: string): Promise<{ is_pinned: boolean }> {
  // Use credentials (token in httpOnly cookie)
  const response = await fetch(`/api/dify/conversations/${convId}/pin`, {
    method: 'POST',
    credentials: 'same-origin',
  })

  if (!response.ok) {
    if (response.status === 401) {
      handle401Response()
    }
    throw new Error('Failed to pin/unpin conversation')
  }

  return await response.json()
}

async function deleteConversationAPI(convId: string): Promise<void> {
  const response = await fetch(`/api/dify/conversations/${convId}`, {
    method: 'DELETE',
    credentials: 'same-origin',
  })

  if (!response.ok) {
    if (response.status === 401) {
      handle401Response()
    }
    throw new Error('Failed to delete conversation')
  }
}

async function renameConversationAPI(convId: string, name: string): Promise<{ name: string }> {
  const response = await fetch(`/api/dify/conversations/${convId}/name`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, auto_generate: false }),
  })

  if (!response.ok) {
    if (response.status === 401) {
      handle401Response()
    }
    throw new Error('Failed to rename conversation')
  }

  const result = await response.json()
  return result.data || { name }
}

async function generateTitleAPI(convId: string): Promise<{ name: string }> {
  const response = await fetch(`/api/dify/conversations/${convId}/name`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ auto_generate: true }),
  })

  if (!response.ok) {
    if (response.status === 401) {
      handle401Response()
    }
    throw new Error('Failed to generate conversation title')
  }

  const result = await response.json()
  return result.data || { name: '' }
}

// ============================================================================
// Mutation Composables
// ============================================================================

/**
 * Pin or unpin a conversation
 * Invalidates: conversations, pinned
 */
export function usePinConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (convId: string) => pinConversationAPI(convId),
    onSuccess: () => {
      // Invalidate both conversations and pinned lists
      queryClient.invalidateQueries({ queryKey: difyKeys.conversations() })
      queryClient.invalidateQueries({ queryKey: difyKeys.pinned() })
    },
  })
}

/**
 * Delete a conversation
 * Invalidates: conversations, messages[convId]
 */
export function useDeleteConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (convId: string) => deleteConversationAPI(convId),
    onSuccess: (_, convId) => {
      // Invalidate conversations list
      queryClient.invalidateQueries({ queryKey: difyKeys.conversations() })
      // Remove messages cache for this conversation
      queryClient.removeQueries({ queryKey: difyKeys.messages(convId) })
    },
  })
}

/**
 * Rename a conversation (manual rename)
 * Invalidates: conversations
 */
export function useRenameConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ convId, name }: { convId: string; name: string }) =>
      renameConversationAPI(convId, name),
    onSuccess: () => {
      // Invalidate conversations list to get updated name
      queryClient.invalidateQueries({ queryKey: difyKeys.conversations() })
    },
  })
}

/**
 * Generate conversation title using Dify's LLM
 * Called after 1-second delay (to allow Dify to process messages)
 * Invalidates: conversations
 */
export function useGenerateTitle() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (convId: string) => generateTitleAPI(convId),
    onSuccess: () => {
      // Invalidate conversations list to get generated title
      queryClient.invalidateQueries({ queryKey: difyKeys.conversations() })
    },
  })
}
