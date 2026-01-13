<script setup lang="ts">
/**
 * KnowledgeSpacePage - Personal Knowledge Space interface
 * Route: /knowledge-space
 * Full-page layout with header, document table, and modals
 * 
 * Features:
 * - Background processing: Documents process in background, user can navigate away
 * - State persistence: Pinia store persists state across navigation
 * - Auto-resume polling: Automatically resumes polling when returning to page
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useKnowledgeSpace } from '@/composables/useKnowledgeSpace'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import KnowledgeSpaceHeader from '@/components/knowledge-space/KnowledgeSpaceHeader.vue'
import DocumentTable from '@/components/knowledge-space/DocumentTable.vue'
import DocumentUpload from '@/components/knowledge-space/DocumentUpload.vue'
import RetrievalTest from '@/components/knowledge-space/RetrievalTest.vue'
import KnowledgeSpaceSettings from '@/components/knowledge-space/KnowledgeSpaceSettings.vue'
import ProcessingProgressBar from '@/components/knowledge-space/ProcessingProgressBar.vue'
import ChunkPreviewModal from '@/components/knowledge-space/ChunkPreviewModal.vue'

const {
  documents,
  loading,
  uploading,
  documentCount,
  completedCount,
  pendingCount,
  canUpload,
  fetchDocuments,
  uploadDocument,
  deleteDocument,
  startProcessing,
  processSelected,
  resumePolling,
  stopAllPolling,
} = useKnowledgeSpace()

const selectedDocumentIds = ref<number[]>([])
const showUploadModal = ref(false)
const showSettingsModal = ref(false)
const showRetrievalTestModal = ref(false)
const showChunkPreviewModal = ref(false)
const viewingDocumentId = ref<number | null>(null)
const viewingDocumentName = ref('')

onMounted(async () => {
  // Fetch documents first
  await fetchDocuments()
  // Resume polling for any documents that are processing
  // This ensures progress continues even if user navigated away
  resumePolling()
  
  // Debug: Log documents count
  console.log('[KnowledgeSpacePage] Loaded documents:', documentCount)
})

onUnmounted(() => {
  // Clean up polling when component unmounts
  // Note: We don't stop polling completely because user might navigate to another page
  // and come back. Polling will resume automatically via resumePolling()
  // Only stop if we're sure user is leaving the app (handled by app-level cleanup if needed)
})

// Watch for new processing documents and start polling automatically
watch(
  documents,
  (newDocuments: KnowledgeDocument[]) => {
    const processingDocs = newDocuments.filter((d: KnowledgeDocument) => 
      d.status === 'processing' || d.status === 'pending'
    )
    if (processingDocs.length > 0) {
      // Resume polling for all processing documents
      // resumePolling handles duplicate prevention internally
      resumePolling()
    }
  },
  { deep: true }
)

const handleUpload = () => {
  showUploadModal.value = true
}

const handleSettings = () => {
  showSettingsModal.value = true
}

const handleRetrievalTest = () => {
  showRetrievalTestModal.value = true
}

const handleDelete = (id: number) => {
  deleteDocument(id)
}

const handleView = (id: number) => {
  const doc = documents.value.find((d: KnowledgeDocument) => d.id === id)
  if (doc && doc.status === 'completed') {
    viewingDocumentId.value = id
    viewingDocumentName.value = doc.file_name
    showChunkPreviewModal.value = true
  }
}

// Selection related computed and handlers
const selectedCount = computed(() => selectedDocumentIds.value.length)

const selectedPendingCount = computed(() => {
  return documents.value.filter(
    (d: KnowledgeDocument) => 
      selectedDocumentIds.value.includes(d.id) && 
      (d.status === 'pending' || d.status === 'failed')
  ).length
})

const handleProcessSelected = () => {
  if (selectedDocumentIds.value.length === 0) return
  processSelected(selectedDocumentIds.value)
  // Clear selection after starting processing
  selectedDocumentIds.value = []
}
</script>

<template>
  <div class="knowledge-space-page flex-1 flex flex-col bg-white h-full overflow-hidden">
    <!-- Header -->
    <KnowledgeSpaceHeader
      :document-count="documentCount"
      :completed-count="completedCount"
      :pending-count="pendingCount"
      :can-upload="canUpload"
      :selected-count="selectedCount"
      :selected-pending-count="selectedPendingCount"
      @upload="handleUpload"
      @settings="handleSettings"
      @retrieval-test="handleRetrievalTest"
      @start-processing="startProcessing"
      @process-selected="handleProcessSelected"
    />

    <!-- Processing Progress Bar -->
    <ProcessingProgressBar :documents="documents" />

    <!-- Document Table -->
    <div class="flex-1 overflow-hidden p-6">
      <DocumentTable
        :documents="documents"
        :loading="loading"
        :selected-ids="selectedDocumentIds"
        @delete="handleDelete"
        @view="handleView"
        @update:selected-ids="selectedDocumentIds = $event"
      />
    </div>

    <!-- Upload Modal -->
    <DocumentUpload
      v-model:visible="showUploadModal"
      :uploading="uploading"
      :can-upload="canUpload"
      @upload="uploadDocument"
      @close="showUploadModal = false"
    />

    <!-- Settings Modal -->
    <KnowledgeSpaceSettings
      v-model:visible="showSettingsModal"
      @close="showSettingsModal = false"
    />

    <!-- Retrieval Test Modal -->
    <RetrievalTest
      v-model:visible="showRetrievalTestModal"
      @close="showRetrievalTestModal = false"
    />

    <!-- Chunk Preview Modal -->
    <ChunkPreviewModal
      v-model:visible="showChunkPreviewModal"
      :document-id="viewingDocumentId"
      :file-name="viewingDocumentName"
    />
  </div>
</template>

<style scoped>
.knowledge-space-page {
  width: 100%;
}
</style>
