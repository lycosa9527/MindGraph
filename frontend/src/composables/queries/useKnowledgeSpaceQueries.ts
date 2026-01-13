/**
 * Knowledge Space Query Composables
 *
 * Vue Query composables for fetching knowledge space data with automatic caching.
 */
import { useQuery } from '@tanstack/vue-query'
import { apiRequest } from '@/utils/apiClient'
import { knowledgeSpaceKeys } from './knowledgeSpaceKeys'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

// ============================================================================
// Types
// ============================================================================

export interface DocumentListResponse {
  documents: KnowledgeDocument[]
  total: number
}

export interface DocumentStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  error_message?: string | null
  processing_progress?: string | null
  processing_progress_percent?: number
}

// ============================================================================
// Helper Functions
// ============================================================================

async function fetchDocuments(): Promise<DocumentListResponse> {
  const response = await apiRequest('/api/knowledge-space/documents')

  if (!response.ok) {
    // Silently handle 404 (endpoint not available) - don't show error
    if (response.status === 404) {
      return { documents: [], total: 0 }
    }
    throw new Error('Failed to fetch documents')
  }

  return await response.json()
}

async function fetchDocumentStatus(documentId: number): Promise<DocumentStatus> {
  const response = await apiRequest(`/api/knowledge-space/documents/${documentId}/status`)

  if (!response.ok) {
    throw new Error('Failed to fetch document status')
  }

  return await response.json()
}

// ============================================================================
// Query Composables
// ============================================================================

/**
 * Fetch all documents in knowledge space
 * Stale time: 30 seconds (documents change frequently)
 * Refetch interval: 5 seconds for processing documents (handled by refetchInterval)
 */
export function useDocuments(options?: { 
  refetchInterval?: number | false | ((query: { state: { data: DocumentListResponse | undefined } }) => number | false) 
}) {
  return useQuery({
    queryKey: knowledgeSpaceKeys.documents(),
    queryFn: fetchDocuments,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: options?.refetchInterval ?? false,
    retry: 1,
  })
}

/**
 * Fetch status for a specific document
 * Used for polling document processing status
 * Stale time: 0 (always fresh for status checks)
 * Refetch interval: 5 seconds when document is processing
 */
export function useDocumentStatus(
  documentId: number | null,
  options?: { enabled?: boolean; refetchInterval?: number | false }
) {
  return useQuery({
    queryKey: knowledgeSpaceKeys.documentStatus(documentId || 0),
    queryFn: () => fetchDocumentStatus(documentId!),
    staleTime: 0, // Always fetch fresh status
    refetchInterval: options?.refetchInterval ?? false,
    enabled: (options?.enabled ?? true) && documentId !== null,
  })
}
