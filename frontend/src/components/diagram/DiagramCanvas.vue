<script setup lang="ts">
/**
 * DiagramCanvas - Vue Flow wrapper for MindGraph diagrams
 * Provides unified interface for all diagram types with drag-drop, zoom, and pan
 *
 * Two-View Zoom System:
 * - fitToFullCanvas(): Fits diagram to full canvas (no panel space reserved)
 * - fitWithPanel(): Fits diagram with space reserved for right-side panels
 * - Mind maps: manual zoom only; initial view centers diagram at 100% (no scale-to-fit).
 * - Desktop concept maps: manual zoom; IHMC cmap imports trigger one-shot fit on init.
 *
 * SVG text / RTL: primary labels use InlineEditableText (HTML, dir=auto). Decorative
 * overlays (brace/tree/bridge) use SVG <text>; bidi for all-RTL strings can be weaker
 * in some browsers — if reported, consider foreignObject + HTML for those labels.
 */
import { computed, onMounted, onUnmounted, provide, ref, toRef, unref, watch } from 'vue'

import { Background } from '@vue-flow/background'
import { type GraphNode, SelectionMode, VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'

import { storeToRefs } from 'pinia'

import { ExportToCommunityModal, CanvasNodeFloatingToolbar, MindMapSubgraphPreviewBar } from '@/components/canvas'
import { useBranchMoveDrag, useLanguage } from '@/composables'
import { useNodeFloatingToolbarPosition } from '@/composables/canvasToolbar'
import { useMindMapSubgraphSuggest } from '@/composables/editor/useMindMapSubgraphSuggest'
import {
  useLearningSheetCustomMode,
  useLearningSheetPickKeyboard,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { LEARNING_SHEET_HAMMER_CURSOR } from '@/config/learningSheetCursor'
import { registerDiagramLayoutRecalcBootstrap } from '@/composables/core/diagramLayoutRecalcBootstrap'
import { ensureMarkdownRenderer } from '@/composables/core/useMarkdown'
import { useTheme } from '@/composables/core/useTheme'
import {
  diagramCanvasGridConfig,
  diagramCanvasZoomConfig,
  useConceptMapCmapMeasuredLayoutRelax,
  useDiagramCanvasConceptMapLink,
  useDiagramCanvasContextMenu,
  useDiagramCanvasEventBus,
  useDiagramCanvasExport,
  useDiagramCanvasFit,
  useDiagramCanvasMobileTouch,
  useDiagramCanvasNodesEdges,
  useDiagramCanvasVueFlowHandlers,
  useDiagramCanvasVueFlowUi,
} from '@/composables/diagramCanvas'
import { useDiagramCanvasMindMapPaletteDrop } from '@/composables/diagramCanvas/useDiagramCanvasMindMapPaletteDrop'
import { useMindMapMultiLinePaste } from '@/composables/mindMap/useMindMapMultiLinePaste'
import {
  CONCEPT_MAP_GENERATING_KEY,
  useConceptMapRelationship,
} from '@/composables/editor/useConceptMapRelationship'
import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import { useDiagramStore, usePanelsStore, usePresentationPointerStore, useUIStore } from '@/stores'
import type { MindGraphNode, PresentationHighlightStroke, PresentationToolId } from '@/types'

import BraceOverlay from './BraceOverlay.vue'
import BridgeOverlay from './BridgeOverlay.vue'
import MindMapCollapseToggleOverlay from './MindMapCollapseToggleOverlay.vue'
import MindMapDirectionalAddOverlay from './MindMapDirectionalAddOverlay.vue'
import ContextMenu from './ContextMenu.vue'
import DiagramCanvasZoomPaneOverlays from './DiagramCanvasZoomPaneOverlays.vue'
import LearningSheetOverlay from './LearningSheetOverlay.vue'
import LearningSheetPickBanner from '@/components/canvas/LearningSheetPickBanner.vue'
import PresentationHighlightOverlay from './PresentationHighlightOverlay.vue'
import TreeMapOverlay from './TreeMapOverlay.vue'
import './diagramCanvas.css'
import { diagramCanvasEdgeTypes, diagramCanvasNodeTypes } from './diagramCanvasVueFlowTypes'

interface Props {
  showBackground?: boolean
  showMinimap?: boolean
  fitViewOnInit?: boolean
  /**
   * Concept maps: when fitViewOnInit is false, zoom to the topic on first init only if true.
   * Desktop canvas leaves this false (default viewport). Mobile passes true so small screens
   * center the topic on first paint.
   */
  conceptMapInitialTopicFit?: boolean
  handToolActive?: boolean
  collabLockedNodeIds?: string[]
  panOnDragButtons?: number[] | null
  presentationRailOpen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showBackground: true,
  showMinimap: false,
  fitViewOnInit: true,
  conceptMapInitialTopicFit: false,
  handToolActive: false,
  collabLockedNodeIds: () => [],
  panOnDragButtons: null,
  presentationRailOpen: false,
})

const presentationHighlightStrokes = defineModel<PresentationHighlightStroke[]>(
  'presentationHighlightStrokes',
  { default: () => [] }
)

const presentationTool = defineModel<PresentationToolId>('presentationTool', {
  default: 'laser',
})

const presentationHighlighterColor = defineModel<string>('presentationHighlighterColor', {
  default: DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR,
})

const presentationPenColor = defineModel<string>('presentationPenColor', {
  default: 'rgba(239, 68, 68, 0.92)',
})

const emit = defineEmits<{
  (e: 'nodeClick', node: MindGraphNode): void
  (e: 'nodeDoubleClick', node: MindGraphNode): void
  (e: 'nodeDragStop', node: MindGraphNode): void
  (e: 'selectionChange', nodes: MindGraphNode[]): void
  (e: 'paneClick'): void
}>()

const diagramStore = useDiagramStore()
const panelsStore = usePanelsStore()
const uiStore = useUIStore()

const { generateRelationship, generatingConnectionIds, regenerateForNodeIfNeeded } =
  useConceptMapRelationship()
provide(CONCEPT_MAP_GENERATING_KEY, generatingConnectionIds)

const { backgroundColor } = useTheme({
  diagramType: computed(() => diagramStore.type),
})

const { t } = useLanguage()

const vueFlowWrapper = ref<HTMLElement | null>(null)
const canvasContainer = ref<HTMLElement | null>(null)

const {
  onNodesChange,
  onNodeClick,
  onNodeDoubleClick,
  onNodeDragStop,
  onEdgeClick,
  fitView,
  getNodes: getVueFlowNodes,
  setViewport,
  getViewport,
  zoomIn,
  zoomOut,
  screenToFlowCoordinate,
} = useVueFlow()

onEdgeClick(({ edge }) => {
  if (diagramStore.type === 'concept_map') {
    diagramStore.selectConnection(edge.id)
  }
})

function getVueFlowNodesForOverlays(): GraphNode[] {
  return unref(getVueFlowNodes) as GraphNode[]
}

const branchMove = useBranchMoveDrag({
  allowNodeMove: () => !props.handToolActive && !props.presentationRailOpen,
})
provide('branchMove', branchMove)

const presentationHighlighterStrokeScale = computed(() =>
  presentationTool.value === 'highlighter' ? 1.42 : 1
)

const presentationPointerStore = usePresentationPointerStore()
const { highlighterScale, penScale } = storeToRefs(presentationPointerStore)

const presentationStrokePointerScale = computed(() => {
  const t = presentationTool.value
  if (t === 'highlighter') {
    return highlighterScale.value
  }
  if (t === 'pen') {
    return penScale.value
  }
  return 1
})

const {
  presentationStrokeToolActive,
  presentationStrokeColor,
  effectivePanOnDrag,
  presentationToolIsNotTimer,
  nodesDraggable,
  elementsSelectable,
  selectNodesOnDrag,
  selectionKeyCode,
  vueFlowBackgroundClasses,
} = useDiagramCanvasVueFlowUi({
  diagramStore,
  presentationRailOpen: toRef(props, 'presentationRailOpen'),
  handToolActive: toRef(props, 'handToolActive'),
  panOnDragButtons: toRef(props, 'panOnDragButtons'),
  presentationTool,
  presentationHighlighterColor,
  presentationPenColor,
})

const { nodes, edges, nodesLength } = useDiagramCanvasNodesEdges({
  diagramStore,
  branchMove,
  collabLockedNodeIds: () => props.collabLockedNodeIds,
})

const useMindMapV2 = useMindMapV2Chrome()

const { handlePaste: handleMindMapMultiLinePaste } = useMindMapMultiLinePaste()

function onCanvasPaste(event: ClipboardEvent): void {
  if (!useMindMapV2.value) return
  handleMindMapMultiLinePaste(event)
}

const { isPickActive: isLearningSheetPickActive } = useLearningSheetCustomMode()
const hammerPickCursor = LEARNING_SHEET_HAMMER_CURSOR
useLearningSheetPickKeyboard()

watch(
  isLearningSheetPickActive,
  (active) => {
    document.documentElement.classList.toggle('mg-learning-sheet-pick', active)
    if (active) {
      document.documentElement.style.setProperty('--mg-hammer-cursor', hammerPickCursor)
    } else {
      document.documentElement.style.removeProperty('--mg-hammer-cursor')
    }
  },
  { immediate: true }
)

const floatingToolbarNodeIds = computed(() => {
  if (!useMindMapV2.value) return []
  return diagramStore.selectedNodes.slice()
})

const floatingToolbarEnabled = computed(() => floatingToolbarNodeIds.value.length > 0)

const floatingToolbarAnchorId = computed(() => floatingToolbarNodeIds.value[0] ?? null)

const { position: floatingToolbarPosition, scheduleMeasure: scheduleFloatingToolbarMeasure } =
  useNodeFloatingToolbarPosition({
    containerRef: canvasContainer,
    selectedNodeIds: floatingToolbarNodeIds,
    enabled: floatingToolbarEnabled,
  })

const subgraphPreviewLayoutTick = ref(0)

watch(
  () =>
    nodes.value
      .map((n) => `${n.id}:${n.position?.x ?? 0}:${n.position?.y ?? 0}`)
      .join('|'),
  () => {
    scheduleFloatingToolbarMeasure()
    subgraphPreviewLayoutTick.value += 1
  }
)

const {
  isGenerating: subgraphGenerating,
  hasPreview: subgraphPreviewActive,
  anchorNodeId: subgraphPreviewAnchorId,
  generateSubgraph,
  acceptPreview: acceptSubgraphPreview,
  discardPreview: discardSubgraphPreview,
} = useMindMapSubgraphSuggest()

async function handleAiSubgraphGenerate() {
  await generateSubgraph(floatingToolbarAnchorId.value)
}

const {
  isFittedForPanel,
  handleViewportChange,
  handleNodesInitialized,
  fitToFullCanvas,
  fitWithPanel,
  fitDiagram,
  fitForExport,
  fitToNodes,
  scheduleFitAfterStructuralNodeChange,
  clearFitTimersOnUnmount,
} = useDiagramCanvasFit({
  fitView,
  getNodes: () => unref(getVueFlowNodes),
  setViewport,
  getViewport,
  canvasContainer,
  diagramStore,
  panelsStore,
  fitViewOnInit: toRef(props, 'fitViewOnInit'),
  conceptMapInitialTopicFit: toRef(props, 'conceptMapInitialTopicFit'),
  presentationRailOpen: toRef(props, 'presentationRailOpen'),
  presentationToolIsNotTimer,
  nodesLength,
})

const {
  showExportToCommunityModal,
  getExportContainer,
  getExportTitle,
  getExportSpec,
  exportByFormat,
  prepareForCommunityExport,
  restoreViewportAfterCommunityExport,
} = useDiagramCanvasExport({
  vueFlowWrapper,
  diagramStore,
  fitForExport,
  getViewport,
  setViewport,
})

function handleViewportChangeWithToolbar(
  ...args: Parameters<typeof handleViewportChange>
) {
  handleViewportChange(...args)
  scheduleFloatingToolbarMeasure()
}

useConceptMapCmapMeasuredLayoutRelax(diagramStore)

const conceptMapLink = useDiagramCanvasConceptMapLink({
  diagramStore,
  screenToFlowCoordinate,
  t,
  generateRelationship,
})

const {
  linkPreviewPath,
  linkDragCursor,
  linkDragTargetNodeId,
  linkPreviewShowArrow,
  handleConceptMapDragOver,
  handleConceptMapDrop,
} = conceptMapLink

const mindMapPaletteDrop = useDiagramCanvasMindMapPaletteDrop({ diagramStore })

function handleCanvasDragOver(event: DragEvent): void {
  handleConceptMapDragOver(event)
  mindMapPaletteDrop.handleMindMapPaletteDragOver(event)
}

function handleCanvasDrop(event: DragEvent): void {
  handleConceptMapDrop(event)
  mindMapPaletteDrop.handleMindMapPaletteDrop(event)
}

const suppressPaneClearUntil = ref(0)

function markSelectionDragEnded() {
  suppressPaneClearUntil.value = Date.now() + 150
}

const contextMenu = useDiagramCanvasContextMenu({
  vueFlowWrapper,
  getNodes: () => unref(getVueFlowNodes),
  screenToFlowCoordinate,
  presentationRailOpen: toRef(props, 'presentationRailOpen'),
  emitPaneClick: () => emit('paneClick'),
  diagramStore,
  t,
  shouldSuppressPaneClear: () => Date.now() < suppressPaneClearUntil.value,
})

const {
  contextMenuVisible,
  contextMenuX,
  contextMenuY,
  contextMenuNode,
  contextMenuTarget,
  handlePaneClick,
  handleContextMenuEvent,
  closeContextMenu,
  handleContextMenuPaste,
  handleContextMenuAddConcept,
} = contextMenu

const { mountSubscriptions, clearDoubleBubbleTimer } = useDiagramCanvasEventBus()

const { setupMobileTouchZoom, mobileTouchCleanup } = useDiagramCanvasMobileTouch({
  canvasContainer,
  getViewport,
  setViewport,
  branchMove,
})

useDiagramCanvasVueFlowHandlers({
  diagramStore,
  getVueFlowNodes: () => unref(getVueFlowNodes) as GraphNode[],
  emit,
  scheduleFitAfterStructuralNodeChange,
  onSelectionDragEnd: markSelectionDragEnded,
  vueFlowHandlers: {
    onNodesChange,
    onNodeClick,
    onNodeDoubleClick,
    onNodeDragStop,
  },
})

let unsubscribeEventBus: (() => void) | null = null

onMounted(() => {
  registerDiagramLayoutRecalcBootstrap()
  void ensureMarkdownRenderer()
  unsubscribeEventBus = mountSubscriptions({
    diagramStore,
    getNodes: () => unref(getVueFlowNodes) as unknown as MindGraphNode[],
    getViewport,
    setViewport,
    zoomIn,
    zoomOut,
    fitApi: {
      fitToFullCanvas,
      fitWithPanel,
      fitDiagram,
      fitForExport,
      fitToNodes,
    },
    emit,
    exportByFormat,
    showExportToCommunityModal,
    prepareForCommunityExport,
    restoreViewportAfterCommunityExport,
    regenerateForNodeIfNeeded,
  })
  if (props.panOnDragButtons) {
    setupMobileTouchZoom()
  }
})

onUnmounted(() => {
  document.documentElement.classList.remove('mg-learning-sheet-pick')
  document.documentElement.style.removeProperty('--mg-hammer-cursor')
  unsubscribeEventBus?.()
  unsubscribeEventBus = null
  clearFitTimersOnUnmount()
  clearDoubleBubbleTimer()
  mobileTouchCleanup.value?.()
})

defineExpose({
  fitToFullCanvas,
  fitWithPanel,
  fitDiagram,
  fitForExport,
  isFittedForPanel,
})
</script>

<template>
  <div
    ref="canvasContainer"
    class="diagram-canvas relative w-full h-full"
    :class="{
      'mind-map-canvas': useMindMapV2,
      'diagram-canvas--hand-tool': props.handToolActive,
      'diagram-canvas--learning-sheet-pick': isLearningSheetPickActive,
    }"
    @contextmenu.capture="handleContextMenuEvent"
    @paste.capture="onCanvasPaste"
  >
    <LearningSheetPickBanner v-if="useMindMapV2" />
    <div
      ref="vueFlowWrapper"
      class="vue-flow-wrapper w-full h-full"
      :class="{ 'wireframe-mode': uiStore.wireframeMode }"
      @dragover="handleCanvasDragOver"
      @drop="handleCanvasDrop"
    >
      <VueFlow
        :nodes="nodes"
        :edges="edges"
        :node-types="diagramCanvasNodeTypes"
        :edge-types="diagramCanvasEdgeTypes"
        :default-viewport="{ x: 0, y: 0, zoom: diagramCanvasZoomConfig.default }"
        :min-zoom="diagramCanvasZoomConfig.min"
        :max-zoom="diagramCanvasZoomConfig.max"
        :snap-to-grid="true"
        :snap-grid="diagramCanvasGridConfig.snapSize"
        :nodes-draggable="nodesDraggable"
        :nodes-connectable="false"
        :elements-selectable="elementsSelectable"
        :select-nodes-on-drag="selectNodesOnDrag"
        :selection-key-code="selectionKeyCode"
        :selection-mode="SelectionMode.Partial"
        :pan-on-scroll="false"
        :zoom-on-scroll="true"
        :zoom-on-double-click="false"
        :pan-on-drag="effectivePanOnDrag"
        :class="vueFlowBackgroundClasses"
        :style="{ backgroundColor: backgroundColor }"
        @pane-click="handlePaneClick"
        @nodes-initialized="handleNodesInitialized"
        @viewport-change="handleViewportChangeWithToolbar"
      >
        <Background
          v-if="showBackground"
          :gap="diagramCanvasGridConfig.backgroundGap"
          :size="diagramCanvasGridConfig.backgroundDotSize"
          pattern-color="#e5e7eb"
        />

        <MiniMap
          v-if="showMinimap"
          position="bottom-left"
          :pannable="true"
          :zoomable="true"
        />

        <BraceOverlay />
        <BridgeOverlay />
        <TreeMapOverlay />
        <LearningSheetOverlay />

        <PresentationHighlightOverlay
          v-if="props.presentationRailOpen"
          v-model="presentationHighlightStrokes"
          :active="presentationStrokeToolActive"
          :current-color="presentationStrokeColor"
          :pointer-size-scale="presentationStrokePointerScale"
          :stroke-width-role-scale="presentationHighlighterStrokeScale"
          :mode="presentationTool === 'pen' ? 'pen' : 'highlighter'"
        />

        <template #zoom-pane>
          <DiagramCanvasZoomPaneOverlays
            :branch-move="branchMove"
            :get-vue-flow-nodes="getVueFlowNodesForOverlays"
            :link-preview-path="linkPreviewPath"
            :link-drag-cursor="linkDragCursor"
            :link-drag-target-node-id="linkDragTargetNodeId"
            :show-concept-link-preview="diagramStore.type === 'concept_map'"
            :link-preview-show-arrow="linkPreviewShowArrow"
          />
        </template>
      </VueFlow>
    </div>

    <CanvasNodeFloatingToolbar
      v-if="useMindMapV2"
      :position="floatingToolbarPosition"
      :node-id="floatingToolbarAnchorId"
      :ai-generating="subgraphGenerating"
      :ai-disabled="subgraphPreviewActive"
      @ai-subgraph-generate="handleAiSubgraphGenerate"
    />

    <MindMapSubgraphPreviewBar
      v-if="useMindMapV2"
      :visible="subgraphPreviewActive"
      :anchor-node-id="subgraphPreviewAnchorId"
      :container-ref="canvasContainer"
      :layout-tick="subgraphPreviewLayoutTick"
      @accept="acceptSubgraphPreview"
      @discard="discardSubgraphPreview"
    />

    <MindMapDirectionalAddOverlay
      v-if="useMindMapV2"
      :container-ref="canvasContainer"
    />
    <MindMapCollapseToggleOverlay
      v-if="useMindMapV2"
      :container-ref="canvasContainer"
    />

    <ContextMenu
      :visible="contextMenuVisible"
      :x="contextMenuX"
      :y="contextMenuY"
      :node="contextMenuNode"
      :target="contextMenuTarget"
      @close="closeContextMenu"
      @paste="handleContextMenuPaste"
      @add-concept="handleContextMenuAddConcept"
    />

    <ExportToCommunityModal
      v-model:visible="showExportToCommunityModal"
      mode="create"
      :get-container="getExportContainer"
      :get-diagram-spec="getExportSpec"
      :get-title="getExportTitle"
      :prepare-for-thumbnail="prepareForCommunityExport"
      :restore-after-thumbnail="restoreViewportAfterCommunityExport"
      :diagram-type="diagramStore.type || 'mind_map'"
    />
  </div>
