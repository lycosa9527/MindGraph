<script setup lang="ts">
/**
 * DiagramCanvas - Vue Flow wrapper for MindGraph diagrams
 * Provides unified interface for all diagram types with drag-drop, zoom, and pan
 *
 * Two-View Zoom System:
 * - fitToFullCanvas(): Fits diagram to full canvas (no panel space reserved)
 * - fitWithPanel(): Fits diagram with space reserved for right-side panels
 * - Automatically re-fits when panels open/close
 *
 * SVG text / RTL: primary labels use InlineEditableText (HTML, dir=auto). Decorative
 * overlays (brace/tree/bridge) use SVG <text>; bidi for all-RTL strings can be weaker
 * in some browsers — if reported, consider foreignObject + HTML for those labels.
 */
import { computed, onMounted, onUnmounted, provide, ref, toRef, unref } from 'vue'

import { Background } from '@vue-flow/background'
import { type GraphNode, VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'

import { storeToRefs } from 'pinia'

import { ExportToCommunityModal } from '@/components/canvas'
import { useBranchMoveDrag, useLanguage } from '@/composables'
import { useTheme } from '@/composables/core/useTheme'
import {
  diagramCanvasGridConfig,
  diagramCanvasZoomConfig,
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
import {
  CONCEPT_MAP_GENERATING_KEY,
  useConceptMapRelationship,
} from '@/composables/editor/useConceptMapRelationship'
import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import { useDiagramStore, usePanelsStore, usePresentationPointerStore, useUIStore } from '@/stores'
import type { MindGraphNode, PresentationHighlightStroke, PresentationToolId } from '@/types'

import BraceOverlay from './BraceOverlay.vue'
import BridgeOverlay from './BridgeOverlay.vue'
import ContextMenu from './ContextMenu.vue'
import DiagramCanvasZoomPaneOverlays from './DiagramCanvasZoomPaneOverlays.vue'
import LearningSheetOverlay from './LearningSheetOverlay.vue'
import PresentationHighlightOverlay from './PresentationHighlightOverlay.vue'
import TreeMapOverlay from './TreeMapOverlay.vue'
import './diagramCanvas.css'
import { diagramCanvasEdgeTypes, diagramCanvasNodeTypes } from './diagramCanvasVueFlowTypes'

interface Props {
  showBackground?: boolean
  showMinimap?: boolean
  fitViewOnInit?: boolean
  handToolActive?: boolean
  collabLockedNodeIds?: string[]
  panOnDragButtons?: number[] | null
  presentationRailOpen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showBackground: true,
  showMinimap: false,
  fitViewOnInit: true,
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

const {
  generateRelationship,
  generatingConnectionIds,
  regenerateForNodeIfNeeded,
  dismissAllOptions,
} = useConceptMapRelationship()
provide(CONCEPT_MAP_GENERATING_KEY, generatingConnectionIds)

const { backgroundColor } = useTheme({
  diagramType: computed(() => diagramStore.type),
})

const { t } = useLanguage()

const vueFlowWrapper = ref<HTMLElement | null>(null)
const canvasContainer = ref<HTMLElement | null>(null)

const {
  showExportToCommunityModal,
  getExportContainer,
  getExportTitle,
  getExportSpec,
  exportByFormat,
} = useDiagramCanvasExport({
  vueFlowWrapper,
  diagramStore,
})

const {
  onNodesChange,
  onNodeClick,
  onNodeDoubleClick,
  onNodeDragStop,
  fitView,
  getNodes: getVueFlowNodes,
  setViewport,
  getViewport,
  zoomIn,
  zoomOut,
  screenToFlowCoordinate,
} = useVueFlow()

function getVueFlowNodesForOverlays(): GraphNode[] {
  return unref(getVueFlowNodes) as GraphNode[]
}

const branchMove = useBranchMoveDrag()
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
  vueFlowBackgroundClasses,
} = useDiagramCanvasVueFlowUi({
  diagramStore,
  presentationRailOpen: toRef(props, 'presentationRailOpen'),
  handToolActive: toRef(props, 'handToolActive'),
  panOnDragButtons: toRef(props, 'panOnDragButtons'),
  presentationTool,
  presentationHighlighterColor,
})

const { nodes, edges, nodesLength } = useDiagramCanvasNodesEdges({
  diagramStore,
  branchMove,
  collabLockedNodeIds: () => props.collabLockedNodeIds,
})

const {
  isFittedForPanel,
  handleViewportChange,
  handleNodesInitialized,
  fitToFullCanvas,
  fitWithPanel,
  fitDiagram,
  fitForExport,
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
  presentationRailOpen: toRef(props, 'presentationRailOpen'),
  presentationToolIsNotTimer,
  nodesLength,
})

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

const contextMenu = useDiagramCanvasContextMenu({
  vueFlowWrapper,
  getNodes: () => unref(getVueFlowNodes),
  screenToFlowCoordinate,
  presentationRailOpen: toRef(props, 'presentationRailOpen'),
  emitPaneClick: () => emit('paneClick'),
  diagramStore,
  dismissAllOptions,
  t,
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
  emit,
  scheduleFitAfterStructuralNodeChange,
  vueFlowHandlers: {
    onNodesChange,
    onNodeClick,
    onNodeDoubleClick,
    onNodeDragStop,
  },
})

let unsubscribeEventBus: (() => void) | null = null

onMounted(() => {
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
    },
    emit,
    exportByFormat,
    showExportToCommunityModal,
    regenerateForNodeIfNeeded,
  })
  if (props.panOnDragButtons) {
    setupMobileTouchZoom()
  }
})

onUnmounted(() => {
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
    class="diagram-canvas w-full h-full"
    @contextmenu.capture="handleContextMenuEvent"
  >
    <div
      ref="vueFlowWrapper"
      class="vue-flow-wrapper w-full h-full"
      :class="{ 'wireframe-mode': uiStore.wireframeMode }"
      @dragover="handleConceptMapDragOver"
      @drop="handleConceptMapDrop"
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
        :pan-on-scroll="false"
        :zoom-on-scroll="true"
        :zoom-on-double-click="false"
        :pan-on-drag="effectivePanOnDrag"
        :class="vueFlowBackgroundClasses"
        :style="{ backgroundColor: backgroundColor }"
        @pane-click="handlePaneClick"
        @nodes-initialized="handleNodesInitialized"
        @viewport-change="handleViewportChange"
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
      :diagram-type="diagramStore.type || 'mind_map'"
    />
  </div>
</template>
