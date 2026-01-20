/**
 * Chunk Test Query Composables
 * 
 * Vue Query composables for chunk test functionality
 */
import { computed, type ComputedRef, type Ref, unref } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { apiRequest } from '@/utils/apiClient'

export interface Benchmark {
  name: string
  description: string
  source: string
  version?: string
  updated_at?: string
}

export interface BenchmarksResponse {
  benchmarks: Benchmark[]
}

export interface ChunkTestProgress {
  test_id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  current_method?: string | null
  current_stage?: string | null
  progress_percent: number
  completed_methods?: string[]
}

export interface ChunkTestResult {
  test_id: number
  dataset_name: string
  document_ids?: number[]
  chunking_comparison: Record<string, any>
  retrieval_comparison: Record<string, any>
  summary: Record<string, any>
  evaluation_results?: Record<string, any>
  status?: string
  current_method?: string | null
  current_stage?: string | null
  progress_percent?: number
  completed_methods?: string[]
  created_at: string
}

export interface ChunkTestHistoryItem {
  test_id: number
  dataset_name: string
  document_ids?: number[]
  semchunk_chunk_count?: number
  mindchunk_chunk_count?: number
  status: string
  summary: Record<string, any>
  created_at: string
}

export interface ChunkTestHistoryResponse {
  results: ChunkTestHistoryItem[]
  total: number
}

export interface TestUserDocumentsRequest {
  document_ids: number[]
  queries: string[]
  modes?: string[]
}

export interface TestBenchmarkRequest {
  dataset_name: string
  queries?: string[]
  modes?: string[]
}

/**
 * Fetch available benchmark datasets
 */
export function useBenchmarks() {
  return useQuery<BenchmarksResponse>({
    queryKey: ['chunk-test', 'benchmarks'],
    queryFn: async () => {
      const response = await apiRequest('/api/knowledge-space/chunk-test/benchmarks')
      if (!response.ok) {
        throw new Error('Failed to fetch benchmarks')
      }
      return response.json()
    },
  })
}

/**
 * Update benchmark datasets mutation
 */
export function useUpdateDatasets() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async () => {
      const response = await apiRequest('/api/knowledge-space/chunk-test/update-datasets', {
        method: 'POST',
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to update datasets' }))
        throw new Error(error.detail || 'Failed to update datasets')
      }
      return response.json()
    },
    onSuccess: () => {
      // Invalidate benchmarks query to refetch after update
      queryClient.invalidateQueries({ queryKey: ['chunk-test', 'benchmarks'] })
    },
  })
}

/**
 * Test chunking methods with user's uploaded documents
 */
export function useTestUserDocuments() {
  return useMutation<ChunkTestResult, Error, TestUserDocumentsRequest>({
    mutationFn: async (request: TestUserDocumentsRequest) => {
      const response = await apiRequest('/api/knowledge-space/chunk-test/user-documents', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          document_ids: request.document_ids,
          queries: request.queries,
          modes: request.modes,
        }),
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to test user documents' }))
        throw new Error(error.detail || 'Failed to test user documents')
      }
      return response.json()
    },
  })
}

/**
 * Test chunking methods with a benchmark dataset
 */
export function useTestBenchmarkDataset() {
  return useMutation<ChunkTestResult, Error, TestBenchmarkRequest>({
    mutationFn: async (request: TestBenchmarkRequest) => {
      const response = await apiRequest('/api/knowledge-space/chunk-test/benchmark', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          dataset_name: request.dataset_name,
          queries: request.queries,
          modes: request.modes,
        }),
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to test benchmark dataset' }))
        throw new Error(error.detail || 'Failed to test benchmark dataset')
      }
      return response.json()
    },
  })
}

/**
 * Test chunking methods with a benchmark dataset (async background execution)
 */
export function useTestBenchmarkDatasetAsync() {
  return useMutation<ChunkTestResult, Error, TestBenchmarkRequest>({
    mutationFn: async (request: TestBenchmarkRequest) => {
      const response = await apiRequest('/api/knowledge-space/chunk-test/benchmark-async', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          dataset_name: request.dataset_name,
          queries: request.queries,
          modes: request.modes,
        }),
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to start benchmark test' }))
        throw new Error(error.detail || 'Failed to start benchmark test')
      }
      return response.json()
    },
  })
}

/**
 * Get test queries for a dataset
 */
export function useTestQueries(datasetName?: string, count: number = 20) {
  return useQuery<string[]>({
    queryKey: ['chunk-test', 'test-queries', datasetName, count],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (datasetName) {
        params.append('dataset_name', datasetName)
      }
      params.append('count', count.toString())
      const response = await apiRequest(`/api/knowledge-space/chunk-test/test-queries?${params.toString()}`)
      if (!response.ok) {
        throw new Error('Failed to fetch test queries')
      }
      const data = await response.json()
      return data.queries || []
    },
    enabled: true,
  })
}

/**
 * Get chunk test progress by test ID (with polling)
 */
