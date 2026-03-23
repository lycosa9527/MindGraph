<script setup lang="ts">
/**
 * ManualEvaluationModal - Manual chunk evaluation using DashScope models
 * Allows users to evaluate chunks with custom queries and optional ground truth answers
 */
import { computed, ref, watch } from 'vue'

import {
  ElButton,
  ElCard,
  ElDialog,
  ElDivider,
  ElIcon,
  ElInput,
  ElOption,
  ElSelect,
} from 'element-plus'

import { Loading } from '@element-plus/icons-vue'

import { Sparkles } from 'lucide-vue-next'

import { notify } from '@/composables/notifications'
import {
  type ManualEvaluationResult,
  useChunkTestChunks,
  useManualEvaluation,
} from '@/composables/queries/useChunkTestQueries'
import { useLanguage } from '@/composables/useLanguage'

interface Props {
  visible: boolean
  testId: number
  method: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
}>()

const { t } = useLanguage()

function metricLabel(key: string): string {
  const path = `knowledge.manualEval.metric.${key}`
  const out = t(path)
  return out === path ? key : out
}

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

// Form state
const query = ref('')
const answer = ref('')
const selectedChunkIds = ref<number[]>([])
const model = ref('qwen-max')

// Chunks data
const { data: chunksData, isLoading: isLoadingChunks } = useChunkTestChunks(
  computed(() => props.testId),
  computed(() => props.method)
)

// Evaluation mutation
const evaluationMutation = useManualEvaluation()

// Evaluation results
const evaluationResults = ref<ManualEvaluationResult | null>(null)
const isEvaluating = computed(() => evaluationMutation.isPending.value)

// Available models
const availableModels = [
  { value: 'qwen-max', label: 'Qwen Max' },
  { value: 'qwen-plus', label: 'Qwen Plus' },
  { value: 'qwen-turbo', label: 'Qwen Turbo' },
]

// Method labels
const methodLabels: Record<string, string> = {
  spacy: 'spaCy',
  semchunk: 'SemChunk',
  chonkie: 'Chonkie',
  langchain: 'LangChain',
  mindchunk: 'MindChunk',
}

const chunks = computed(() => chunksData.value?.chunks || [])

const handleEvaluate = async () => {
  if (!query.value.trim()) {
    notify.warning(t('knowledge.manualEval.notify.enterQuery'))
    return
  }

  try {
    const result = await evaluationMutation.mutateAsync({
      testId: props.testId,
      request: {
        query: query.value.trim(),
        method: props.method,
        chunk_ids: selectedChunkIds.value.length > 0 ? selectedChunkIds.value : undefined,
        answer: answer.value.trim() || undefined,
        model: model.value,
      },
    })

    evaluationResults.value = result
    notify.success(t('knowledge.manualEval.notify.completed'))
  } catch (error) {
    notify.error(
      error instanceof Error ? error.message : t('knowledge.manualEval.notify.failed')
    )
  }
}

const toggleChunkSelection = (chunkIndex: number) => {
  const index = selectedChunkIds.value.indexOf(chunkIndex)
  if (index > -1) {
    selectedChunkIds.value.splice(index, 1)
  } else {
    selectedChunkIds.value.push(chunkIndex)
  }
}

const selectAllChunks = () => {
  if (selectedChunkIds.value.length === chunks.value.length) {
    selectedChunkIds.value = []
  } else {
    selectedChunkIds.value = chunks.value.map((c) => c.chunk_index)
  }
}

const handleClose = () => {
  query.value = ''
  answer.value = ''
  selectedChunkIds.value = []
  evaluationResults.value = null
  dialogVisible.value = false
}

// Reset when dialog opens
watch(
  () => props.visible,
  (newValue) => {
    if (newValue) {
      query.value = ''
      answer.value = ''
      selectedChunkIds.value = []
      evaluationResults.value = null
    }
  }
)
</script>

