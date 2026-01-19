<script setup lang="ts">
/**
 * DatasetTable - Table for displaying benchmark datasets
 * Similar to DocumentTable but for datasets
 */
import { computed } from 'vue'
import { ElTable, ElTableColumn, ElButton, ElIcon, ElEmpty, ElSkeleton, ElTag } from 'element-plus'
import { Document, Link } from '@element-plus/icons-vue'
import type { Benchmark } from '@/composables/queries/useChunkTestQueries'
import { useLanguage } from '@/composables/useLanguage'

const props = defineProps<{
  datasets: Benchmark[]
  loading: boolean
}>()

const emit = defineEmits<{
  test: [datasetName: string]
}>()

const { isZh } = useLanguage()

const sortedDatasets = computed(() => {
  return [...props.datasets].sort((a, b) => a.name.localeCompare(b.name))
})

const formatDate = (dateString?: string) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleDateString(isZh ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

const getVersionInfo = (dataset: Benchmark) => {
  const parts: string[] = []
  if (dataset.version) {
    parts.push(dataset.version)
  }
  if (dataset.updated_at) {
    parts.push(formatDate(dataset.updated_at))
  }
  return parts.length > 0 ? parts.join(' / ') : '-'
}
</script>

<template>
  <div class="dataset-table flex-1 overflow-hidden flex flex-col">
    <ElSkeleton v-if="loading" :rows="5" animated class="p-4" />
    <ElEmpty
      v-else-if="sortedDatasets.length === 0"
      :description="isZh ? '暂无数据集' : 'No datasets available'"
      :image-size="120"
      class="flex-1 flex items-center justify-center"
    />
    <ElTable
      v-else
      :data="sortedDatasets"
      stripe
      class="dataset-table-el"
      :empty-text="isZh ? '暂无数据' : 'No data'"
    >
      <ElTableColumn :label="isZh ? '数据集名称' : 'Dataset Name'" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <ElIcon class="text-stone-400 shrink-0" size="16">
              <Document />
            </ElIcon>
            <span class="font-medium text-stone-900 truncate">{{ row.name }}</span>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '描述' : 'Description'" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="text-stone-600 text-sm truncate block">{{ row.description }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '来源' : 'Source'" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <span class="text-stone-500 text-sm truncate">{{ row.source }}</span>
            <ElIcon class="text-stone-400 shrink-0" size="12">
              <Link />
            </ElIcon>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn :label="isZh ? '版本/日期' : 'Version/Date'" width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="text-stone-600 text-sm truncate">{{ getVersionInfo(row) }}</span>
        </template>
      </ElTableColumn>
    </ElTable>
  </div>
</template>

<style scoped>
.dataset-table {
  background: white;
}

.dataset-table-el {
  --el-table-border-color: #e7e5e4;
  --el-table-header-bg-color: #fafaf9;
  --el-table-row-hover-bg-color: #fafaf9;
}

.dataset-table-el :deep(.el-table__header) {
  background-color: #fafaf9;
}

.dataset-table-el :deep(.el-table__header th) {
  background-color: #fafaf9;
  color: #57534e;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 12px 0;
}

.dataset-table-el :deep(.el-table__body td) {
  color: #57534e;
  font-size: 14px;
  padding: 14px 0;
  border-bottom: 1px solid #f5f5f4;
  white-space: nowrap;
}

.dataset-table-el :deep(.el-table__body td .cell) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dataset-table-el :deep(.el-table__row:hover) {
  background-color: #fafaf9;
}

</style>
