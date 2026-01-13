<script setup lang="ts">
/**
 * KnowledgeSpaceHeader - Header component for Knowledge Space page
 * Swiss design style matching MindMate/MindGraph
 */
import { computed } from 'vue'
import { ElButton, ElIcon, ElTooltip } from 'element-plus'
import { Upload, Setting, Search, Document, VideoPlay } from '@element-plus/icons-vue'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  documentCount: number
  completedCount: number
  pendingCount: number
  canUpload: boolean
  selectedCount: number
  selectedPendingCount: number
}>()

const emit = defineEmits<{
  (e: 'upload'): void
  (e: 'settings'): void
  (e: 'retrieval-test'): void
  (e: 'start-processing'): void
  (e: 'process-selected'): void
}>()

const { isZh } = useLanguage()

const showRetrievalTest = computed(() => props.completedCount > 0)
const showStartProcessing = computed(() => props.pendingCount > 0)
const hasSelectedPending = computed(() => props.selectedPendingCount > 0)
</script>

<template>
  <div
    class="knowledge-space-header h-14 px-6 flex items-center justify-between border-b border-stone-200 bg-white shrink-0"
  >
    <div class="flex items-center gap-3 min-w-0 flex-1">
      <h1 class="text-lg font-semibold text-stone-900">
        {{ isZh ? '个人知识库' : 'Knowledge Base' }}
      </h1>
      <span class="text-sm text-stone-500">
        {{ isZh ? `(${documentCount}/5)` : `(${documentCount}/5)` }}
      </span>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <!-- Upload Documents Button -->
      <ElButton
        class="upload-btn"
        size="small"
        :disabled="!canUpload"
        @click="emit('upload')"
      >
        <ElIcon class="mr-1"><Upload /></ElIcon>
        {{ isZh ? '上传文档' : 'Upload Documents' }}
      </ElButton>

      <!-- Selected Count Badge -->
      <span v-if="selectedCount > 0" class="selected-badge">
        {{ isZh ? `已选 ${selectedCount} 项` : `${selectedCount} selected` }}
      </span>

      <!-- Process Selected Button (when documents are selected) -->
      <ElButton
        v-if="hasSelectedPending"
        class="start-processing-btn"
        size="small"
        @click="emit('process-selected')"
      >
        <ElIcon class="mr-1"><VideoPlay /></ElIcon>
        {{ isZh ? `处理选中 (${selectedPendingCount})` : `Process Selected (${selectedPendingCount})` }}
      </ElButton>

      <!-- Start All Processing Button (when no selection but has pending) -->
      <ElButton
        v-else-if="showStartProcessing && selectedCount === 0"
        class="start-processing-btn-secondary"
        size="small"
        @click="emit('start-processing')"
      >
        <ElIcon class="mr-1"><VideoPlay /></ElIcon>
        {{ isZh ? '处理全部' : 'Process All' }}
      </ElButton>

      <!-- Retrieval Test Button -->
      <ElTooltip
        :content="isZh ? '检索测试' : 'Retrieval Test'"
      >
        <ElButton
          text
          circle
          size="small"
          class="action-btn"
          :disabled="completedCount === 0"
          @click="emit('retrieval-test')"
        >
          <ElIcon><Search /></ElIcon>
        </ElButton>
      </ElTooltip>

      <!-- Settings Button -->
      <ElTooltip :content="isZh ? '设置' : 'Settings'">
        <ElButton
          text
          circle
          size="small"
          class="action-btn"
          @click="emit('settings')"
        >
          <ElIcon><Setting /></ElIcon>
        </ElButton>
      </ElTooltip>
    </div>
  </div>
</template>

<style scoped>
/* Upload button - Swiss Design style (grey, round) */
.upload-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  --el-button-disabled-bg-color: #f5f5f4;
  --el-button-disabled-text-color: #a8a29e;
  font-weight: 500;
  border-radius: 9999px;
}

/* Start Processing button - Swiss Design style (blue accent) */
.start-processing-btn {
  --el-button-bg-color: #3b82f6;
  --el-button-border-color: #3b82f6;
  --el-button-hover-bg-color: #2563eb;
  --el-button-hover-border-color: #2563eb;
  --el-button-active-bg-color: #1d4ed8;
  --el-button-active-border-color: #1d4ed8;
  --el-button-text-color: #ffffff;
  font-weight: 500;
  border-radius: 9999px;
}

/* Start Processing button secondary - Swiss Design style (grey) */
.start-processing-btn-secondary {
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

/* Action buttons - Swiss Design style */
.action-btn {
  --el-button-text-color: #78716c;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
  --el-button-disabled-text-color: #d6d3d1;
  --el-button-disabled-bg-color: transparent;
}

/* Selected count badge */
.selected-badge {
  font-size: 13px;
  color: #3b82f6;
  font-weight: 500;
  padding: 4px 12px;
  background: #eff6ff;
  border-radius: 9999px;
}
</style>
