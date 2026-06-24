<script setup lang="ts">
/**
 * DiagramTemplateInput - Template-based input with fill-in slots
 * Migrated from prototype MindMateChatPage template system
 */
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ElButton, ElIcon, ElInput } from 'element-plus'

import { Close, Loading, Promotion } from '@element-plus/icons-vue'

import { ChevronDown } from '@lucide/vue'

import { useLanguage, useNotifications } from '@/composables'
import { useLandingGenerateGraph } from '@/composables/mindgraph/useLandingGenerateGraph'
import {
  DIAGRAM_TEMPLATES,
  getDiagramTemplateBody,
  useAuthStore,
  useDiagramStore,
  useLLMResultsStore,
  useUIStore,
} from '@/stores'
import type { DiagramType } from '@/types'

const MAX_PROMPT_LENGTH = 10000

const LANDING_LLM_MODEL = 'qwen'

const uiStore = useUIStore()
const authStore = useAuthStore()
const diagramStore = useDiagramStore()
const router = useRouter()
const { promptLanguage, t } = useLanguage()
const notify = useNotifications()
const {
  loadPhase,
  isGenerating,
  generateLandingGraph,
  beginGeneration,
  endGeneration,
  abortGeneration,
} = useLandingGenerateGraph({
  t,
  notify,
})

// Aborted on unmount to avoid leaks

// Map Chinese diagram type names to DiagramType for URL
const diagramTypeMap: Record<string, DiagramType> = {
  圆圈图: 'circle_map',
  气泡图: 'bubble_map',
  双气泡图: 'double_bubble_map',
  树形图: 'tree_map',
  括号图: 'brace_map',
  流程图: 'flow_map',
  复流程图: 'multi_flow_map',
  桥形图: 'bridge_map',
  思维导图: 'mindmap',
  概念图: 'concept_map',
}

const chartTypes = [
  '选择具体图示',
  '圆圈图',
  '气泡图',
  '双气泡图',
  '树形图',
  '括号图',
  '流程图',
  '复流程图',
  '桥形图',
  '思维导图',
]

const CHART_TYPE_I18N_KEY: Record<string, string> = {
  选择具体图示: 'landing.chartType.selectPlaceholder',
  圆圈图: 'landing.chartType.circle_map',
  气泡图: 'landing.chartType.bubble_map',
  双气泡图: 'landing.chartType.double_bubble_map',
  树形图: 'landing.chartType.tree_map',
  括号图: 'landing.chartType.brace_map',
  流程图: 'landing.chartType.flow_map',
  复流程图: 'landing.chartType.multi_flow_map',
  桥形图: 'landing.chartType.bridge_map',
  思维导图: 'landing.chartType.mindmap',
}

function chartTypeLabel(chartType: string): string {
  const key = CHART_TYPE_I18N_KEY[chartType]
  return key ? String(t(key)) : chartType
}

function slotPlaceholder(slotId: string): string {
  return String(t(`landing.template.slot.${slotId}`))
}

const selectedType = computed(() => uiStore.selectedChartType)
const templateSlots = computed(() => uiStore.templateSlots)

const canSubmit = computed(() => uiStore.hasValidSlots() && authStore.isAuthenticated)

const currentTemplate = computed(() => {
  if (selectedType.value === '选择具体图示') return null
  const def = DIAGRAM_TEMPLATES[selectedType.value]
  if (!def) return null
  return {
    template: getDiagramTemplateBody(def, uiStore.language),
    slots: def.slots,
  }
})

function handleTypeChange(type: string) {
  uiStore.setSelectedChartType(type)
}

function clearType() {
  uiStore.setSelectedChartType('选择具体图示')
}

function handleFreeInputFocus() {
  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
  }
}

