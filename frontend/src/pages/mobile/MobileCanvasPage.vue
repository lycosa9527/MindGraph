<script setup lang="ts">
/**
 * MobileCanvasPage — Simplified mobile diagram editor.
 * Vue Flow with touch support, minimal top toolbar, AI model selector at bottom.
 * Reuses DiagramCanvas + stores from desktop, but strips collaboration, presentation,
 * and other desktop-only features. Concept map: 启用 AI in top bar; bottom shows inline
 * rec only while active (tap canvas to dismiss, same as desktop coordinator).
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

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

import {
  AIModelSelector,
  ConceptMapFocusReviewPicker,
  ConceptMapLabelPicker,
  ConceptMapRootConceptPicker,
} from '@/components/canvas'
import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { NodePalettePanel, RootConceptModal } from '@/components/panels'
import {
  eventBus,
  getDefaultDiagramName,
  getNodePalette,
  getPanelCoordinator,
  useCanvasToolbarApps,
  useDiagramSpecForSave,
  useInlineRecommendations,
  useInlineRecommendationsCoordinator,
  useLanguage,
  useNodeActions,
  useNotifications,
} from '@/composables'
import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import {
  diagramSpecLikelyNeedsMarkdownPipeline,
  loadDiagramMarkdownPipeline,
} from '@/composables/core/diagramMarkdownPipeline'
import { useDiagramAutoSave } from '@/composables/editor/useDiagramAutoSave'
import { IMPORT_SPEC_KEY } from '@/config'
import { ensureFontsForLanguageCode } from '@/fonts/promptLanguageFonts'
import {
  type LLMResult,
  useAuthStore,
  useConceptMapRelationshipStore,
  useConceptMapRootConceptReviewStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
  useUIStore,
} from '@/stores'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

const route = useRoute()
const router = useRouter()
const diagramStore = useDiagramStore()
const uiStore = useUIStore()
const authStore = useAuthStore()
const savedDiagramsStore = useSavedDiagramsStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
const inlineRecStore = useInlineRecommendationsStore()
const focusReviewStore = useConceptMapFocusReviewStore()
const rootConceptReviewStore = useConceptMapRootConceptReviewStore()
const relationshipStore = useConceptMapRelationshipStore()
const { activeEntry: relationshipActiveEntry } = storeToRefs(relationshipStore)
const { t, currentLanguage, promptLanguage } = useLanguage()
const notify = useNotifications()

getPanelCoordinator()
const { startSession: startNodePaletteSession } = getNodePalette({
  onError: (err: string) => notify.error(err),
})

const { handleAIGenerate, handleConceptGeneration, isAIGenerating } = useCanvasToolbarApps()

const diagramAutoSave = useDiagramAutoSave()

const inlineRecCoordinator = useInlineRecommendationsCoordinator()
useNodeActions()
const { startRecommendations, selectOptionByGlobalIndex, fetchNextBatch } =
  useInlineRecommendations()

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
  if (!authStore.isAuthenticated) return false
  if (!inlineRecStore.isReady) return false
  if (isConceptMap.value) {
    return llmResultsStore.selectedModel != null
  }
  return true
})

const MOBILE_REC_PER_PAGE_NON_CONCEPT = 3
const MOBILE_REC_PER_PAGE_CONCEPT_MAP = 4

/** Concept map: show four suggestions per “page”; other diagrams keep three. */
const mobileRecPerPage = computed(() =>
  isConceptMap.value ? MOBILE_REC_PER_PAGE_CONCEPT_MAP : MOBILE_REC_PER_PAGE_NON_CONCEPT
)

const inlineRecActive = computed(() => !!inlineRecStore.activeNodeId)
const inlineRecGenerating = computed(() => {
  const nid = inlineRecStore.activeNodeId
  return !!nid && inlineRecStore.generatingNodeIds.has(nid)
})
/** Concept map: bottom bar only while inline rec is open or loading (dismiss: canvas tap via coordinator) */
const showMobileConceptRecBottom = computed(
  () => isConceptMap.value && (inlineRecActive.value || inlineRecGenerating.value)
)

