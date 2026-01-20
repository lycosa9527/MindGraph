<script setup lang="ts">
/**
 * ChunkTestHeader - Header component for Chunk Test page
 * Swiss design style matching KnowledgeSpaceHeader
 */
import { computed } from 'vue'
import { ElButton, ElIcon, ElTooltip } from 'element-plus'
import { Upload, VideoPlay, RefreshRight } from '@element-plus/icons-vue'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  documentCount: number
  canUpload: boolean
  hasDocuments: boolean
  hasPendingDocuments?: boolean
}>()

const emit = defineEmits<{
  (e: 'upload'): void
  (e: 'test-user-documents'): void
  (e: 'test-all-datasets'): void
  (e: 'process-documents'): void
}>()

const { isZh } = useLanguage()
</script>

<template>
  <div
    class="chunk-test-header h-14 px-6 flex items-center justify-between border-b border-stone-200 bg-white shrink-0"
  >
    <div class="flex items-center gap-3 min-w-0 flex-1">
      <h1 class="text-lg font-semibold text-stone-900">
        {{ isZh ? 'RAG分块测试' : 'RAG Chunk Test' }}
      </h1>
      <span class="text-sm text-stone-500">
        {{ isZh ? `(${documentCount}/5)` : `(${documentCount}/5)` }}
      </span>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <!-- Process Documents Button -->
      <ElTooltip
        :content="isZh ? '处理待处理的文档' : 'Process pending documents'"
        :disabled="hasPendingDocuments"
        placement="bottom"
      >
        <ElButton
          class="process-docs-btn"
          size="small"
          :disabled="!hasPendingDocuments"
          @click="emit('process-documents')"
        >
          <ElIcon class="mr-1"><RefreshRight /></ElIcon>
          {{ isZh ? '处理文档' : 'Process Documents' }}
        </ElButton>
      </ElTooltip>
      <!-- Test Upload Documents Button -->
      <ElTooltip
        :content="isZh ? '请等待文档处理完成后再进行测试' : 'Please wait for documents to finish processing before testing'"
        :disabled="hasDocuments"
        placement="bottom"
      >
        <ElButton
          class="test-user-docs-btn"
          size="small"
          :disabled="!hasDocuments"
          @click="emit('test-user-documents')"
        >
          <ElIcon class="mr-1"><VideoPlay /></ElIcon>
          {{ isZh ? '测试上传文档' : 'Test Upload Documents' }}
        </ElButton>
      </ElTooltip>
      <!-- Test All Datasets Button -->
      <ElButton
        class="test-all-datasets-btn"
        size="small"
        @click="emit('test-all-datasets')"
      >
        <ElIcon class="mr-1"><VideoPlay /></ElIcon>
        {{ isZh ? '测试所有数据集' : 'Test All Datasets' }}
      </ElButton>
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
    </div>
  </div>
</template>

<style scoped>
/* Test Upload Documents button - Swiss Design style (blue accent) */
.test-user-docs-btn {
  --el-button-bg-color: #3b82f6;
  --el-button-border-color: #3b82f6;
  --el-button-hover-bg-color: #2563eb;
  --el-button-hover-border-color: #2563eb;
  --el-button-active-bg-color: #1d4ed8;
  --el-button-active-border-color: #1d4ed8;
  --el-button-text-color: #ffffff;
  --el-button-disabled-bg-color: #f5f5f4;
  --el-button-disabled-text-color: #a8a29e;
  font-weight: 500;
  border-radius: 9999px;
}

/* Test All Datasets button - Swiss Design style (blue accent) */
.test-all-datasets-btn {
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

/* Process Documents button - Swiss Design style (green accent) */
.process-docs-btn {
  --el-button-bg-color: #10b981;
  --el-button-border-color: #10b981;
  --el-button-hover-bg-color: #059669;
  --el-button-hover-border-color: #059669;
  --el-button-active-bg-color: #047857;
  --el-button-active-border-color: #047857;
  --el-button-text-color: #ffffff;
  --el-button-disabled-bg-color: #f5f5f4;
  --el-button-disabled-text-color: #a8a29e;
  font-weight: 500;
  border-radius: 9999px;
}

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
</style>
