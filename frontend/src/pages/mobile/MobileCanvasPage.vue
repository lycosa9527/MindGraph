<script setup lang="ts">
/**
 * MobileCanvasPage — Simplified mobile diagram editor.
 * Vue Flow with touch support, minimal top toolbar, AI model selector at bottom.
 * Reuses DiagramCanvas + stores from desktop, but strips collaboration, presentation,
 * inline recommendations, and other desktop-only features.
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import {
  Bot,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  Loader2,
  Plus,
  Save,
  Sparkles,
  TableProperties,
  Trash2,
  X,
} from 'lucide-vue-next'

import { AIModelSelector } from '@/components/canvas'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { NodePalettePanel } from '@/components/panels'
import {
  eventBus,
  getNodePalette,
  getPanelCoordinator,
  useAutoComplete,
  useDiagramAutoSave,
  useInlineRecommendations,
  useInlineRecommendationsCoordinator,
  useLanguage,
  useNodeActions,
  useNotifications,
} from '@/composables'
import { INLINE_RECOMMENDATIONS_SUPPORTED_TYPES } from '@/composables/nodePalette/constants'
import {
  diagramSpecLikelyNeedsMarkdownPipeline,
  loadDiagramMarkdownPipeline,
} from '@/composables/core/diagramMarkdownPipeline'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import {
  useAuthStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
  useUIStore,
} from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

const route = useRoute()
const diagramStore = useDiagramStore()
const uiStore = useUIStore()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
const inlineRecStore = useInlineRecommendationsStore()
const { t } = useLanguage()
const notify = useNotifications()

getPanelCoordinator()
const { startSession: startNodePaletteSession } = getNodePalette({
  onError: (err: string) => notify.error(err),
})

const { autoComplete, isGenerating } = useAutoComplete()

const diagramAutoSave = useDiagramAutoSave()

useInlineRecommendationsCoordinator()
useNodeActions()
const { startRecommendations, selectOption, fetchNextBatch } = useInlineRecommendations()

const isSaving = ref(false)

async function handleSave() {
  if (isSaving.value) return
  if (!authStore.isAuthenticated) {
    notify.warning(t('notification.signInToUse'))
    return
  }
  isSaving.value = true
  try {
    const result = await diagramAutoSave.flush()
    if (result.saved) {
      notify.success(t('notification.saved', '已保存'))
    } else if (result.reason === 'skipped_slots_full') {
      notify.warning(t('notification.slotsFull', '图示槽位已满'))
    }
  } finally {
    isSaving.value = false
  }
}

const DIAGRAM_TYPE_MAP: Record<string, DiagramType> = {
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

const DIAGRAM_TYPE_TO_ZH: Record<DiagramType, string> = {
  circle_map: '圆圈图',
  bubble_map: '气泡图',
  double_bubble_map: '双气泡图',
  tree_map: '树形图',
  brace_map: '括号图',
  flow_map: '流程图',
  multi_flow_map: '复流程图',
  bridge_map: '桥形图',
  mindmap: '思维导图',
  mind_map: '思维导图',
  concept_map: '概念图',
  diagram: '图表',
}

const VALID_TYPES: DiagramType[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'mindmap',
  'mind_map',
  'concept_map',
]

const chartType = computed(() => uiStore.selectedChartType)
const diagramType = computed<DiagramType | null>(() => {
  if (!chartType.value) return null
  return DIAGRAM_TYPE_MAP[chartType.value] || null
})

const showNodePalette = ref(false)
const showModelDrawer = ref(false)

const isConceptMap = computed(() => diagramStore.type === 'concept_map')
const tabReady = computed(() => {
  if (isConceptMap.value) return false
  return inlineRecStore.isReady && authStore.isAuthenticated
})

const MOBILE_REC_PER_PAGE = 3

const inlineRecActive = computed(() => !!inlineRecStore.activeNodeId)
const inlineRecGenerating = computed(() => {
  const nid = inlineRecStore.activeNodeId
  return !!nid && inlineRecStore.generatingNodeIds.has(nid)
})

const mobileRecPage = ref(0)
const mobileRecOptions = computed(() => {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return []
  const all = inlineRecStore.allOptions[nid] ?? []
  const start = mobileRecPage.value * MOBILE_REC_PER_PAGE
  return all.slice(start, start + MOBILE_REC_PER_PAGE)
})
const mobileRecTotalPages = computed(() => {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return 0
  const total = (inlineRecStore.allOptions[nid] ?? []).length
  return total <= 0 ? 0 : Math.ceil(total / MOBILE_REC_PER_PAGE)
})
const mobileCanPrev = computed(() => mobileRecPage.value > 0)
const mobileRecFetching = computed(() => {
  const nid = inlineRecStore.activeNodeId
  return !!nid && inlineRecStore.fetchingNextBatchNodeIds.has(nid)
})

watch(
  () => inlineRecStore.activeNodeId,
  () => {
    mobileRecPage.value = 0
  }
)

function isNodeEligibleForInlineRec(node: { id?: string; type?: string }): boolean {
  const dt = diagramStore.type === 'mind_map' ? 'mindmap' : diagramStore.type
  if (!dt || !(INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(dt))
    return false
  const nid = node.id ?? ''
  if (dt === 'mindmap') return /^branch-(l|r)-(1|2)-/.test(nid)
  if (dt === 'flow_map') return nid.startsWith('flow-step-') || nid.startsWith('flow-substep-')
  if (dt === 'tree_map')
    return nid === 'dimension-label' || /^tree-cat-\d+$/.test(nid) || /^tree-leaf-/.test(nid)
  if (dt === 'brace_map')
    return nid === 'dimension-label' || node.type === 'brace' || nid.startsWith('brace-')
  if (dt === 'circle_map') return nid.startsWith('context-')
  if (dt === 'bubble_map') return nid.startsWith('bubble-')
  if (dt === 'double_bubble_map')
    return (
      nid.startsWith('similarity-') || nid.startsWith('left-diff-') || nid.startsWith('right-diff-')
    )
  if (dt === 'multi_flow_map') return nid.startsWith('cause-') || nid.startsWith('effect-')
  if (dt === 'bridge_map')
    return (
      nid === 'dimension-label' ||
      (nid.startsWith('pair-') && (nid.endsWith('-left') || nid.endsWith('-right')))
    )
  return false
}

function handleTabMode(): void {
  if (!authStore.isAuthenticated) {
    notify.warning(t('notification.signInToUse'))
    return
  }
  if (!inlineRecStore.isReady) return

  const selectedId = diagramStore.selectedNodes[0]
  if (!selectedId) {
    notify.warning(t('canvas.toolbar.selectNodesToDelete', '请先选择一个节点'))
    return
  }
  const nodes = diagramStore.data?.nodes ?? []
  const node = nodes.find((n) => n.id === selectedId)
  if (!node || !isNodeEligibleForInlineRec(node)) {
    notify.warning(t('notification.nodeNotEligible', '该节点不支持推荐'))
    return
  }
  startRecommendations(selectedId)
}

function handleRecSelect(localIdx: number): void {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return
  const globalIdx = mobileRecPage.value * MOBILE_REC_PER_PAGE + localIdx
  selectOption(nid, globalIdx)
}

async function handleRecNext(): Promise<void> {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return
  const hasMoreLocal = mobileRecPage.value < mobileRecTotalPages.value - 1
  if (hasMoreLocal) {
    mobileRecPage.value++
    return
  }
  await fetchNextBatch(nid)
  const newTotal = (inlineRecStore.allOptions[nid] ?? []).length
  const newTotalPages = Math.ceil(newTotal / MOBILE_REC_PER_PAGE)
  if (newTotalPages > mobileRecPage.value + 1) {
    mobileRecPage.value++
  }
}

function handleRecPrev(): void {
  if (mobileRecPage.value > 0) mobileRecPage.value--
}

function handleRecDismiss(): void {
  inlineRecStore.invalidateAll()
}

function handleAddNode() {
  if (diagramStore.type === 'concept_map') return
  eventBus.emit('diagram:add_node_requested', {})
}

function handleDeleteSelected() {
  eventBus.emit('diagram:delete_selected_requested', {})
}

function handleAutoComplete() {
  if (!authStore.isAuthenticated) {
    notify.warning(t('notification.signInToUse'))
    return
  }
  if (isGenerating.value) return
  autoComplete()
}

function toggleNodePalette() {
  if (panelsStore.nodePalettePanel.isOpen) {
    panelsStore.closeNodePalette()
    showNodePalette.value = false
  } else {
    panelsStore.openNodePalette()
    showNodePalette.value = true
  }
}

watch(
  () => panelsStore.nodePalettePanel.isOpen,
  (isOpen) => {
    showNodePalette.value = isOpen
  }
)

watch(
  () => uiStore.selectedChartType,
  () => {
    if (diagramType.value) {
      diagramStore.setDiagramType(diagramType.value)
      if (!diagramStore.data) {
        diagramStore.loadDefaultTemplate(diagramType.value)
      }
    }
  },
  { immediate: true }
)

eventBus.onWithOwner(
  'nodePalette:opened',
  (data: { hasRestoredSession?: boolean; wasPanelAlreadyOpen?: boolean }) => {
    if (!data.hasRestoredSession && diagramStore.data?.nodes?.length) {
      startNodePaletteSession({ keepSessionId: data.wasPanelAlreadyOpen ?? false })
    }
  },
  'MobileCanvasPage'
)

onMounted(async () => {
  await ensureFontsForLanguageCode(uiStore.promptLanguage)
  await savedDiagramsStore.fetchDiagrams()

  const diagramIdRaw = route.query.diagramId ?? route.query.diagram_id
  const diagramId = typeof diagramIdRaw === 'string' ? diagramIdRaw : undefined
  if (diagramId) {
    await loadDiagramFromLibrary(diagramId)
    return
  }

  const typeFromUrl = route.query.type as DiagramType | undefined
  if (typeFromUrl && VALID_TYPES.includes(typeFromUrl)) {
    const zhName = DIAGRAM_TYPE_TO_ZH[typeFromUrl]
    if (zhName) {
      uiStore.setSelectedChartType(zhName)
    }
    diagramStore.setDiagramType(typeFromUrl)
    if (!diagramStore.data) {
      diagramStore.loadDefaultTemplate(typeFromUrl)
    }
    return
  }

  if (diagramType.value) {
    diagramStore.setDiagramType(diagramType.value)
    if (!diagramStore.data) {
      diagramStore.loadDefaultTemplate(diagramType.value)
    }
  }
})

async function loadDiagramFromLibrary(diagramId: string): Promise<void> {
  const diagram = await savedDiagramsStore.getDiagram(diagramId)
  if (!diagram) return

  savedDiagramsStore.setActiveDiagram(diagramId)
  diagramStore.clearHistory()

  const spec = diagram.spec as Record<string, unknown>
  llmResultsStore.clearCache()

  eventBus.emit('diagram:loaded_from_library', {
    diagramId,
    diagramType: diagram.diagram_type,
  })
  if (diagramSpecLikelyNeedsMarkdownPipeline(spec)) {
    await loadDiagramMarkdownPipeline({ bumpLayout: false })
  }
  const loaded = diagramStore.loadFromSpec(spec, diagram.diagram_type as DiagramType)
  if (loaded) {
    const zhName = Object.entries(DIAGRAM_TYPE_MAP).find(([, v]) => v === diagram.diagram_type)?.[0]
    if (zhName) uiStore.setSelectedChartType(zhName)
  }
}

onUnmounted(() => {
  diagramAutoSave.flush()
  diagramAutoSave.teardown()
  eventBus.removeAllListenersForOwner('MobileCanvasPage')

  diagramStore.reset()
  savedDiagramsStore.clearActiveDiagram()
  useLLMResultsStore().reset()
  usePanelsStore().reset()
  uiStore.setSelectedChartType('选择具体图示')
  uiStore.setFreeInputValue('')
})
</script>

<template>
  <div class="mobile-canvas flex flex-col flex-1 min-h-0 bg-gray-50 relative overflow-hidden">
    <!-- Top toolbar (fixed, no zoom/pan) -->
    <div
      class="mobile-toolbar flex items-center justify-evenly px-2 py-1.5 bg-white border-b border-gray-200 shrink-0 touch-none"
    >
      <button
        class="toolbar-btn"
        :disabled="isSaving"
        @click="handleSave"
      >
        <Save :size="18" />
        <span class="toolbar-label">{{ t('canvas.toolbar.save', '保存') }}</span>
      </button>

      <button
        class="toolbar-btn"
        :disabled="diagramStore.type === 'concept_map'"
        @click="handleAddNode"
      >
        <Plus :size="18" />
        <span class="toolbar-label">{{ t('canvas.toolbar.add', '添加') }}</span>
      </button>

      <button
        class="toolbar-btn"
        @click="handleDeleteSelected"
      >
        <Trash2 :size="18" />
        <span class="toolbar-label">{{ t('canvas.toolbar.delete', '删除') }}</span>
      </button>

      <button
        class="toolbar-btn toolbar-btn--primary"
        :class="{ 'toolbar-btn--generating': isGenerating }"
        @click="handleAutoComplete"
      >
        <Sparkles
          :size="18"
          class="ai-icon"
        />
        <span class="toolbar-label">{{ t('canvas.toolbar.aiGenerate', 'AI生成') }}</span>
      </button>

      <button
        class="toolbar-btn toolbar-btn--purple"
        :class="{ 'toolbar-btn--active': showNodePalette }"
        @click="toggleNodePalette"
      >
        <LayoutGrid :size="18" />
        <span class="toolbar-label">{{ t('canvas.toolbar.nodePalette', '节点面板') }}</span>
      </button>
    </div>

    <!-- Node Palette slide-over -->
    <Transition name="palette-slide">
      <div
        v-if="showNodePalette && panelsStore.nodePalettePanel.isOpen"
        class="absolute inset-0 z-30 bg-white flex flex-col"
        style="top: 44px"
      >
        <NodePalettePanel @close="toggleNodePalette" />
      </div>
    </Transition>

    <!-- Diagram canvas with touch support (only this area is pannable/zoomable) -->
    <div class="canvas-area flex-1 min-h-0 relative overflow-hidden">
      <DiagramCanvas
        v-if="diagramStore.data"
        class="absolute inset-0 canvas-touch"
        :show-background="true"
        :show-minimap="false"
        :fit-view-on-init="true"
        :hand-tool-active="false"
        :collab-locked-node-ids="[]"
        :pan-on-drag-buttons="[0, 1, 2]"
      />
      <div
        v-else
        class="flex items-center justify-center h-full text-gray-400 text-sm"
      >
        {{ t('canvas.emptyState', '选择图示类型开始创建') }}
      </div>
    </div>

    <!-- Bottom bar (fixed, no zoom/pan) -->
    <div
      class="mobile-bottom-bar shrink-0 px-3 py-2 bg-white/90 backdrop-blur-md border-t border-gray-200 touch-none"
    >
      <!-- Inline recommendations mode -->
      <div
        v-if="inlineRecActive"
        class="flex items-center gap-1.5 min-h-[36px]"
      >
        <button
          class="shrink-0 p-1.5 rounded-md bg-red-50 active:bg-red-100 text-red-500 transition-colors"
          @click="handleRecDismiss"
        >
          <X :size="14" />
        </button>

        <button
          class="shrink-0 p-1.5 rounded-md transition-colors"
          :class="
            mobileCanPrev
              ? 'bg-gray-100 active:bg-gray-200 text-gray-600'
              : 'bg-gray-50 text-gray-300'
          "
          :disabled="!mobileCanPrev"
          @click="handleRecPrev"
        >
          <ChevronLeft
            :size="14"
            class="mg-icon-flip-rtl"
          />
        </button>

        <div
          v-if="inlineRecGenerating && mobileRecOptions.length === 0"
          class="flex-1 flex items-center justify-center gap-2 text-xs text-gray-500"
        >
          <Loader2
            :size="14"
            class="animate-spin text-green-500"
          />
          <span>{{ t('inlineRec.generating', '生成推荐中...') }}</span>
        </div>
        <div
          v-else
          class="rec-scroll-area flex-1 overflow-x-auto"
        >
          <div class="flex items-stretch gap-1.5">
            <button
              v-for="(opt, idx) in mobileRecOptions"
              :key="`${inlineRecStore.activeNodeId}-${mobileRecPage}-${idx}`"
              class="rec-chip shrink-0 px-2.5 py-1.5 rounded-lg bg-green-50 active:bg-green-100 text-xs text-green-700 font-medium transition-colors border border-green-200 whitespace-nowrap"
              @click="handleRecSelect(idx)"
            >
              <span class="text-green-500 font-bold mr-1">{{
                mobileRecPage * MOBILE_REC_PER_PAGE + idx + 1
              }}</span>
              {{ opt }}
            </button>
          </div>
        </div>

        <button
          class="shrink-0 p-1.5 rounded-md transition-colors"
          :class="
            mobileRecFetching
              ? 'bg-gray-50 text-gray-300'
              : 'bg-gray-100 active:bg-gray-200 text-gray-600'
          "
          :disabled="mobileRecFetching"
          @click="handleRecNext"
        >
          <Loader2
            v-if="mobileRecFetching"
            :size="14"
            class="animate-spin"
          />
          <ChevronRight
            v-else
            :size="14"
            class="mg-icon-flip-rtl"
          />
        </button>
      </div>

      <!-- Normal mode: AI models + Tab button -->
      <div
        v-else
        class="flex items-center justify-between"
      >
        <button
          class="bottom-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 active:bg-gray-200 transition-colors"
          @click="showModelDrawer = true"
        >
          <Bot
            :size="16"
            class="text-indigo-500"
          />
          <span class="text-xs font-medium text-gray-700">{{ t('aiModel.label', 'AI 模型') }}</span>
        </button>

        <button
          class="bottom-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors"
          :class="
            tabReady
              ? 'bg-green-50 active:bg-green-100 text-green-600'
              : 'bg-gray-100 text-gray-400 opacity-50'
          "
          :disabled="!tabReady"
          @click="handleTabMode"
        >
          <TableProperties :size="16" />
          <span class="text-xs font-medium">Tab</span>
        </button>
      </div>
    </div>

    <!-- AI Model Bottom Sheet -->
    <Teleport to="body">
      <Transition name="model-sheet">
        <div
          v-if="showModelDrawer"
          class="model-sheet-overlay"
          @click.self="showModelDrawer = false"
        >
          <div class="model-sheet-panel">
            <div class="model-sheet-handle" />
            <div class="flex items-center justify-center px-4 py-4">
              <AIModelSelector />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.mobile-canvas {
  overflow: hidden;
}

.mobile-toolbar {
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  z-index: 20;
  position: relative;
}

.mobile-toolbar::-webkit-scrollbar {
  display: none;
}

.toolbar-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 12px;
  border-radius: 8px;
  color: #374151;
  background: transparent;
  border: none;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.toolbar-btn:active {
  background: #f3f4f6;
}

.toolbar-btn:disabled {
  opacity: 0.4;
  pointer-events: none;
}

.toolbar-btn--active {
  color: #4f46e5;
  background: #eef2ff;
}

.toolbar-btn--primary {
  color: #ffffff;
  background: #4f46e5;
  border-radius: 10px;
}

.toolbar-btn--primary:active {
  background: #4338ca;
}

.toolbar-btn--generating {
  position: relative;
  background: transparent !important;
  box-shadow: none;
  padding: 2px 8px !important;
}

.toolbar-btn--generating::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 10px;
  padding: 2px;
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
  animation: ai-ring-spin 2.5s linear infinite;
  background: conic-gradient(
    from var(--ai-ring-angle, 0deg) at 50% 50%,
    rgba(59, 130, 246, 0.35) 0deg,
    rgba(255, 255, 255, 0.75) 52deg,
    #93c5fd 130deg,
    #3b82f6 180deg,
    #60a5fa 228deg,
    rgba(255, 255, 255, 0.75) 308deg,
    rgba(59, 130, 246, 0.35) 360deg
  );
}

.toolbar-btn--generating .ai-icon {
  animation: ai-sparkle-pulse 1.2s ease-in-out infinite;
}

.toolbar-btn--generating .toolbar-label {
  position: relative;
  z-index: 1;
}

.toolbar-btn--purple {
  color: #ffffff;
  background: #7c3aed;
  border-radius: 10px;
}

.toolbar-btn--purple:active {
  background: #6d28d9;
}

.toolbar-label {
  font-size: 10px;
  line-height: 1.2;
}

.palette-slide-enter-active,
.palette-slide-leave-active {
  transition: transform 0.25s ease;
}

.palette-slide-enter-from,
.palette-slide-leave-to {
  transform: translateY(100%);
}

.canvas-area {
  z-index: 1;
  touch-action: none;
}

.canvas-touch :deep(.vue-flow__viewport) {
  touch-action: none;
}

.canvas-touch :deep(.vue-flow__node) {
  touch-action: none;
}

.mobile-bottom-bar {
  padding-bottom: max(8px, env(safe-area-inset-bottom));
  z-index: 20;
  position: relative;
}

.bottom-btn:disabled {
  pointer-events: none;
}

.rec-scroll-area {
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.rec-scroll-area::-webkit-scrollbar {
  display: none;
}

.rec-chip {
  text-align: left;
  line-height: 1.3;
  max-width: 45vw;
}
</style>

<style>
@property --ai-ring-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

@keyframes ai-ring-spin {
  to {
    --ai-ring-angle: 360deg;
  }
}

@keyframes ai-sparkle-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.6;
    transform: scale(0.85);
  }
}

.model-sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}

.model-sheet-panel {
  width: 100%;
  background: #ffffff;
  border-radius: 16px 16px 0 0;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.15);
}

.model-sheet-handle {
  width: 36px;
  height: 4px;
  background: #d1d5db;
  border-radius: 2px;
  margin: 10px auto 0;
}

.model-sheet-enter-active,
.model-sheet-leave-active {
  transition: opacity 0.2s ease;
}

.model-sheet-enter-active .model-sheet-panel,
.model-sheet-leave-active .model-sheet-panel {
  transition: transform 0.25s ease;
}

.model-sheet-enter-from,
.model-sheet-leave-to {
  opacity: 0;
}

.model-sheet-enter-from .model-sheet-panel,
.model-sheet-leave-to .model-sheet-panel {
  transform: translateY(100%);
}
</style>
