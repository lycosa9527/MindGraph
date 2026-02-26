<script setup lang="ts">
/**
 * DiagramTemplateInput - Template-based input with fill-in slots
 * Migrated from prototype MindMateChatPage template system
 */
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { ElButton, ElIcon, ElInput } from 'element-plus'

import { Close, Loading, Promotion } from '@element-plus/icons-vue'

import { ChevronDown } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import {
  DIAGRAM_TEMPLATES,
  useAuthStore,
  useDiagramStore,
  useLLMResultsStore,
  useUIStore,
} from '@/stores'
import type { DiagramType } from '@/types'
import { authFetch } from '@/utils/api'

const MAX_PROMPT_LENGTH = 10000

// LLMs to use for parallel generation (first-success-wins)
const LANDING_LLM_MODELS = ['qwen', 'deepseek', 'kimi', 'doubao'] as const

const uiStore = useUIStore()
const authStore = useAuthStore()
const diagramStore = useDiagramStore()
const router = useRouter()
const { isZh } = useLanguage()
const notify = useNotifications()

const isGenerating = ref(false)

// AbortControllers for in-flight generation; aborted on unmount to avoid leaks
const landingAbortControllers = ref<AbortController[]>([])

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

const selectedType = computed(() => uiStore.selectedChartType)
const templateSlots = computed(() => uiStore.templateSlots)

const canSubmit = computed(() => uiStore.hasValidSlots() && authStore.isAuthenticated)

const currentTemplate = computed(() => {
  if (selectedType.value === '选择具体图示') return null
  return DIAGRAM_TEMPLATES[selectedType.value] || null
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
  const isSpecificDiagram = selectedType.value !== '选择具体图示'
  const diagramTypeParam = isSpecificDiagram ? diagramTypeMap[selectedType.value] : null

  const requestText = uiStore.getTemplateText().trim()
  if (!requestText) return

  if (requestText.length > MAX_PROMPT_LENGTH) {
    notify.error(
      isZh.value
        ? `输入内容过长（${requestText.length}字符）。最大允许${MAX_PROMPT_LENGTH}字符。`
        : `Prompt too long (${requestText.length} chars). Maximum is ${MAX_PROMPT_LENGTH} chars.`
    )
    return
  }

  const requestBody: Record<string, unknown> = {
    prompt: requestText,
    diagram_type: diagramTypeParam,
    language: isZh.value ? 'zh' : 'en',
  }

  if (isSpecificDiagram) {
    const dimPref = uiStore.getTemplateDimensionPreference()
    if (dimPref) requestBody.dimension_preference = dimPref
    const fixedDim = uiStore.getTemplateFixedDimension()
    if (fixedDim) requestBody.fixed_dimension = fixedDim
  }

  landingAbortControllers.value = LANDING_LLM_MODELS.map(() => new AbortController())

  async function fetchWithModel(model: string, index: number) {
    const response = await authFetch('/api/generate_graph', {
      method: 'POST',
      body: JSON.stringify({ ...requestBody, llm: model }),
      signal: landingAbortControllers.value[index].signal,
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Request failed' }))
      throw new Error(err.detail || `HTTP ${response.status}`)
    }

    const result = await response.json()
    if (result.success && result.spec) {
      landingAbortControllers.value.forEach((c, j) => j !== index && c.abort())
      return { model, result }
    }
    throw new Error(result.error || 'Generation failed')
  }

  isGenerating.value = true
  try {
    const promises = LANDING_LLM_MODELS.map((model, i) => fetchWithModel(model, i))

    const { model: winningModel, result } = await Promise.any(promises)
    const finalDiagramType = (result.diagram_type as DiagramType) || diagramTypeParam
    if (!finalDiagramType) {
      throw new Error('No diagram type specified')
    }

    const loaded = diagramStore.loadFromSpec(result.spec, finalDiagramType)
    if (loaded) {
      useLLMResultsStore().reset()
      notify.success(
        isZh.value ? `图表生成成功 (${winningModel})` : `Diagram generated (${winningModel})`
      )
      router.push({ path: '/canvas' })
    } else {
      throw new Error('Failed to load diagram data')
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AggregateError') {
      const msg = isZh.value ? '所有模型均生成失败，请重试' : 'All models failed, please try again'
      notify.error(msg)
    } else {
      console.error('Generate from landing failed:', error)
      const errorMessage =
        error instanceof Error ? error.message : isZh.value ? '生成失败' : 'Generation failed'
      notify.error(errorMessage)
    }
  } finally {
    isGenerating.value = false
  }
}

onUnmounted(() => {
  landingAbortControllers.value.forEach((c) => c.abort())
  landingAbortControllers.value = []
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
        :rows="2"
        size="large"
        :maxlength="50"
        show-word-limit
        :placeholder="
          isZh
            ? '描述你的图示，或从下方选择具体图示模板...'
            : 'Describe your diagram, or select a template below...'
        "
        :disabled="!authStore.isAuthenticated"
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
            {{ selectedType }}
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
              :placeholder="part.name"
              size="small"
              class="template-slot-input"
              :disabled="!authStore.isAuthenticated"
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
      <div class="relative w-1/4">
        <select
          :value="selectedType"
          :disabled="!authStore.isAuthenticated"
          class="diagram-type-select w-full appearance-none bg-white border border-blue-500 rounded-md py-2 pl-3 pr-10 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          @change="handleTypeChange(($event.target as HTMLSelectElement).value)"
          @focus="!authStore.isAuthenticated && authStore.handleTokenExpired(undefined, undefined)"
        >
          <option
            v-for="type in chartTypes"
            :key="type"
            :value="type"
          >
            {{ type }}
          </option>
        </select>
        <div class="absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none">
          <ChevronDown class="w-3.5 h-3.5 text-gray-400" />
        </div>
      </div>

      <!-- Submit button: Element Plus primary when enabled, grey when empty -->
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
