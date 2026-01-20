<script setup lang="ts">
/**
 * ChunkTestResultsPage - Display chunk test results with progress tracking
 * Route: /chunk-test/results/:testId
 * Shows real-time progress and final metrics table
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElProgress, ElTable, ElTableColumn, ElTag, ElIcon, ElButton, ElMessage, ElCard, ElMessageBox } from 'element-plus'
import { Loading, Check, CircleCheck, CircleClose, View } from '@element-plus/icons-vue'
import { Sparkles } from 'lucide-vue-next'
import { useChunkTestProgress, useChunkTestResult, useChunkTestChunks, useCancelChunkTest } from '@/composables/queries/useChunkTestQueries'
import { useLanguage } from '@/composables/useLanguage'

const route = useRoute()
const router = useRouter()
const { isZh } = useLanguage()

const testId = computed(() => parseInt(route.params.testId as string, 10))

const { data: progress, isLoading: isLoadingProgress } = useChunkTestProgress(testId.value)
const { data: result, isLoading: isLoadingResult } = useChunkTestResult(testId.value)
const cancelTestMutation = useCancelChunkTest()

// Chunk viewing state
const selectedMethod = ref<string>('')
const showChunks = ref(false)
const { data: chunksData, isLoading: isLoadingChunks } = useChunkTestChunks(
  computed(() => testId.value),
  computed(() => selectedMethod.value)
)

// Manual evaluation state
const showManualEvaluation = ref(false)
const evaluationMethod = ref<string>('')

const isProcessing = computed(() => {
  const status = progress.value?.status || result.value?.status
  return status === 'pending' || status === 'processing'
})

const isCompleted = computed(() => {
  const status = progress.value?.status || result.value?.status
  return status === 'completed'
})

const isFailed = computed(() => {
  const status = progress.value?.status || result.value?.status
  return status === 'failed'
})

const currentMethod = computed(() => progress.value?.current_method || result.value?.current_method)
const currentStage = computed(() => progress.value?.current_stage || result.value?.current_stage)
const progressPercent = computed(() => progress.value?.progress_percent || result.value?.progress_percent || 0)
const completedMethods = computed(() => progress.value?.completed_methods || result.value?.completed_methods || [])

const allMethods = ['spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk']

const stageLabels: Record<string, string> = {
  pending: isZh.value ? '等待中' : 'Pending',
  chunking: isZh.value ? '分块处理' : 'Chunking',
  retrieval: isZh.value ? '检索测试' : 'Retrieval Testing',
  evaluation: isZh.value ? '评估计算' : 'Evaluation',
  completed: isZh.value ? '已完成' : 'Completed',
  failed: isZh.value ? '失败' : 'Failed',
}

const methodLabels: Record<string, string> = {
  spacy: 'spaCy',
  semchunk: 'SemChunk',
  chonkie: 'Chonkie',
  langchain: 'LangChain',
  mindchunk: 'MindChunk',
}

// Watch for completion and fetch full results
watch(isCompleted, (completed) => {
  if (completed && !result.value) {
    // Results will be fetched automatically by useChunkTestResult
  }
}, { immediate: true })

// Prepare metrics table data
const metricsTableData = computed(() => {
  if (!result.value?.evaluation_results) {
    return []
  }

  const evalResults = result.value.evaluation_results
  const methods = allMethods

  return methods.map((method) => {
    const row: Record<string, any> = { method: methodLabels[method] || method }

    // Standard IR Metrics
    const standardIr = evalResults.standard_ir?.[method] || {}
    row.precision = standardIr.precision?.toFixed(3) || '-'
    row.recall = standardIr.recall?.toFixed(3) || '-'
    row.mrr = standardIr.mrr?.toFixed(3) || '-'
    row.ndcg = standardIr.ndcg?.toFixed(3) || '-'
    row.f1 = standardIr.f1?.toFixed(3) || '-'
    row.map = standardIr.map?.toFixed(3) || '-'

    // Chunk Quality
    const chunkQuality = evalResults.chunk_quality?.[method] || {}
    row.coverage_score = chunkQuality.coverage_score?.toFixed(3) || '-'
    row.semantic_coherence = chunkQuality.semantic_coherence?.toFixed(3) || '-'

    // Answer Quality
    const answerQuality = evalResults.answer_quality?.[method] || {}
    row.answer_coverage = answerQuality.answer_coverage?.toFixed(3) || '-'
    row.answer_completeness = answerQuality.answer_completeness?.toFixed(3) || '-'
    row.context_recall = answerQuality.context_recall?.toFixed(3) || '-'

    // Diversity & Efficiency
    const diversityEff = evalResults.diversity_efficiency?.[method] || {}
    row.storage_efficiency = diversityEff.storage_efficiency?.toFixed(3) || '-'
    row.semantic_diversity = diversityEff.semantic_diversity?.toFixed(3) || '-'
    row.avg_latency_ms = diversityEff.avg_latency_ms?.toFixed(1) || '-'

    return row
  })
})

const handleBack = () => {
  router.push('/chunk-test')
}

const getMethodKeyFromLabel = (label: string): string => {
  const reverseMap: Record<string, string> = {
    'spaCy': 'spacy',
    'SemChunk': 'semchunk',
    'Chonkie': 'chonkie',
    'LangChain': 'langchain',
    'MindChunk': 'mindchunk',
  }
  return reverseMap[label] || label.toLowerCase()
}

const handleViewChunks = (method: string) => {
  selectedMethod.value = method
  showChunks.value = true
}

const handleManualEvaluation = (method: string) => {
  evaluationMethod.value = method
  showManualEvaluation.value = true
}

const handleCloseChunks = () => {
  showChunks.value = false
  selectedMethod.value = ''
}

const handleCancelTest = async () => {
  try {
    await ElMessageBox.confirm(
      isZh.value
        ? '确定要取消这个测试吗？测试将在下一个检查点停止。'
        : 'Are you sure you want to cancel this test? The test will stop at the next checkpoint.',
      isZh.value ? '取消测试' : 'Cancel Test',
      {
        confirmButtonText: isZh.value ? '取消测试' : 'Cancel Test',
        cancelButtonText: isZh.value ? '返回' : 'Back',
        type: 'warning',
      }
    )

    await cancelTestMutation.mutateAsync(testId.value)
    ElMessage.success(
      isZh.value ? '测试取消请求已发送' : 'Test cancellation requested'
    )
  } catch (error) {
    if (error instanceof Error && error.message !== 'cancel') {
      ElMessage.error(
        error.message || (isZh.value ? '取消失败' : 'Failed to cancel test')
      )
    }
  }
}
</script>

<template>
  <div class="chunk-test-results-page flex-1 flex flex-col bg-white h-full overflow-hidden">
    <!-- Header -->
    <div class="h-14 px-6 flex items-center justify-between border-b border-stone-200 bg-white shrink-0">
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-semibold text-stone-900">
          {{ isZh ? 'RAG分块测试结果' : 'RAG Chunk Test Results' }}
        </h1>
        <span class="text-sm text-stone-500">#{{ testId }}</span>
      </div>
      <div class="flex items-center gap-2">
        <ElButton
          v-if="isProcessing"
          size="small"
          type="warning"
          @click="handleCancelTest"
          :loading="cancelTestMutation.isPending.value"
        >
          {{ isZh ? '取消测试' : 'Cancel Test' }}
        </ElButton>
        <ElButton size="small" @click="handleBack">
          {{ isZh ? '返回' : 'Back' }}
        </ElButton>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-auto p-6">
      <!-- Progress Display (shown when processing) -->
      <div v-if="isProcessing" class="mb-8">
        <div class="bg-stone-50 rounded-lg p-6 border border-stone-200">
          <div class="flex items-center gap-3 mb-4">
            <ElIcon class="text-blue-500 animate-spin">
              <Loading />
            </ElIcon>
            <h2 class="text-lg font-semibold text-stone-900">
              {{ isZh ? '测试进行中...' : 'Testing in progress...' }}
            </h2>
          </div>

          <!-- Current Method -->
          <div v-if="currentMethod" class="mb-4">
            <div class="text-sm text-stone-600 mb-2">
              {{ isZh ? '当前方法' : 'Current Method' }}
            </div>
            <ElTag type="primary" size="large">
              {{ methodLabels[currentMethod] || currentMethod }}
            </ElTag>
          </div>

          <!-- Current Stage -->
          <div v-if="currentStage" class="mb-4">
            <div class="text-sm text-stone-600 mb-2">
              {{ isZh ? '当前阶段' : 'Current Stage' }}
            </div>
            <ElTag type="info" size="large">
              {{ stageLabels[currentStage] || currentStage }}
            </ElTag>
          </div>

          <!-- Progress Bar -->
          <div class="mb-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm text-stone-600">
                {{ isZh ? '总体进度' : 'Overall Progress' }}
              </span>
              <span class="text-sm font-medium text-stone-900">
                {{ progressPercent }}%
              </span>
            </div>
            <ElProgress
              :percentage="progressPercent"
              :color="progressPercent < 50 ? '#3b82f6' : progressPercent < 80 ? '#8b5cf6' : '#10b981'"
              :stroke-width="8"
            />
          </div>

          <!-- Completed Methods -->
          <div>
            <div class="text-sm text-stone-600 mb-2">
              {{ isZh ? '已完成方法' : 'Completed Methods' }}
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <template v-for="(method, idx) in allMethods" :key="method">
                <template v-if="completedMethods.includes(method)">
                  <ElTag type="success" size="small">
                    <ElIcon class="mr-1"><Check /></ElIcon>
                    {{ methodLabels[method] || method }}
                  </ElTag>
                </template>
                <template v-else-if="currentMethod === method">
                  <ElTag type="primary" size="small">
                    <ElIcon class="mr-1 animate-spin"><Loading /></ElIcon>
                    {{ methodLabels[method] || method }}
                  </ElTag>
                </template>
                <template v-else>
                  <ElTag type="info" size="small" effect="plain">
                    {{ methodLabels[method] || method }}
                  </ElTag>
                </template>
                <span v-if="idx < allMethods.length - 1" class="text-stone-400">→</span>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Display -->
      <div v-if="isFailed" class="mb-8">
        <div class="bg-red-50 rounded-lg p-6 border border-red-200">
          <div class="flex items-center gap-3 mb-4">
            <ElIcon class="text-red-500">
              <CircleClose />
            </ElIcon>
            <h2 class="text-lg font-semibold text-red-900">
              {{ isZh ? '测试失败' : 'Test Failed' }}
            </h2>
          </div>
          <p class="text-stone-700">
            {{ isZh ? '测试执行过程中发生错误，请重试。' : 'An error occurred during test execution. Please try again.' }}
          </p>
        </div>
      </div>

      <!-- Results Table (shown when completed) -->
      <div v-if="isCompleted && metricsTableData.length > 0">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-stone-900">
            {{ isZh ? '评估指标' : 'Evaluation Metrics' }}
          </h2>
        </div>

        <div class="bg-white rounded-lg border border-stone-200 overflow-hidden">
          <ElTable :data="metricsTableData" stripe style="width: 100%">
            <ElTableColumn prop="method" :label="isZh ? '方法' : 'Method'" width="120" fixed="left" />
            <ElTableColumn :label="isZh ? '操作' : 'Actions'" width="240" fixed="right">
              <template #default="{ row }">
                <div class="flex items-center gap-2">
                  <ElButton
                    size="small"
                    type="primary"
                    link
                    @click="handleViewChunks(getMethodKeyFromLabel(row.method))"
                  >
                    <ElIcon class="mr-1"><View /></ElIcon>
                    {{ isZh ? '查看分块' : 'View Chunks' }}
                  </ElButton>
                  <ElButton
                    size="small"
                    type="success"
                    link
                    @click="handleManualEvaluation(getMethodKeyFromLabel(row.method))"
                  >
                    <ElIcon class="mr-1"><Sparkles /></ElIcon>
                    {{ isZh ? '手动评估' : 'Evaluate' }}
                  </ElButton>
                </div>
              </template>
            </ElTableColumn>

            <!-- Standard IR Metrics -->
            <ElTableColumn :label="isZh ? '标准IR指标' : 'Standard IR Metrics'" align="center">
              <ElTableColumn prop="precision" :label="isZh ? '精确率' : 'Precision'" width="100" />
              <ElTableColumn prop="recall" :label="isZh ? '召回率' : 'Recall'" width="100" />
              <ElTableColumn prop="mrr" label="MRR" width="100" />
              <ElTableColumn prop="ndcg" label="NDCG" width="100" />
              <ElTableColumn prop="f1" label="F1" width="100" />
              <ElTableColumn prop="map" label="MAP" width="100" />
            </ElTableColumn>

            <!-- Chunk Quality -->
            <ElTableColumn :label="isZh ? '分块质量' : 'Chunk Quality'" align="center">
              <ElTableColumn prop="coverage_score" :label="isZh ? '覆盖率' : 'Coverage'" width="120" />
              <ElTableColumn prop="semantic_coherence" :label="isZh ? '语义连贯性' : 'Coherence'" width="140" />
            </ElTableColumn>

            <!-- Answer Quality -->
            <ElTableColumn :label="isZh ? '答案质量' : 'Answer Quality'" align="center">
              <ElTableColumn prop="answer_coverage" :label="isZh ? '答案覆盖率' : 'Answer Coverage'" width="140" />
              <ElTableColumn prop="answer_completeness" :label="isZh ? '答案完整性' : 'Completeness'" width="140" />
              <ElTableColumn prop="context_recall" :label="isZh ? '上下文召回' : 'Context Recall'" width="140" />
            </ElTableColumn>

            <!-- Diversity & Efficiency -->
            <ElTableColumn :label="isZh ? '多样性 & 效率' : 'Diversity & Efficiency'" align="center">
              <ElTableColumn prop="storage_efficiency" :label="isZh ? '存储效率' : 'Storage Eff.'" width="130" />
              <ElTableColumn prop="semantic_diversity" :label="isZh ? '语义多样性' : 'Diversity'" width="130" />
              <ElTableColumn prop="avg_latency_ms" :label="isZh ? '平均延迟(ms)' : 'Avg Latency'" width="130" />
            </ElTableColumn>
          </ElTable>
        </div>
      </div>

      <!-- Chunks View (shown when viewing chunks) -->
      <div v-if="showChunks && isCompleted" class="mt-6">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-stone-900">
            {{ isZh ? `查看分块 - ${methodLabels[selectedMethod] || selectedMethod}` : `View Chunks - ${methodLabels[selectedMethod] || selectedMethod}` }}
          </h2>
          <ElButton size="small" @click="handleCloseChunks">
            {{ isZh ? '关闭' : 'Close' }}
          </ElButton>
        </div>
          <div v-if="isLoadingChunks" class="text-center py-8">
            <ElIcon class="text-stone-400 animate-spin text-4xl mb-4">
              <Loading />
            </ElIcon>
            <p class="text-stone-600">
              {{ isZh ? '正在生成分块...' : 'Generating chunks...' }}
            </p>
          </div>
          <div v-else-if="chunksData && chunksData.chunks.length > 0" class="chunks-container">
            <div class="mb-4 text-sm text-stone-600">
              {{ isZh ? `共 ${chunksData.chunks.length} 个分块` : `Total ${chunksData.chunks.length} chunks` }}
            </div>
            <div class="space-y-4">
              <ElCard
                v-for="(chunk, idx) in chunksData.chunks"
                :key="idx"
                shadow="hover"
                class="chunk-card"
              >
                <template #header>
                  <div class="flex items-center justify-between">
                    <span class="font-medium text-stone-900">
                      {{ isZh ? `分块 #${chunk.chunk_index + 1}` : `Chunk #${chunk.chunk_index + 1}` }}
                    </span>
                    <span v-if="chunk.start_char !== undefined && chunk.end_char !== undefined" class="text-xs text-stone-500">
                      {{ isZh ? `位置: ${chunk.start_char}-${chunk.end_char}` : `Position: ${chunk.start_char}-${chunk.end_char}` }}
                    </span>
                  </div>
                </template>
                <div class="chunk-content text-sm text-stone-700 leading-relaxed whitespace-pre-wrap">
                  {{ chunk.text }}
                </div>
                <div v-if="chunk.metadata && Object.keys(chunk.metadata).length > 0" class="mt-3 pt-3 border-t border-stone-200">
                  <div class="text-xs text-stone-500">
                    <div v-for="(value, key) in chunk.metadata" :key="key" class="mb-1">
                      <span class="font-medium">{{ key }}:</span> {{ value }}
                    </div>
                  </div>
                </div>
              </ElCard>
            </div>
          </div>
          <div v-else-if="chunksData && chunksData.chunks.length === 0" class="text-center py-8 text-stone-500">
            {{ isZh ? '没有找到分块' : 'No chunks found' }}
          </div>
        </div>

      <!-- Loading State -->
      <div v-if="isLoadingProgress && !progress" class="text-center py-12">
        <ElIcon class="text-stone-400 animate-spin text-4xl mb-4">
          <Loading />
        </ElIcon>
        <p class="text-stone-600">
          {{ isZh ? '加载中...' : 'Loading...' }}
        </p>
      </div>
    </div>

    <!-- Manual Evaluation Modal -->
    <ManualEvaluationModal
      v-model:visible="showManualEvaluation"
      :test-id="testId"
      :method="evaluationMethod"
    />
  </div>
</template>

<style scoped>
.chunk-test-results-page {
  width: 100%;
}

:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table th) {
  background-color: #fafaf9;
  color: #1c1917;
  font-weight: 600;
}

:deep(.el-table td) {
  color: #292524;
}

.chunks-container {
  max-height: 600px;
  overflow-y: auto;
}

.chunk-card {
  border: 1px solid #e7e5e4;
}

.chunk-card:hover {
  border-color: #d6d3d1;
}

.chunk-content {
  max-height: 300px;
  overflow-y: auto;
  padding: 8px;
  background-color: #fafaf9;
  border-radius: 4px;
}

:deep(.el-collapse-item__header) {
  font-weight: 600;
  color: #1c1917;
}

:deep(.el-collapse-item__content) {
  padding-bottom: 16px;
}
</style>
