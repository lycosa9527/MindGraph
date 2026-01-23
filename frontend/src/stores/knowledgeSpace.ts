/**
 * Knowledge Space Store - Pinia store for UI state only
 *
 * Note: API calls are handled by Vue Query composables.
 * This store provides a thin wrapper for backward compatibility.
 * Components should use Vue Query composables directly for new code.
 */
import { defineStore } from 'pinia'

export interface KnowledgeDocument {
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

export interface DocumentListResponse {
  documents: KnowledgeDocument[]
  total: number
}

export const useKnowledgeSpaceStore = defineStore('knowledgeSpace', () => {
  // This store is now a thin wrapper
  // Actual state is managed by Vue Query composables
  // Components should use useKnowledgeSpace() composable which provides
  // access to both Pinia store and Vue Query composables

  // Legacy functions kept for backward compatibility
  // These are no-ops - actual implementation is in useKnowledgeSpace composable
  function startPolling(_documentId: number) {
    // No-op: Vue Query handles polling via refetchInterval
  }

  function stopPolling(_documentId: number) {
    // No-op: Vue Query handles polling via refetchInterval
  }

  function stopAllPolling() {
    // No-op: Vue Query handles polling via refetchInterval
  }

  function resumePolling() {
    // No-op: Vue Query handles polling via refetchInterval
  }

  return {
    startPolling,
    stopPolling,
    stopAllPolling,
    resumePolling,
  }
})
