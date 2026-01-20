/**
 * Chunk Test Documents Composable
 * 
 * Provides access to chunk test document management (separate from knowledge space).
 * Uses Vue Query for server state management.
 */
import { computed } from 'vue'
import {
  useChunkTestDocuments,
  useUploadChunkTestDocument,
  useDeleteChunkTestDocument,
  useStartProcessingChunkTestDocuments,
  useProcessSelectedChunkTestDocuments,
  type ChunkTestDocument
} from '@/composables/queries/useChunkTestDocumentQueries'

export function useChunkTestDocumentsComposable() {
  // Vue Query composables for server state
  const documentsQuery = useChunkTestDocuments({
    // Enable auto-refetch every 5 seconds if there are processing documents
    refetchInterval: (query: { state: { data: { documents: ChunkTestDocument[]; total: number } | undefined } }): number | false => {
      const data = query.state.data
      if (data?.documents.some((d: ChunkTestDocument) => d.status === 'processing' || d.status === 'pending')) {
        return 5000 // Refetch every 5 seconds
      }
      return false // Stop refetching when no processing documents
    },
  })

  const uploadMutation = useUploadChunkTestDocument()
  const deleteMutation = useDeleteChunkTestDocument()
  const startProcessingMutation = useStartProcessingChunkTestDocuments()
  const processSelectedMutation = useProcessSelectedChunkTestDocuments()

  // Computed properties that use Vue Query data
  const documents = computed(() => documentsQuery.data.value?.documents || [])
  const loading = computed(() => documentsQuery.isLoading.value)
  const uploading = computed(() => uploadMutation.isPending.value)

  // Computed properties
  const documentCount = computed(() => documents.value.length)
  const completedCount = computed(() => 
    documents.value.filter((d: ChunkTestDocument) => d.status === 'completed').length
  )
  const canUpload = computed(() => documentCount.value < 5)
  
  const processingDocuments = computed(() => 
    documents.value.filter((d: ChunkTestDocument) => d.status === 'processing' || d.status === 'pending')
  )

  const pendingCount = computed(() => 
    documents.value.filter((d: ChunkTestDocument) => d.status === 'pending' || d.status === 'failed').length
  )

  // Wrapper functions
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
    
    // Expose query and mutations for advanced usage
    documentsQuery,
    uploadMutation,
    deleteMutation,
    startProcessingMutation,
    processSelectedMutation,
  }
}
