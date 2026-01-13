/**
 * Knowledge Space Composable
 * 
 * Provides access to knowledge space store and Vue Query composables.
 * This is the main entry point for knowledge space functionality.
 * 
 * Uses Vue Query for server state (API calls) and Pinia for UI state.
 */
import { computed } from 'vue'
import { useKnowledgeSpaceStore } from '@/stores/knowledgeSpace'
import { useDocuments, type DocumentListResponse } from '@/composables/queries/useKnowledgeSpaceQueries'
import { useUploadDocument, useDeleteDocumentWithConfirmation, useStartProcessing, useProcessSelected } from '@/composables/queries/useKnowledgeSpaceMutations'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

export function useKnowledgeSpace() {
  const store = useKnowledgeSpaceStore()

  // Vue Query composables for server state
  const documentsQuery = useDocuments({
    // Enable auto-refetch every 5 seconds if there are processing documents
    refetchInterval: (query: { state: { data: DocumentListResponse | undefined } }): number | false => {
      const data = query.state.data
      if (data?.documents.some((d: KnowledgeDocument) => d.status === 'processing' || d.status === 'pending')) {
        return 5000 // Refetch every 5 seconds
      }
      return false // Stop refetching when no processing documents
    },
  })

  const uploadMutation = useUploadDocument()
  const deleteMutation = useDeleteDocumentWithConfirmation()
  const startProcessingMutation = useStartProcessing()
  const processSelectedMutation = useProcessSelected()

  // Computed properties that use Vue Query data
  const documents = computed(() => documentsQuery.data.value?.documents || [])
  const loading = computed(() => documentsQuery.isLoading.value)
  const uploading = computed(() => uploadMutation.isPending.value)

  // Computed properties
  const documentCount = computed(() => documents.value.length)
  const completedCount = computed(() => 
    documents.value.filter((d: KnowledgeDocument) => d.status === 'completed').length
  )
  const canUpload = computed(() => documentCount.value < 5)
  
  const processingDocuments = computed(() => 
    documents.value.filter((d: KnowledgeDocument) => d.status === 'processing' || d.status === 'pending')
  )

  const pendingCount = computed(() => 
    documents.value.filter((d: KnowledgeDocument) => d.status === 'pending' || d.status === 'failed').length
  )

  // Wrapper functions for backward compatibility
  async function fetchDocuments() {
    await documentsQuery.refetch()
  }

  async function uploadDocument(file: File) {
    if (!canUpload.value) {
      return // Error message handled in mutation
    }
    uploadMutation.mutate(file)
  }

  async function deleteDocument(documentId: number) {
    await deleteMutation.mutate(documentId)
  }

  async function startProcessing() {
    startProcessingMutation.mutate()
  }

  async function processSelected(documentIds: number[]) {
    if (documentIds.length === 0) return
    processSelectedMutation.mutate(documentIds)
  }

  return {
    // Data (from Vue Query)
    documents,
    loading,
    uploading,
    
    // Computed properties
    documentCount,
    completedCount,
    pendingCount,
    processingDocuments,
    canUpload,
    
    // Actions (wrappers around Vue Query)
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    startProcessing,
    processSelected,
    
    // Legacy polling functions (no-ops, kept for backward compatibility)
    startPolling: store.startPolling,
    stopPolling: store.stopPolling,
    stopAllPolling: store.stopAllPolling,
    resumePolling: store.resumePolling,
    
    // Expose query and mutations for advanced usage
    documentsQuery,
    uploadMutation,
    deleteMutation,
    startProcessingMutation,
    processSelectedMutation,
  }
}
