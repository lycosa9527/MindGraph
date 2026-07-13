<script setup lang="ts">
/**
 * MobileCanvasPage — Simplified mobile diagram editor.
 * Vue Flow with touch support, minimal top toolbar, AI model selector at bottom.
 * Reuses DiagramCanvas + stores from desktop, but strips collaboration, presentation,
 * and other desktop-only features. Concept map: 启用 AI in top bar; bottom shows inline
 * rec only while active (tap canvas to dismiss, same as desktop coordinator).
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

import { storeToRefs } from 'pinia'

import {
  Bot,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  Loader2,
  Maximize2,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  TableProperties,
  Trash2,
  X,
} from '@lucide/vue'

import {
  AIModelSelector,
  ConceptMapFocusReviewPicker,
  ConceptMapLabelPicker,
  ConceptMapRootConceptPicker,
} from '@/components/canvas'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { NodePalettePanel, RootConceptModal } from '@/components/panels'
import {
  getDiagramOperations,
  getNodePalette,
  getPanelCoordinator,
  useCanvasToolbarApps,
  useInlineRecommendations,
  useInlineRecommendationsCoordinator,
  useLanguage,
  useNodeActions,
  useNotifications,
} from '@/composables'
import { useCanvasAutoSaveStatus } from '@/composables/canvasPage/useCanvasAutoSaveStatus'
import { useCanvasUnsavedLeaveGuard } from '@/composables/canvasPage/useCanvasUnsavedLeaveGuard'
import { useCanvasPageTabRecIndicator } from '@/composables/canvasPage/useCanvasPageTabRecIndicator'
import { useConceptMapRelationshipTabFromSelection } from '@/composables/canvasPage/useConceptMapRelationshipTabFromSelection'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import { useKittyVoiceSelectionBus } from '@/composables/kitty/useKittyVoiceSelectionBus'
import { useMobileCanvasEventHandlers } from '@/composables/mobile/useMobileCanvasEventHandlers'
import { useMobileCanvasInlineRecBar } from '@/composables/mobile/useMobileCanvasInlineRecBar'
import { useMobileCanvasRouteLoader } from '@/composables/mobile/useMobileCanvasRouteLoader'
import { useMobileCanvasToolbar } from '@/composables/mobile/useMobileCanvasToolbar'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import {
  useAuthStore,
  useConceptMapRelationshipStore,
  useDiagramStore,
  useFeatureFlagsStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
  useUIStore,
} from '@/stores'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import type { DiagramType } from '@/types'
import {
  DEFAULT_CHART_TYPE_KEY,
  diagramTypeFromKey,
} from '@/utils/diagramTypeKeys'

const diagramStore = useDiagramStore()
const uiStore = useUIStore()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
getDiagramOperations()

const inlineRecStore = useInlineRecommendationsStore()
const focusReviewStore = useConceptMapFocusReviewStore()
const rootConceptReviewStore = useConceptMapRootConceptReviewStore()
const relationshipStore = useConceptMapRelationshipStore()
const { activeEntry: relationshipActiveEntry } = storeToRefs(relationshipStore)
const featureFlagsStore = useFeatureFlagsStore()
const { t, currentLanguage, promptLanguage } = useLanguage()
const notify = useNotifications()

getPanelCoordinator()
const { startSession: startNodePaletteSession } = getNodePalette({
  onError: (err: string) => notify.error(err),
})

const { handleAIGenerate, handleConceptGeneration, isAIGenerating } = useCanvasToolbarApps()
const diagramAutoSave = useDiagramAutoSave()
const previewStore = useMindMapSubgraphPreviewStore()
const inlineRecCoordinator = useInlineRecommendationsCoordinator()
useCanvasPageTabRecIndicator()
useNodeActions()
const { startRecommendations, selectOptionByGlobalIndex, fetchNextBatch } =
  useInlineRecommendations()

useConceptMapRelationshipTabFromSelection({ startRecommendations })
useKittyVoiceSelectionBus('MobileCanvasPage')

const chartType = computed(() => uiStore.selectedChartType)
const diagramType = computed<DiagramType | null>(() => diagramTypeFromKey(chartType.value))
const isConceptMap = computed(() => diagramStore.type === 'concept_map')
const useMindMapV2 = useMindMapV2Chrome()
const fitViewOnInit = computed(
  () =>
    !isConceptMap.value &&
    !useMindMapV2.value
)

const tabReady = computed(() => {
  if (!authStore.isAuthenticated) return false
  if (!inlineRecStore.isReady) return false
  if (isConceptMap.value) {
    return llmResultsStore.selectedModel != null
  }
  return true
})

const {
  isSaving,
  showNodePalette,
  showModelDrawer,
  handleSave,
  handleAddNode,
  handleDeleteSelected,
  handleToolbarAI,
  toggleConceptMapAiToolbar,
  toggleNodePalette,
  handleFitToScreen,
  handleZoomReset,
} = useMobileCanvasToolbar({
  diagramStore,
  authStore,
  llmResultsStore,
  panelsStore,
  diagramAutoSave,
  saveGuardState: () => ({
    llmGenerating: llmResultsStore.isGenerating,
    subgraphGenerating: previewStore.isGenerating,
    collabSessionActive: diagramStore.collabSessionActive,
    isCollabGuest: false,
  }),
  isConceptMap,
  isAIGenerating,
  handleAIGenerate,
  handleConceptGeneration,
  translate: t,
  notifySuccess: (message) => notify.success(message),
  notifyWarning: (message) => notify.warning(message),
})

const {
  inlineRecActive,
  inlineRecGenerating,
  showMobileConceptRecBottom,
  mobileRecOptions,
  mobileRecPage,
  mobileRecPerPage,
  mobileCanPrev,
  mobileRecFetching,
  handleRecSelect,
  handleRecNext,
  handleRecPrev,
  handleRecDismiss,
  handleTabMode,
} = useMobileCanvasInlineRecBar({
  diagramStore,
  inlineRecStore,
  authStore,
  llmResultsStore,
  focusReviewStore,
  rootConceptReviewStore,
  isConceptMap,
  startRecommendations,
  selectOptionByGlobalIndex,
  fetchNextBatch,
  translate: t,
  notifyWarning: (message) => notify.warning(message),
})

const { autoSavedStatusText } = useCanvasAutoSaveStatus({
  diagramAutoSave,
  isAuthenticated: computed(() => authStore.isAuthenticated),
  isSlotsFullyUsed: computed(() => savedDiagramsStore.isSlotsFullyUsed),
  activeDiagramId: computed(() => savedDiagramsStore.activeDiagramId),
})

const saveStatusDirty = computed(
  () => diagramAutoSave.isDirty.value && !diagramAutoSave.isSaving.value
)

const mobileCanvasEvents = useMobileCanvasEventHandlers({
  diagramStore,
  authStore,
  inlineRecStore,
  llmResultsStore,
  focusReviewStore,
  rootConceptReviewStore,
  isConceptMap,
  isAIGenerating,
  startNodePaletteSession,
  startRecommendations,
  handleAIGenerate,
  handleConceptGeneration,
  translate: t,
  notifyWarning: (message) => notify.warning(message),
})

useMobileCanvasRouteLoader({
  diagramStore,
  authStore,
  uiStore,
  llmResultsStore,
  savedDiagramsStore,
  featureFlagsStore,
  inlineRecCoordinator,
  diagramType,
  currentLanguage,
  promptLanguage,
  translate: t,
  notifySuccess: (message) => notify.success(message),
  notifyWarning: (message) => notify.warning(message),
  notifyError: (message) => notify.error(message),
  onCollabClear: () => diagramStore.setCollabSessionActive(false),
})

const preserveDiagramForKittyHub = ref(false)

onBeforeRouteLeave((to) => {
  preserveDiagramForKittyHub.value = to.path === '/m/kitty' || to.name === 'MobileKitty'
})

useCanvasUnsavedLeaveGuard({
  isDirty: diagramAutoSave.isDirty,
})

watch(
  () => panelsStore.nodePalettePanel.isOpen,
  (isOpen) => {
    showNodePalette.value = isOpen
  }
)

watch(isConceptMap, (v) => {
  if (v) {
    showModelDrawer.value = false
  }
})

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

onUnmounted(() => {
  inlineRecCoordinator.teardown()
  mobileCanvasEvents.teardown()
  void diagramAutoSave.flush().finally(() => {
    diagramAutoSave.teardown()
  })
  focusReviewStore.clear()
  rootConceptReviewStore.clear()

  if (!preserveDiagramForKittyHub.value) {
    diagramStore.reset()
    savedDiagramsStore.clearActiveDiagram()
  }
  useLLMResultsStore().reset()
  usePanelsStore().reset()
  uiStore.setSelectedChartType(DEFAULT_CHART_TYPE_KEY)
  uiStore.setFreeInputValue('')
})
</script>

<template>
  <div class="mobile-canvas flex flex-col flex-1 min-h-0 bg-gray-50 relative overflow-hidden">
    <!-- Top toolbar (fixed, no zoom/pan) -->
    <div
      :class="[
        'mobile-toolbar flex flex-col w-full bg-white border-b border-gray-200 shrink-0 touch-none',
        isConceptMap ? 'mobile-toolbar--concept-map' : '',
      ]"
    >
      <div
        :class="[
          'flex items-stretch w-full px-1.5 py-1.5 gap-1',
          isConceptMap ? 'mobile-toolbar-row--concept-map' : 'justify-evenly',
        ]"
      >
        <button
          class="toolbar-btn"
          :class="{ 'toolbar-btn--dirty': saveStatusDirty }"
          :disabled="isSaving"
          :aria-label="t('canvas.toolbar.save', '保存')"
          @click="handleSave"
        >
          <Save :size="18" />
          <span class="toolbar-label">{{ t('canvas.toolbar.save', '保存') }}</span>
        </button>

        <button
          class="toolbar-btn"
          :disabled="diagramStore.type === 'concept_map'"
          :aria-label="t('canvas.toolbar.add', '添加')"
          @click="handleAddNode"
        >
          <Plus :size="18" />
          <span class="toolbar-label">{{ t('canvas.toolbar.add', '添加') }}</span>
        </button>

        <button
          class="toolbar-btn"
          :aria-label="t('canvas.toolbar.delete', '删除')"
          @click="handleDeleteSelected"
        >
          <Trash2 :size="18" />
          <span class="toolbar-label">{{ t('canvas.toolbar.delete', '删除') }}</span>
        </button>

      <!-- 概念图：5 等分；生成概念 = Sparkles，启动 AI = Bot -->
      <template v-if="isConceptMap">
        <button
          class="toolbar-btn toolbar-btn--primary"
          :class="{ 'toolbar-btn--generating': isAIGenerating }"
          @click="handleToolbarAI"
        >
          <Sparkles
            :size="18"
            class="ai-icon"
          />
          <span class="toolbar-label truncate max-w-full">{{
            t('canvas.toolbar.conceptGeneration', '生成概念')
          }}</span>
        </button>
        <button
          type="button"
          class="toolbar-btn toolbar-btn--ai"
          :class="{ 'toolbar-btn--ai-on': llmResultsStore.selectedModel }"
          @click="toggleConceptMapAiToolbar"
        >
          <Bot
            :size="18"
            class="ai-icon"
          />
          <span class="toolbar-label truncate max-w-full">{{
            t('aiModel.enableAi', '启动 AI')
          }}</span>
        </button>
      </template>
      <template v-else>
        <button
          class="toolbar-btn toolbar-btn--primary"
          :class="{
            'toolbar-btn--generating': isAIGenerating,
          }"
          :aria-label="t('canvas.toolbar.aiGenerate', 'AI生成')"
          @click="handleToolbarAI"
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
          :aria-label="t('panel.nodePalette')"
          @click="toggleNodePalette"
        >
          <LayoutGrid :size="18" />
          <span class="toolbar-label">{{ t('panel.nodePalette') }}</span>
        </button>
      </template>
      </div>

      <p
        v-if="autoSavedStatusText"
        class="mobile-save-status px-3 pb-1 text-[10px] text-gray-500 truncate"
      >
        {{ autoSavedStatusText }}
      </p>
    </div>

    <!-- Diagram canvas with touch support (only this area is pannable/zoomable) -->
    <div class="canvas-area flex-1 min-h-0 relative overflow-hidden">
      <DiagramCanvas
        v-if="diagramStore.data"
        class="absolute inset-0 canvas-touch"
        :show-background="true"
        :show-minimap="false"
        :fit-view-on-init="fitViewOnInit"
        :concept-map-initial-topic-fit="isConceptMap"
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

      <div class="mobile-zoom-controls absolute bottom-3 end-3 z-10 flex flex-col gap-1.5">
        <button
          type="button"
          class="mobile-zoom-btn"
          :aria-label="t('canvas.zoomControls.fitCanvas')"
          @click="handleFitToScreen"
        >
          <Maximize2 :size="18" />
        </button>
        <button
          type="button"
          class="mobile-zoom-btn"
          :aria-label="t('editor.zoomReset', '重置缩放')"
          @click="handleZoomReset"
        >
          <RotateCcw :size="18" />
        </button>
      </div>
    </div>

    <!-- Concept map: relationship / root / focus pickers (same as desktop bar, mobile strip) -->
    <div
      v-if="
        isConceptMap &&
        !inlineRecActive &&
        (relationshipActiveEntry ||
          rootConceptReviewStore.showPicker ||
          focusReviewStore.showPicker)
      "
      class="concept-map-pickers-row shrink-0 z-20 px-2 py-1.5 bg-white/95 border-t border-gray-200 touch-none"
    >
      <ConceptMapLabelPicker
        v-if="relationshipActiveEntry"
        class="w-full min-w-0"
      />
      <ConceptMapRootConceptPicker
        v-else-if="rootConceptReviewStore.showPicker"
        class="w-full min-w-0"
      />
      <ConceptMapFocusReviewPicker
        v-else-if="focusReviewStore.showPicker"
        class="w-full min-w-0"
      />
    </div>

    <!-- Bottom bar: non–concept map = AI sheet + Tab; concept map = inline rec only (no overlap) -->
    <div
      v-if="!isConceptMap || showMobileConceptRecBottom"
      class="mobile-bottom-bar shrink-0 px-3 py-2 bg-white/90 backdrop-blur-md border-t border-gray-200 touch-none"
    >
      <!-- Inline recommendations (full width; concept map has no second row for AI/Tab) -->
      <div
        v-if="inlineRecActive"
        :class="[
          'flex items-center w-full min-w-0',
          isConceptMap ? 'gap-2 min-h-[48px] mobile-inline-rec--concept' : 'gap-1.5 min-h-[36px]',
        ]"
      >
        <button
          :class="[
            'shrink-0 rounded-xl bg-red-50 active:bg-red-100 text-red-500 transition-colors',
            isConceptMap
              ? 'p-2.5 min-w-[44px] min-h-[44px] flex items-center justify-center'
              : 'p-1.5',
          ]"
          @click="handleRecDismiss"
        >
          <X :size="isConceptMap ? 20 : 14" />
        </button>

        <button
          :class="[
            'shrink-0 rounded-xl transition-colors',
            isConceptMap
              ? 'p-3 min-w-[48px] min-h-[48px] flex items-center justify-center'
              : 'p-2 min-w-[40px] min-h-[40px] flex items-center justify-center',
            mobileCanPrev
              ? 'bg-gray-100 active:bg-gray-200 text-gray-600'
              : 'bg-gray-50 text-gray-300',
          ]"
          :disabled="!mobileCanPrev"
          @click="handleRecPrev"
        >
          <ChevronLeft
            :size="isConceptMap ? 28 : 18"
            class="mg-icon-flip-rtl"
          />
        </button>

        <div
          v-if="inlineRecGenerating && mobileRecOptions.length === 0"
          class="flex-1 flex items-center justify-center gap-2 text-xs text-gray-500"
        >
          <Loader2
            :size="isConceptMap ? 18 : 14"
            class="animate-spin text-green-500"
          />
          <span :class="isConceptMap ? 'text-sm' : ''">{{
            t('inlineRec.generating', '生成推荐中...')
          }}</span>
        </div>
        <div
          v-else
          class="rec-scroll-area flex-1 overflow-x-auto min-w-0"
        >
          <div :class="['flex items-stretch', isConceptMap ? 'gap-2' : 'gap-1.5']">
            <button
              v-for="(opt, idx) in mobileRecOptions"
              :key="`${inlineRecStore.activeNodeId}-${mobileRecPage}-${idx}`"
              :class="[
                'rec-chip shrink-0 rounded-xl bg-green-50 active:bg-green-100 text-green-700 font-medium transition-colors border border-green-200 whitespace-nowrap',
                isConceptMap
                  ? 'rec-chip--concept px-3 py-2.5 text-sm min-h-[44px] flex items-center'
                  : 'px-2.5 py-1.5 text-xs',
              ]"
              @click="handleRecSelect(idx)"
            >
              <span :class="['text-green-500 font-bold mr-1', isConceptMap ? 'text-sm' : '']">
                {{ mobileRecPage * mobileRecPerPage + idx + 1 }}
              </span>
              {{ opt }}
            </button>
          </div>
        </div>

        <button
          :class="[
            'shrink-0 rounded-xl transition-colors',
            isConceptMap
              ? 'p-3 min-w-[48px] min-h-[48px] flex items-center justify-center'
              : 'p-2 min-w-[40px] min-h-[40px] flex items-center justify-center',
            mobileRecFetching
              ? 'bg-gray-50 text-gray-300'
              : 'bg-gray-100 active:bg-gray-200 text-gray-600',
          ]"
          :disabled="mobileRecFetching"
          @click="handleRecNext"
        >
          <Loader2
            v-if="mobileRecFetching"
            :size="isConceptMap ? 20 : 16"
            class="animate-spin"
          />
          <ChevronRight
            v-else
            :size="isConceptMap ? 28 : 18"
            class="mg-icon-flip-rtl"
          />
        </button>
      </div>

      <!-- Other diagrams: open AI sheet + Tab (inline rec) -->
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

    <!--
      Node palette / root concept: must render after canvas so the overlay wins hit-testing
      (Vue Flow + mobile touch use capture on the canvas; z-index must also clear .canvas-area).
    -->
    <Transition name="palette-slide">
      <div
        v-if="showNodePalette && panelsStore.nodePalettePanel.isOpen"
        class="mobile-node-palette-overlay absolute inset-0 z-[100] flex flex-col touch-manipulation bg-white"
        style="top: var(--mg-mobile-palette-top, 9.5rem)"
      >
        <RootConceptModal
          v-if="isConceptMap"
          @close="panelsStore.closeNodePalette"
        />
        <NodePalettePanel
          v-else
          @close="panelsStore.closeNodePalette"
        />
      </div>
    </Transition>

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

<style scoped src="./mobileCanvasPage.scoped.css"></style>

<style src="./mobileCanvasPage.global.css"></style>
