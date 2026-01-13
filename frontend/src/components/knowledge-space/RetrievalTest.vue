<script setup lang="ts">
/**
 * RetrievalTest - Modal/drawer for testing retrieval functionality
 * Uses Vue Query mutation for state management
 */
import { ref, watch } from 'vue'
import { ElDrawer, ElForm, ElFormItem, ElInput, ElSelect, ElButton, ElTable, ElTableColumn, ElCard, ElDivider } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useLanguage } from '@/composables/useLanguage'
import { useRetrievalTest, type RetrievalTestResponse } from '@/composables/queries'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
}>()

const { isZh } = useLanguage()

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
  (error) => {
    // Error handling is done in mutation's onError callback
    // This watch is just for reactivity if needed
  }
)

function testRetrieval() {
  if (!query.value.trim()) {
    ElMessage.warning(isZh.value ? '请输入测试查询' : 'Please enter a test query')
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
    :title="isZh ? '检索测试' : 'Retrieval Test'"
    size="800px"
    @update:model-value="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div class="retrieval-test-content p-4">
      <ElForm :model="{ query, method, topK, scoreThreshold }" label-width="120px" label-position="left">
        <ElFormItem :label="isZh ? '测试查询' : 'Test Query'">
          <ElInput
            v-model="query"
            :placeholder="isZh ? '输入测试查询...' : 'Enter test query...'"
            :maxlength="250"
            show-word-limit
          />
        </ElFormItem>
        <ElFormItem :label="isZh ? '检索方法' : 'Retrieval Method'">
          <ElSelect v-model="method" style="width: 100%">
            <el-option :label="isZh ? '混合检索' : 'Hybrid Search'" value="hybrid" />
            <el-option :label="isZh ? '语义检索' : 'Semantic Search'" value="semantic" />
            <el-option :label="isZh ? '关键词检索' : 'Keyword Search'" value="keyword" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="isZh ? '返回数量' : 'Top K'">
          <ElSelect v-model="topK" style="width: 120px">
            <el-option :label="i" :value="i" v-for="i in [1, 3, 5, 10]" :key="i" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem :label="isZh ? '分数阈值' : 'Score Threshold'">
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
            {{ isZh ? '测试检索' : 'Test Retrieval' }}
          </ElButton>
        </ElFormItem>
      </ElForm>

      <ElDivider v-if="results" />

      <div v-if="results" class="mt-6">
        <ElCard shadow="never" class="results-card">
          <template #header>
            <div class="flex justify-between items-center">
              <span class="font-semibold">{{ isZh ? '检索结果' : 'Retrieval Results' }}</span>
              <div class="text-sm text-stone-500">
                {{ isZh ? '耗时' : 'Time' }}: {{ results.timing.total_ms.toFixed(0) }}ms
                ({{ isZh ? '嵌入' : 'Embed' }}: {{ results.timing.embedding_ms.toFixed(0) }}ms,
                {{ isZh ? '搜索' : 'Search' }}: {{ results.timing.search_ms.toFixed(0) }}ms,
                {{ isZh ? '重排' : 'Rerank' }}: {{ results.timing.rerank_ms.toFixed(0) }}ms)
              </div>
            </div>
          </template>

          <ElTable :data="results.results" stripe class="results-table">
            <ElTableColumn :label="isZh ? '文档' : 'Document'" width="150">
              <template #default="{ row }">
                <span class="text-stone-700">{{ row.document_name }}</span>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="isZh ? '分数' : 'Score'" width="100">
              <template #default="{ row }">
                <span :class="row.score > 0.7 ? 'text-green-600' : row.score > 0.5 ? 'text-yellow-600' : 'text-stone-600'">
                  {{ row.score.toFixed(3) }}
                </span>
              </template>
            </ElTableColumn>
            <ElTableColumn :label="isZh ? '内容' : 'Content'" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="text-stone-700">{{ row.text.substring(0, 200) }}{{ row.text.length > 200 ? '...' : '' }}</div>
              </template>
            </ElTableColumn>
          </ElTable>

          <div class="mt-4 text-sm text-stone-500 space-y-1">
            <div>{{ isZh ? '总搜索块数' : 'Total chunks searched' }}: {{ results.stats.total_chunks_searched }}</div>
            <div>{{ isZh ? '重排前' : 'Before rerank' }}: {{ results.stats.chunks_before_rerank }}</div>
            <div>{{ isZh ? '重排后' : 'After rerank' }}: {{ results.stats.chunks_after_rerank }}</div>
            <div>{{ isZh ? '阈值过滤' : 'Filtered by threshold' }}: {{ results.stats.chunks_filtered_by_threshold }}</div>
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
