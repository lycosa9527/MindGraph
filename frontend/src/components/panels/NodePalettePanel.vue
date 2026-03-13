<script setup lang="ts">
/**
 * Node Palette Panel (瀑布流) - AI-suggested nodes with streaming
 *
 * Displays AI-generated node suggestions in a grid.
 * - Concept map: nodes are draggable onto canvas (free-form)
 * - Other diagrams: select nodes and click Finish to add
 *
 * For double_bubble_map: shows tabs (相似点/Similarities | 差异点/Differences).
 * Differences tab displays paired attributes for both Topic A and Topic B.
 */
import { computed, nextTick, onMounted, watch } from 'vue'

import { ElButton, ElTooltip } from 'element-plus'
import { Check, Loader2, RefreshCw, X } from 'lucide-vue-next'

import { getLLMColor } from '@/config/llmModelColors'
import { useLanguage, useNotifications } from '@/composables'
import { getNodePalette } from '@/composables/useNodePalette'
import { useDiagramStore, usePanelsStore, useUIStore } from '@/stores'
import type { NodeSuggestion } from '@/types/panels'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { isZh } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()
const panelsStore = usePanelsStore()
const diagramStore = useDiagramStore()

const {
  isLoading,
  isLoadingMore,
  errorMessage,
  suggestions,
  selectedIds,
  diagramType,
  diagramData,
  doubleBubbleTopics,
  bridgeMapDimension,
  isStagedDiagram,
  isDimensionsStage,
  showNextButton,
  stage2Parents,
  stage2StageName,
  defaultStage,
  getStageDataForParent,
  sessionId,
  startSession,
  loadNextBatch,
  toggleSelection,
  finishSelection,
  cancel,
  dismiss,
  switchTab,
  switchStageTab,
  switchConceptMapTab,
} = getNodePalette({
  language: isZh.value ? 'zh' : 'en',
  onError: (err) => notify.error(err),
})

const isDoubleBubble = computed(() => diagramType.value === 'double_bubble_map')
const isMultiFlowMap = computed(() => diagramType.value === 'multi_flow_map')
const isBridgeMap = computed(() => diagramType.value === 'bridge_map')
const isConceptMap = computed(() => diagramType.value === 'concept_map')
const currentMode = computed(
  () =>
    (panelsStore.nodePalettePanel.mode as
      | 'similarities'
      | 'differences'
      | 'causes'
      | 'effects') ??
    (isMultiFlowMap.value ? 'causes' : 'similarities')
)
const currentStage = computed(() => panelsStore.nodePalettePanel.stage ?? '')
const showStage2Tabs = computed(
  () =>
    isStagedDiagram.value &&
    stage2Parents.value.length > 0 &&
    currentStage.value === stage2StageName.value
)

/** Show paired format (one up, one down) for double bubble differences or bridge map pairs */
const showPairedFormat = computed(
  () =>
    (currentMode.value === 'differences' && isDoubleBubble.value) ||
    (isBridgeMap.value && (panelsStore.nodePalettePanel.mode as string) === 'pairs')
)

/** Concept map tabs (main topic + per-node sub-concept tabs), excluding tabs for deleted nodes */
const conceptMapTabs = computed(() => {
  const tabs = panelsStore.nodePalettePanel.conceptMapTabs ?? []
  if (!isConceptMap.value) return tabs
  const nodes = diagramStore.data?.nodes ?? []
  const nodeIds = new Set(nodes.map((n) => n.id))
  return tabs.filter((t) => t.id === 'topic' || nodeIds.has(t.id))
})
const showConceptMapTabs = computed(
  () => isConceptMap.value && conceptMapTabs.value.length > 0
)

/** When current tab is for a deleted node, switch to topic */
watch(
  () => [conceptMapTabs.value, panelsStore.nodePalettePanel.mode] as const,
  ([tabs, mode]) => {
    if (!isConceptMap.value || !mode || !tabs.length) return
    const valid = tabs.some((t) => t.id === mode)
    if (!valid) switchConceptMapTab('topic')
  }
)

/** Labels for paired display: Topic A/B for double bubble, Source/Analogy for bridge map */
const pairedLabelLeft = computed(() =>
  isBridgeMap.value ? (isZh.value ? '原词' : 'Source') : (doubleBubbleTopics?.value?.left ?? 'A')
)
const pairedLabelRight = computed(() =>
  isBridgeMap.value ? (isZh.value ? '类比词' : 'Analogy') : (doubleBubbleTopics?.value?.right ?? 'B')
)

function handleClose() {
  dismiss()
  emit('close')
}

async function handleFinish() {
  const closed = await finishSelection()
  if (closed) emit('close')
}

function handleCancel() {
  cancel()
  emit('close')
}

function handleRefresh() {
  startSession()
}