async function generateFromLanding() {
  if (isGenerating.value) return

  const isSpecificDiagram = selectedType.value !== '选择具体图示'
  const diagramTypeParam = isSpecificDiagram ? diagramTypeMap[selectedType.value] : null

  const topicText = isSpecificDiagram
    ? uiStore.getTemplateTopic().trim() || uiStore.getTemplateText().trim()
    : uiStore.getTemplateText().trim()
  if (!topicText) return

  if (topicText.length > MAX_PROMPT_LENGTH) {
    notify.error(
      t('diagramTemplate.promptTooLong', {
        length: topicText.length,
        max: MAX_PROMPT_LENGTH,
      })
    )
    return
  }

  const requestBody: Record<string, unknown> = {
    prompt: topicText,
    diagram_type: diagramTypeParam,
    language: promptLanguage.value,
  }

  if (isSpecificDiagram) {
    const dimPref = uiStore.getTemplateDimensionPreference()
    if (dimPref) requestBody.dimension_preference = dimPref
    const fixedDim = uiStore.getTemplateFixedDimension()
    if (fixedDim) requestBody.fixed_dimension = fixedDim
  }

  const abortController = beginGeneration()

  try {
    const outcome = await generateLandingGraph(
      { ...requestBody, llm: LANDING_LLM_MODEL },
      abortController.signal
    )

    if (!outcome.ok) {
      return
    }

    const finalDiagramType =
      (outcome.diagramType as DiagramType) || (diagramTypeParam as DiagramType | null)
    if (!finalDiagramType) {
      notify.error(t('diagramTemplate.generationFailed'))
      return
    }

    diagramStore.clearHistory()
    const loaded = diagramStore.loadFromSpec(outcome.result.spec!, finalDiagramType)
    if (loaded) {
      useLLMResultsStore().reset()
      router.push({ path: '/canvas' })
    } else {
      notify.error(t('diagramTemplate.generationFailed'))
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return
    }
    console.error('Generate from landing failed:', error)
    notify.error(
      error instanceof Error ? error.message : t('diagramTemplate.generationFailed')
    )
  } finally {
    endGeneration()
  }
}

onUnmounted(() => {
  abortGeneration()
})

async function handleSubmit() {
  if (!uiStore.hasValidSlots()) return

  if (!authStore.isAuthenticated) {
    authStore.handleTokenExpired(undefined, undefined)
    return
  }

  await generateFromLanding()
}

// Parse template into parts with slots
function parseTemplate(template: string, slots: string[]) {
  const parts: Array<{ type: 'text'; content: string } | { type: 'slot'; name: string }> = []
  let remaining = template

  for (const slot of slots) {
    const marker = `【${slot}】`
    const index = remaining.indexOf(marker)
    if (index > 0) {
      parts.push({ type: 'text', content: remaining.substring(0, index) })
    }
    if (index >= 0) {
      parts.push({ type: 'slot', name: slot })
      remaining = remaining.substring(index + marker.length)
    }
  }

  if (remaining) {
    parts.push({ type: 'text', content: remaining })
  }

  return parts
}

const templateParts = computed(() => {
  if (!currentTemplate.value) return []
  return parseTemplate(currentTemplate.value.template, currentTemplate.value.slots)
})
</script>

