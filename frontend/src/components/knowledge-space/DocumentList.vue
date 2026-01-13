<script setup lang="ts">
/**
 * DocumentList - List of uploaded documents
 */
import { computed } from 'vue'
import { ElCard, ElEmpty, ElSkeleton } from 'element-plus'
import type { KnowledgeDocument } from '@/stores/knowledgeSpace'
import DocumentCard from './DocumentCard.vue'

const props = defineProps<{
  documents: KnowledgeDocument[]
  loading: boolean
}>()

const emit = defineEmits<{
  delete: [id: number]
  refresh: []
}>()

const sortedDocuments = computed(() => {
  return [...props.documents].sort((a, b) => {
    // Sort by created_at descending
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
})
</script>

<template>
  <div class="document-list">
    <ElSkeleton v-if="loading" :rows="3" animated />
    <div v-else-if="sortedDocuments.length === 0" class="empty-state">
      <ElEmpty description="暂无文档" />
    </div>
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <DocumentCard
        v-for="document in sortedDocuments"
        :key="document.id"
        :document="document"
        @delete="emit('delete', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.document-list {
  min-height: 200px;
}
</style>
