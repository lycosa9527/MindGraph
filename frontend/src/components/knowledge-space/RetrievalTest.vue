<script setup lang="ts">
/**
 * RetrievalTest - Modal/drawer for testing retrieval functionality
 * Uses Vue Query mutation for state management
 */
import { ref, watch } from 'vue'

import {
  ElButton,
  ElCard,
  ElDivider,
  ElDrawer,
  ElForm,
  ElFormItem,
  ElInput,
  ElSelect,
  ElTable,
  ElTableColumn,
} from 'element-plus'

import { Search } from '@element-plus/icons-vue'

import { notify } from '@/composables/core/notifications'
import { type RetrievalTestResponse, useRetrievalTest } from '@/composables/queries'
import { useLanguage } from '@/composables/core/useLanguage'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { t } = useLanguage()

const query = ref('')
const method = ref<'hybrid' | 'semantic' | 'keyword'>('hybrid')
const topK = ref(5)
const scoreThreshold = ref(0.0)
const results = ref<RetrievalTestResponse | null>(null)

// Use Vue Query mutation
const retrievalTestMutation = useRetrievalTest()

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
  // Reset form when closing
  query.value = ''
  results.value = null
  // Reset mutation state
  retrievalTestMutation.reset()
}

// Watch for mutation success to update results
watch(
  () => retrievalTestMutation.data.value,
  (data) => {
    if (data) {
      results.value = data
    }
  }
)

// Watch for mutation error (error handling is done in mutation onError)
watch(
  () => retrievalTestMutation.error.value,
  (_error) => {
    // Error handling is done in mutation's onError callback
    // This watch is just for reactivity if needed
  }
)

function testRetrieval() {
  if (!query.value.trim()) {
    notify.warning(t('knowledge.retrieval.enterQuery'))
    return
  }

  retrievalTestMutation.mutate({
    query: query.value,
    method: method.value,
    top_k: topK.value,
    score_threshold: scoreThreshold.value,
  })
}
</script>

<template>
  <ElDrawer
    :model-value="visible"
    :title="t('knowledge.retrieval.title')"
    size="800px"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div class="retrieval-test-content p-4">
      <ElForm
        :model="{ query, method, topK, scoreThreshold }"
        label-width="120px"
        label-position="left"
      >
        <ElFormItem :label="t('knowledge.retrieval.testQuery')">
          <ElInput
            v-model="query"
            :placeholder="t('knowledge.retrieval.testQueryPlaceholder')"
            :maxlength="250"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem :label="t('knowledge.retrieval.method')">
          <ElSelect
            v-model="method"
            style="width: 100%"
          >
            <el-option
              :label="t('knowledge.retrieval.hybrid')"
              value="hybrid"
            />
            <el-option
              :label="t('knowledge.retrieval.semantic')"
              value="semantic"
            />
            <el-option
              :label="t('knowledge.retrieval.keyword')"
              value="keyword"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="t('knowledge.retrieval.topK')">
          <ElSelect
            v-model="topK"
            style="width: 120px"
          >
            <el-option
              v-for="i in [1, 3, 5, 10]"
              :key="i"
              :label="i"
              :value="i"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="t('knowledge.retrieval.scoreThreshold')">
          <ElInput
            v-model.number="scoreThreshold"
            type="number"
            :min="0"
            :max="1"
            :step="0.1"
            style="width: 120px"
          />
        </ElFormItem>
        <ElFormItem>
          <ElButton
            type="primary"
            :icon="Search"
            :loading="retrievalTestMutation.isPending.value"
            class="test-btn"
            @click="testRetrieval"
          >
            {{ t('knowledge.retrieval.run') }}
          </ElButton>
        </ElFormItem>
      </ElForm>

      <ElDivider v-if="results" />

      <div
        v-if="results"
        class="mt-6"
      >
        <ElCard
          shadow="never"
          class="results-card"
        >
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-semibold">{{ t('knowledge.retrieval.results') }}</span>
              <div class="text-sm text-stone-500">
                {{ t('knowledge.retrieval.timingTotal') }}:
                {{ results.timing.total_ms.toFixed(0) }}ms ({{
                  t('knowledge.retrieval.timingEmbed')
                }}: {{ results.timing.embedding_ms.toFixed(0) }}ms,
                {{ t('knowledge.retrieval.timingSearch') }}:
                {{ results.timing.search_ms.toFixed(0) }}ms,
                {{ t('knowledge.retrieval.timingRerank') }}:
                {{ results.timing.rerank_ms.toFixed(0) }}ms)
              </div>
            </div>
          </template>

          <ElTable
            :data="results.results"
            stripe
            class="results-table"
          >
            <ElTableColumn
              :label="t('knowledge.retrieval.colDocument')"
              width="150"
            >
              <template #default="{ row }">
                <span class="text-stone-700">{{ row.document_name }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn
              :label="t('knowledge.retrieval.colScore')"
              width="100"
            >
              <template #default="{ row }">
                <span
                  :class="
                    row.score > 0.7
                      ? 'text-green-600'
                      : row.score > 0.5
                        ? 'text-yellow-600'
                        : 'text-stone-600'
                  "
                >
                  {{ row.score.toFixed(3) }}
                </span>
              </template>
            </ElTableColumn>
            <ElTableColumn
              :label="t('knowledge.retrieval.colContent')"
              show-overflow-tooltip
            >
              <template #default="{ row }">
                <div class="text-stone-700">
                  {{ row.text.substring(0, 200) }}{{ row.text.length > 200 ? '...' : '' }}
                </div>
              </template>
            </ElTableColumn>
          </ElTable>

          <div class="mt-4 text-sm text-stone-500 space-y-1">
            <div>
              {{ t('knowledge.retrieval.statsTotalChunks') }}:
              {{ results.stats.total_chunks_searched }}
            </div>
            <div>
              {{ t('knowledge.retrieval.statsBeforeRerank') }}:
              {{ results.stats.chunks_before_rerank }}
            </div>
            <div>
              {{ t('knowledge.retrieval.statsAfterRerank') }}:
              {{ results.stats.chunks_after_rerank }}
            </div>
            <div>
              {{ t('knowledge.retrieval.statsFiltered') }}:
              {{ results.stats.chunks_filtered_by_threshold }}
            </div>
          </div>
        </ElCard>
      </div>
    </div>
  </ElDrawer>
</template>

<style scoped>
.retrieval-test-content {
  height: 100%;
  overflow-y: auto;
}

.test-btn {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  font-weight: 500;
}

.results-card {
  --el-card-border-color: #e7e5e4;
}

.results-table {
  --el-table-border-color: #e7e5e4;
  --el-table-header-bg-color: #f5f5f4;
  --el-table-row-hover-bg-color: #fafaf9;
}
</style>