</template>

<style scoped>
.diagram-canvas--learning-sheet-pick,
.diagram-canvas--learning-sheet-pick :deep(.vue-flow__pane),
.diagram-canvas--learning-sheet-pick :deep(.vue-flow__node),
.diagram-canvas--learning-sheet-pick :deep(.branch-node),
.diagram-canvas--learning-sheet-pick :deep(.topic-node),
.diagram-canvas--learning-sheet-pick :deep(.mind-map-node),
.diagram-canvas--learning-sheet-pick :deep(.mind-map-legacy-node),
.diagram-canvas--learning-sheet-pick :deep(.mind-map-topic-node),
.diagram-canvas--learning-sheet-pick :deep(.topic-node.pill-shape),
.diagram-canvas--learning-sheet-pick :deep(.inline-editable-text),
.diagram-canvas--learning-sheet-pick :deep(.inline-edit-display),
.diagram-canvas--learning-sheet-pick :deep(.cursor-grab) {
  cursor: v-bind('hammerPickCursor') !important;
}
</style>

<style>
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .vue-flow__pane,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .vue-flow__node,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .branch-node,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .topic-node,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .mind-map-node,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .mind-map-legacy-node,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .topic-node.pill-shape,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .inline-editable-text,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .inline-edit-display,
html.mg-learning-sheet-pick .diagram-canvas--learning-sheet-pick .cursor-grab {
  cursor: var(--mg-hammer-cursor) !important;
}
</style>
