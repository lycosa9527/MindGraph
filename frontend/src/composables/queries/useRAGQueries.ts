/**
 * RAG Query Composables
 *
 * Vue Query composables for fetching RAG-related data with automatic caching.
 */
import { useQuery } from '@tanstack/vue-query'
import { apiRequest } from '@/utils/apiClient'
import { ragKeys } from './ragKeys'

// ============================================================================
// Types
// ============================================================================

export interface RAGSettings {
  default_method: 'hybrid' | 'semantic' | 'keyword'
  vector_weight: number
  keyword_weight: number
  reranking_mode: 'reranking_model' | 'weighted_score' | 'none'
  rerank_threshold: number
  chunk_size: number
  chunk_overlap: number
}

export interface QueryAnalytics {
  common_queries: Array<{
    query: string
    count: number
    average_score: number
  }>
  low_performing_queries: Array<{
    query: string
    count: number
    average_score: number
  }>
  average_scores: Record<string, number>
  suggestions: string[]
}

export interface CompressionMetrics {
  compression_enabled: boolean
  compression_type: string | null
  points_count: number
  vector_size: number
  estimated_uncompressed_size: number
  estimated_compressed_size: number
  compression_ratio: number
  storage_savings_percent: number
  error: string | null
}

export interface RetrievalTestHistoryItem {
  id: number
  query: string
  method: string
  top_k: number
  score_threshold: number
  result_count: number
  timing: {
    embedding_ms: number | null
    search_ms: number | null
    rerank_ms: number | null
    total_ms: number | null
  }
  created_at: string
}

export interface RetrievalTestHistoryResponse {
  queries: RetrievalTestHistoryItem[]
  total: number
}

// ============================================================================
// Helper Functions
// ============================================================================

async function fetchRAGSettings(): Promise<RAGSettings> {
  // Note: This endpoint may not exist yet, but we're preparing for it
  // For now, return default settings
  const response = await apiRequest('/api/knowledge-space/settings')

  if (!response.ok) {
    // Return default settings if endpoint doesn't exist
    if (response.status === 404) {
      return {
        default_method: 'hybrid',
        vector_weight: 0.5,
        keyword_weight: 0.5,
        reranking_mode: 'reranking_model',
        rerank_threshold: 0.5,
        chunk_size: 512,
        chunk_overlap: 50,
      }
    }
    throw new Error('Failed to fetch RAG settings')
  }

  return await response.json()
}

async function fetchQueryAnalytics(days: number = 30): Promise<QueryAnalytics> {
  const response = await apiRequest(`/api/knowledge-space/queries/analytics?days=${days}`)

  if (!response.ok) {
    throw new Error('Failed to fetch query analytics')
  }

  return await response.json()
}

async function fetchCompressionMetrics(): Promise<CompressionMetrics> {
  const response = await apiRequest('/api/knowledge-space/metrics/compression')

  if (!response.ok) {
    throw new Error('Failed to fetch compression metrics')
  }

  return await response.json()
}

async function fetchRetrievalTestHistory(): Promise<RetrievalTestHistoryResponse> {
  const response = await apiRequest('/api/knowledge-space/queries/retrieval-test-history')

  if (!response.ok) {
    throw new Error('Failed to fetch retrieval test history')
  }

  return await response.json()
}

// ============================================================================
// Query Composables
// ============================================================================

/**
 * Fetch RAG settings
 * Stale time: 5 minutes (settings don't change often)
 */
export function useRAGSettings() {
  return useQuery({
    queryKey: ragKeys.settings(),
    queryFn: fetchRAGSettings,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1, // Only retry once for 404 (endpoint may not exist)
  })
}

/**
 * Fetch query analytics
 * Stale time: 10 minutes (analytics don't change frequently)
 */
export function useQueryAnalytics(days: number = 30) {
  return useQuery({
    queryKey: ragKeys.queryAnalytics(days),
    queryFn: () => fetchQueryAnalytics(days),
    staleTime: 10 * 60 * 1000, // 10 minutes
    enabled: days > 0,
  })
}

/**
 * Fetch compression metrics
 * Stale time: 5 minutes
 */
export function useCompressionMetrics() {
  return useQuery({
    queryKey: ragKeys.compressionMetrics(),
    queryFn: fetchCompressionMetrics,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Fetch retrieval test history (most recent 10 queries)
 * Stale time: 1 minute (history changes when new tests are run)
 */
export function useRetrievalTestHistory() {
  return useQuery({
    queryKey: ragKeys.retrievalTestHistory(),
    queryFn: fetchRetrievalTestHistory,
    staleTime: 60 * 1000, // 1 minute
  })
}
