/**
 * Knowledge Space Store - UI state for Knowledge Space / File Center.
 *
 * Server data is managed by Vue Query composables; this store holds selection
 * and legacy polling no-ops for backward compatibility.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

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
  chunking_engine?: string | null
  chunking_mode?: string | null
  rag_status?: 'not_yet' | 'processing' | 'complete' | 'failed' | null
  wiki_status?: 'disabled' | 'not_yet' | 'pending' | 'complete' | null
  /** Extracted markdown size when Document Summary lite has finished. */
  extract_char_count?: number | null
  created_at: string
  updated_at: string
}

const ACTIVE_PACKAGE_KEY = 'mindgraph.knowledgeSpace.activePackageId'

function readActivePackageId(): number | null {
  const raw = sessionStorage.getItem(ACTIVE_PACKAGE_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function writeActivePackageId(packageId: number | null): void {
  if (packageId === null) {
    sessionStorage.removeItem(ACTIVE_PACKAGE_KEY)
  } else {
    sessionStorage.setItem(ACTIVE_PACKAGE_KEY, String(packageId))
  }
}

export const useKnowledgeSpaceStore = defineStore('knowledgeSpace', () => {
  const activePackageId = ref<number | null>(readActivePackageId())

  function selectPackage(packageId: number | null): void {
    activePackageId.value = packageId
    writeActivePackageId(packageId)
  }

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
    activePackageId,
    selectPackage,
    startPolling,
    stopPolling,
    stopAllPolling,
    resumePolling,
  }
})
