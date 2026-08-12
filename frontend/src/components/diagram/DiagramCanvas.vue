<script setup lang="ts">
/**
 * DiagramCanvas - Vue Flow wrapper for MindGraph diagrams
 * Provides unified interface for all diagram types with drag-drop, zoom, and pan
 *
 * Two-View Zoom System:
 * - fitToFullCanvas(): Fits diagram to full canvas (no panel space reserved)
 * - fitWithPanel(): Fits diagram with space reserved for right-side panels
 * - Mind map v2: fit-to-canvas on enter; no auto-refit while editing (manual zoom).
 * - Legacy mind maps: assistive fit on enter and when node count changes.
 * - Desktop concept maps: manual zoom; IHMC cmap imports trigger one-shot fit on init.
 *
 * SVG text / RTL: primary labels use InlineEditableText (HTML, dir=auto). Decorative
 * overlays (brace/tree/bridge) use SVG <text>; bidi for all-RTL strings can be weaker
 * in some browsers — if reported, consider foreignObject + HTML for those labels.
 */
import { computed, onMounted, onUnmounted, provide, ref, toRef, unref, watch, toValue } from 'vue'

import { Background } from '@vue-flow/background'
import { type GraphNode, SelectionMode, VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'

import { storeToRefs } from 'pinia'

import { ExportToCommunityModal } from '@/components/canvas'
import CanvasWorksheetTextModal from '@/components/canvas/CanvasWorksheetTextModal.vue'
import MindMapNodeExplainModal from '@/components/canvas/MindMapNodeExplainModal.vue'
import { useBranchMoveDrag, useLanguage } from '@/composables'
import type { CanvasExportColorMode, CanvasExportLayout } from '@/config/canvasExportOptions'
import type { CanvasWorksheetTextOptions } from '@/config/canvasWorksheetText'
import { useCanvasExportStore } from '@/stores/canvasExport'
import {
  useNodeFloatingToolbarPosition,
  type FloatingToolbarSize,
} from '@/composables/canvasToolbar'
import { registerDiagramLayoutRecalcSession } from '@/composables/core/diagramLayoutRecalcBootstrap'
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
import {
  CONCEPT_MAP_GENERATING_KEY,
  useConceptMapRelationship,
} from '@/composables/editor/useConceptMapRelationship'
import { useMindMapSubgraphSuggest } from '@/composables/editor/useMindMapSubgraphSuggest'
import { MIND_MAP_CANVAS_VARIANT_KEY } from '@/composables/mindMap/mindMapCanvasVariantKey'
import {
  useLearningSheetCustomMode,
  useLearningSheetPickKeyboard,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { useMindMapCanvasVisuals } from '@/composables/mindMap/useMindMapCanvasVisuals'
import { useMindMapConnectorDebugLog } from '@/composables/mindMap/useMindMapConnectorDebugLog'
import { useMindMapMultiLinePaste } from '@/composables/mindMap/useMindMapMultiLinePaste'
import { useMindMapNodeExplain } from '@/composables/mindMap/useMindMapNodeExplain'
import {
  diagramPresentationReadOnlyRef,
  resolvePresentationTeleportTarget,
} from '@/composables/presentation/presentationDiagramEdit'
import { LEARNING_SHEET_HAMMER_CURSOR } from '@/config/learningSheetCursor'
import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import { usePanelsStore, usePresentationPointerStore, useUIStore } from '@/stores'
import { diagramSessionRef, useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { isDiagramPresentationReadOnly } from '@/stores/diagram/presentationReadOnlyGuard'
import type { MindMapCanvasMode } from '@/stores/ui'
import type { MindGraphNode, PresentationHighlightStroke, PresentationToolId } from '@/types'
import { isMindMapConnectorDebugEnabled } from '@/utils/mindMapConnectorDebugLevel'
import { isMindMapSubgraphExpandable } from '@/utils/mindMapSubgraphContext'

import BraceOverlay from './BraceOverlay.vue'
import BridgeOverlay from './BridgeOverlay.vue'
import ContextMenu from './ContextMenu.vue'
import DiagramCanvasZoomPaneOverlays from './DiagramCanvasZoomPaneOverlays.vue'
import LearningSheetOverlay from './LearningSheetOverlay.vue'
import PresentationHighlightOverlay from './PresentationHighlightOverlay.vue'
import TreeMapOverlay from './TreeMapOverlay.vue'
import './diagramCanvas.css'
import { diagramCanvasEdgeTypesLegacy } from './diagramCanvasEdgeTypesLegacy'
import { diagramCanvasEdgeTypesMindMapV2 } from './diagramCanvasEdgeTypesMindMapV2'
import { diagramCanvasEdgeTypes, diagramCanvasNodeTypes } from './diagramCanvasVueFlowTypes'

interface Props {
  /** Locks mind map rendering when mounted via MindMapLegacyCanvas / MindMapV2Canvas. */
  mindMapVariant?: MindMapCanvasMode
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
  presentationPointerEditMode?: boolean
  presentationHandPanMode?: boolean
  collabLockedNodeIds?: string[]
  mindMapSlideFocusNodeId?: string | null
  mindMapSlideDimFocusNodeIds?: Set<string> | null
  panOnDragButtons?: number[] | null
  /**
   * Desktop classroom e-blackboard: two-finger pan/zoom (1-finger stays tap/select);
   * mouse middle-button pan stays. Phone mobile uses panOnDragButtons instead.
   */
  enableTouchPanPinch?: boolean
  presentationRailOpen?: boolean
  presentationSideToolbarVisible?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showBackground: true,
  showMinimap: false,
  fitViewOnInit: true,
  conceptMapInitialTopicFit: false,
  handToolActive: false,
  presentationPointerEditMode: false,
  presentationHandPanMode: false,
  collabLockedNodeIds: () => [],
  mindMapSlideFocusNodeId: null,
  mindMapSlideDimFocusNodeIds: null,
  panOnDragButtons: null,
  enableTouchPanPinch: false,
  presentationRailOpen: false,
  presentationSideToolbarVisible: true,
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

const presentationStrokeEraserActive = defineModel<boolean>('presentationStrokeEraserActive', {
  default: false,
})

const emit = defineEmits<{
  (e: 'nodeClick', node: MindGraphNode): void
  (e: 'nodeDoubleClick', node: MindGraphNode): void
  (e: 'nodeDragStop', node: MindGraphNode): void
  (e: 'selectionChange', nodes: MindGraphNode[]): void
  (e: 'paneClick'): void
}>()

const diagramStore = useDiagramSession()
const mindMapBulkLoading = diagramSessionRef(diagramStore, 'mindMapBulkLoading')
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
} = useVueFlow(diagramStore.vueFlowId)

onEdgeClick(({ edge }) => {
  if (diagramStore.type === 'concept_map') {
    diagramStore.selectConnection(edge.id)
  }
})

function getVueFlowNodesForOverlays(): GraphNode[] {
  return unref(getVueFlowNodes) as GraphNode[]
}

const branchMove = useBranchMoveDrag({
  allowNodeMove: () =>
    (!props.presentationRailOpen && !props.handToolActive) ||
    (props.presentationRailOpen && props.presentationPointerEditMode),
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
  presentationPointerEditMode: toRef(props, 'presentationPointerEditMode'),
  presentationHandPanMode: toRef(props, 'presentationHandPanMode'),
  panOnDragButtons: toRef(props, 'panOnDragButtons'),
  enableTouchPanPinch: toRef(props, 'enableTouchPanPinch'),
  presentationTool,
  presentationHighlighterColor,
  presentationPenColor,
})

/** Mobile page or desktop e-blackboard — CSS touch-action + marquee hide. */
const canvasTouchGesturesActive = computed(
  () =>
    props.enableTouchPanPinch ||
    (Array.isArray(props.panOnDragButtons) && props.panOnDragButtons.length > 0)
)

const presentationDiagramEditLocked = computed(
  () =>
    diagramPresentationReadOnlyRef.value || toValue(diagramStore.isReadonly)
)

const presentationStrokeOverlayMode = computed((): 'pen' | 'highlighter' | 'eraser' => {
  if (presentationStrokeEraserActive.value) return 'eraser'
  return presentationTool.value === 'pen' ? 'pen' : 'highlighter'
})

/** Zoom-bar hand or presentation hand: grab-pan the canvas. */
const useHandToolPanClass = computed(
  () => props.presentationHandPanMode || (props.handToolActive && !props.presentationRailOpen)
)

const presentationTeleportTarget = computed(() => resolvePresentationTeleportTarget())

const { nodes, edges, nodesLength } = useDiagramCanvasNodesEdges({
  diagramStore,
  branchMove,
  collabLockedNodeIds: () => props.collabLockedNodeIds,
  mindMapSlideFocusNodeId: () => props.mindMapSlideFocusNodeId,
  mindMapSlideDimFocusNodeIds: () => props.mindMapSlideDimFocusNodeIds,
})

provide(
  MIND_MAP_CANVAS_VARIANT_KEY,
  computed(() => props.mindMapVariant ?? null)
)

const useMindMapV2 = useMindMapCanvasVisuals()

const resolvedEdgeTypes = computed(() => {
  if (props.mindMapVariant === 'legacy') {
    return diagramCanvasEdgeTypesLegacy
  }
  if (props.mindMapVariant === 'v2') {
    return diagramCanvasEdgeTypesMindMapV2
  }
  const isMindMap = diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
  if (isMindMap && useMindMapV2.value) {
    return diagramCanvasEdgeTypesMindMapV2
  }
  if (isMindMap) {
    return diagramCanvasEdgeTypesLegacy
  }
  return diagramCanvasEdgeTypes
})

const mindMapConnectorDebugEnabled = computed(
  () =>
    isMindMapConnectorDebugEnabled() &&
    useMindMapV2.value &&
    (diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map')
)
useMindMapConnectorDebugLog({
  enabled: mindMapConnectorDebugEnabled,
  containerRef: canvasContainer,
  screenToFlowCoordinate,
})

const { handlePaste: handleMindMapMultiLinePaste } = useMindMapMultiLinePaste()

function onCanvasPaste(event: ClipboardEvent): void {
  if (isDiagramPresentationReadOnly(diagramStore)) return
  if (diagramStore.canPaste) {
    event.preventDefault()
    const anchor = diagramStore.selectedNodes[0]
    diagramStore.pasteClipboardAt({ anchorNodeId: anchor })
    return
  }
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

const nodeExplain = useMindMapNodeExplain()
const {
  visible: nodeExplainVisible,
  target: nodeExplainTarget,
  panels: nodeExplainPanels,
  loading: nodeExplainLoading,
  openExplain: openNodeExplain,
  close: closeNodeExplain,
} = nodeExplain

const floatingToolbarNodeIds = computed(() => {
  if (!useMindMapV2.value) return []
  return diagramStore.selectedNodes.slice()
})

const floatingToolbarEnabled = computed(() => floatingToolbarNodeIds.value.length > 0)

const floatingToolbarAnchorId = computed(() => floatingToolbarNodeIds.value[0] ?? null)

const floatingToolbarShowAiSubgraph = computed(() =>
  isMindMapSubgraphExpandable(floatingToolbarAnchorId.value)
)

const floatingToolbarSize = ref<FloatingToolbarSize | null>(null)

const { position: floatingToolbarPosition, scheduleMeasure: scheduleFloatingToolbarMeasure } =
  useNodeFloatingToolbarPosition({
    containerRef: canvasContainer,
    selectedNodeIds: floatingToolbarNodeIds,
    enabled: floatingToolbarEnabled,
    toolbarSize: floatingToolbarSize,
  })

function handleFloatingToolbarSizeChange(size: FloatingToolbarSize | null): void {
  floatingToolbarSize.value = size
}

watch(
  () => {
    const selected = floatingToolbarNodeIds.value
    if (selected.length === 0) return ''
    const selectedSet = new Set(selected)
    return nodes.value
      .filter((n) => selectedSet.has(n.id))
      .map((n) => `${n.id}:${n.position?.x ?? 0}:${n.position?.y ?? 0}`)
      .join('|')
  },
  () => {
    scheduleFloatingToolbarMeasure()
  }
)

const { isGenerating: subgraphGenerating, generateSubgraph } = useMindMapSubgraphSuggest()

async function handleAiSubgraphGenerate() {
  await generateSubgraph(floatingToolbarAnchorId.value)
}

function handleFloatingToolbarExplainNode(): void {
  const nodeId = floatingToolbarAnchorId.value
  if (!nodeId) return
  openNodeExplain(nodeId)
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
  ensureNodeVisibleInSafeFraction,
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
  presentationSideToolbarVisible: toRef(props, 'presentationSideToolbarVisible'),
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
  captureWorksheetPreviewPng,
} = useDiagramCanvasExport({
  vueFlowWrapper,
  diagramStore,
  fitForExport,
  getViewport,
  setViewport,
})

const canvasExportStore = useCanvasExportStore()
const {
  exportOptions,
  worksheetTextOptions,
  worksheetTextModalOpen,
} = storeToRefs(canvasExportStore)

function handleWorksheetTextSave(payload: {
  worksheetText: CanvasWorksheetTextOptions
  colorMode: CanvasExportColorMode
  layout: CanvasExportLayout
  format: 'pdf' | 'worksheet_docx'
}) {
  canvasExportStore.commitWorksheetAndExport(
    payload.worksheetText,
    payload.colorMode,
    payload.format,
    payload.layout
  )
}

const worksheetDefaultTopic = computed(() => getExportTitle())

async function captureWorksheetPreview(preview?: {
  colorMode?: CanvasExportColorMode
}): Promise<string | null> {
  return canvasExportStore.runExportSession(async () =>
    captureWorksheetPreviewPng({
      ...exportOptions.value,
      colorMode: preview?.colorMode ?? exportOptions.value.colorMode,
      answerMode: exportOptions.value.answerMode,
    })
  )
}

function handleViewportChangeWithToolbar(...args: Parameters<typeof handleViewportChange>) {
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
const paletteDragPreview = computed(() => mindMapPaletteDrop.paletteDragPreview.value)

function handleCanvasDragOver(event: DragEvent): void {
  handleConceptMapDragOver(event)
  mindMapPaletteDrop.handleMindMapPaletteDragOver(event)
}

function handleCanvasDragLeave(event: DragEvent): void {
  mindMapPaletteDrop.handleMindMapPaletteDragLeave(event)
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
  presentationDiagramEditLocked: diagramPresentationReadOnlyRef,
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
  // Phone mobile keeps 1-finger pan; e-blackboard uses 2-finger pan so 1-finger can select.
  allowSingleFingerPan: () => !props.enableTouchPanPinch,
})

function syncTouchPanPinchLayer(): void {
  mobileTouchCleanup.value?.()
  mobileTouchCleanup.value = null
  if (props.enableTouchPanPinch || props.panOnDragButtons) {
    setupMobileTouchZoom()
  }
}

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
let unregisterLayoutRecalcSession: (() => void) | null = null

onMounted(() => {
  unregisterLayoutRecalcSession = registerDiagramLayoutRecalcSession(diagramStore)
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
      ensureNodeVisibleInSafeFraction,
    },
    emit,
    exportByFormat,
    getExportContainer,
    showExportToCommunityModal,
    prepareForCommunityExport,
    restoreViewportAfterCommunityExport,
    regenerateForNodeIfNeeded,
  })
  syncTouchPanPinchLayer()
})

watch(
  () => [props.panOnDragButtons, props.enableTouchPanPinch] as const,
  () => {
    syncTouchPanPinchLayer()
  }
)

onUnmounted(() => {
  document.documentElement.classList.remove('mg-learning-sheet-pick')
  document.documentElement.style.removeProperty('--mg-hammer-cursor')
  unregisterLayoutRecalcSession?.()
  unregisterLayoutRecalcSession = null
  unsubscribeEventBus?.()
  unsubscribeEventBus = null
  clearFitTimersOnUnmount()
  clearDoubleBubbleTimer()
  mobileTouchCleanup.value?.()
  mobileTouchCleanup.value = null
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
      'canvas-touch': canvasTouchGesturesActive,
      'diagram-canvas--hand-tool': useHandToolPanClass,
      'diagram-canvas--learning-sheet-pick': isLearningSheetPickActive,
      'diagram-canvas--bulk-load': mindMapBulkLoading,
    }"
    @contextmenu.capture="handleContextMenuEvent"
    @paste.capture="onCanvasPaste"
  >
    <div
      ref="vueFlowWrapper"
      class="vue-flow-wrapper w-full h-full"
      :class="{
        'wireframe-mode': uiStore.wireframeMode,
        'export-outline-wireframe': uiStore.exportWireframeOutline,
      }"
      @dragover="handleCanvasDragOver"
      @dragleave="handleCanvasDragLeave"
      @drop="handleCanvasDrop"
    >
      <VueFlow
        :id="diagramStore.vueFlowId"
        :nodes="nodes"
        :edges="edges"
        :node-types="diagramCanvasNodeTypes"
        :edge-types="resolvedEdgeTypes"
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
        :style="{ backgroundColor: uiStore.exportRasterCapture ? 'transparent' : backgroundColor }"
        @pane-click="handlePaneClick"
        @nodes-initialized="handleNodesInitialized"
        @viewport-change="handleViewportChangeWithToolbar"
      >
        <Background
          v-if="showBackground && !uiStore.exportRasterCapture"
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
          :mode="presentationStrokeOverlayMode"
        />

        <template #zoom-pane>
          <DiagramCanvasZoomPaneOverlays
            :branch-move="branchMove"
            :palette-drag-preview="paletteDragPreview"
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

    <slot
      v-if="useMindMapV2"
      name="v2-canvas-overlays"
      :presentation-diagram-edit-locked="presentationDiagramEditLocked"
      :floating-toolbar-position="floatingToolbarPosition"
      :floating-toolbar-anchor-id="floatingToolbarAnchorId"
      :subgraph-generating="subgraphGenerating"
      :floating-toolbar-show-ai-subgraph="floatingToolbarShowAiSubgraph"
      :node-explain-open="nodeExplainVisible"
      :canvas-container="canvasContainer"
      :presentation-teleport-target="presentationTeleportTarget"
      :on-ai-subgraph-generate="handleAiSubgraphGenerate"
      :on-explain-node="handleFloatingToolbarExplainNode"
      :on-floating-toolbar-size-change="handleFloatingToolbarSizeChange"
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

    <MindMapNodeExplainModal
      v-model:visible="nodeExplainVisible"
      :target="nodeExplainTarget"
      :panels="nodeExplainPanels"
      :loading="nodeExplainLoading"
      @close="closeNodeExplain"
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

    <CanvasWorksheetTextModal
      v-model:visible="worksheetTextModalOpen"
      :color-mode="exportOptions.colorMode"
      :options="worksheetTextOptions"
      :layout="exportOptions.layout"
      :default-topic="worksheetDefaultTopic"
      :capture-diagram-preview="captureWorksheetPreview"
      @save="handleWorksheetTextSave"
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