onMounted(async () => {
  if (isDoubleBubble.value && !panelsStore.nodePalettePanel.mode) {
    panelsStore.updateNodePalette({ mode: 'similarities' })
  }
  if (isMultiFlowMap.value && !panelsStore.nodePalettePanel.mode) {
    panelsStore.updateNodePalette({ mode: 'causes' })
  }
  const storedStage = panelsStore.nodePalettePanel.stage
  const stageName = defaultStage.value
  const stage1ToStage2 =
    (storedStage === 'branches' && stageName === 'children') ||
    (storedStage === 'steps' && stageName === 'substeps') ||
    (storedStage === 'categories' && stageName === 'children') ||
    (storedStage === 'parts' && stageName === 'subparts')
  const needsSync =
    isStagedDiagram.value &&
    (!storedStage ||
      (storedStage === 'dimensions' && stageName !== 'dimensions') ||
      stage1ToStage2)
  if (needsSync) {
    const parents = stage2Parents.value
    if (parents.length > 0 && stageName !== 'dimensions') {
      panelsStore.updateNodePalette({
        stage: stage2StageName.value,
        stage_data: getStageDataForParent(parents[0]),
        mode: parents[0].name,
      })
    } else {
      let stage_data: { dimension: string } | null = null
      if (isBridgeMap.value && stageName === 'pairs') {
        const dim = ((diagramData.value as { dimension?: string })?.dimension ?? '').trim()
        if (dim) stage_data = { dimension: dim }
      }
      panelsStore.updateNodePalette({
        stage: stageName,
        stage_data,
        mode: stageName,
      })
    }
  }
  await nextTick()
  if (
    panelsStore.nodePalettePanel.suggestions.length === 0 &&
    !isLoading.value
  ) {
    startSession()
  }
})

function getNodeCardStyle(suggestion: { source_llm?: string }, isSelected: boolean) {
  const colors = suggestion.source_llm
    ? getLLMColor(suggestion.source_llm, uiStore.isDark)
    : null
  const selectedStyle = uiStore.isDark
    ? { borderColor: 'rgb(96, 165, 250)', backgroundColor: 'rgb(30, 58, 95)' }
    : { borderColor: 'rgb(59, 130, 246)', backgroundColor: 'rgb(239, 246, 255)' }
  if (!colors) {
    return isSelected ? selectedStyle : {}
  }
  if (isSelected) {
    return {
      ...selectedStyle,
      borderLeftWidth: '4px',
      borderLeftStyle: 'solid',
      borderLeftColor: colors.text,
    }
  }
  return {
    borderColor: colors.border,
    backgroundColor: colors.bg,
  }
}

async function handleTabSwitch(
  mode: 'similarities' | 'differences' | 'causes' | 'effects'
) {
  if (mode === currentMode.value) return
  await switchTab(mode)
}

async function handleStageTabSwitch(parentId: string, parentName: string) {
  if (panelsStore.nodePalettePanel.mode === parentName) return
  await switchStageTab(parentId, parentName)
}

const PALETTE_CONCEPT_DATA_TYPE = 'application/mindgraph-palette-concept'

function handleConceptMapDragStart(event: DragEvent, suggestion: NodeSuggestion) {
  if (!event.dataTransfer) return
  event.dataTransfer.setData(PALETTE_CONCEPT_DATA_TYPE, JSON.stringify({ text: suggestion.text }))
  event.dataTransfer.effectAllowed = 'copy'
}

function getDisplayText(suggestion: NodeSuggestion): string {
  if (showPairedFormat.value && (suggestion.left || suggestion.right)) {
    const left = suggestion.left ?? ''
    const right = suggestion.right ?? ''
    return left && right ? `${left} | ${right}` : suggestion.text
  }
  return suggestion.text
}

</script>

