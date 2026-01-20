<script setup lang="ts">
/**
 * ProcessingProgressBar - Shows document processing progress
 * Similar to Dify's progress indicator
 * Enhanced to show method-specific progress for chunk tests
 */
import { computed, ref, watch } from 'vue'
import { ElProgress, ElIcon, ElTable, ElTableColumn } from 'element-plus'
import { Loading, Check, Minus } from '@element-plus/icons-vue'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  documents: KnowledgeDocument[]
}>()

const { isZh } = useLanguage()

const processingDocuments = computed(() => 
  props.documents.filter(d => d.status === 'processing')
)

// Method states tracking for chunk test documents
const methodStates = ref<Record<number, Record<string, {
  chunk: 'pending' | 'processing' | 'completed'
  embed: 'pending' | 'processing' | 'completed'
  index: 'pending' | 'processing' | 'completed'
}>>>({})

// Initialize method states for each document
const initializeMethodStates = (docId: number) => {
  if (!methodStates.value[docId]) {
    methodStates.value[docId] = {
      semchunk: { chunk: 'pending', embed: 'pending', index: 'pending' },
      spacy: { chunk: 'pending', embed: 'pending', index: 'pending' },
      chonkie: { chunk: 'pending', embed: 'pending', index: 'pending' },
      langchain: { chunk: 'pending', embed: 'pending', index: 'pending' },
      mindchunk: { chunk: 'pending', embed: 'pending', index: 'pending' },
    }
  }
}

// Parse progress string to extract method and stage
const parseProgress = (progress: string | null | undefined): { stage: string; method: string | null } => {
  if (!progress) return { stage: '', method: null }
  
  // Match format: "stage (method)" e.g., "chunking (semchunk)"
  const match = progress.match(/^(\w+)\s*\((\w+)\)$/)
  if (match) {
    return { stage: match[1], method: match[2] }
  }
  
  // Fallback: simple stage name
  return { stage: progress, method: null }
}

// Update method states based on progress
watch(() => props.documents, (docs) => {
  docs.forEach(doc => {
    if (doc.status === 'processing' && doc.processing_progress) {
      initializeMethodStates(doc.id)
      const { stage, method } = parseProgress(doc.processing_progress)
      
      if (method && methodStates.value[doc.id] && methodStates.value[doc.id][method]) {
        const methodState = methodStates.value[doc.id][method]
        
        // Update state based on stage
        if (stage === 'chunking') {
          methodState.chunk = 'processing'
        } else if (stage === 'embedding') {
          methodState.chunk = 'completed'
          methodState.embed = 'processing'
        } else if (stage === 'indexing') {
          methodState.embed = 'completed'
          methodState.index = 'processing'
        } else if (stage === 'completed') {
          methodState.chunk = 'completed'
          methodState.embed = 'completed'
          methodState.index = 'completed'
        }
      }
    }
  })
}, { immediate: true, deep: true })

const progressLabels = computed<Record<string, string>>(() => ({
  queued: isZh.value ? '排队中' : 'Queued',
  extracting: isZh.value ? '提取文本' : 'Extracting',
  cleaning: isZh.value ? '清理文本' : 'Cleaning',
  chunking: isZh.value ? '分块处理' : 'Chunking',
  embedding: isZh.value ? '生成向量' : 'Embedding',
  indexing: isZh.value ? '建立索引' : 'Indexing',
  starting: isZh.value ? '开始处理' : 'Starting',
  completed: isZh.value ? '已完成' : 'Completed',
}))

const getProgressLabel = (progress: string | null | undefined): string => {
  if (!progress) return ''
  const { stage } = parseProgress(progress)
  return progressLabels.value[stage] || progress
}

// Check if document is a chunk test (has method-specific progress)
const isChunkTest = (doc: KnowledgeDocument): boolean => {
  if (!doc.processing_progress) return false
  const { method } = parseProgress(doc.processing_progress)
  return method !== null
}

// Get method display name
const getMethodDisplayName = (method: string): string => {
  const methodNames: Record<string, string> = {
    semchunk: 'SemChunk',
    spacy: 'spaCy',
    chonkie: 'Chonkie',
    langchain: 'LangChain',
    mindchunk: 'MindChunk',
  }
  return methodNames[method] || method
}