<template>
  <ElDialog
    v-model="dialogVisible"
    :title="t('knowledge.manualEval.dialogTitle', { method: methodLabels[method] || method })"
    width="900px"
    :close-on-click-modal="false"
    class="manual-evaluation-modal"
    @close="handleClose"
  >
    <div class="evaluation-container">
      <!-- Form Section -->
      <div class="form-section mb-6">
        <div class="mb-4">
          <label class="block text-sm font-medium text-stone-700 mb-2">
            {{ t('knowledge.manualEval.queryLabel') }} <span class="text-red-500">*</span>
          </label>
          <ElInput
            v-model="query"
            type="textarea"
            :rows="3"
            :placeholder="t('knowledge.manualEval.queryPlaceholder')"
            maxlength="500"
            show-word-limit
          />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-stone-700 mb-2">
            {{ t('knowledge.manualEval.groundTruthLabel') }}
          </label>
          <ElInput
            v-model="answer"
            type="textarea"
            :rows="2"
            :placeholder="t('knowledge.manualEval.groundTruthPlaceholder')"
          />
        </div>

        <div class="mb-4">
          <label class="block text-sm font-medium text-stone-700 mb-2">
            {{ t('knowledge.manualEval.modelLabel') }}
          </label>
          <ElSelect
            v-model="model"
            class="w-full"
          >
            <ElOption
              v-for="m in availableModels"
              :key="m.value"
              :label="m.label"
              :value="m.value"
            />
          </ElSelect>
        </div>

        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <label class="block text-sm font-medium text-stone-700">
              {{ t('knowledge.manualEval.selectChunksHeading') }}
            </label>
            <ElButton
              size="small"
              text
              @click="selectAllChunks"
            >
              {{
                selectedChunkIds.length === chunks.length
                  ? t('knowledge.manualEval.deselectAll')
                  : t('knowledge.manualEval.selectAll')
              }}
            </ElButton>
          </div>
          <div
            v-if="isLoadingChunks"
            class="flex items-center justify-center py-8"
          >
            <ElIcon class="animate-spin text-stone-400">
              <Loading />
            </ElIcon>
          </div>
          <div
            v-else-if="chunks.length === 0"
            class="text-center py-8 text-stone-500"
          >
            {{ t('knowledge.manualEval.noChunks') }}
          </div>
          <div
            v-else
            class="chunks-selection max-h-40 overflow-y-auto border border-stone-200 rounded p-2"
          >
            <div
              v-for="chunk in chunks.slice(0, 20)"
              :key="chunk.chunk_index"
              class="chunk-item flex items-start gap-2 p-2 hover:bg-stone-50 rounded cursor-pointer"
              @click="toggleChunkSelection(chunk.chunk_index)"
            >
              <input
                type="checkbox"
                :checked="selectedChunkIds.includes(chunk.chunk_index)"
                class="mt-1"
                @click.stop
                @change="toggleChunkSelection(chunk.chunk_index)"
              />
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-stone-900 mb-1">
                  {{ t('chunkTestResults.chunkLabel', { n: chunk.chunk_index + 1 }) }}
                </div>
                <div class="text-xs text-stone-600 truncate">
                  {{ chunk.text.substring(0, 100) }}{{ chunk.text.length > 100 ? '...' : '' }}
                </div>
              </div>
            </div>
            <div
              v-if="chunks.length > 20"
              class="text-xs text-stone-500 text-center py-2"
            >
              {{ t('knowledge.manualEval.showingFirst20', { total: chunks.length }) }}
            </div>
          </div>
        </div>

        <ElButton
          type="primary"
          class="w-full"
          :loading="isEvaluating"
          :disabled="!query.trim()"
          @click="handleEvaluate"
        >
          <ElIcon class="mr-1"><Sparkles /></ElIcon>
          {{ t('knowledge.manualEval.startEvaluation') }}
        </ElButton>
      </div>

      <!-- Results Section -->
      <div
        v-if="evaluationResults"
        class="results-section"
      >
        <ElDivider>
          <span class="text-sm font-medium text-stone-700">
            {{ t('knowledge.manualEval.resultsTitle') }}
          </span>
        </ElDivider>

        <div class="space-y-4">
          <!-- Answer Relevance Results -->
          <div
            v-for="result in evaluationResults.results"
            :key="result.type"
            class="result-card"
          >
            <ElCard shadow="hover">
              <template #header>
                <div class="font-semibold text-stone-900">
                  {{
                    result.type === 'answer_relevance'
                      ? t('knowledge.manualEval.result.answerRelevance')
                      : t('knowledge.manualEval.result.chunkQuality')
                  }}
                </div>
              </template>

              <!-- Answer Relevance -->
              <div
                v-if="result.type === 'answer_relevance' && result.evaluation"
                class="evaluation-scores"
              >
                <div class="grid grid-cols-2 gap-4">
                  <div
                    v-for="(score, key) in result.evaluation"
                    :key="key"
                    class="score-item"
                  >
                    <div class="text-xs text-stone-500 mb-1">
                      {{ metricLabel(String(key)) }}
                    </div>
                    <div
                      v-if="key === 'reasoning'"
                      class="text-sm text-stone-700"
                    >
                      {{ score }}
                    </div>
                    <div
                      v-else-if="typeof score === 'number'"
                      class="text-lg font-semibold"
                      :class="
                        score >= 0.8
                          ? 'text-green-600'
                          : score >= 0.6
                            ? 'text-yellow-600'
                            : 'text-red-600'
                      "
                    >
                      {{ score.toFixed(3) }}
                    </div>
                  </div>
                </div>
              </div>

              <!-- Chunk Quality -->
              <div
                v-else-if="result.type === 'chunk_quality' && result.evaluations"
                class="chunk-evaluations"
              >
                <div
                  v-for="(eval_item, idx) in result.evaluations"
                  :key="idx"
                  class="chunk-eval-item mb-4 pb-4 border-b border-stone-200 last:border-0"
                >
                  <div class="font-medium text-stone-900 mb-2">
                    {{ t('chunkTestResults.chunkLabel', { n: eval_item.chunk_index + 1 }) }}
                  </div>
                  <div class="grid grid-cols-3 gap-3">
                    <div
                      v-for="(score, key) in eval_item.evaluation"
                      :key="key"
                      class="score-item"
                    >
                      <div class="text-xs text-stone-500 mb-1">
                        {{ metricLabel(String(key)) }}
                      </div>
                      <div
                        v-if="key === 'reasoning'"
                        class="text-xs text-stone-600"
                      >
                        {{ score }}
                      </div>
                      <div
                        v-else-if="typeof score === 'number'"
                        class="text-base font-semibold"
                        :class="
                          score >= 0.8
                            ? 'text-green-600'
                            : score >= 0.6
                              ? 'text-yellow-600'
                              : 'text-red-600'
                        "
                      >
                        {{ score.toFixed(3) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </ElCard>
          </div>
        </div>
      </div>
    </div>
  </ElDialog>
</template>

<style scoped>
.manual-evaluation-modal :deep(.el-dialog__body) {
  padding: 24px;
}

.chunks-selection {
  max-height: 200px;
}

.chunk-item {
  transition: background-color 0.15s;
}

.chunk-item:hover {
  background-color: #fafaf9;
}

.evaluation-scores,
.chunk-evaluations {
  padding: 8px 0;
}

.score-item {
  padding: 8px;
  background-color: #fafaf9;
  border-radius: 6px;
}

.chunk-eval-item {
  padding: 12px;
  background-color: #fafaf9;
  border-radius: 8px;
}
</style>
