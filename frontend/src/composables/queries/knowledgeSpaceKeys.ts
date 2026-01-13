/**
 * Knowledge Space Query Keys Factory
 *
 * Centralized query keys for Vue Query cache management.
 * Ensures consistent cache key structure across all knowledge space queries.
 */
export const knowledgeSpaceKeys = {
  all: ['knowledge-space'] as const,
  documents: () => [...knowledgeSpaceKeys.all, 'documents'] as const,
  document: (id: number) => [...knowledgeSpaceKeys.all, 'document', id] as const,
  documentStatus: (id: number) => [...knowledgeSpaceKeys.all, 'document-status', id] as const,
}