const mobileRecPage = ref(0)
const mobileRecOptions = computed(() => {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return []
  const all = inlineRecStore.allOptions[nid] ?? []
  const per = mobileRecPerPage.value
  const start = mobileRecPage.value * per
  return all.slice(start, start + per)
})
const mobileRecTotalPages = computed(() => {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return 0
  const total = (inlineRecStore.allOptions[nid] ?? []).length
  const per = mobileRecPerPage.value
  return total <= 0 ? 0 : Math.ceil(total / per)
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

watch(isConceptMap, (v) => {
  mobileRecPage.value = 0
  if (v) {
    showModelDrawer.value = false
  }
})

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

  if (isConceptMap.value && selectedId === 'topic') {
    void focusReviewStore.runFocusReviewManual()
    return
  }
  if (isConceptMap.value) {
    const rootTid = getTopicRootConceptTargetId(diagramStore.data?.connections)
    if (rootTid && selectedId === rootTid) {
      void rootConceptReviewStore.runRootConceptManual()
      return
    }
  }
  if (isConceptMap.value && !llmResultsStore.selectedModel) {
    notify.warning(
      t('notification.conceptMapTabNeedsAi', '请先在顶栏启用「启动 AI」再使用 Tab 推荐')
    )
    return
  }

  const nodes = diagramStore.data?.nodes ?? []
  const node = nodes.find((n) => n.id === selectedId)
  if (
    !node ||
    !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
  ) {
    notify.warning(t('notification.nodeNotEligible', '该节点不支持推荐'))
    return
  }
  void startRecommendations(selectedId)
}

function handleRecSelect(localIdx: number): void {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return
  const per = mobileRecPerPage.value
  const globalIdx = mobileRecPage.value * per + localIdx
  selectOptionByGlobalIndex(nid, globalIdx)
}

async function handleRecNext(): Promise<void> {
  const nid = inlineRecStore.activeNodeId
  if (!nid) return
  const per = mobileRecPerPage.value
  const hasMoreLocal = mobileRecPage.value < mobileRecTotalPages.value - 1
  if (hasMoreLocal) {
    mobileRecPage.value++
    return
  }
  await fetchNextBatch(nid)
  const newTotal = (inlineRecStore.allOptions[nid] ?? []).length
  const newTotalPages = Math.ceil(newTotal / per)
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

function handleToolbarAI() {
  if (!authStore.isAuthenticated) {
    notify.warning(t('notification.signInToUse'))
    return
  }
  if (isConceptMap.value) {
    handleConceptGeneration()
    return
  }
  if (isAIGenerating.value) return
  void handleAIGenerate()
}

function toggleConceptMapAiToolbar(): void {
  if (llmResultsStore.selectedModel) {
    llmResultsStore.setSelectedModel(null)
  } else {
    llmResultsStore.setSelectedModel('qwen')
  }
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

// Concept maps are handled by RootConceptModal.onMounted → initializeConceptMapRootModal(),
// which runs bootstrap_domains + sequential per-tab streams. Firing startSession() here in
// parallel would launch a second concurrent NODE_PALETTE_START request on the same session
// and topic, causing duplicate RAG initialization, flickering suggestions (each stream calls
// setNodePaletteSuggestions([]) when append=false), and intermittent "No response returned"
// cancellations when one of the racing streams aborts.
eventBus.onWithOwner(
  'nodePalette:opened',
  (data: { hasRestoredSession?: boolean; wasPanelAlreadyOpen?: boolean }) => {
    if (diagramStore.type === 'concept_map') return
    if (!data.hasRestoredSession && diagramStore.data?.nodes?.length) {
      startNodePaletteSession({ keepSessionId: data.wasPanelAlreadyOpen ?? false })
    }
  },
  'MobileCanvasPage'
)

eventBus.onWithOwner(
  'node_editor:tab_pressed',
  (data: { nodeId?: string; draftText?: string }) => {
    const nodeId = data?.nodeId
    if (!nodeId) return

    if (diagramStore.type === 'concept_map' && nodeId === 'topic') {
      const draft = typeof data.draftText === 'string' ? data.draftText.trim() : ''
      if (draft) {
        eventBus.emit('node:text_updated', { nodeId: 'topic', text: draft })
      }
      void focusReviewStore.runFocusReviewManual()
      return
    }

    if (diagramStore.type === 'concept_map') {
      const rootTid = getTopicRootConceptTargetId(diagramStore.data?.connections)
      if (rootTid && nodeId === rootTid) {
        const draft = typeof data.draftText === 'string' ? data.draftText.trim() : ''
        if (draft) {
          eventBus.emit('node:text_updated', { nodeId: rootTid, text: draft })
        }
        if (!authStore.isAuthenticated) {
          notify.warning(t('notification.signInToUse'))
          return
        }
        void rootConceptReviewStore.runRootConceptManual()
        return
      }
    }

    const nodes = diagramStore.data?.nodes ?? []
    const node = nodes.find((n) => n.id === nodeId) as
      | { id?: string; type?: string; data?: { nodeType?: string } }
      | undefined
    if (
      !node ||
      !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
    ) {
      return
    }
    if (!inlineRecStore.isReady) return
    if (diagramStore.type === 'concept_map' && !llmResultsStore.selectedModel) {
      notify.warning(
        t('notification.conceptMapTabNeedsAi', '请先在顶栏启用「启动 AI」再使用 Tab 推荐')
      )
      return
    }
    if (!authStore.isAuthenticated) {
      notify.warning(t('notification.signInToUse'))
      return
    }
    void startRecommendations(nodeId)
  },
  'MobileCanvasPage'
)

onMounted(async () => {
  await ensureFontsForLanguageCode(uiStore.promptLanguage)
  inlineRecCoordinator.setup()
  await savedDiagramsStore.fetchDiagrams()

  const diagramIdRaw = route.query.diagramId ?? route.query.diagram_id
  const diagramId = typeof diagramIdRaw === 'string' ? diagramIdRaw : undefined
  if (diagramId) {
    await loadDiagramFromLibrary(diagramId)
    return
  }

  const importFlag = route.query.import
  if (importFlag === '1') {
    const importJson = sessionStorage.getItem(IMPORT_SPEC_KEY)
    if (importJson) {
      try {
        const spec = JSON.parse(importJson) as Record<string, unknown>
        sessionStorage.removeItem(IMPORT_SPEC_KEY)
        const diagramType = (spec.type as DiagramType) || null
        if (!diagramType || !VALID_TYPES.includes(diagramType)) {
          notify.error(t('notification.importUnsupportedType'))
        } else {
          const llmResults = spec.llm_results as
            | { results?: Record<string, unknown>; selectedModel?: string }
            | undefined
          let specForLoad = spec
          if (llmResults?.results && typeof llmResults.results === 'object') {
            llmResultsStore.restoreFromSaved(
              llmResults as { results?: Record<string, LLMResult>; selectedModel?: string },
              diagramType
            )
            specForLoad = { ...spec }
            delete (specForLoad as Record<string, unknown>).llm_results
          } else {
            llmResultsStore.clearCache()
          }
          if (diagramSpecLikelyNeedsMarkdownPipeline(specForLoad)) {
            await loadDiagramMarkdownPipeline({ bumpLayout: false })
          }
          const loaded = diagramStore.loadFromSpec(specForLoad, diagramType)
          if (loaded) {
            const zhName = DIAGRAM_TYPE_TO_ZH[diagramType]
            if (zhName) {
              uiStore.setSelectedChartType(zhName)
            }
            router.replace({ path: '/m/canvas' })

            const topicText = diagramStore.getTopicNodeText()
            const importTitle =
              topicText ||
              diagramStore.effectiveTitle ||
              getDefaultDiagramName(diagramType, currentLanguage.value)
            diagramStore.initTitle(importTitle)
            const getDiagramSpec = useDiagramSpecForSave()
            const specToSave = getDiagramSpec()
            if (specToSave && authStore.isAuthenticated) {
              const saveResult = await savedDiagramsStore.manualSaveDiagram(
                importTitle,
                diagramType,
                specToSave,
                promptLanguage.value,
                null
              )
              if (saveResult.success) {
                notify.success(t('notification.importSuccess'))
              } else if (saveResult.needsSlotClear) {
                eventBus.emit('canvas:show_slot_full_modal', {})
              } else if (!saveResult.success) {
                notify.warning(saveResult.error || t('notification.importSavePartial'))
              }
            }
            return
          }
          notify.error(t('notification.importLoadFailed'))
        }
      } catch (error) {
        console.error('Import load failed:', error)
        notify.error(t('notification.importInvalidData'))
      }
    } else {
      notify.error(t('canvas.import.invalidFile'))
      const restQuery = { ...route.query }
      delete restQuery.import
      await router.replace({ path: route.path, query: restQuery })
    }
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
  inlineRecCoordinator.teardown()
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
      :class="[
        'mobile-toolbar flex items-stretch w-full px-1.5 py-1.5 bg-white border-b border-gray-200 shrink-0 touch-none gap-1',
        isConceptMap ? 'mobile-toolbar--concept-map' : 'justify-evenly',
      ]"
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
          @click="toggleNodePalette"
        >
          <LayoutGrid :size="18" />
          <span class="toolbar-label">{{ t('canvas.toolbar.nodePalette', '节点面板') }}</span>
        </button>
      </template>
    </div>

    <!-- Diagram canvas with touch support (only this area is pannable/zoomable) -->
    <div class="canvas-area flex-1 min-h-0 relative overflow-hidden">
      <DiagramCanvas
        v-if="diagramStore.data"
        class="absolute inset-0 canvas-touch"
        :show-background="true"
        :show-minimap="false"
        :fit-view-on-init="!isConceptMap"
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
        style="top: 44px"
      >
        <RootConceptModal
          v-if="isConceptMap"
          @close="panelsStore.closeNodePalette"
        />
        <NodePalettePanel
          v-else
          @close="toggleNodePalette"
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

/* Concept map: five equal columns (save, add, delete, 生成概念, 启动 AI) */
.mobile-toolbar--concept-map .toolbar-btn {
  flex: 1 1 0;
  min-width: 0;
  padding: 6px 4px;
  border-radius: 10px;
}

/* 启动 AI: Bot 图标 — 琥珀关 / 翠绿开（与 生成概念 的 Sparkles 区分） */
.toolbar-btn--ai {
  color: #92400e;
  background: #fffbeb;
  border: 1.5px solid #fcd34d;
  box-sizing: border-box;
}

.toolbar-btn--ai .ai-icon {
  color: #d97706;
}

.toolbar-btn--ai:active {
  background: #fef3c7;
}

.toolbar-btn--ai-on {
  color: #ffffff !important;
  background: #059669 !important;
  border-color: #047857 !important;
}

.toolbar-btn--ai-on .ai-icon {
  color: #ffffff;
  filter: drop-shadow(0 0 2px rgba(255, 255, 255, 0.35));
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

/* Concept map: four chips, larger tap targets; keep a sane max width for long text */
.rec-chip--concept {
  max-width: min(40vw, 12rem);
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
