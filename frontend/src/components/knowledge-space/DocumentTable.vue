<script setup lang="ts">
/**
 * DocumentTable - Dify-style table listing for documents
 * Clean, minimal design with Swiss aesthetics
 */
import { computed } from 'vue'
import { ElTable, ElTableColumn, ElButton, ElBadge, ElIcon, ElEmpty, ElSkeleton, ElTag, ElCheckbox } from 'element-plus'
import { Delete, Document, Loading, Check, Close, View } from '@element-plus/icons-vue'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  documents: KnowledgeDocument[]
  loading: boolean
  selectedIds: number[]
  showDataset?: boolean
  greyOutDataset?: boolean
}>()

const emit = defineEmits<{
  delete: [id: number]
  view: [id: number]
  'update:selectedIds': [ids: number[]]
}>()

const { isZh } = useLanguage()

const sortedDocuments = computed(() => {
  return [...props.documents].sort((a, b) => {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
})

const statusConfig = (status: string) => {
  type BadgeType = 'success' | 'warning' | 'info' | 'danger'
  let type: BadgeType = 'info'
  let text = '未知'
  
  switch (status) {
    case 'pending':
      text = isZh ? '等待处理' : 'Pending'
      type = 'info'
      break
    case 'processing':
      text = isZh ? '处理中' : 'Processing'
      type = 'warning'
      break
    case 'completed':
      text = isZh ? '已完成' : 'Completed'
      type = 'success'
      break
    case 'failed':
      text = isZh ? '失败' : 'Failed'
      type = 'danger'
      break
  }
  
  return { text, type }
}

const formatFileSize = (size: number) => {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleDateString(isZh ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Convert MIME type to user-friendly file type name
 */
const getFileTypeName = (mimeType: string): string => {
  const mimeToName: Record<string, string> = {
    // Microsoft Office
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
    'application/msword': 'DOC',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
    'application/vnd.ms-excel': 'XLS',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
    'application/vnd.ms-powerpoint': 'PPT',
    
    // PDF
    'application/pdf': 'PDF',
    
    // Text
    'text/plain': 'TXT',
    'text/markdown': 'MD',
    'text/html': 'HTML',
    'text/csv': 'CSV',
    
    // Images
    'image/jpeg': 'JPG',
    'image/jpg': 'JPG',
    'image/png': 'PNG',
    'image/gif': 'GIF',
    'image/webp': 'WEBP',
    
    // Archives
    'application/zip': 'ZIP',
    'application/x-zip-compressed': 'ZIP',
    'application/x-rar-compressed': 'RAR',
    'application/x-7z-compressed': '7Z',
  }
  
  // Try exact match first
  if (mimeToName[mimeType]) {
    return mimeToName[mimeType]
  }
  
  // Try partial match for Office documents
  if (mimeType.includes('wordprocessingml')) return 'DOCX'
  if (mimeType.includes('spreadsheetml')) return 'XLSX'
  if (mimeType.includes('presentationml')) return 'PPTX'
  
  // Extract extension from MIME type as fallback
  const parts = mimeType.split('/')
  if (parts.length === 2) {
    const subtype = parts[1]
    // Try to extract meaningful part
    if (subtype.includes('word')) return 'DOC'
    if (subtype.includes('excel') || subtype.includes('spreadsheet')) return 'XLS'
    if (subtype.includes('powerpoint') || subtype.includes('presentation')) return 'PPT'
    // Return uppercase subtype as fallback
    return subtype.split('.')[0].toUpperCase()
  }
  
  return 'FILE'
}

// Selection logic
const isAllSelected = computed(() => {
  if (sortedDocuments.value.length === 0) return false
  return sortedDocuments.value.every(doc => props.selectedIds.includes(doc.id))
})

const isIndeterminate = computed(() => {
  const selectedCount = sortedDocuments.value.filter(doc => props.selectedIds.includes(doc.id)).length
  return selectedCount > 0 && selectedCount < sortedDocuments.value.length
})

const toggleSelectAll = (checked: boolean | string | number) => {
  if (checked) {
    emit('update:selectedIds', sortedDocuments.value.map(doc => doc.id))
  } else {
    emit('update:selectedIds', [])
  }
}

const toggleSelectRow = (docId: number, checked: boolean | string | number) => {
  if (checked) {
    emit('update:selectedIds', [...props.selectedIds, docId])
  } else {
    emit('update:selectedIds', props.selectedIds.filter(id => id !== docId))
  }
}

const isRowSelected = (docId: number) => props.selectedIds.includes(docId)
</script>

<template>
  <div class="document-table flex-1 overflow-hidden flex flex-col">
    <ElSkeleton v-if="loading" :rows="5" animated class="p-4" />
    <ElEmpty
      v-else-if="sortedDocuments.length === 0"
      :description="isZh ? '暂无文档，请上传文档开始构建知识库' : 'No documents yet. Upload documents to build your knowledge base.'"
      :image-size="120"
      class="flex-1 flex items-center justify-center"
    />
    <ElTable
      v-else
      :data="sortedDocuments"
      stripe
      class="document-table-el"
      :empty-text="isZh ? '暂无数据' : 'No data'"
    >
      <!-- Selection Column -->
      <ElTableColumn width="50" align="center">
        <template #header>
          <ElCheckbox
            :model-value="isAllSelected"
            :indeterminate="isIndeterminate"
            @change="toggleSelectAll"
          />
        </template>
        <template #default="{ row }">
          <ElCheckbox
            :model-value="isRowSelected(row.id)"
            @change="(val) => toggleSelectRow(row.id, val)"
          />
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '文档名称' : 'Document Name'" min-width="250">
        <template #default="{ row }">
          <div class="flex flex-col gap-1">
            <div class="flex items-center gap-3">
              <ElIcon class="text-stone-400" size="18">
                <Document />
              </ElIcon>
              <span class="font-medium text-stone-900 truncate">{{ row.file_name }}</span>
            </div>
            <!-- Error message display -->
            <div v-if="row.status === 'failed' && row.error_message" class="error-message mt-1.5 ml-9">
              <div class="flex items-start gap-1.5">
                <ElIcon class="text-red-600 mt-0.5" size="14">
                  <Close />
                </ElIcon>
                <div class="flex-1">
                  <span class="text-red-600 text-xs font-medium">{{ isZh ? '错误：' : 'Error: ' }}</span>
                  <span class="text-red-600 text-xs">{{ row.error_message }}</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '类型' : 'Type'" width="90" align="center">
        <template #default="{ row }">
          <ElTag size="small" type="info" effect="plain">
            {{ getFileTypeName(row.file_type) }}
          </ElTag>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '大小' : 'Size'" width="90" align="right">
        <template #default="{ row }">
          <span class="text-stone-600 text-sm">{{ formatFileSize(row.file_size) }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '状态' : 'Status'" width="110" align="center">
        <template #default="{ row }">
          <ElBadge 
            :type="statusConfig(row.status).type" 
            :value="statusConfig(row.status).text"
            class="status-badge"
          />
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '分块数' : 'Chunks'" width="90" align="center">
        <template #default="{ row }">
          <span v-if="row.status === 'completed'" class="text-stone-600 text-sm">
            {{ row.chunk_count || 0 }}
          </span>
          <span v-else class="text-stone-400">-</span>
        </template>
      </ElTableColumn>

      <ElTableColumn
        v-if="showDataset"
        :label="isZh ? '数据集' : 'Dataset'"
        width="120"
        align="center"
        :class-name="greyOutDataset ? 'dataset-column-greyed' : ''"
      >
        <template #default="{ row }">
          <span
            class="text-sm"
            :class="greyOutDataset ? 'text-stone-400' : 'text-stone-600'"
          >
            {{ (row as any).dataset_name || '-' }}
          </span>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '上传时间' : 'Upload Date'" width="140">
        <template #default="{ row }">
          <span class="text-stone-600 text-sm">{{ formatDate(row.created_at) }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '操作' : 'Actions'" width="140" fixed="right" align="center">
        <template #default="{ row }">
          <div class="flex items-center gap-1 justify-center">
            <ElButton
              text
              size="small"
              class="action-btn-view"
              @click="emit('view', row.id)"
            >
              <ElIcon><View /></ElIcon>
            </ElButton>
            <ElButton
              text
              type="danger"
              size="small"
              class="action-btn-delete"
              @click="emit('delete', row.id)"
            >
              <ElIcon><Delete /></ElIcon>
            </ElButton>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>
  </div>
</template>

<style scoped>
.document-table {
  background: white;
}

.document-table-el {
  --el-table-border-color: #e7e5e4;
  --el-table-header-bg-color: #fafaf9;
  --el-table-row-hover-bg-color: #fafaf9;
}

.document-table-el :deep(.el-table__header) {
  background-color: #fafaf9;
}

.document-table-el :deep(.el-table__header th) {
  background-color: #fafaf9;
  color: #57534e;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 12px 0;
}

.document-table-el :deep(.el-table__body td) {
  color: #57534e;
  font-size: 14px;
  padding: 14px 0;
  border-bottom: 1px solid #f5f5f4;
}

.document-table-el :deep(.el-table__row:hover) {
  background-color: #fafaf9;
}

.status-badge {
  font-size: 12px;
  padding: 2px 8px;
}

.action-btn-view {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
  padding: 6px;
}

.action-btn-delete {
  --el-button-text-color: #dc2626;
  --el-button-hover-text-color: #991b1b;
  --el-button-hover-bg-color: #fef2f2;
  padding: 6px;
}

.dataset-column-greyed :deep(.cell) {
  color: #a8a29e;
  opacity: 0.6;
}
</style>
