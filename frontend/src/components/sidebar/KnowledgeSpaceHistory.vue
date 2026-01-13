<script setup lang="ts">
/**
 * KnowledgeSpaceHistory - Sidebar history component for knowledge space documents
 */
import { computed, onMounted } from 'vue'
import { ElScrollbar, ElEmpty } from 'element-plus'
import { Document } from '@element-plus/icons-vue'
import { useKnowledgeSpace } from '@/composables/useKnowledgeSpace'

const { documents: allDocuments, fetchDocuments } = useKnowledgeSpace()

const documents = computed(() => allDocuments.value.slice(0, 10)) // Show last 10

onMounted(() => {
  fetchDocuments()
})

function formatDate(dateString: string) {
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
  })
}

function getStatusColor(status: string) {
  switch (status) {
    case 'completed':
      return 'text-green-600'
    case 'processing':
      return 'text-blue-600'
    case 'failed':
      return 'text-red-600'
    default:
      return 'text-gray-600'
  }
}
</script>

<template>
  <div class="knowledge-space-history flex flex-col h-full border-t border-stone-200 relative overflow-hidden">
    <!-- Header -->
    <div class="px-4 py-3">
      <div class="text-xs font-medium text-stone-400 uppercase tracking-wider">
        知识库文档
      </div>
    </div>

    <ElScrollbar class="flex-1 px-4 pb-4">
      <div v-if="documents.length === 0" class="text-center py-8">
        <ElEmpty description="暂无文档" :image-size="60" />
      </div>
      <div v-else>
        <div
          v-for="doc in documents"
          :key="doc.id"
          class="document-item"
        >
          <div class="flex items-center gap-2 min-w-0">
            <ElIcon class="text-stone-500 shrink-0">
              <Document />
            </ElIcon>
            <div class="flex-1 min-w-0">
              <div class="doc-name truncate">
                {{ doc.file_name }}
              </div>
              <div class="doc-meta flex items-center gap-2">
                <span>{{ formatDate(doc.created_at) }}</span>
                <span :class="getStatusColor(doc.status)">
                  {{ doc.status === 'completed' ? '已完成' : doc.status === 'processing' ? '处理中' : doc.status === 'failed' ? '失败' : '等待' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ElScrollbar>
  </div>
</template>

<style scoped>
.knowledge-space-history {
  min-height: 120px;
}

.document-item {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 6px 8px;
  border-radius: 6px;
  color: #57534e;
  font-size: 13px;
  text-align: left;
  transition: background-color 0.15s ease;
  cursor: pointer;
  border: none;
  background: transparent;
}

.document-item:hover {
  background-color: #f5f5f4;
}

.doc-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #57534e;
  font-size: 13px;
}

.doc-meta {
  font-size: 10px;
  color: #a8a29e;
  margin-top: 1px;
}
</style>
