<script setup lang="ts">
/**
 * Node Palette Panel (瀑布流) - AI-suggested nodes with streaming
 *
 * Displays AI-generated node suggestions in a grid.
 * - Select nodes and click Finish to add (concept map uses RootConceptModal)
 *
 * For double_bubble_map: shows tabs (相似点/Similarities | 差异点/Differences).
 * Differences tab displays paired attributes for both Topic A and Topic B.
 */
import { type ComputedRef, computed, inject, nextTick, onMounted } from 'vue'

import { ElButton, ElTooltip } from 'element-plus'

import { Check, Loader2, RefreshCw, X } from 'lucide-vue-next'

import { useLanguage, useNotifications } from '@/composables'
import { getNodePalette } from '@/composables/nodePalette/useNodePalette'
import { getLLMColor } from '@/config/llmModelColors'
import { useDiagramStore, usePanelsStore, useUIStore } from '@/stores'
import type { NodeSuggestion } from '@/types/panels'

const emit = defineEmits<{
  (e: 'close'): void
}>()

const { t } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()
const panelsStore = usePanelsStore()
const diagramStore = useDiagramStore()

const collabCanvas = inject<{ isDiagramOwner?: ComputedRef<boolean> } | undefined>(
  'collabCanvas',
  undefined
)
const isGuestCollab = computed(() => {
  if (!diagramStore.collabSessionActive) return false
  const own = collabCanvas?.isDiagramOwner
  return own ? !own.value : false
})

const {
  isLoading,
  isLoadingMore,
  paletteStreamPhase,
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
} = getNodePalette({
  onError: (err) => notify.error(err),
})

const isDoubleBubble = computed(() => diagramType.value === 'double_bubble_map')
const isMultiFlowMap = computed(() => diagramType.value === 'multi_flow_map')
const isBridgeMap = computed(() => diagramType.value === 'bridge_map')
const currentMode = computed(
  () =>
    (panelsStore.nodePalettePanel.mode as 'similarities' | 'differences' | 'causes' | 'effects') ??
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

/** Taller header + topic legend when viewing double-bubble differences */
const showDoubleBubbleDiffLegend = computed(
  () => isDoubleBubble.value && currentMode.value === 'differences'
)

/** Traveling border on tab strip: blue = request in flight, green = SSE nodes arriving */
const paletteTabStripGlowClass = computed(() => {
  if (!isLoading.value && !isLoadingMore.value) return ''
  if (paletteStreamPhase.value === 'streaming') return 'palette-tab-strip-wrap--streaming'
  if (paletteStreamPhase.value === 'requesting') return 'palette-tab-strip-wrap--requesting'
  return 'palette-tab-strip-wrap--requesting'
})

/** Labels for paired display: Topic A/B for double bubble, Source/Analogy for bridge map */
const pairedLabelLeft = computed(() =>
  isBridgeMap.value ? t('nodePalette.bridgeSource') : (doubleBubbleTopics?.value?.left ?? 'A')
)
const pairedLabelRight = computed(() =>
  isBridgeMap.value ? t('nodePalette.bridgeAnalogy') : (doubleBubbleTopics?.value?.right ?? 'B')
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
    (!storedStage || (storedStage === 'dimensions' && stageName !== 'dimensions') || stage1ToStage2)
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
  if (panelsStore.nodePalettePanel.suggestions.length === 0 && !isLoading.value) {
    startSession()
  }
})

