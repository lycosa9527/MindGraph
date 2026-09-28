<script setup lang="ts">
/**
 * ChunkTestResultsPage - Display chunk test results with progress tracking
 * Route: /chunk-test/results/:testId
 * Shows real-time progress and final metrics table
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ElButton, ElCard, ElIcon, ElProgress, ElTable, ElTableColumn, ElTag } from 'element-plus'

import { Check, CircleClose, Loading, View } from '@element-plus/icons-vue'

import { Sparkles } from '@lucide/vue'

import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'
import { notify } from '@/composables/core/notifications'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  useCancelChunkTest,
  useChunkTestChunks,
  useChunkTestProgress,
  useChunkTestResult,
} from '@/composables/queries/useChunkTestQueries'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()

const testId = computed(() => parseInt(route.params.testId as string, 10))

const { data: progress, isLoading: isLoadingProgress } = useChunkTestProgress(testId.value)
const { data: result } = useChunkTestResult(testId.value)
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
const progressPercent = computed(
  () => progress.value?.progress_percent || result.value?.progress_percent || 0
)
const completedMethods = computed(
  () => progress.value?.completed_methods || result.value?.completed_methods || []
)

const allMethods = ['spacy', 'semchunk', 'chonkie', 'langchain', 'mindchunk']

const stageLabels = computed((): Record<string, string> => ({
  pending: t('chunkTest.stage.pending'),
  chunking: t('chunkTest.stage.chunking'),
  retrieval: t('chunkTest.stage.retrieval'),
  evaluation: t('chunkTest.stage.evaluation'),
  completed: t('chunkTest.stage.completed'),
  failed: t('chunkTest.stage.failed'),
}))

const methodLabels: Record<string, string> = {
  spacy: 'spaCy',
  semchunk: 'SemChunk',
  chonkie: 'Chonkie',
  langchain: 'LangChain',
  mindchunk: 'MindChunk',
}

/** Per-method metric rows from API evaluation_results buckets */
type MethodMetricRow = Record<string, number | undefined>

interface EvalResultsBuckets {
  standard_ir?: Record<string, MethodMetricRow>
  chunk_quality?: Record<string, MethodMetricRow>
  answer_quality?: Record<string, MethodMetricRow>
  diversity_efficiency?: Record<string, MethodMetricRow>
}

// Watch for completion and fetch full results
watch(
  isCompleted,
  (completed) => {
    if (completed && !result.value) {
      // Results will be fetched automatically by useChunkTestResult
    }
  },
  { immediate: true }
)