export function useChunkTestProgress(testId: number) {
  return useQuery<ChunkTestProgress>({
    queryKey: ['chunk-test', 'progress', testId],
    queryFn: async () => {
      const response = await apiRequest(`/api/knowledge-space/chunk-test/progress/${testId}`)
      if (!response.ok) {
        throw new Error('Failed to fetch test progress')
      }
      return response.json()
    },
    refetchInterval: (query) => {
      const data = query.state.data
      // Poll every 2 seconds if test is pending or processing
      if (data?.status === 'pending' || data?.status === 'processing') {
        return 2000
      }
      // Stop polling if completed or failed
      return false
    },
    enabled: !!testId,
  })
}

/**
 * Get complete chunk test result by test ID
 */
export function useChunkTestResult(testId: number) {
  return useQuery<ChunkTestResult>({
    queryKey: ['chunk-test', 'result', testId],
    queryFn: async () => {
      const response = await apiRequest(`/api/knowledge-space/chunk-test/results/${testId}`)
      if (!response.ok) {
        throw new Error('Failed to fetch test result')
      }
      return response.json()
    },
    enabled: !!testId,
  })
}

/**
 * Get chunk test history (recent tests)
 */
export function useChunkTestHistory(limit: number = 20) {
  return useQuery<ChunkTestHistoryResponse>({
    queryKey: ['chunk-test', 'history', limit],
    queryFn: async () => {
      const params = new URLSearchParams()
      params.append('limit', limit.toString())
      const response = await apiRequest(`/api/knowledge-space/chunk-test/results?${params.toString()}`)
      if (!response.ok) {
        throw new Error('Failed to fetch chunk test history')
      }
      return response.json()
    },
  })
}

export interface ChunkTestChunk {
  chunk_index: number
  text: string
  metadata?: Record<string, any>
  start_char?: number
  end_char?: number
}

export interface ChunkTestChunksResponse {
  chunks: ChunkTestChunk[]
  method: string
  test_id: number
}

export interface ManualEvaluationRequest {
  query: string
  method: string
  chunk_ids?: number[]
  answer?: string
  model?: string
}

export interface ManualEvaluationResult {
  test_id: number
  method: string
  query: string
  chunk_count: number
  results: Array<{
    type: string
    evaluation?: Record<string, any>
    evaluations?: Array<{
      chunk_index: number
      evaluation: Record<string, any>
    }>
  }>
}

/**
 * Get chunks for a test and method (on-demand generation)
 */
export function useChunkTestChunks(testId: Ref<number> | ComputedRef<number>, method: Ref<string> | ComputedRef<string>) {
  return useQuery<ChunkTestChunksResponse>({
    queryKey: computed(() => ['chunk-test', 'chunks', unref(testId), unref(method)]),
    queryFn: async () => {
      const id = unref(testId)
      const m = unref(method)
      if (!id || !m) {
        throw new Error('Test ID and method are required')
      }
      const response = await apiRequest(`/api/knowledge-space/chunk-test/${id}/chunks/${m}`)
      if (!response.ok) {
        throw new Error('Failed to fetch chunks')
      }
      return response.json()
    },
    enabled: computed(() => !!unref(testId) && !!unref(method)),
  })
}

/**
 * Manual evaluation mutation using DashScope models
 */
export function useManualEvaluation() {
  return useMutation<ManualEvaluationResult, Error, { testId: number; request: ManualEvaluationRequest }>({
    mutationFn: async ({ testId, request }) => {
      const response = await apiRequest(`/api/knowledge-space/chunk-test/${testId}/evaluate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to evaluate chunks' }))
        throw new Error(error.detail || 'Failed to evaluate chunks')
      }
      return response.json()
    },
  })
}

/**
 * Delete chunk test result mutation
 */
export function useDeleteChunkTest() {
  const queryClient = useQueryClient()
  
  return useMutation<void, Error, number>({
    mutationFn: async (testId: number) => {
      const response = await apiRequest(`/api/knowledge-space/chunk-test/results/${testId}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to delete test' }))
        throw new Error(error.detail || 'Failed to delete test')
      }
    },
    onSuccess: () => {
      // Invalidate history query to refetch after deletion
      queryClient.invalidateQueries({ queryKey: ['chunk-test', 'history'] })
    },
  })
}

/**
 * Cancel chunk test mutation
 */
export function useCancelChunkTest() {
  const queryClient = useQueryClient()
  
  return useMutation<{ success: boolean; message: string }, Error, number>({
    mutationFn: async (testId: number) => {
      const response = await apiRequest(`/api/knowledge-space/chunk-test/${testId}/cancel`, {
        method: 'POST',
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to cancel test' }))
        throw new Error(error.detail || 'Failed to cancel test')
      }
      return response.json()
    },
    onSuccess: (_, testId) => {
      // Invalidate progress and result queries to refetch updated status
      queryClient.invalidateQueries({ queryKey: ['chunk-test', 'progress', testId] })
      queryClient.invalidateQueries({ queryKey: ['chunk-test', 'result', testId] })
      queryClient.invalidateQueries({ queryKey: ['chunk-test', 'history'] })
    },
  })
}
