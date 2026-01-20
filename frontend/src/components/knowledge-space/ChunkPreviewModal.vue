<script setup lang="ts">
/**
 * ChunkPreviewModal - View document chunks
 * Shows paginated list of chunks with text preview
 */
import { ref, watch, computed } from 'vue'
import { ElDialog, ElPagination, ElEmpty, ElIcon, ElTag } from 'element-plus'
import { Document, Loading } from '@element-plus/icons-vue'
import { useLanguage } from '@/composables/useLanguage'
import { apiRequest } from '@/utils/apiClient'

interface Chunk {
  id: number
  chunk_index: number
  text: string
  start_char: number
  end_char: number
  metadata: Record<string, any> | null
}

interface ChunksResponse {
  document_id: number
  file_name: string
  total: number
  page: number
  page_size: number
  chunks: Chunk[]
}

const props = defineProps<{
  visible: boolean
  documentId: number | null
  fileName: string
  isChunkTest?: boolean  // If true, use chunk test endpoints
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { isZh } = useLanguage()

const loading = ref(false)
const chunks = ref<Chunk[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

async function fetchChunks() {
  if (!props.documentId) return
  
  loading.value = true
  try {
    // Use chunk test endpoint if isChunkTest is true
    const endpoint = props.isChunkTest
      ? `/api/knowledge-space/chunk-test/documents/${props.documentId}/chunks`
      : `/api/knowledge-space/documents/${props.documentId}/chunks`
    
    const response = await apiRequest(
      `${endpoint}?page=${currentPage.value}&page_size=${pageSize.value}`
    )
    
    if (response.ok) {
      const data: ChunksResponse = await response.json()
      chunks.value = data.chunks
      total.value = data.total
    }
  } catch (error) {
    console.error('Failed to fetch chunks:', error)
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  fetchChunks()
}

function truncateText(text: string, maxLength: number = 300): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

// Fetch chunks when dialog opens
watch(() => props.visible, (newValue) => {
  if (newValue && props.documentId) {
    currentPage.value = 1
    fetchChunks()
  }
})
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    :title="isZh ? `文档分块预览 - ${fileName}` : `Document Chunks - ${fileName}`"
    width="800px"
    :close-on-click-modal="false"
    class="chunk-preview-modal"
  >
    <div v-if="loading" class="flex items-center justify-center py-12">
      <ElIcon class="animate-spin text-3xl text-stone-400">
        <Loading />
      </ElIcon>
    </div>
    
    <div v-else-if="chunks.length === 0" class="py-8">
      <ElEmpty :description="isZh ? '暂无分块数据' : 'No chunks found'" />
    </div>
    
    <div v-else class="chunk-list">
      <div class="mb-4 text-sm text-stone-500">
        {{ isZh ? `共 ${total} 个分块` : `Total ${total} chunks` }}
      </div>
      
      <div class="space-y-4 max-h-[500px] overflow-y-auto pr-2">
        <div
          v-for="chunk in chunks"
          :key="chunk.id"
          class="chunk-item bg-stone-50 rounded-lg p-4 border border-stone-200"
        >
          <div class="flex items-center gap-2 mb-2">
            <ElIcon class="text-stone-400">
              <Document />
            </ElIcon>
            <span class="text-sm font-medium text-stone-700">
              {{ isZh ? `分块 #${chunk.chunk_index + 1}` : `Chunk #${chunk.chunk_index + 1}` }}
            </span>
            <ElTag size="small" type="info">
              {{ chunk.text.length }} {{ isZh ? '字符' : 'chars' }}
            </ElTag>
            <ElTag v-if="chunk.metadata?.page_number" size="small">
              {{ isZh ? `第${chunk.metadata.page_number}页` : `Page ${chunk.metadata.page_number}` }}
            </ElTag>
          </div>
          <div class="text-sm text-stone-600 leading-relaxed whitespace-pre-wrap">
            {{ truncateText(chunk.text) }}
          </div>
        </div>
      </div>
      
      <div v-if="total > pageSize" class="mt-4 flex justify-center">
        <ElPagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </ElDialog>
</template>

<style scoped>
.chunk-preview-modal :deep(.el-dialog__body) {
  padding: 20px 24px;
}

.chunk-item {
  transition: box-shadow 0.2s;
}

.chunk-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.chunk-list::-webkit-scrollbar {
  width: 6px;
}

.chunk-list::-webkit-scrollbar-track {
  background: #f5f5f4;
  border-radius: 3px;
}

.chunk-list::-webkit-scrollbar-thumb {
  background: #d6d3d1;
  border-radius: 3px;
}

.chunk-list::-webkit-scrollbar-thumb:hover {
  background: #a8a29e;
}
</style>