<template>
  <div
    class="node-palette-panel bg-white dark:bg-gray-800 flex flex-col h-full"
  >
    <!-- Header (matches MindMate panel) -->
    <div
      class="panel-header h-14 px-4 flex items-center justify-between border-b border-gray-200 dark:border-gray-700 shrink-0"
    >
      <div class="flex items-center gap-3 min-w-0 flex-1">
        <h3 class="text-sm font-semibold text-gray-800 dark:text-white truncate shrink-0">
          瀑布流
        </h3>
        <!-- Staged diagram stage 2 tabs (one per parent) -->
        <div
          v-if="showStage2Tabs"
          class="flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
        >
          <button
            v-for="parent in stage2Parents"
            :key="parent.id"
            type="button"
            class="px-2 py-1 text-xs font-medium rounded-md transition-colors shrink-0"
            :class="
              panelsStore.nodePalettePanel.mode === parent.name
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            "
            :disabled="isLoading"
            :title="parent.name"
            @click="handleStageTabSwitch(parent.id, parent.name)"
          >
            {{ parent.name.length > 8 ? parent.name.slice(0, 7) + '…' : parent.name }}
          </button>
        </div>
        <!-- Double bubble map tabs: Similarities | Differences -->
        <div
          v-else-if="isDoubleBubble"
          class="flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
        >
          <button
            type="button"
            class="px-2.5 py-1 text-xs font-medium rounded-md transition-colors"
            :class="
              currentMode === 'similarities'
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            "
            :disabled="isLoading"
            @click="handleTabSwitch('similarities')"
          >
            {{ isZh ? '相似点' : 'Similarities' }}
          </button>
          <button
            type="button"
            class="px-2.5 py-1 text-xs font-medium rounded-md transition-colors"
            :class="
              currentMode === 'differences'
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            "
            :disabled="isLoading"
            @click="handleTabSwitch('differences')"
          >
            {{ isZh ? '差异点' : 'Differences' }}
          </button>
        </div>
        <!-- Concept map tabs: main topic + per-node sub-concept tabs -->
        <div
          v-else-if="showConceptMapTabs"
          class="flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
        >
          <button
            v-for="tab in conceptMapTabs"
            :key="tab.id"
            type="button"
            class="px-2 py-1 text-xs font-medium rounded-md transition-colors shrink-0"
            :class="
              panelsStore.nodePalettePanel.mode === tab.id
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            "
            :disabled="isLoading"
            :title="tab.name"
            @click="switchConceptMapTab(tab.id)"
          >
            {{ tab.name.length > 10 ? tab.name.slice(0, 9) + '…' : tab.name }}
          </button>
        </div>
        <!-- Multi flow map tabs: Causes | Effects -->
        <div
          v-else-if="isMultiFlowMap"
          class="flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
        >
          <button
            type="button"
            class="px-2.5 py-1 text-xs font-medium rounded-md transition-colors"
            :class="
              currentMode === 'causes'
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            "
            :disabled="isLoading"
            @click="handleTabSwitch('causes')"
          >
            {{ isZh ? '原因' : 'Causes' }}
          </button>
          <button
            type="button"
            class="px-2.5 py-1 text-xs font-medium rounded-md transition-colors"
            :class="
              currentMode === 'effects'
                ? 'bg-white dark:bg-gray-600 text-gray-900 dark:text-white shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
            "
            :disabled="isLoading"
            @click="handleTabSwitch('effects')"
          >
            {{ isZh ? '结果' : 'Effects' }}
          </button>
        </div>
        <!-- Bridge map: dimension tab when in pairs stage -->
        <div
          v-else-if="isBridgeMap && bridgeMapDimension"
          class="flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 px-2 py-1"
        >
          <span
            class="text-xs font-medium text-gray-700 dark:text-gray-300 truncate"
            :title="bridgeMapDimension"
          >
            {{ bridgeMapDimension.length > 12 ? bridgeMapDimension.slice(0, 11) + '…' : bridgeMapDimension }}
          </span>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <span
          v-if="!isConceptMap && selectedIds.length > 0"
          class="text-xs text-gray-500 dark:text-gray-400"
        >
          {{ selectedIds.length }} {{ isZh ? '已选' : 'selected' }}
        </span>
        <div class="flex items-center gap-0">
          <ElTooltip
            :content="isZh ? '重新生成' : 'Refresh'"
            placement="bottom"
          >
            <ElButton
              text
              circle
              size="small"
              class="shrink-0"
              :disabled="isLoading"
              @click="handleRefresh"
            >
              <RefreshCw
                :class="['w-4 h-4', isLoading ? 'animate-spin' : '']"
              />
            </ElButton>
          </ElTooltip>
          <ElButton
            text
            circle
            size="small"
            class="shrink-0"
            @click="handleClose"
          >
            <X class="w-4 h-4" />
          </ElButton>
        </div>
      </div>
    </div>

    <!-- Content -->
    <div class="panel-content flex-1 overflow-y-auto p-4 min-h-0">
      <!-- Loading (only when no suggestions yet - allow streaming nodes to show) -->
      <div
        v-if="isLoading && suggestions.length === 0"
        class="flex flex-col items-center justify-center py-12 gap-4"
      >
        <Loader2 class="w-8 h-8 animate-spin text-blue-500" />
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ isZh ? '正在生成创意...' : 'Generating ideas...' }}
        </p>
      </div>

      <!-- Error -->
      <div
        v-else-if="errorMessage"
        class="py-4 text-sm text-red-600 dark:text-red-400"
      >
        {{ errorMessage }}
      </div>

      <!-- Suggestions grid (show during loading so nodes stream in progressively) -->
      <div v-else class="flex flex-col gap-2">
        <p
          v-if="isLoading && suggestions.length > 0"
          class="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5"
        >
          <Loader2 class="w-3.5 h-3.5 animate-spin shrink-0" />
          {{ isZh ? `正在生成... 已收到 ${suggestions.length} 个` : `Generating... ${suggestions.length} received` }}
        </p>
        <div class="grid grid-cols-2 gap-2">
        <div
          v-for="suggestion in suggestions"
          :key="suggestion.id"
          class="node-card p-3 rounded-lg border-2 transition-all"
          :class="[
            isConceptMap ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer',
            !suggestion.source_llm && (isConceptMap || !selectedIds.includes(suggestion.id))
              ? 'border-gray-200 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700'
              : '',
          ]"
          :style="isConceptMap ? getNodeCardStyle(suggestion, false) : getNodeCardStyle(suggestion, selectedIds.includes(suggestion.id))"
          :draggable="isConceptMap"
          @dragstart="isConceptMap ? handleConceptMapDragStart($event, suggestion) : undefined"
          @click="!isConceptMap ? toggleSelection(suggestion.id) : undefined"
        >
          <div class="flex items-start gap-2">
            <div
              v-if="!isConceptMap && selectedIds.includes(suggestion.id)"
              class="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center shrink-0 mt-0.5"
            >
              <Check class="w-3 h-3 text-white" />
            </div>
            <!-- Paired format (one up, one down): double bubble differences or bridge map pairs -->
            <div
              v-if="showPairedFormat && (suggestion.left || suggestion.right)"
              class="flex flex-col gap-1 text-sm min-w-0 flex-1"
            >
              <div class="text-gray-700 dark:text-gray-300">
                <span class="font-medium text-blue-600 dark:text-blue-400">
                  {{ pairedLabelLeft }}:
                </span>
                {{ suggestion.left ?? '—' }}
              </div>
              <div class="text-gray-700 dark:text-gray-300">
                <span class="font-medium text-amber-600 dark:text-amber-400">
                  {{ pairedLabelRight }}:
                </span>
                {{ suggestion.right ?? '—' }}
              </div>
            </div>
            <!-- Similarities or fallback: plain text -->
            <span
              v-else
              class="text-sm text-gray-700 dark:text-gray-300 line-clamp-3 break-words"
            >
              {{ getDisplayText(suggestion) }}
            </span>
          </div>
        </div>
        </div>
      </div>

      <!-- Load more (only when we have an active session) -->
      <div
        v-if="sessionId && !isLoading && suggestions.length > 0 && !isLoadingMore"
        class="mt-4 flex justify-center"
      >
        <el-button
          size="small"
          @click="loadNextBatch"
        >
          {{ isZh ? '加载更多' : 'Load more' }}
        </el-button>
      </div>
      <div
        v-if="isLoadingMore"
        class="mt-4 flex justify-center"
      >
        <Loader2 class="w-5 h-5 animate-spin text-blue-500" />
      </div>

      <!-- Help text -->
      <div
        v-if="!isLoading && suggestions.length > 0"
        class="mt-4 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg"
      >
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {{
            isConceptMap
              ? isZh
                ? '拖拽概念到画布上添加。'
                : 'Drag concepts onto the canvas to add.'
              : isDimensionsStage
                ? isZh
                  ? '仅可选择1个维度，点击「下一步」继续。'
                  : 'Select exactly 1 dimension only, then click Next to continue.'
              : showNextButton
                ? isZh
                  ? '选择节点，点击「下一步」生成下一阶段节点。'
                  : 'Select nodes, then click Next to generate second-stage nodes.'
                : isZh
                  ? '点击选择节点，选择完成后点击下方「完成」添加到图示。'
                  : 'Click to select nodes, then click Finish to add to diagram.'
          }}
        </p>
      </div>
    </div>

    <!-- Footer: hide Finish for concept_map (drag-only) -->
    <div
      v-if="!isConceptMap"
      class="panel-footer p-4 border-t border-gray-200 dark:border-gray-700 flex gap-2 justify-center shrink-0"
    >
      <el-button
        size="default"
        @click="handleCancel"
      >
        {{ isZh ? '取消' : 'Cancel' }}
      </el-button>
      <el-button
        type="primary"
        size="default"
        :disabled="
          isDimensionsStage ? selectedIds.length !== 1 : selectedIds.length === 0
        "
        @click="handleFinish"
      >
        {{ showNextButton ? (isZh ? '下一步' : 'Next') : isZh ? '完成' : 'Finish' }}
      </el-button>
    </div>
    <!-- Concept map: minimal footer with close only -->
    <div
      v-else
      class="panel-footer p-4 border-t border-gray-200 dark:border-gray-700 flex gap-2 justify-center shrink-0"
    >
      <el-button
        size="default"
        @click="handleCancel"
      >
        {{ isZh ? '关闭' : 'Close' }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.node-palette-panel {
  display: flex;
  flex-direction: column;
}

.node-card:hover {
  opacity: 0.95;
}

.node-card:active {
  transform: scale(0.98);
}
</style>