function getNodeCardStyle(suggestion: { source_llm?: string }, isSelected: boolean) {
  const colors = suggestion.source_llm ? getLLMColor(suggestion.source_llm, uiStore.isDark) : null
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

async function handleTabSwitch(mode: 'similarities' | 'differences' | 'causes' | 'effects') {
  if (mode === currentMode.value) return
  await switchTab(mode)
}

async function handleStageTabSwitch(parentId: string, parentName: string) {
  if (panelsStore.nodePalettePanel.mode === parentName) return
  await switchStageTab(parentId, parentName)
}

/** Parse paired lines for double-bubble differences (API fields or "left | right" in text) */
function getDoubleBubblePairedParts(suggestion: NodeSuggestion): { left: string; right: string } {
  const l = (suggestion.left ?? '').trim()
  const r = (suggestion.right ?? '').trim()
  if (l || r) {
    return { left: l, right: r }
  }
  const t = (suggestion.text ?? '').trim()
  if (!t) return { left: '', right: '' }
  if (t.includes('|')) {
    const parts = t.split('|').map((x) => x.trim())
    const left = parts[0] ?? ''
    if (parts.length === 2) {
      return { left, right: parts[1] ?? '' }
    }
    if (parts.length >= 3) {
      return { left, right: parts[1] ?? '' }
    }
    return { left, right: '' }
  }
  return { left: t, right: '' }
}

function getPairedPartsForSuggestion(suggestion: NodeSuggestion): { left: string; right: string } {
  if (isDoubleBubble.value && currentMode.value === 'differences') {
    return getDoubleBubblePairedParts(suggestion)
  }
  return {
    left: (suggestion.left ?? '').trim(),
    right: (suggestion.right ?? '').trim(),
  }
}

function showPairedCardRows(suggestion: NodeSuggestion): boolean {
  if (!showPairedFormat.value) return false
  const p = getPairedPartsForSuggestion(suggestion)
  return !!(p.left || p.right)
}

function getDisplayText(suggestion: NodeSuggestion): string {
  if (showPairedFormat.value && (suggestion.left || suggestion.right)) {
    const left = suggestion.left ?? ''
    const right = suggestion.right ?? ''
    return left && right ? `${left} | ${right}` : suggestion.text
  }
  if (showPairedFormat.value && isDoubleBubble.value && currentMode.value === 'differences') {
    const p = getDoubleBubblePairedParts(suggestion)
    if (p.left && p.right) return `${p.left} | ${p.right}`
    if (p.left || p.right) return p.left || p.right
  }
  return suggestion.text
}
</script>

<template>
  <div class="node-palette-panel bg-white dark:bg-gray-800 flex flex-col h-full">
    <!-- Header (matches MindMate panel) -->
    <div
      class="panel-header px-4 flex justify-between border-b border-gray-200 dark:border-gray-700 shrink-0"
      :class="showDoubleBubbleDiffLegend ? 'min-h-[7rem] items-start py-2' : 'h-14 items-center'"
    >
      <div
        class="flex gap-3 min-w-0 flex-1"
        :class="showDoubleBubbleDiffLegend ? 'items-start' : 'items-center'"
      >
        <h3 class="text-sm font-semibold text-gray-800 dark:text-white truncate shrink-0">
          {{ t('nodePalette.panelTitle') }}
        </h3>
        <!-- Staged diagram stage 2 tabs (one per parent) -->
        <div
          v-if="showStage2Tabs"
          class="palette-tab-strip-wrap flex flex-1 min-w-0"
          :class="paletteTabStripGlowClass"
        >
          <div
            class="palette-tab-strip-inner flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
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
        </div>
        <!-- Double bubble map tabs: Similarities | Differences (+ stacked topic legend in differences) -->
        <div
          v-else-if="isDoubleBubble"
          class="palette-tab-strip-wrap flex flex-col flex-1 min-w-0 gap-1.5"
          :class="paletteTabStripGlowClass"
        >
          <div
            class="palette-tab-strip-inner flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
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
              {{ t('nodePalette.similarities') }}
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
              {{ t('nodePalette.differences') }}
            </button>
          </div>
          <div
            v-if="currentMode === 'differences'"
            class="db-diff-topic-legend flex flex-col gap-0.5 w-full min-w-0 pl-0.5 pr-1"
          >
            <div
              class="text-[10px] leading-tight font-medium text-blue-600 dark:text-blue-400 truncate"
              :title="`${pairedLabelLeft}: ${doubleBubbleTopics?.left ?? ''}`"
            >
              <span class="font-normal text-gray-500 dark:text-gray-400"
                >{{ pairedLabelLeft }} ·
              </span>
              {{ doubleBubbleTopics?.left ?? '—' }}
            </div>
            <div
              class="text-[10px] leading-tight font-medium text-amber-600 dark:text-amber-400 truncate"
              :title="`${pairedLabelRight}: ${doubleBubbleTopics?.right ?? ''}`"
            >
              <span class="font-normal text-gray-500 dark:text-gray-400"
                >{{ pairedLabelRight }} ·
              </span>
              {{ doubleBubbleTopics?.right ?? '—' }}
            </div>
          </div>
        </div>
        <!-- Multi flow map tabs: Causes | Effects -->
        <div
          v-else-if="isMultiFlowMap"
          class="palette-tab-strip-wrap flex flex-1 min-w-0"
          :class="paletteTabStripGlowClass"
        >
          <div
            class="palette-tab-strip-inner flex flex-1 min-w-0 rounded-lg bg-gray-100 dark:bg-gray-700 p-0.5 overflow-x-auto"
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
              {{ t('nodePalette.causes') }}
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
              {{ t('nodePalette.effects') }}
            </button>
          </div>
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
            {{
              bridgeMapDimension.length > 12
                ? bridgeMapDimension.slice(0, 11) + '…'
                : bridgeMapDimension
            }}
          </span>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <span
          v-if="selectedIds.length > 0"
          class="text-xs text-gray-500 dark:text-gray-400"
        >
          {{ selectedIds.length }} {{ t('nodePalette.selected') }}
        </span>
        <div class="flex items-center gap-0">
          <ElTooltip
            :content="t('nodePalette.refresh')"
            placement="bottom"
          >
            <ElButton
              text
              circle
              size="small"
              class="shrink-0"
              :disabled="isLoading || isGuestCollab"
              @click="handleRefresh"
            >
              <RefreshCw :class="['w-4 h-4', isLoading ? 'animate-spin' : '']" />
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
          {{ t('nodePalette.generatingIdeas') }}
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
      <div
        v-else
        class="flex flex-col gap-2"
      >
        <p
          v-if="isLoading && suggestions.length > 0"
          class="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1.5"
        >
          <Loader2 class="w-3.5 h-3.5 animate-spin shrink-0" />
          {{ t('nodePalette.generatingProgress', { count: suggestions.length }) }}
        </p>
        <div class="grid grid-cols-2 gap-2">
          <div
            v-for="suggestion in suggestions"
            :key="suggestion.id"
            class="node-card p-3 rounded-lg border-2 transition-all"
            :class="[
              isGuestCollab ? 'cursor-default opacity-70' : 'cursor-pointer',
              !suggestion.source_llm && !selectedIds.includes(suggestion.id)
                ? 'border-gray-200 dark:border-gray-600 hover:border-blue-300 dark:hover:border-blue-700'
                : '',
            ]"
            :style="getNodeCardStyle(suggestion, selectedIds.includes(suggestion.id))"
            @click="isGuestCollab ? undefined : toggleSelection(suggestion.id)"
          >
            <div class="flex items-start gap-2">
              <div
                v-if="selectedIds.includes(suggestion.id)"
                class="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center shrink-0 mt-0.5"
              >
                <Check class="w-3 h-3 text-white" />
              </div>
              <!-- Paired format (A over B): double bubble differences (incl. parsed text) or bridge pairs -->
              <div
                v-if="showPairedCardRows(suggestion)"
                dir="auto"
                class="flex flex-col gap-1 text-sm min-w-0 flex-1"
                style="line-break: auto"
              >
                <div class="text-gray-700 dark:text-gray-300">
                  <span class="font-medium text-blue-600 dark:text-blue-400">
                    {{ pairedLabelLeft }}:
                  </span>
                  {{ getPairedPartsForSuggestion(suggestion).left || '—' }}
                </div>
                <div class="text-gray-700 dark:text-gray-300">
                  <span class="font-medium text-amber-600 dark:text-amber-400">
                    {{ pairedLabelRight }}:
                  </span>
                  {{ getPairedPartsForSuggestion(suggestion).right || '—' }}
                </div>
              </div>
              <!-- Similarities or fallback: plain text -->
              <span
                v-else
                dir="auto"
                class="text-sm text-gray-700 dark:text-gray-300 line-clamp-3 break-words"
                style="line-break: auto"
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
          {{ t('nodePalette.loadMore') }}
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
            isDimensionsStage
              ? t('nodePalette.helpDimension')
              : showNextButton
                ? t('nodePalette.helpNext')
                : t('nodePalette.helpFinish')
          }}
        </p>
      </div>
    </div>

    <div
      class="panel-footer p-4 border-t border-gray-200 dark:border-gray-700 flex gap-2 justify-center shrink-0"
    >
      <el-button
        size="default"
        @click="handleCancel"
      >
        {{ t('nodePalette.cancel') }}
      </el-button>
      <el-button
        type="primary"
        size="default"
        :disabled="
          isGuestCollab || (isDimensionsStage ? selectedIds.length !== 1 : selectedIds.length === 0)
        "
        @click="handleFinish"
      >
        {{ showNextButton ? t('nodePalette.next') : t('nodePalette.finish') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
@property --palette-border-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

.node-palette-panel {
  display: flex;
  flex-direction: column;
}

.palette-tab-strip-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  border-radius: 0.5rem;
}

.palette-tab-strip-wrap--requesting,
.palette-tab-strip-wrap--streaming {
  padding: 2px;
}

.palette-tab-strip-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 2px;
  --palette-border-angle: 0deg;
  opacity: 0;
  pointer-events: none;
  z-index: 0;
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  animation: palette-border-travel 2.5s linear infinite;
  transition: opacity 0.15s ease;
}

