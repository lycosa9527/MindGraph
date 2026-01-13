/**
 * Knowledge Space Mutation Composables
 *
 * Vue Query mutations for knowledge space operations with automatic cache invalidation.
 */
import { useMutation, useQueryClient } from '@tanstack/vue-query'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'
import { apiUpload, apiRequest, apiDelete } from '@/utils/apiClient'
import { knowledgeSpaceKeys } from './knowledgeSpaceKeys'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

// ============================================================================
// Types
// ============================================================================

export interface StartProcessingResponse {
  processed_count: number
}

export interface ProcessSelectedRequest {
  document_ids: number[]
}

// ============================================================================
// Helper Functions
// ============================================================================

async function uploadDocumentAPI(file: File): Promise<KnowledgeDocument> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiUpload('/api/knowledge-space/documents/upload', formData)

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Upload failed')
  }

  return await response.json()
}

async function deleteDocumentAPI(documentId: number): Promise<void> {
  const response = await apiRequest(`/api/knowledge-space/documents/${documentId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error('Delete failed')
  }
}

async function startProcessingAPI(): Promise<StartProcessingResponse> {
  const response = await apiRequest('/api/knowledge-space/documents/start-processing', {
    method: 'POST',
  })

  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Start processing failed')
  }

  return await response.json()
}

async function processSelectedAPI(documentIds: number[]): Promise<StartProcessingResponse> {
  const response = await apiRequest('/api/knowledge-space/documents/process-selected', {
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
// Mutation Composables
// ============================================================================

/**
 * Upload a document
 * Invalidates: documents list
 * Optimistic update: Adds document to list immediately
 */
export function useUploadDocument() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...knowledgeSpaceKeys.all, 'upload'],
    mutationFn: (file: File) => uploadDocumentAPI(file),
    onMutate: async (file) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: knowledgeSpaceKeys.documents() })

      // Snapshot previous value
      const previousData = queryClient.getQueryData<{ documents: KnowledgeDocument[]; total: number }>(
        knowledgeSpaceKeys.documents()
      )

      // Optimistically update
      if (previousData) {
        const optimisticDocument: KnowledgeDocument = {
          id: Date.now(), // Temporary ID
          file_name: file.name,
          file_type: file.type || 'unknown',
          file_size: file.size,
          status: 'pending',
          chunk_count: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }

        queryClient.setQueryData(knowledgeSpaceKeys.documents(), {
          ...previousData,
          documents: [optimisticDocument, ...previousData.documents],
          total: previousData.total + 1,
        })
      }

      return { previousData }
    },
    onSuccess: (data) => {
      // Invalidate to refetch with real data
      queryClient.invalidateQueries({ queryKey: knowledgeSpaceKeys.documents() })
      ElMessage.success(isZh.value ? '文档上传成功，正在处理中...' : 'Document uploaded successfully, processing...')
    },
    onError: (error: Error, _file, context) => {
      // Rollback optimistic update
      if (context?.previousData) {
        queryClient.setQueryData(knowledgeSpaceKeys.documents(), context.previousData)
      }
      console.error('Upload failed:', error)
      ElMessage.error(error.message || (isZh.value ? '文档上传失败' : 'Document upload failed'))
    },
  })
}

/**
 * Delete a document
 * Invalidates: documents list
 * Optimistic update: Removes document from list immediately
 */
export function useDeleteDocument() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...knowledgeSpaceKeys.all, 'delete'],
    mutationFn: (documentId: number) => deleteDocumentAPI(documentId),
    onMutate: async (documentId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: knowledgeSpaceKeys.documents() })

      // Snapshot previous value
      const previousData = queryClient.getQueryData<{ documents: KnowledgeDocument[]; total: number }>(
        knowledgeSpaceKeys.documents()
      )

      // Optimistically update
      if (previousData) {
        queryClient.setQueryData(knowledgeSpaceKeys.documents(), {
          ...previousData,
          documents: previousData.documents.filter((d) => d.id !== documentId),
          total: previousData.total - 1,
        })
      }

      return { previousData }
    },
    onSuccess: () => {
      // Invalidate to ensure consistency
      queryClient.invalidateQueries({ queryKey: knowledgeSpaceKeys.documents() })
      ElMessage.success(isZh.value ? '文档已删除' : 'Document deleted')
    },
    onError: (error: Error, _documentId, context) => {
      // Rollback optimistic update
      if (context?.previousData) {
        queryClient.setQueryData(knowledgeSpaceKeys.documents(), context.previousData)
      }
      console.error('Delete failed:', error)
      ElMessage.error(error.message || (isZh.value ? '删除失败' : 'Delete failed'))
    },
  })
}

/**
 * Start processing documents
 * Invalidates: documents list
 */
export function useStartProcessing() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...knowledgeSpaceKeys.all, 'start-processing'],
    mutationFn: startProcessingAPI,
    onSuccess: (data) => {
      // Invalidate documents to refresh status
      queryClient.invalidateQueries({ queryKey: knowledgeSpaceKeys.documents() })
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
 * Process selected documents by IDs
 * Invalidates: documents list
 */
export function useProcessSelected() {
  const queryClient = useQueryClient()
  const { isZh } = useLanguage()

  return useMutation({
    mutationKey: [...knowledgeSpaceKeys.all, 'process-selected'],
    mutationFn: (documentIds: number[]) => processSelectedAPI(documentIds),
    onSuccess: (data) => {
      // Invalidate documents to refresh status
      queryClient.invalidateQueries({ queryKey: knowledgeSpaceKeys.documents() })
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

/**
 * Delete document with confirmation dialog
 * Wrapper around useDeleteDocument that shows confirmation first
 */
export function useDeleteDocumentWithConfirmation() {
  const deleteMutation = useDeleteDocument()
  const { isZh } = useLanguage()

  const deleteWithConfirmation = async (documentId: number) => {
    try {
      await ElMessageBox.confirm(
        isZh.value ? '确定要删除这个文档吗？删除后无法恢复。' : 'Are you sure you want to delete this document? This action cannot be undone.',
        isZh.value ? '确认删除' : 'Confirm Delete',
        {
          confirmButtonText: isZh.value ? '删除' : 'Delete',
          cancelButtonText: isZh.value ? '取消' : 'Cancel',
          type: 'warning',
        }
      )
      deleteMutation.mutate(documentId)
    } catch (error) {
      // User cancelled - do nothing
      if (error !== 'cancel') {
        throw error
      }
    }
  }

  return {
    ...deleteMutation,
    mutate: deleteWithConfirmation,
  }
}
