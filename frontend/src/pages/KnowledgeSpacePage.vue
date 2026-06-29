<script setup lang="ts">
/**
 * KnowledgeSpacePage - Personal Knowledge Space interface
 * Route: /knowledge-space
 */
import { computed, onMounted, ref, watch } from 'vue'

import ChunkPreviewModal from '@/components/knowledge-space/ChunkPreviewModal.vue'
import DocumentTable from '@/components/knowledge-space/DocumentTable.vue'
import DocumentUpload from '@/components/knowledge-space/DocumentUpload.vue'
import KnowledgeSpaceHeader from '@/components/knowledge-space/KnowledgeSpaceHeader.vue'
import KnowledgeSpacePackageGroups from '@/components/knowledge-space/KnowledgeSpacePackageGroups.vue'
import KnowledgeSpaceSettings from '@/components/knowledge-space/KnowledgeSpaceSettings.vue'
import ProcessingProgressBar from '@/components/knowledge-space/ProcessingProgressBar.vue'
import RetrievalTest from '@/components/knowledge-space/RetrievalTest.vue'
import { useKnowledgeSpacePackagePage } from '@/composables/knowledge/useKnowledgeSpacePackagePage'
import { documentNeedsPipelinePoll } from '@/composables/knowledge/usePipelineStatusBadge'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

const {
  activePackageId,
  activePackageName,
  documents,
  loading,
  uploading,
  documentCount,
  completedCount,
  pendingCount,
  canUpload,
  resumePolling,
  uploadDocument,
  deleteDocument,
  startProcessing,
  processSelected,
} = useKnowledgeSpacePackagePage()

const selectedDocumentIds = ref<number[]>([])
const showUploadModal = ref(false)
const showSettingsModal = ref(false)
const showRetrievalTestModal = ref(false)
const showChunkPreviewModal = ref(false)
const viewingDocumentId = ref<number | null>(null)
const viewingDocumentName = ref('')

onMounted(() => {
  resumePolling()
})

watch(
  activePackageId,
  () => {
    selectedDocumentIds.value = []
    resumePolling()
  }
)

watch(
  documents,
  (newDocuments: KnowledgeDocument[]) => {
    if (documentNeedsPipelinePoll(newDocuments)) {
      resumePolling()
    }
  },
  { deep: true }
)

const selectedCount = computed(() => selectedDocumentIds.value.length)

const selectedPendingCount = computed(() =>
  documents.value.filter(
    (doc: KnowledgeDocument) =>
      selectedDocumentIds.value.includes(doc.id) &&
      (doc.status === 'pending' || doc.status === 'failed')
  ).length
)

function handleProcessSelected(): void {
  if (selectedDocumentIds.value.length === 0) return
  processSelected(selectedDocumentIds.value)
  selectedDocumentIds.value = []
}

function handleDelete(id: number): void {
  void deleteDocument(id)
}

function handleView(id: number): void {
  const doc = documents.value.find((item: KnowledgeDocument) => item.id === id)
  if (doc && doc.status === 'completed') {
    viewingDocumentId.value = id
    viewingDocumentName.value = doc.file_name
    showChunkPreviewModal.value = true
  }
}
</script>

<template>
  <div class="knowledge-space-page flex-1 flex flex-col bg-white h-full overflow-hidden">
    <KnowledgeSpaceHeader
      :package-name="activePackageName"
      :document-count="documentCount"
      :completed-count="completedCount"
      :pending-count="pendingCount"
      :can-upload="canUpload"
      :selected-count="selectedCount"
      :selected-pending-count="selectedPendingCount"
      @upload="showUploadModal = true"
      @settings="showSettingsModal = true"
      @retrieval-test="showRetrievalTestModal = true"
      @start-processing="startProcessing"
      @process-selected="handleProcessSelected"
    />

    <ProcessingProgressBar :documents="documents" />

    <div class="flex-1 overflow-y-auto p-6">
      <KnowledgeSpacePackageGroups v-if="activePackageId === null" />

      <DocumentTable
        v-else
        :documents="documents"
        :loading="loading"
        :selected-ids="selectedDocumentIds"
        @delete="handleDelete"
        @view="handleView"
        @update:selected-ids="selectedDocumentIds = $event"
      />
    </div>

    <DocumentUpload
      v-model:visible="showUploadModal"
      :uploading="uploading"
      :can-upload="canUpload"
      @upload="uploadDocument"
      @close="showUploadModal = false"
    />

    <KnowledgeSpaceSettings
      v-model:visible="showSettingsModal"
      @close="showSettingsModal = false"
    />

    <RetrievalTest
      v-model:visible="showRetrievalTestModal"
      @close="showRetrievalTestModal = false"
    />

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
