/**
 * Chunk Test Query Composables
 * 
 * Vue Query composables for chunk test functionality
 */
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
