<script setup lang="ts">
/**
 * KnowledgeSpaceHeader - Header with breadcrumb for Knowledge Space page.
 */
import { computed } from 'vue'

import { ElButton, ElIcon, ElTooltip } from 'element-plus'

import { Search, Setting, Upload, VideoPlay } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables/core/useLanguage'

const props = defineProps<{
  packageName: string | null
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
  (e: 'retrievalTest'): void
  (e: 'startProcessing'): void
  (e: 'processSelected'): void
}>()

const { t } = useLanguage()

const breadcrumb = computed(() => {
  const segments = [{ label: t('knowledge.header.title') }]
  if (props.packageName) {
    segments.push({ label: props.packageName })
  }
  return segments
})

const showStartProcessing = computed(() => props.pendingCount > 0)
const hasSelectedPending = computed(() => props.selectedPendingCount > 0)
</script>

<template>
  <div
    class="knowledge-space-header h-14 px-6 flex items-center justify-between border-b border-stone-200 bg-white shrink-0"
  >
    <nav
      aria-label="breadcrumb"
      class="flex min-w-0 flex-1 items-center gap-1 text-sm truncate"
    >
      <template
        v-for="(segment, index) in breadcrumb"
        :key="index"
      >
        <span
          v-if="index > 0"
          class="shrink-0 text-stone-400"
          aria-hidden="true"
        >
          /
        </span>
        <span
          class="truncate"
          :class="
            index === breadcrumb.length - 1
              ? 'font-semibold text-stone-900'
              : 'text-stone-500'
          "
        >
          {{ segment.label }}
        </span>
      </template>
      <span
        v-if="packageName"
        class="ml-2 shrink-0 text-sm text-stone-400"
      >
        ({{ documentCount }}/5)
      </span>
    </nav>

    <div class="flex items-center gap-2 shrink-0">
      <ElButton
        class="upload-btn"
        size="small"
        :disabled="!canUpload"
        @click="emit('upload')"
      >
        <ElIcon class="mr-1"><Upload /></ElIcon>
        {{ t('knowledge.header.upload') }}
      </ElButton>

      <span
        v-if="selectedCount > 0"
        class="selected-badge"
      >
        {{ t('knowledge.header.selected', { n: selectedCount }) }}
      </span>

      <ElButton
        v-if="hasSelectedPending"
        class="start-processing-btn"
        size="small"
        @click="emit('processSelected')"
      >
        <ElIcon class="mr-1"><VideoPlay /></ElIcon>
        {{ t('knowledge.header.processSelected', { n: selectedPendingCount }) }}
      </ElButton>

      <ElButton
        v-else-if="showStartProcessing && selectedCount === 0"
        class="start-processing-btn-secondary"
        size="small"
        @click="emit('startProcessing')"
      >
        <ElIcon class="mr-1"><VideoPlay /></ElIcon>
        {{ t('knowledge.header.processAll') }}
      </ElButton>

      <ElTooltip :content="t('knowledge.header.retrievalTest')">
        <ElButton
          text
          circle
          size="small"
          class="action-btn"
          :disabled="completedCount === 0"
          @click="emit('retrievalTest')"
        >
          <ElIcon><Search /></ElIcon>
        </ElButton>
      </ElTooltip>

      <ElTooltip :content="t('knowledge.header.settings')">
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

.action-btn {
  --el-button-text-color: #78716c;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
  --el-button-disabled-text-color: #d6d3d1;
  --el-button-disabled-bg-color: transparent;
}

.selected-badge {
  font-size: 13px;
  color: #3b82f6;
  font-weight: 500;
  padding: 4px 12px;
  background: #eff6ff;
  border-radius: 9999px;
}
</style>