// Get stage icon
const getStageIcon = (state: 'pending' | 'processing' | 'completed') => {
  if (state === 'completed') return Check
  if (state === 'processing') return Loading
  return Minus  // Use Minus icon for pending state
}

// Get stage color
const getStageColor = (state: 'pending' | 'processing' | 'completed'): string => {
  if (state === 'completed') return '#10b981' // green
  if (state === 'processing') return '#3b82f6' // blue
  return '#9ca3af' // gray
}

const getProgressColor = (progress: string | null | undefined): string => {
  if (!progress) return '#3b82f6'
  
  // Parse progress to get stage
  const { stage } = parseProgress(progress)
  
  switch (stage) {
    case 'queued':
      return '#6b7280'
    case 'extracting':
    case 'starting':
      return '#3b82f6'
    case 'cleaning':
      return '#8b5cf6'
    case 'chunking':
      return '#ec4899'
    case 'embedding':
      return '#f59e0b'
    case 'indexing':
      return '#10b981'
    case 'completed':
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
      class="progress-item mb-4 last:mb-0"
    >
      <!-- Document header -->
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

      <!-- Overall progress bar -->
      <ElProgress
        :percentage="doc.processing_progress_percent || 0"
        :color="getProgressColor(doc.processing_progress)"
        :stroke-width="6"
        :show-text="false"
        class="progress-bar mb-3"
      />

      <!-- Method-specific progress grid for chunk tests -->
      <div v-if="isChunkTest(doc) && methodStates[doc.id]" class="method-progress-grid mt-3">
        <div class="text-xs font-medium text-stone-700 mb-2">
          {{ isZh ? '方法处理进度' : 'Method Progress' }}
        </div>
        <ElTable
          :data="Object.entries(methodStates[doc.id]).map(([method, states]) => ({ method, ...states }))"
          size="small"
          :show-header="true"
          class="method-table"
        >
          <ElTableColumn
            :label="isZh ? '方法' : 'Method'"
            prop="method"
            width="100"
          >
            <template #default="{ row }">
              <span class="text-xs font-medium">{{ getMethodDisplayName(row.method) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn
            :label="isZh ? '分块' : 'Chunk'"
            prop="chunk"
            width="80"
            align="center"
          >
            <template #default="{ row }">
              <ElIcon
                :class="row.chunk === 'processing' ? 'animate-spin' : ''"
                :style="{ color: getStageColor(row.chunk) }"
              >
                <component :is="getStageIcon(row.chunk)" />
              </ElIcon>
            </template>
          </ElTableColumn>
          <ElTableColumn
            :label="isZh ? '向量化' : 'Embed'"
            prop="embed"
            width="80"
            align="center"
          >
            <template #default="{ row }">
              <ElIcon
                :class="row.embed === 'processing' ? 'animate-spin' : ''"
                :style="{ color: getStageColor(row.embed) }"
              >
                <component :is="getStageIcon(row.embed)" />
              </ElIcon>
            </template>
          </ElTableColumn>
          <ElTableColumn
            :label="isZh ? '索引' : 'Index'"
            prop="index"
            width="80"
            align="center"
          >
            <template #default="{ row }">
              <ElIcon
                :class="row.index === 'processing' ? 'animate-spin' : ''"
                :style="{ color: getStageColor(row.index) }"
              >
                <component :is="getStageIcon(row.index)" />
              </ElIcon>
            </template>
          </ElTableColumn>
        </ElTable>
      </div>
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

.method-progress-grid {
  background-color: #fafaf9;
  border-radius: 8px;
  padding: 12px;
}

.method-table :deep(.el-table__header) {
  background-color: transparent;
}

.method-table :deep(.el-table__body) {
  background-color: transparent;
}

.method-table :deep(.el-table th) {
  background-color: transparent;
  border-bottom: 1px solid #e7e5e4;
  padding: 8px 0;
  font-size: 11px;
  font-weight: 600;
  color: #78716c;
}

.method-table :deep(.el-table td) {
  border-bottom: 1px solid #e7e5e4;
  padding: 8px 0;
}

.method-table :deep(.el-table__row:hover) {
  background-color: #f5f5f4;
}
</style>
