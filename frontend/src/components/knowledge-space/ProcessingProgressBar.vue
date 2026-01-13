<script setup lang="ts">
/**
 * ProcessingProgressBar - Shows document processing progress
 * Similar to Dify's progress indicator
 */
import { computed } from 'vue'
import { ElProgress, ElIcon } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  documents: KnowledgeDocument[]
}>()

const { isZh } = useLanguage()

const processingDocuments = computed(() => 
  props.documents.filter(d => d.status === 'processing')
)

const progressLabels = computed<Record<string, string>>(() => ({
  queued: isZh.value ? '排队中' : 'Queued',
  extracting: isZh.value ? '提取文本' : 'Extracting',
  cleaning: isZh.value ? '清理文本' : 'Cleaning',
  chunking: isZh.value ? '分块处理' : 'Chunking',
  embedding: isZh.value ? '生成向量' : 'Embedding',
  indexing: isZh.value ? '建立索引' : 'Indexing',
}))

const getProgressLabel = (progress: string | null | undefined): string => {
  if (!progress) return ''
  return progressLabels.value[progress] || progress
}

const getProgressColor = (progress: string | null | undefined): string => {
  switch (progress) {
    case 'queued':
      return '#6b7280'
    case 'extracting':
      return '#3b82f6'
    case 'cleaning':
      return '#8b5cf6'
    case 'chunking':
      return '#ec4899'
    case 'embedding':
      return '#f59e0b'
    case 'indexing':
      return '#10b981'
    default:
      return '#3b82f6'
  }
}
</script>

<template>
  <div
    v-if="processingDocuments.length > 0"
    class="processing-progress-bar bg-stone-50 border-b border-stone-200 px-6 py-3"
  >
    <div
      v-for="doc in processingDocuments"
      :key="doc.id"
      class="progress-item mb-3 last:mb-0"
    >
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <ElIcon class="text-stone-500 animate-spin">
            <Loading />
          </ElIcon>
          <span class="text-sm font-medium text-stone-900">{{ doc.file_name }}</span>
          <span
            v-if="doc.processing_progress"
            class="text-xs text-stone-600 px-2 py-0.5 rounded"
            :style="{ backgroundColor: getProgressColor(doc.processing_progress) + '15', color: getProgressColor(doc.processing_progress) }"
          >
            {{ getProgressLabel(doc.processing_progress) }}
          </span>
        </div>
        <span class="text-xs text-stone-500">
          {{ doc.processing_progress_percent || 0 }}%
        </span>
      </div>
      <ElProgress
        :percentage="doc.processing_progress_percent || 0"
        :color="getProgressColor(doc.processing_progress)"
        :stroke-width="6"
        :show-text="false"
        class="progress-bar"
      />
    </div>
  </div>
</template>

<style scoped>
.processing-progress-bar {
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.progress-item {
  min-height: 40px;
}

.progress-bar :deep(.el-progress-bar__outer) {
  background-color: #e7e5e4;
  border-radius: 9999px;
}

.progress-bar :deep(.el-progress-bar__inner) {
  border-radius: 9999px;
  transition: width 0.3s ease;
}
</style>
