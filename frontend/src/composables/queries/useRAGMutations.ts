/**
 * RAG Mutation Composables
 *
 * Vue Query mutations for RAG operations with automatic cache invalidation.
 */
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'
import { apiPost } from '@/utils/apiClient'
import { ragKeys } from './ragKeys'

// ============================================================================
// Types
// ============================================================================

export interface RetrievalResult {
  chunk_id: number
  text: string
  score: number
  document_id: number
  document_name: string
  chunk_index: number
}

export interface RetrievalTestRequest {
  query: string
  method: 'hybrid' | 'semantic' | 'keyword'
  top_k: number
  score_threshold: number
}

export interface RetrievalTestResponse {
  query: string
  method: string
  results: RetrievalResult[]
  timing: {
    total_ms: number
    embedding_ms: number
    search_ms: number
    rerank_ms: number
  }
  stats: {
    total_chunks_searched: number
    chunks_before_rerank: number
    chunks_after_rerank: number
    chunks_filtered_by_threshold: number
  }
}

// ============================================================================
// Helper Functions
// ============================================================================

async function retrievalTestAPI(params: RetrievalTestRequest): Promise<RetrievalTestResponse> {
  const response = await apiPost('/api/knowledge-space/retrieval-test', params)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Retrieval test failed')
  }

  return await response.json()
}

// ============================================================================
// Mutation Composables
// ============================================================================

/**
 * Test retrieval functionality
 * Invalidates: retrieval test history
 */
export function useRetrievalTest() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: ragKeys.retrievalTest(),
    mutationFn: (params: RetrievalTestRequest) => retrievalTestAPI(params),
    onSuccess: () => {
      // Invalidate retrieval test history to refresh the list
      queryClient.invalidateQueries({ queryKey: ragKeys.retrievalTestHistory() })
      ElMessage.success(isZh.value ? '检索测试完成' : 'Retrieval test completed')
    },
    onError: (error: Error) => {
      console.error('Retrieval test failed:', error)
      ElMessage.error(error.message || (isZh.value ? '检索测试失败' : 'Retrieval test failed'))
    },
  })
}