.palette-tab-strip-wrap--requesting::before {
  opacity: 1;
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 50deg,
    #93c5fd 130deg,
    #3b82f6 180deg,
    #60a5fa 230deg,
    #d6d3d1 310deg,
    #e7e5e4 360deg
  );
}

.palette-tab-strip-wrap--streaming::before {
  opacity: 1;
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #e7e5e4 0deg,
    #d6d3d1 50deg,
    #86efac 130deg,
    #22c55e 180deg,
    #4ade80 230deg,
    #d6d3d1 310deg,
    #e7e5e4 360deg
  );
}

:global(.dark) .palette-tab-strip-wrap--requesting::before {
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #1f2937 0deg,
    #374151 50deg,
    #60a5fa 130deg,
    #2563eb 180deg,
    #38bdf8 230deg,
    #374151 310deg,
    #1f2937 360deg
  );
}

:global(.dark) .palette-tab-strip-wrap--streaming::before {
  background: conic-gradient(
    from var(--palette-border-angle) at 50% 50%,
    #1f2937 0deg,
    #374151 50deg,
    #4ade80 130deg,
    #16a34a 180deg,
    #86efac 230deg,
    #374151 310deg,
    #1f2937 360deg
  );
}

.palette-tab-strip-inner {
  position: relative;
  z-index: 1;
}

@keyframes palette-border-travel {
  to {
    --palette-border-angle: 360deg;
  }
}

.node-card:hover {
  opacity: 0.95;
}

.node-card:active {
  transform: scale(0.98);
}
</style>