// Prepare metrics table data
const metricsTableData = computed(() => {
  if (!result.value?.evaluation_results) {
    return []
  }

  const evalResults = result.value.evaluation_results as EvalResultsBuckets
  const methods = allMethods

  return methods.map((method) => {
    const row: Record<string, string> = { method: methodLabels[method] || method }

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
    spaCy: 'spacy',
    SemChunk: 'semchunk',
    Chonkie: 'chonkie',
    LangChain: 'langchain',
    MindChunk: 'mindchunk',
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
    await swissGlassConfirm(
      t('chunkTestResults.cancelConfirmBody'),
      t('chunkTestResults.cancelTest'),
      {
        confirmButtonText: t('chunkTestResults.cancelTest'),
        cancelButtonText: t('chunkTestResults.back'),
        type: 'warning',
      }
    )

    await cancelTestMutation.mutateAsync(testId.value)
    notify.success(t('chunkTestResults.cancelRequested'))
  } catch (error) {
    if (error instanceof Error && error.message !== 'cancel') {
      notify.error(error.message || t('chunkTestResults.cancelFailed'))
    }
  }
}
</script>

<template>
  <div class="chunk-test-results-page flex-1 flex flex-col bg-white h-full overflow-hidden">
    <!-- Header -->
    <div
      class="h-14 px-6 flex items-center justify-between border-b border-stone-200 bg-white shrink-0"
    >
      <div class="flex items-center gap-3">
        <h1 class="text-lg font-semibold text-stone-900">
          <I18nText k="chunkTestResults.pageTitle" />
        </h1>
        <span class="text-sm text-stone-500">#{{ testId }}</span>
      </div>
      <div class="flex items-center gap-2">
        <ElButton
          v-if="isProcessing"
          size="small"
          type="warning"
          :loading="cancelTestMutation.isPending.value"
          @click="handleCancelTest"
        >
          <I18nText k="chunkTestResults.cancelTest" />
        </ElButton>
        <ElButton
          size="small"
          @click="handleBack"
        >
          <I18nText k="chunkTestResults.back" />
        </ElButton>
      </div>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-auto p-6">
      <!-- Progress Display (shown when processing) -->
      <div
        v-if="isProcessing"
        class="mb-8"
      >
        <div class="bg-stone-50 rounded-lg p-6 border border-stone-200">
          <div class="flex items-center gap-3 mb-4">
            <ElIcon class="text-blue-500 animate-spin">
              <Loading />
            </ElIcon>
            <h2 class="text-lg font-semibold text-stone-900">
              <I18nText k="chunkTestResults.testingInProgress" />
            </h2>
          </div>

          <!-- Current Method -->
          <div
            v-if="currentMethod"
            class="mb-4"
          >
            <div class="text-sm text-stone-600 mb-2">
              <I18nText k="chunkTestResults.currentMethod" />
            </div>
            <ElTag
              type="primary"
              size="large"
            >
              {{ methodLabels[currentMethod] || currentMethod }}
            </ElTag>
          </div>

          <!-- Current Stage -->
          <div
            v-if="currentStage"
            class="mb-4"
          >
            <div class="text-sm text-stone-600 mb-2">
              <I18nText k="chunkTestResults.currentStage" />
            </div>
            <ElTag
              type="info"
              size="large"
            >
              {{ stageLabels[currentStage] ?? currentStage }}
            </ElTag>
          </div>

          <!-- Progress Bar -->
          <div class="mb-4">
            <div class="flex items-center justify-between mb-2">
              <span class="text-sm text-stone-600">
                <I18nText k="chunkTestResults.overallProgress" />
              </span>
              <span class="text-sm font-medium text-stone-900"> {{ progressPercent }}% </span>
            </div>
            <ElProgress
              :percentage="progressPercent"
              :color="
                progressPercent < 50 ? '#3b82f6' : progressPercent < 80 ? '#8b5cf6' : '#10b981'
              "
              :stroke-width="8"
            />
          </div>

          <!-- Completed Methods -->
          <div>
            <div class="text-sm text-stone-600 mb-2">
              <I18nText k="chunkTestResults.completedMethods" />
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <template
                v-for="(method, idx) in allMethods"
                :key="method"
              >
                <template v-if="completedMethods.includes(method)">
                  <ElTag
                    type="success"
                    size="small"
                  >
                    <ElIcon class="mr-1"><Check /></ElIcon>
                    {{ methodLabels[method] || method }}
                  </ElTag>
                </template>
                <template v-else-if="currentMethod === method">
                  <ElTag
                    type="primary"
                    size="small"
                  >
                    <ElIcon class="mr-1 animate-spin"><Loading /></ElIcon>
                    {{ methodLabels[method] || method }}
                  </ElTag>
                </template>
                <template v-else>
                  <ElTag
                    type="info"
                    size="small"
                    effect="plain"
                  >
                    {{ methodLabels[method] || method }}
                  </ElTag>
                </template>
                <span
                  v-if="idx < allMethods.length - 1"
                  class="text-stone-400"
                  >→</span
                >
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Display -->
      <div
        v-if="isFailed"
        class="mb-8"
      >
        <div class="bg-red-50 rounded-lg p-6 border border-red-200">
          <div class="flex items-center gap-3 mb-4">
            <ElIcon class="text-red-500">
              <CircleClose />
            </ElIcon>
            <h2 class="text-lg font-semibold text-red-900">
              <I18nText k="chunkTestResults.testFailed" />
            </h2>
          </div>
          <p class="text-stone-700">
            <I18nText k="chunkTestResults.testFailedHint" />
          </p>
        </div>
      </div>

      <!-- Results Table (shown when completed) -->
      <div v-if="isCompleted && metricsTableData.length > 0">
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-lg font-semibold text-stone-900">
            <I18nText k="chunkTestResults.evaluationMetrics" />
          </h2>
        </div>

        <div class="bg-white rounded-lg border border-stone-200 overflow-hidden">
          <ElTable
            :data="metricsTableData"
            stripe
            style="width: 100%"
          >
            <ElTableColumn
              prop="method"
              width="120"
              fixed="left"
            >
              <template #header>
                <I18nText k="chunkTestResults.method" />
              </template>
            </ElTableColumn>
            <ElTableColumn
              width="240"
              fixed="right"
            >
              <template #header>
                <I18nText k="chunkTestResults.actions" />
              </template>
              <template #default="{ row }">
                <div class="flex items-center gap-2">
                  <ElButton
                    size="small"
                    type="primary"
                    link
                    @click="handleViewChunks(getMethodKeyFromLabel(row.method))"
                  >
                    <ElIcon class="mr-1"><View /></ElIcon>
                    <I18nText k="chunkTestResults.viewChunks" />
                  </ElButton>
                  <ElButton
                    size="small"
                    type="success"
                    link
                    @click="handleManualEvaluation(getMethodKeyFromLabel(row.method))"
                  >
                    <ElIcon class="mr-1"><Sparkles /></ElIcon>
                    <I18nText k="chunkTestResults.evaluate" />
                  </ElButton>
                </div>
              </template>
            </ElTableColumn>

            <!-- Standard IR Metrics -->
            <ElTableColumn align="center">
              <template #header>
                <I18nText k="chunkTestResults.standardIrMetrics" />
              </template>
              <ElTableColumn
                prop="precision"
                width="100"
              >
                <template #header>
                  <I18nText k="chunkTestResults.precision" />
                </template>
              </ElTableColumn>
              <ElTableColumn
                prop="recall"
                width="100"
              >
                <template #header>
                  <I18nText k="chunkTestResults.recall" />
                </template>
              </ElTableColumn>
              <ElTableColumn
                prop="mrr"
                label="MRR"
                width="100"
              />
              <ElTableColumn
                prop="ndcg"
                label="NDCG"
                width="100"
              />
              <ElTableColumn
                prop="f1"
                label="F1"
                width="100"
              />
              <ElTableColumn
                prop="map"
                label="MAP"
                width="100"
              />
            </ElTableColumn>

            <!-- Chunk Quality -->
            <ElTableColumn align="center">
              <template #header>
                <I18nText k="chunkTestResults.chunkQuality" />
              </template>
              <ElTableColumn
                prop="coverage_score"
                width="120"
              >
                <template #header>
                  <I18nText k="chunkTestResults.coverage" />
                </template>
              </ElTableColumn>
              <ElTableColumn
                prop="semantic_coherence"
                width="140"
              >
                <template #header>
                  <I18nText k="chunkTestResults.coherence" />
                </template>
              </ElTableColumn>
            </ElTableColumn>

            <!-- Answer Quality -->
            <ElTableColumn align="center">
              <template #header>
                <I18nText k="chunkTestResults.answerQuality" />
              </template>
              <ElTableColumn
                prop="answer_coverage"
                width="140"
              >
                <template #header>
                  <I18nText k="chunkTestResults.answerCoverage" />
                </template>
              </ElTableColumn>
              <ElTableColumn
                prop="answer_completeness"
                width="140"
              >
                <template #header>
                  <I18nText k="chunkTestResults.completeness" />
                </template>
              </ElTableColumn>
              <ElTableColumn
                prop="context_recall"
                width="140"
              >
                <template #header>
                  <I18nText k="chunkTestResults.contextRecall" />
                </template>
              </ElTableColumn>
            </ElTableColumn>

            <!-- Diversity & Efficiency -->
            <ElTableColumn align="center">
              <template #header>
                <I18nText k="chunkTestResults.diversityEfficiency" />
              </template>
              <ElTableColumn
                prop="storage_efficiency"
                width="130"
              >
                <template #header>
                  <I18nText k="chunkTestResults.storageEff" />
                </template>
              </ElTableColumn>
              <ElTableColumn
                prop="semantic_diversity"
                width="130"
              >
                <template #header>
                  <I18nText k="chunkTestResults.diversity" />
                </template>
              </ElTableColumn>
              <ElTableColumn
                prop="avg_latency_ms"
                width="130"
              >
                <template #header>
                  <I18nText k="chunkTestResults.avgLatency" />
                </template>
              </ElTableColumn>
            </ElTableColumn>
          </ElTable>
        </div>
      </div>

      <!-- Chunks View (shown when viewing chunks) -->
      <div
        v-if="showChunks && isCompleted"
        class="mt-6"
      >
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-stone-900">
            <I18nText
              k="chunkTestResults.viewChunksHeading"
              :params="{
                method: methodLabels[selectedMethod] || selectedMethod,
              }"
            />
          </h2>
          <ElButton
            size="small"
            @click="handleCloseChunks"
          >
            <I18nText k="chunkTestResults.close" />
          </ElButton>
        </div>
        <div
          v-if="isLoadingChunks"
          class="text-center py-8"
        >
          <ElIcon class="text-stone-400 animate-spin text-4xl mb-4">
            <Loading />
          </ElIcon>
          <p class="text-stone-600">
            <I18nText k="chunkTestResults.generatingChunks" />
          </p>
        </div>
        <div
          v-else-if="chunksData && chunksData.chunks.length > 0"
          class="chunks-container"
        >
          <div class="mb-4 text-sm text-stone-600">
            <I18nText
              k="chunkTestResults.totalChunks"
              :params="{ n: chunksData.chunks.length }"
            />
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
                    <I18nText
                      k="chunkTestResults.chunkLabel"
                      :params="{ n: chunk.chunk_index + 1 }"
                    />
                  </span>
                  <span
                    v-if="chunk.start_char !== undefined && chunk.end_char !== undefined"
                    class="text-xs text-stone-500"
                  >
                    <I18nText
                      k="chunkTestResults.positionRange"
                      :params="{
                        start: chunk.start_char,
                        end: chunk.end_char,
                      }"
                    />
                  </span>
                </div>
              </template>
              <div class="chunk-content text-sm text-stone-700 leading-relaxed whitespace-pre-wrap">
                {{ chunk.text }}
              </div>
              <div
                v-if="chunk.metadata && Object.keys(chunk.metadata).length > 0"
                class="mt-3 pt-3 border-t border-stone-200"
              >
                <div class="text-xs text-stone-500">
                  <div
                    v-for="(value, key) in chunk.metadata"
                    :key="key"
                    class="mb-1"
                  >
                    <span class="font-medium">{{ key }}:</span> {{ value }}
                  </div>
                </div>
              </div>
            </ElCard>
          </div>
        </div>
        <div
          v-else-if="chunksData && chunksData.chunks.length === 0"
          class="text-center py-8 text-stone-500"
        >
          <I18nText k="chunkTestResults.noChunks" />
        </div>
      </div>

      <!-- Loading State -->
      <div
        v-if="isLoadingProgress && !progress"
        class="text-center py-12"
      >
        <ElIcon class="text-stone-400 animate-spin text-4xl mb-4">
          <Loading />
        </ElIcon>
        <p class="text-stone-600">
          <I18nText k="chunkTestResults.loading" />
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