<template>
  <div
    class="diagram-template-input rounded-xl border border-gray-200 p-5 bg-white shadow-sm"
    :class="{ 'prompt-box-rainbow': selectedType === '选择具体图示' && isGenerating }"
  >
    <!-- Input area -->
    <div class="mb-4">
      <!-- Free input mode: Element Plus input with blinking cursor and placeholder -->
      <ElInput
        v-if="selectedType === '选择具体图示'"
        :model-value="uiStore.freeInputValue"
        type="textarea"
        :rows="4"
        size="large"
        :maxlength="MAX_PROMPT_LENGTH"
        show-word-limit
        :placeholder="t('landing.template.freePlaceholder')"
        :disabled="!authStore.isAuthenticated || isGenerating"
        class="mindgraph-free-input"
        @update:model-value="uiStore.setFreeInputValue"
        @focus="handleFreeInputFocus"
      />

      <!-- Template mode -->
      <div
        v-else
        class="flex items-center rounded-lg p-2"
      >
        <!-- Chart type tag with close icon on top right -->
        <div class="relative mr-2 inline-block">
          <span
            class="diagram-type-tag bg-blue-50 text-blue-600 px-3 py-1.5 pr-7 rounded-md font-medium"
          >
            {{ chartTypeLabel(selectedType) }}
          </span>
          <ElButton
            :icon="Close"
            circle
            size="small"
            class="clear-type-btn"
            @click.stop="clearType"
          />
        </div>

        <!-- Template with slots: Element Plus inputs -->
        <div class="flex-1 flex flex-wrap items-center gap-2">
          <template
            v-for="(part, index) in templateParts"
            :key="index"
          >
            <span
              v-if="part.type === 'text'"
              class="template-text text-gray-800"
              >{{ part.content }}</span
            >
            <ElInput
              v-else
              :model-value="templateSlots[part.name] || ''"
              :placeholder="slotPlaceholder(part.name)"
              size="small"
              class="template-slot-input"
              :disabled="!authStore.isAuthenticated || isGenerating"
              @update:model-value="(v: string) => uiStore.setTemplateSlot(part.name, v)"
              @focus="handleFreeInputFocus"
            />
          </template>
        </div>
      </div>
    </div>

    <!-- Controls -->
    <div class="flex items-center justify-between">
      <!-- Chart type selector -->
      <div class="relative w-1/4 min-w-[150px]">
        <select
          :value="selectedType"
          :disabled="!authStore.isAuthenticated || isGenerating"
          class="diagram-type-select w-full appearance-none bg-white border border-blue-500 rounded-md py-2 pl-3 pr-10 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          @change="handleTypeChange(($event.target as HTMLSelectElement).value)"
          @focus="!authStore.isAuthenticated && authStore.handleTokenExpired(undefined, undefined)"
        >
          <option
            v-for="type in chartTypes"
            :key="type"
            :value="type"
          >
            {{ chartTypeLabel(type) }}
          </option>
        </select>
        <div class="absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none">
          <ChevronDown class="w-3.5 h-3.5 text-gray-400" />
        </div>
      </div>

      <!-- Submit button: Element Plus primary when enabled, grey when empty -->
      <LlmPhaseRing
        :phase="loadPhase"
        :active="isGenerating"
        border-radius="50%"
        streaming-variant="qwen"
        ring-padding="2px"
      >
        <ElButton
          :type="canSubmit ? 'primary' : 'default'"
          :loading="isGenerating"
          :loading-icon="Loading"
          :disabled="!canSubmit || isGenerating"
          circle
          class="submit-btn"
          @click="handleSubmit"
        >
          <ElIcon v-if="!isGenerating">
            <Promotion />
          </ElIcon>
        </ElButton>
      </LlmPhaseRing>
    </div>
  </div>
</template>

<style scoped>
.mindgraph-free-input :deep(.el-textarea__inner) {
  box-shadow: none;
  border: 1px solid #e5e7eb;
  resize: none;
  font-size: 18px;
}

.mindgraph-free-input :deep(.el-textarea__inner::placeholder) {
  font-size: 18px;
  color: #9ca3af;
}

.mindgraph-free-input :deep(.el-textarea__inner:focus) {
  border-color: #60a5fa;
  box-shadow: 0 0 0 1px #60a5fa;
}

.mindgraph-free-input :deep(.el-input__count) {
  font-size: 12px;
  color: #9ca3af;
}

.template-slot-input {
  min-width: 80px;
  max-width: 140px;
}

.template-slot-input :deep(.el-input__inner) {
  font-size: 18px;
}

.template-slot-input :deep(.el-input__inner::placeholder) {
  font-size: 18px;
}

.template-slot-input :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #e5e7eb;
}

.template-slot-input :deep(.el-input__wrapper:hover),
.template-slot-input :deep(.el-input.is-focus .el-input__wrapper) {
  box-shadow: 0 0 0 1px #60a5fa;
}

.clear-type-btn {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 22px;
  width: 22px;
  height: 22px;
  padding: 0;
}

.diagram-type-tag {
  font-size: 16px;
}

.diagram-type-select {
  font-size: 16px;
}

.template-text {
  font-size: 18px;
}

/* Rainbow glowing border when free-form + generating */
.prompt-box-rainbow {
  position: relative;
  overflow: visible;
}

.prompt-box-rainbow::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 3px;
  background: conic-gradient(from 0deg, red, orange, yellow, green, cyan, blue, violet, red);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  animation: rainbowRotate 2s linear infinite;
  z-index: 0;
  pointer-events: none;
}

.prompt-box-rainbow > * {
  position: relative;
  z-index: 1;
}

@keyframes rainbowRotate {
  to {
    transform: rotate(360deg);
  }
}

.submit-btn {
  min-width: 40px;
  height: 40px;
  padding: 0;
}
</style>
