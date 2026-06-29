/**
 * RAG Query Composables
 *
 * Vue Query composables for fetching RAG-related data with automatic caching.
 */
import { useQuery } from '@tanstack/vue-query'

import { apiRequest, apiRequestJson } from '@/utils/apiClient'

import { ragKeys } from './ragKeys'

// ============================================================================
// Types
// ============================================================================

export type RetrievalMethod = 'hybrid' | 'semantic' | 'keyword'

export interface RAGSettings {
  default_method: RetrievalMethod
  top_k: number
  score_threshold: number
  chunk_size: number
  chunk_overlap: number
  vector_weight: number
  keyword_weight: number
  reranking_mode: string
  wiki_compile_enabled: boolean
  chunking_engine: string
  has_user_overrides: boolean
}

export type RAGSettingsUpdatePayload = Pick<
  RAGSettings,
  'default_method' | 'top_k' | 'score_threshold' | 'chunk_size' | 'chunk_overlap'
>

export interface RAGSettingsUpdateResponse {
  settings: RAGSettings
  reindex_required: boolean
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
  return apiRequestJson<RAGSettings>('/api/knowledge-space/settings')
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
    staleTime: 5 * 60 * 1000,
    retry: 1,
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
    staleTime: 10 * 60 * 1000,
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
    staleTime: 5 * 60 * 1000,
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
    staleTime: 60 * 1000,
  })
}
