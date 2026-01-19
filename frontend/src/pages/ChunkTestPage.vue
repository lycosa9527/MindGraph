<script setup lang="ts">
/**
 * ChunkTestPage - RAG Chunk Test interface
 * Route: /chunk-test
 * Page for testing and comparing RAG chunking strategies
 * Shows default benchmark datasets and user documents
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElIcon, ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import {
  useBenchmarks,
  useUpdateDatasets,
  useTestUserDocuments,
  useTestBenchmarkDataset,
  useTestQueries,
} from '@/composables/queries/useChunkTestQueries'
import { useKnowledgeSpace } from '@/composables/useKnowledgeSpace'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import ChunkTestHeader from '@/components/knowledge-space/ChunkTestHeader.vue'
import DatasetTable from '@/components/knowledge-space/DatasetTable.vue'
import DocumentTable from '@/components/knowledge-space/DocumentTable.vue'
import DocumentUpload from '@/components/knowledge-space/DocumentUpload.vue'
import ProcessingProgressBar from '@/components/knowledge-space/ProcessingProgressBar.vue'
import ChunkPreviewModal from '@/components/knowledge-space/ChunkPreviewModal.vue'
import { useLanguage } from '@/composables/useLanguage'

const { isZh } = useLanguage()
const router = useRouter()

const { data: benchmarksData, isLoading: isLoadingBenchmarks } = useBenchmarks()
const updateDatasetsMutation = useUpdateDatasets()
const testUserDocumentsMutation = useTestUserDocuments()
const testBenchmarkMutation = useTestBenchmarkDataset()
const { data: defaultQueries } = useTestQueries('mixed', 20)

const {
  documents,
  loading: loadingDocuments,
  uploading,
  documentCount,
  canUpload,
  fetchDocuments,
  uploadDocument,
  deleteDocument,
  resumePolling,
} = useKnowledgeSpace()

const datasets = computed(() => benchmarksData.value?.benchmarks || [])
const selectedDocumentIds = ref<number[]>([])
const showUploadModal = ref(false)
const showChunkPreviewModal = ref(false)
const viewingDocumentId = ref<number | null>(null)
const viewingDocumentName = ref('')

const hasDocuments = computed(() => {
  return documents.value.some((doc: KnowledgeDocument) => doc.status === 'completed')
})

onMounted(async () => {
  await fetchDocuments()
  resumePolling()
})

const handleUpload = () => {
  showUploadModal.value = true
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

const handleTestUserDocuments = async () => {
  // Get completed documents (use selected if available, otherwise all completed)
  const completedDocs = documents.value.filter(
    (doc: KnowledgeDocument) => doc.status === 'completed'
  )

  if (completedDocs.length === 0) {
    ElMessage.warning(isZh ? '没有可测试的文档' : 'No completed documents available for testing')
    return
  }

  const docIdsToTest = selectedDocumentIds.value.length > 0
    ? selectedDocumentIds.value.filter((id) =>
        completedDocs.some((doc: KnowledgeDocument) => doc.id === id)
      )
    : completedDocs.map((doc: KnowledgeDocument) => doc.id)

  if (docIdsToTest.length === 0) {
    ElMessage.warning(isZh ? '请选择已完成的文档进行测试' : 'Please select completed documents for testing')
    return
  }

  // Use default queries if available, otherwise generate simple queries
  const queries = defaultQueries.value && defaultQueries.value.length > 0
    ? defaultQueries.value.slice(0, 10) // Use first 10 queries
    : [
        'What is the main topic?',
        'What are the key points?',
        'What information is provided?',
        'What are the important details?',
        'What can you tell me about this document?',
      ]

  try {
    ElMessage.info(isZh ? '开始测试上传文档...' : 'Starting test for uploaded documents...')
    const result = await testUserDocumentsMutation.mutateAsync({
      document_ids: docIdsToTest,
      queries,
    })
    // Navigate to results page immediately
    router.push(`/chunk-test/results/${result.test_id}`)
  } catch (error) {
    ElMessage.error(
      error instanceof Error
        ? error.message
        : isZh ? '测试失败' : 'Test failed'
    )
  }
}

const handleTestAllDatasets = async () => {
  if (datasets.value.length === 0) {
    ElMessage.warning(isZh ? '没有可用的数据集' : 'No datasets available')
    return
  }

  try {
    ElMessage.info(isZh ? '开始测试所有数据集...' : 'Starting test for all datasets...')
    const results = []

    for (const dataset of datasets.value) {
      try {
        ElMessage.info(
          isZh
            ? `正在测试数据集: ${dataset.name}...`
            : `Testing dataset: ${dataset.name}...`
        )
        const result = await testBenchmarkMutation.mutateAsync({
          dataset_name: dataset.name,
        })
        results.push({ dataset: dataset.name, result })
      } catch (error) {
        console.error(`Failed to test dataset ${dataset.name}:`, error)
        ElMessage.warning(
          isZh
            ? `数据集 ${dataset.name} 测试失败`
            : `Failed to test dataset ${dataset.name}`
        )
      }
    }

    if (results.length > 0) {
      ElMessage.success(
        isZh
          ? `所有数据集测试完成！共测试 ${results.length} 个数据集`
          : `All datasets tested! Tested ${results.length} datasets`
      )
      // TODO: Display aggregated results in a modal or results panel
      console.log('All test results:', results)
    } else {
      ElMessage.error(isZh ? '所有数据集测试失败' : 'All dataset tests failed')
    }
  } catch (error) {
    ElMessage.error(
      error instanceof Error
        ? error.message
        : isZh ? '测试失败' : 'Test failed'
    )
  }
}

const handleUpdateDatasets = async () => {
  try {
    await updateDatasetsMutation.mutateAsync()
    ElMessage.success(isZh ? '数据集更新成功' : 'Datasets updated successfully')
  } catch (error) {
    ElMessage.error(
      error instanceof Error
        ? error.message
        : isZh ? '数据集更新失败' : 'Failed to update datasets'
    )
  }
}
</script>

<template>
  <div class="chunk-test-page flex-1 flex flex-col bg-white h-full overflow-hidden">
    <!-- Header -->
    <ChunkTestHeader
      :document-count="documentCount"
      :can-upload="canUpload"
      :has-documents="hasDocuments"
      @upload="handleUpload"
      @test-user-documents="handleTestUserDocuments"
      @test-all-datasets="handleTestAllDatasets"
    />

    <!-- Processing Progress Bar -->
    <ProcessingProgressBar :documents="documents" />

    <!-- Content: Datasets and Documents -->
    <div class="flex-1 overflow-auto p-6">
      <!-- Benchmark Datasets Section -->
      <div class="mb-8">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-stone-900">
            {{ isZh ? '基准数据集' : 'Benchmark Datasets' }}
          </h2>
          <ElButton
            size="small"
            :loading="updateDatasetsMutation.isPending.value"
            class="update-datasets-btn"
            @click="handleUpdateDatasets"
          >
            <ElIcon class="mr-1"><RefreshRight /></ElIcon>
            {{ isZh ? '更新数据集' : 'Update Datasets' }}
          </ElButton>
        </div>
        <DatasetTable
          :datasets="datasets"
          :loading="isLoadingBenchmarks"
        />
      </div>

      <!-- User Documents Section -->
      <div>
        <h2 class="text-lg font-semibold text-stone-900 mb-4">
          {{ isZh ? '我的文档' : 'My Documents' }}
        </h2>
        <DocumentTable
          :documents="documents"
          :loading="loadingDocuments"
          :selected-ids="selectedDocumentIds"
          :show-dataset="true"
          :grey-out-dataset="true"
          @delete="handleDelete"
          @view="handleView"
          @update:selected-ids="selectedDocumentIds = $event"
        />
      </div>
    </div>

    <!-- Upload Modal -->
    <DocumentUpload
      v-model:visible="showUploadModal"
      :uploading="uploading"
      :can-upload="canUpload"
      @upload="uploadDocument"
      @close="showUploadModal = false"
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
.chunk-test-page {
  width: 100%;
}

.update-datasets-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}
</style>
