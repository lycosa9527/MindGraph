<script setup lang="ts">
/**
 * DocumentCard - Individual document card component
 */
import { computed } from 'vue'
import { ElCard, ElBadge, ElButton, ElIcon } from 'element-plus'
import { Delete, Document, Loading, Check, Close } from '@element-plus/icons-vue'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'

const props = defineProps<{
  document: KnowledgeDocument
}>()

const emit = defineEmits<{
  delete: [id: number]
}>()

const statusConfig = computed(() => {
  type BadgeType = 'success' | 'warning' | 'info' | 'primary' | 'danger'
  let type: BadgeType = 'info'
  let text = '未知'
  let icon = Document
  
  switch (props.document.status) {
    case 'pending':
      text = '等待处理'
      type = 'info'
      icon = Document
      break
    case 'processing':
      text = '处理中...'
      type = 'warning'
      icon = Loading
      break
    case 'completed':
      text = '已完成'
      type = 'success'
      icon = Check
      break
    case 'failed':
      text = '处理失败'
      type = 'danger'
      icon = Close
      break
  }
  
  return { text, type, icon }
})

const fileSize = computed(() => {
  const size = props.document.file_size
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
})

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
</script>

<template>
  <ElCard class="document-card" shadow="hover">
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2 flex-1 min-w-0">
          <ElIcon class="text-stone-500">
            <Document />
          </ElIcon>
          <span class="font-medium text-stone-900 truncate">
            {{ document.file_name }}
          </span>
        </div>
        <ElBadge :type="statusConfig.type" :value="statusConfig.text" />
      </div>
    </template>

    <div class="document-info space-y-2">
      <div class="text-sm text-stone-600">
        <div>文件类型: {{ document.file_type }}</div>
        <div>文件大小: {{ fileSize }}</div>
        <div>上传时间: {{ formatDate(document.created_at) }}</div>
        <div v-if="document.status === 'completed'">
          分块数量: {{ document.chunk_count }}
        </div>
        <div v-if="document.status === 'failed' && document.error_message" class="text-red-600 mt-2">
          错误: {{ document.error_message }}
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end">
        <ElButton
          type="danger"
          :icon="Delete"
          size="small"
          @click="emit('delete', document.id)"
        >
          删除
        </ElButton>
      </div>
    </template>
  </ElCard>
</template>

<style scoped>
.document-card {
  height: 100%;
}
</style>
