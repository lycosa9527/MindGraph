/**
 * Dify Query Keys Factory
 *
 * Centralized query keys for Vue Query cache management.
 * Ensures consistent cache key structure across all Dify-related queries.
 */
export const difyKeys = {
  all: ['dify'] as const,
  appParams: () => [...difyKeys.all, 'appParams'] as const,
  conversations: () => [...difyKeys.all, 'conversations'] as const,
  pinned: () => [...difyKeys.all, 'pinned'] as const,
  messages: (convId: string) => [...difyKeys.all, 'messages', convId] as const,
}
