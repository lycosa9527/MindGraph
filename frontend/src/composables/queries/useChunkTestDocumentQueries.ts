/**
 * Chunk Test Document Query Composables
 *
 * Vue Query composables for managing chunk test documents (separate from knowledge space).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { apiRequest, apiUpload } from '@/utils/apiClient'
import { ElMessage } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'

// ============================================================================
// Types
// ============================================================================

export interface ChunkTestDocument {
  id: number
  file_name: string
  file_type: string
  file_size: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  error_message?: string | null
  processing_progress?: string | null
  processing_progress_percent?: number
  created_at: string
  updated_at: string
}

export interface ChunkTestDocumentListResponse {
  documents: ChunkTestDocument[]
  total: number
}

export interface ProcessSelectedRequest {
  document_ids: number[]
}

// ============================================================================
// Query Keys
// ============================================================================

export const chunkTestDocumentKeys = {
  all: ['chunk-test-documents'] as const,
  lists: () => [...chunkTestDocumentKeys.all, 'list'] as const,
  list: () => [...chunkTestDocumentKeys.lists()] as const,
}

// ============================================================================
// Helper Functions
// ============================================================================

async function fetchChunkTestDocuments(): Promise<ChunkTestDocumentListResponse> {
  const response = await apiRequest('/api/knowledge-space/chunk-test/documents')

  if (!response.ok) {
    if (response.status === 404) {
      return { documents: [], total: 0 }
    }
    throw new Error('Failed to fetch documents')
  }

  return await response.json()
}

async function uploadChunkTestDocumentAPI(file: File): Promise<ChunkTestDocument> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiUpload('/api/knowledge-space/chunk-test/documents/upload', formData)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Upload failed')
  }

  return await response.json()
}

async function deleteChunkTestDocumentAPI(documentId: number): Promise<void> {
  const response = await apiRequest(`/api/knowledge-space/chunk-test/documents/${documentId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error('Delete failed')
  }
}

async function startProcessingChunkTestDocumentsAPI(): Promise<{ message: string; processed_count: number }> {
  const response = await apiRequest('/api/knowledge-space/chunk-test/documents/start-processing', {
    method: 'POST',
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Start processing failed')
  }

  return await response.json()
}

async function processSelectedChunkTestDocumentsAPI(documentIds: number[]): Promise<{ message: string; processed_count: number }> {
  const response = await apiRequest('/api/knowledge-space/chunk-test/documents/process-selected', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ document_ids: documentIds }),
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Process selected failed')
  }

  return await response.json()
}

// ============================================================================
// Query Composables
// ============================================================================

/**
 * Fetch all chunk test documents
 * Auto-refetches every 5 seconds if there are processing documents
 */
export function useChunkTestDocuments(options?: { 
  refetchInterval?: number | false | ((query: { state: { data: ChunkTestDocumentListResponse | undefined } }) => number | false) 
}) {
  return useQuery({
    queryKey: chunkTestDocumentKeys.list(),
    queryFn: fetchChunkTestDocuments,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: options?.refetchInterval ?? ((query) => {
      const data = query.state.data
      if (data?.documents.some((d: ChunkTestDocument) => d.status === 'processing' || d.status === 'pending')) {
        return 5000 // Refetch every 5 seconds
      }
      return false // Stop refetching when no processing documents
    }),
    retry: 1,
  })
}

// ============================================================================
// Mutation Composables
// ============================================================================

/**
 * Upload a chunk test document
 * Invalidates: documents list
 */
export function useUploadChunkTestDocument() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...chunkTestDocumentKeys.all, 'upload'],
    mutationFn: (file: File) => uploadChunkTestDocumentAPI(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chunkTestDocumentKeys.list() })
      ElMessage.success(isZh.value ? '文档上传成功' : 'Document uploaded successfully')
    },
    onError: (error: Error) => {
      console.error('Upload failed:', error)
      ElMessage.error(error.message || (isZh.value ? '文档上传失败' : 'Document upload failed'))
    },
  })
}

/**
 * Delete a chunk test document
 * Invalidates: documents list
 */
export function useDeleteChunkTestDocument() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...chunkTestDocumentKeys.all, 'delete'],
    mutationFn: (documentId: number) => deleteChunkTestDocumentAPI(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: chunkTestDocumentKeys.list() })
      ElMessage.success(isZh.value ? '文档已删除' : 'Document deleted')
    },
    onError: (error: Error) => {
      console.error('Delete failed:', error)
      ElMessage.error(error.message || (isZh.value ? '删除失败' : 'Delete failed'))
    },
  })
}

/**
 * Start processing all pending chunk test documents
 * Invalidates: documents list
 */
export function useStartProcessingChunkTestDocuments() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...chunkTestDocumentKeys.all, 'start-processing'],
    mutationFn: startProcessingChunkTestDocumentsAPI,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: chunkTestDocumentKeys.list() })
      if (data.processed_count === 0) {
        ElMessage.info(isZh.value ? '没有待处理的文档' : 'No documents to process')
      } else {
        ElMessage.success(
          isZh.value
            ? `已开始处理 ${data.processed_count} 个文档`
            : `Started processing ${data.processed_count} documents`
        )
      }
    },
    onError: (error: Error) => {
      console.error('Start processing failed:', error)
      ElMessage.error(error.message || (isZh.value ? '启动处理失败' : 'Failed to start processing'))
    },
  })
}

/**
 * Process selected chunk test documents by IDs
 * Invalidates: documents list
 */
export function useProcessSelectedChunkTestDocuments() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...chunkTestDocumentKeys.all, 'process-selected'],
    mutationFn: (documentIds: number[]) => processSelectedChunkTestDocumentsAPI(documentIds),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: chunkTestDocumentKeys.list() })
      if (data.processed_count === 0) {
        ElMessage.info(isZh.value ? '没有待处理的文档' : 'No documents to process')
      } else {
        ElMessage.success(
          isZh.value
            ? `已开始处理 ${data.processed_count} 个文档`
            : `Started processing ${data.processed_count} documents`
        )
      }
    },
    onError: (error: Error) => {
      console.error('Process selected failed:', error)
      ElMessage.error(error.message || (isZh.value ? '启动处理失败' : 'Failed to start processing'))
    },
  })
}
