/**
 * RAG Query Keys Factory
 *
 * Centralized query keys for Vue Query cache management.
 * Ensures consistent cache key structure across all RAG-related queries.
 */
export const ragKeys = {
  all: ['rag'] as const,
  retrievalTest: () => [...ragKeys.all, 'retrieval-test'] as const,
  retrievalTestHistory: () => [...ragKeys.all, 'retrieval-test-history'] as const,
  settings: () => [...ragKeys.all, 'settings'] as const,
  queryAnalytics: (days?: number) => [...ragKeys.all, 'query-analytics', days] as const,
  compressionMetrics: () => [...ragKeys.all, 'compression-metrics'] as const,
}
