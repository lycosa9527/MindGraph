<script setup lang="ts">
/**
 * DiagramCanvas - Vue Flow wrapper for MindGraph diagrams
 * Provides unified interface for all diagram types with drag-drop, zoom, and pan
 *
 * Two-View Zoom System:
 * - fitToFullCanvas(): Fits diagram to full canvas (no panel space reserved)
 * - fitWithPanel(): Fits diagram with space reserved for right-side panels
 * - Automatically re-fits when panels open/close
 */
import { computed, markRaw, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'

import { Background } from '@vue-flow/background'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'

import { getDefaultDiagramName, useDiagramExport, useLanguage } from '@/composables'
import {
  CONCEPT_MAP_GENERATING_KEY,
  useConceptMapRelationship,
} from '@/composables/useConceptMapRelationship'
import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import { ANIMATION, FIT_PADDING, GRID, PANEL, ZOOM } from '@/config/uiConfig'
import { useDiagramStore, useLLMResultsStore, usePanelsStore, useUIStore } from '@/stores'
import type { MindGraphNode } from '@/types'

import BraceOverlay from './BraceOverlay.vue'
import BridgeOverlay from './BridgeOverlay.vue'
import LearningSheetOverlay from './LearningSheetOverlay.vue'
import TreeMapOverlay from './TreeMapOverlay.vue'
import ContextMenu from './ContextMenu.vue'
import BraceEdge from './edges/BraceEdge.vue'
// Import custom edge components
import CurvedEdge from './edges/CurvedEdge.vue'
import HorizontalStepEdge from './edges/HorizontalStepEdge.vue'
import RadialEdge from './edges/RadialEdge.vue'
import StepEdge from './edges/StepEdge.vue'
import StraightEdge from './edges/StraightEdge.vue'
import TreeEdge from './edges/TreeEdge.vue'
import BoundaryNode from './nodes/BoundaryNode.vue'
import BraceNode from './nodes/BraceNode.vue'
import BranchNode from './nodes/BranchNode.vue'
import BubbleNode from './nodes/BubbleNode.vue'
import CircleNode from './nodes/CircleNode.vue'
import ConceptNode from './nodes/ConceptNode.vue'
import FlowNode from './nodes/FlowNode.vue'
import FlowSubstepNode from './nodes/FlowSubstepNode.vue'
import LabelNode from './nodes/LabelNode.vue'
// Import custom node components
import TopicNode from './nodes/TopicNode.vue'

// Props
interface Props {
  showBackground?: boolean
  showMinimap?: boolean
  fitViewOnInit?: boolean
  /** When true, left-click drag pans canvas; nodes are not draggable */
  handToolActive?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showBackground: true,
  showMinimap: false,
  fitViewOnInit: true,
  handToolActive: false,
})

// Emits
const emit = defineEmits<{
  (e: 'nodeClick', node: MindGraphNode): void
  (e: 'nodeDoubleClick', node: MindGraphNode): void
  (e: 'nodeDragStop', node: MindGraphNode): void
  (e: 'selectionChange', nodes: MindGraphNode[]): void
  (e: 'paneClick'): void
}>()

// Stores
const diagramStore = useDiagramStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
const uiStore = useUIStore()

// Concept map AI relationship (provide for CurvedEdge)
const { generateRelationship, generatingConnectionIds, regenerateForNodeIfNeeded } =
  useConceptMapRelationship()
provide(CONCEPT_MAP_GENERATING_KEY, generatingConnectionIds)

// Theme for background color
const { backgroundColor } = useTheme({
  diagramType: computed(() => diagramStore.type),
})

// Language for export messages
const { isZh } = useLanguage()

// Export composable
function getExportTitle(): string {
  const topicText = diagramStore.getTopicNodeText()
  if (topicText) return topicText
  return diagramStore.effectiveTitle || getDefaultDiagramName(diagramStore.type, isZh.value)
}

function getExportSpec(): Record<string, unknown> | null {
  return diagramStore.getSpecForSave()
}

const { exportByFormat } = useDiagramExport({
  getContainer: () => vueFlowWrapper.value,
  getDiagramSpec: getExportSpec,
  getTitle: getExportTitle,
  isZh: () => isZh.value,
})

// Vue Flow instance
const {
  onNodesChange,
  onNodeClick,
  onNodeDoubleClick,
  onNodeDragStop,
  fitView,
  getNodes,
  setViewport,
  getViewport,
  zoomIn,
  zoomOut,
  screenToFlowCoordinate,
} = useVueFlow()

// Vue Flow wrapper reference for context menu
const vueFlowWrapper = ref<HTMLElement | null>(null)

// Track if current fit was done with panel space reserved
const isFittedForPanel = ref(false)

// Track if we've done initial fit for current diagram - prevents fitView on pane click
// (nodes-initialized can re-fire when vueFlowNodes returns new refs on selection clear)
const hasInitialFitDoneForDiagram = ref(false)

// Debounce timeout for fit triggered by onNodesChange (layout/dimension changes)
let fitFromNodesChangeTimeoutId: ReturnType<typeof setTimeout> | null = null

// Reset initial-fit flag when diagram changes (new load, type switch)
watch(
  () => [diagramStore.type, diagramStore.data] as const,
  () => {
    hasInitialFitDoneForDiagram.value = false
  }
)

// Concept map: handle link drop on node (create connection only)
function handleConceptMapLinkDrop(payload: { sourceId: string; targetId: string }) {
  if (diagramStore.type !== 'concept_map') return
  const connId = diagramStore.addConnection(payload.sourceId, payload.targetId, '')
  diagramStore.pushHistory('Add link')
  if (connId && llmResultsStore.selectedModel) {
    generateRelationship(connId, payload.sourceId, payload.targetId)
  }
}

function handleConceptMapLabelCleared(payload: {
  connectionId: string
  sourceId: string
  targetId: string
}) {
  if (diagramStore.type !== 'concept_map') return
  if (!llmResultsStore.selectedModel) return
  generateRelationship(payload.connectionId, payload.sourceId, payload.targetId)
}

// Canvas container reference for size calculations
const canvasContainer = ref<HTMLElement | null>(null)

// Context menu state
const contextMenuVisible = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
const contextMenuNode = ref<MindGraphNode | null>(null)
const contextMenuTarget = ref<'node' | 'pane'>('pane')

// Custom node types registration
// Use markRaw to prevent Vue from making components reactive (performance optimization)
const nodeTypes = {
  topic: markRaw(TopicNode),
  bubble: markRaw(BubbleNode),
  branch: markRaw(BranchNode),
  flow: markRaw(FlowNode),
  flowSubstep: markRaw(FlowSubstepNode), // Substep nodes for flow maps
  brace: markRaw(BraceNode),
  boundary: markRaw(BoundaryNode),
  label: markRaw(LabelNode),
  circle: markRaw(CircleNode), // Perfect circular nodes for circle maps
  concept: markRaw(ConceptNode), // Concept map nodes with link icon
  // Default fallbacks
  tree: markRaw(BranchNode),
  bridge: markRaw(BranchNode),
}

// Custom edge types registration
// Use markRaw to prevent Vue from making components reactive (performance optimization)
const edgeTypes = {
  curved: markRaw(CurvedEdge),
  straight: markRaw(StraightEdge),
  step: markRaw(StepEdge), // T/L shaped orthogonal connectors for tree maps
  horizontalStep: markRaw(HorizontalStepEdge), // Horizontal-first T/L for flow map substeps
  tree: markRaw(TreeEdge), // Straight vertical lines for tree maps (no arrowhead)
  radial: markRaw(RadialEdge), // Center-to-center for radial layouts (bubble maps)
  brace: markRaw(BraceEdge),
  bridge: markRaw(StraightEdge), // Use straight for bridge maps
}

// Computed nodes and edges from store
const nodes = computed(() => diagramStore.vueFlowNodes)
// For brace maps, hide individual edges since BraceOverlay draws the braces
const edges = computed(() => {
  if (diagramStore.type === 'brace_map') {
    // Hide edges for brace maps - the BraceOverlay component draws them
    return []
  }
  return diagramStore.vueFlowEdges
})

// Handle node changes (position updates, etc.)
onNodesChange((changes) => {
  const fitTriggeringTypes = ['position', 'dimensions', 'remove', 'add'] as const
  let hasFitTriggeringChange = false

  changes.forEach((change) => {
    if (change.type === 'position' && change.position) {
      // During drag, update position but don't mark as custom yet
      diagramStore.updateNodePosition(change.id, change.position, false)
    }
    if (fitTriggeringTypes.includes(change.type as (typeof fitTriggeringTypes)[number])) {
      hasFitTriggeringChange = true
    }
  })

  // Refit when nodes change (dimensions, add/remove, position) - except concept map (free-form)
  if (
    hasFitTriggeringChange &&
    diagramStore.type !== 'concept_map' &&
    props.fitViewOnInit &&
    getNodes.value.length > 0
  ) {
    if (fitFromNodesChangeTimeoutId) clearTimeout(fitFromNodesChangeTimeoutId)
    fitFromNodesChangeTimeoutId = setTimeout(() => {
      fitFromNodesChangeTimeoutId = null
      eventBus.emit('view:fit_to_canvas_requested', { animate: true })
    }, ANIMATION.FIT_DELAY)
  }
})

// Helper function to get timestamp for logging
function getTimestamp(): string {
  return new Date().toISOString()
}

// Handle node click
onNodeClick(({ node, event }) => {
  console.log(`[DiagramCanvas] [${getTimestamp()}] ========== NODE CLICKED ==========`)
  console.log(`[DiagramCanvas] [${getTimestamp()}] Node clicked:`, {
    nodeId: node.id,
    nodeType: node.type,
    diagramType: node.data?.diagramType,
    pairIndex: node.data?.pairIndex,
    position: node.data?.position,
    text: node.data?.label || node.data?.text,
    nodePosition: node.position,
    clickEvent: {
      type: event?.type,
      button: (event as MouseEvent)?.button,
      clientX: (event as MouseEvent)?.clientX,
      clientY: (event as MouseEvent)?.clientY,
    },
  })
  console.log(`[DiagramCanvas] [${getTimestamp()}] Currently selected nodes:`, [
    ...diagramStore.selectedNodes,
  ])
  diagramStore.selectNodes(node.id)
  console.log(`[DiagramCanvas] [${getTimestamp()}] After selection, selected nodes:`, [
    ...diagramStore.selectedNodes,
  ])
  console.log(`[DiagramCanvas] [${getTimestamp()}] ====================================`)
  emit('nodeClick', node as unknown as MindGraphNode)
})

// Handle node double-click for editing
onNodeDoubleClick(({ node }) => {
  emit('nodeDoubleClick', node as unknown as MindGraphNode)
})

// Handle node drag stop - mark position as custom (user-dragged)
onNodeDragStop(({ node }) => {
  // Save as custom position since user dragged it
  diagramStore.saveCustomPosition(node.id, node.position.x, node.position.y)
  diagramStore.pushHistory('Move node')
  emit('nodeDragStop', node as unknown as MindGraphNode)
})

// Concept map link drag state
const CONCEPT_LINK_DATA_TYPE = 'application/mindgraph-concept-link'
const PALETTE_CONCEPT_DATA_TYPE = 'application/mindgraph-palette-concept'

function handleConceptMapDragOver(event: DragEvent) {
  if (diagramStore.type !== 'concept_map') return
  const types = event.dataTransfer?.types ?? []
  const hasLinkData = types.includes(CONCEPT_LINK_DATA_TYPE)
  const hasPaletteConcept = types.includes(PALETTE_CONCEPT_DATA_TYPE)
  if ((hasLinkData || hasPaletteConcept) && event.dataTransfer) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }
}

function handleConceptMapDrop(event: DragEvent) {
  if (diagramStore.type !== 'concept_map') return

  const paletteData = event.dataTransfer?.getData(PALETTE_CONCEPT_DATA_TYPE)
  if (paletteData) {
    event.preventDefault()
    const target = event.target as HTMLElement
    if (target.closest('.vue-flow__node')) return
    try {
      const { text } = JSON.parse(paletteData) as { text: string }
      const flowPos = screenToFlowCoordinate({
        x: event.clientX,
        y: event.clientY,
      })
      diagramStore.addNode({
        id: '',
        text: text || '新概念',
        type: 'branch',
        position: { x: flowPos.x - 50, y: flowPos.y - 18 },
      })
      diagramStore.pushHistory('Add concept')
    } catch {
      // Ignore malformed palette data
    }
    return
  }

  const sourceId = event.dataTransfer?.getData(CONCEPT_LINK_DATA_TYPE)
  if (!sourceId) return

  const target = event.target as HTMLElement
  const nodeElement = target.closest('.vue-flow__node')
  if (nodeElement) {
    return
  }

  event.preventDefault()
  const flowPos = screenToFlowCoordinate({
    x: event.clientX,
    y: event.clientY,
  })
  diagramStore.addNode({
    id: '',
    text: '新概念',
    type: 'branch',
    position: { x: flowPos.x - 50, y: flowPos.y - 18 },
  })
  const nodes = diagramStore.data?.nodes ?? []
  const newId = nodes[nodes.length - 1]?.id
  if (newId) {
    diagramStore.addConnection(sourceId, newId, '')
  }
  diagramStore.pushHistory('Add concept and link')
}

// Double-click detection for concept map (create node on empty canvas)
const lastPaneClickTime = ref(0)
const lastPaneClickPosition = ref<{ x: number; y: number } | null>(null)
const DOUBLE_CLICK_THRESHOLD_MS = 300
const DOUBLE_CLICK_POSITION_THRESHOLD = 10

// Handle pane click (deselect) and double-click for concept map
function handlePaneClick(event?: MouseEvent) {
  const now = Date.now()
  const isDoubleClick =
    diagramStore.type === 'concept_map' &&
    event &&
    now - lastPaneClickTime.value < DOUBLE_CLICK_THRESHOLD_MS &&
    lastPaneClickPosition.value &&
    Math.abs(event.clientX - lastPaneClickPosition.value.x) < DOUBLE_CLICK_POSITION_THRESHOLD &&
    Math.abs(event.clientY - lastPaneClickPosition.value.y) < DOUBLE_CLICK_POSITION_THRESHOLD

  if (isDoubleClick && event) {
    const flowPos = screenToFlowCoordinate({
      x: event.clientX,
      y: event.clientY,
    })
    diagramStore.addNode({
      id: '',
      text: '新概念',
      type: 'branch',
      position: { x: flowPos.x - 50, y: flowPos.y - 18 },
    })
    diagramStore.pushHistory('Add concept')
    lastPaneClickTime.value = 0
    lastPaneClickPosition.value = null
  } else {
    if (event) {
      lastPaneClickTime.value = now
      lastPaneClickPosition.value = {
        x: event.clientX,
        y: event.clientY,
      }
    }
    diagramStore.clearSelection()
  }
  emit('paneClick')
}

// Handle pane context menu (right-click on empty canvas)
function handlePaneContextMenu(event: MouseEvent) {
  event.preventDefault()
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuNode.value = null
  contextMenuTarget.value = 'pane'
  contextMenuVisible.value = true
}

// Handle node context menu (right-click on node)
function handleNodeContextMenu(event: MouseEvent, node: MindGraphNode) {
  event.preventDefault()
  contextMenuX.value = event.clientX
  contextMenuY.value = event.clientY
  contextMenuNode.value = node
  contextMenuTarget.value = 'node'
  contextMenuVisible.value = true
}

// Context menu setup - stored for cleanup on unmount
let contextMenuSetupTimeoutId: ReturnType<typeof setTimeout> | null = null
let contextMenuElement: HTMLElement | null = null
let contextMenuHandler: ((event: Event) => void) | null = null

function handleContextMenuEvent(event: Event) {
  const mouseEvent = event as MouseEvent
  const target = mouseEvent.target as HTMLElement

  const nodeElement = target.closest('.vue-flow__node')
  if (nodeElement) {
    const nodeId = nodeElement.getAttribute('data-id')
    if (nodeId) {
      const node = getNodes.value.find((n) => n.id === nodeId)
      if (node) {
        handleNodeContextMenu(mouseEvent, node as unknown as MindGraphNode)
        return
      }
    }
  }

  handlePaneContextMenu(mouseEvent)
}

// Set up context menu listeners and concept map link drop on mount
onMounted(() => {
  eventBus.on('concept_map:link_drop', handleConceptMapLinkDrop)
  eventBus.on('concept_map:label_cleared', handleConceptMapLabelCleared)
  contextMenuSetupTimeoutId = setTimeout(() => {
    contextMenuSetupTimeoutId = null
    const vueFlowElement = vueFlowWrapper.value?.querySelector('.vue-flow') as HTMLElement | null
    if (vueFlowElement) {
      contextMenuElement = vueFlowElement
      contextMenuHandler = handleContextMenuEvent
      vueFlowElement.addEventListener('contextmenu', contextMenuHandler)
    }
  }, 100)
})

// Close context menu
function closeContextMenu() {
  contextMenuVisible.value = false
  contextMenuNode.value = null
}

// Handle paste from context menu - convert screen coords to flow coords
function handleContextMenuPaste(position: { x: number; y: number }) {
  const flowPos = screenToFlowCoordinate({ x: position.x, y: position.y })
  diagramStore.pasteNodesAt(flowPos)
}

// Handle add concept from context menu (concept_map)
function handleContextMenuAddConcept(position: { x: number; y: number }) {
  const flowPos = screenToFlowCoordinate({ x: position.x, y: position.y })
  diagramStore.addNode({
    id: '',
    text: '新概念',
    type: 'branch',
    position: { x: flowPos.x - 50, y: flowPos.y - 18 },
  })
  diagramStore.pushHistory('Add concept')
}

// Handle nodes initialized - Vue Flow has placed nodes, viewport is ready
// Use same flow as zoom fit button; delay to let layout fully settle
// Only fit on first init for current diagram - nodes-initialized re-fires when
// vueFlowNodes returns new refs (e.g. on pane click/selection clear), which would
// otherwise trigger unwanted fitView and the "re-compute" feeling
function handleNodesInitialized() {
  if (!props.fitViewOnInit || getNodes.value.length === 0) return
  if (hasInitialFitDoneForDiagram.value) return
  hasInitialFitDoneForDiagram.value = true
  setTimeout(() => {
    eventBus.emit('view:fit_to_canvas_requested', { animate: true })
  }, ANIMATION.FIT_VIEWPORT_DELAY)
}

// ============================================================================
// Two-View Zoom System
// ============================================================================

/**
 * Get the width of currently open right-side panels
 */
function getRightPanelWidth(): number {
  let width = 0
  if (panelsStore.propertyPanel.isOpen) {
    width = PANEL.PROPERTY_WIDTH
  } else if (panelsStore.mindmatePanel.isOpen) {
    width = PANEL.MINDMATE_WIDTH
  }
  return width
}

/**
 * Get the width of currently open left-side panels.
 * Returns 0 for Node Palette: it uses split layout (50% each), so the diagram
 * container is already sized to the visible area.
 */
function getLeftPanelWidth(): number {
  return 0
}

/**
 * Check if any panel is currently visible
 */
function isAnyPanelOpen(): boolean {
  return panelsStore.anyPanelOpen
}

/**
 * Emit zoom_changed when viewport changes (scroll zoom, fit, etc.) for ZoomControls sync
 */
function handleViewportChange(viewport: { x: number; y: number; zoom: number }): void {
  eventBus.emit('view:zoom_changed', {
    zoom: viewport.zoom,
    zoomPercent: Math.round(viewport.zoom * 100),
  })
}

/**
 * Fit diagram to full canvas (no panel space reserved)
 * Use when no panels are open or when you want the diagram centered on full screen
 */
function fitToFullCanvas(animate = true): void {
  if (getNodes.value.length === 0) return

  isFittedForPanel.value = false

  // Use Vue Flow's fitView with extra bottom padding for ZoomControls + AIModelSelector
  fitView({
    padding: FIT_PADDING.STANDARD_WITH_BOTTOM_UI,
    duration: animate ? ANIMATION.DURATION_NORMAL : 0,
  })

  eventBus.emit('view:fit_completed', {
    mode: 'full_canvas',
    animate,
  })
}

/**
 * Fit diagram with panel space reserved
 * Calculates available canvas area excluding panel widths
 */
function fitWithPanel(animate = true): void {
  if (getNodes.value.length === 0) return

  const rightPanelWidth = getRightPanelWidth()
  const leftPanelWidth = getLeftPanelWidth()
  const totalPanelWidth = rightPanelWidth + leftPanelWidth

  if (totalPanelWidth === 0) {
    // No panels open, use full canvas fit
    fitToFullCanvas(animate)
    return
  }

  isFittedForPanel.value = true

  // Get container dimensions
  const container = canvasContainer.value
  if (!container) {
    // Fallback to standard fitView if container not available
    fitView({
      padding: FIT_PADDING.STANDARD_WITH_BOTTOM_UI,
      duration: animate ? ANIMATION.DURATION_NORMAL : 0,
    })
    return
  }

  const containerWidth = container.clientWidth
  // containerHeight reserved for future vertical panel support
  const _containerHeight = container.clientHeight

  // Calculate available canvas space (excluding panels) - used for ratio calculation
  const _availableWidth = containerWidth - totalPanelWidth

  // Calculate padding ratio based on panel width
  // More panel = more padding to shift diagram away from panel
  const basePadding = FIT_PADDING.STANDARD
  const panelPaddingRatio = totalPanelWidth / containerWidth
  const adjustedPadding = basePadding + panelPaddingRatio * 0.3

  // Use fitView with adjusted padding and extra bottom for ZoomControls + AIModelSelector
  // Top uses pixel value to clear toolbar; never overlap CanvasTopBar + CanvasToolbar
  fitView({
    padding: {
      top: `${FIT_PADDING.TOP_UI_HEIGHT_PX}px`,
      right: adjustedPadding,
      bottom: basePadding + FIT_PADDING.BOTTOM_UI_EXTRA,
      left: adjustedPadding,
    },
    duration: animate ? ANIMATION.DURATION_NORMAL : 0,
  })

  // After fitView, adjust the viewport to account for panel offset
  // This shifts the diagram left/right to center it in the available space
  const delay = animate ? ANIMATION.FIT_VIEWPORT_DELAY : ANIMATION.PANEL_DELAY
  setTimeout(() => {
    const currentViewport = getViewport()

    // Calculate horizontal offset to center in available space
    // If right panel is open, shift diagram left
    // If left panel is open, shift diagram right
    const rightOffset = rightPanelWidth / 2
    const leftOffset = leftPanelWidth / 2
    const netOffset = leftOffset - rightOffset

    setViewport(
      {
        x: currentViewport.x + netOffset,
        y: currentViewport.y,
        zoom: currentViewport.zoom,
      },
      { duration: animate ? ANIMATION.DURATION_FAST : 0 }
    )
  }, delay)

  eventBus.emit('view:fit_completed', {
    mode: 'with_panel',
    animate,
    panelWidth: totalPanelWidth,
  })
}

/**
 * Smart fit based on current panel visibility
 * Automatically chooses full canvas or panel-aware fit
 */
function fitDiagram(animate = true): void {
  if (isAnyPanelOpen()) {
    fitWithPanel(animate)
  } else {
    fitToFullCanvas(animate)
  }
}

/**
 * Fit diagram for export (no animation, minimal padding)
 */
function fitForExport(): void {
  fitView({
    padding: FIT_PADDING.EXPORT,
    duration: 0,
  })
}

// ============================================================================
// Watchers and Event Handlers
// ============================================================================

// Fit view when nodes are added/removed (not initial - that's handleNodesInitialized)
// Skip first run (oldLength undefined) - nodes-initialized handles initial fit
// Concept map: only fit on canvas entry, not when adding nodes/links (avoids fit on menu-icon link creation)
watch(
  () => nodes.value.length,
  (newLength, oldLength) => {
    if (!props.fitViewOnInit || newLength === 0) return
    if (oldLength === undefined) return
    if (diagramStore.type === 'concept_map') return
    setTimeout(() => {
      eventBus.emit('view:fit_to_canvas_requested', { animate: true })
    }, ANIMATION.FIT_DELAY)
  }
)

// Watch panel state changes and re-fit diagram
watch(
  () => panelsStore.anyPanelOpen,
  (isOpen, wasOpen) => {
    // Only re-fit if we have nodes and panel state actually changed
    if (nodes.value.length > 0 && isOpen !== wasOpen) {
      // Delay to allow panel animation to start
      setTimeout(() => fitDiagram(true), ANIMATION.PANEL_DELAY)
    }
  }
)

// Watch individual panel changes for more responsive fitting
watch(
  () => [
    panelsStore.mindmatePanel.isOpen,
    panelsStore.propertyPanel.isOpen,
    panelsStore.nodePalettePanel.isOpen,
  ],
  () => {
    // Re-fit when any panel opens/closes
    if (nodes.value.length > 0) {
      setTimeout(() => fitDiagram(true), ANIMATION.PANEL_DELAY)
    }
  }
)

// ============================================================================
// EventBus Subscriptions
// ============================================================================

// Unsubscribe functions for cleanup
const unsubscribers: (() => void)[] = []

onMounted(() => {
  // Listen for node edit requests from context menu
  unsubscribers.push(
    eventBus.on('node:edit_requested', ({ nodeId }) => {
      const node = getNodes.value.find((n) => n.id === nodeId)
      if (node) {
        emit('nodeDoubleClick', node as unknown as MindGraphNode)
      }
    })
  )

  // Listen for fit requests from other components
  unsubscribers.push(
    eventBus.on('view:fit_to_window_requested', (data) => {
      const animate = data?.animate !== false
      fitToFullCanvas(animate)
    })
  )

  unsubscribers.push(
    eventBus.on('view:fit_to_canvas_requested', (data) => {
      const animate = data?.animate !== false
      fitWithPanel(animate)
    })
  )

  unsubscribers.push(
    eventBus.on('view:fit_diagram_requested', () => {
      fitDiagram(true)
    })
  )

  unsubscribers.push(
    eventBus.on('view:fit_for_export_requested', () => {
      fitForExport()
    })
  )

  unsubscribers.push(
    eventBus.on('toolbar:export_requested', async ({ format }) => {
      const savedViewport = getViewport()
      fitForExport()
      await nextTick()
      await exportByFormat(format)
      setViewport(savedViewport, { duration: ANIMATION.DURATION_FAST })
    })
  )

  unsubscribers.push(
    eventBus.on('view:zoom_in_requested', () => {
      zoomIn()
    })
  )

  unsubscribers.push(
    eventBus.on('view:zoom_out_requested', () => {
      zoomOut()
    })
  )

  unsubscribers.push(
    eventBus.on('view:zoom_set_requested', ({ zoom }) => {
      const vp = getViewport()
      setViewport({ x: vp.x, y: vp.y, zoom }, { duration: ANIMATION.DURATION_FAST })
    })
  )

  // Listen for inline text updates from node components
  unsubscribers.push(
    eventBus.on('node:text_updated', ({ nodeId, text }) => {
      diagramStore.pushHistory('Edit node text')
      diagramStore.updateNode(nodeId, { text })
      // Concept map label agent: regenerate only edges with empty labels (when AI on)
      if (diagramStore.type === 'concept_map') {
        regenerateForNodeIfNeeded(nodeId)
      }
      // Double bubble map: rebuild spec from nodes (new text), reload layout
      // Fit is triggered by onNodesChange when nodes update
      if (diagramStore.type === 'double_bubble_map') {
        const spec = diagramStore.getDoubleBubbleSpecFromData()
        if (spec) {
          diagramStore.loadFromSpec(spec, 'double_bubble_map')
        }
      }
    })
  )

  // Listen for topic node width changes in multi-flow maps
  // When topic node becomes wider, store the width and trigger layout recalculation
  unsubscribers.push(
    eventBus.on('multi_flow_map:topic_width_changed', ({ nodeId, width }) => {
      if (diagramStore.type !== 'multi_flow_map' || nodeId !== 'event' || width === null) {
        return
      }

      // Store the topic node width in the diagram store
      // This will trigger the vueFlowNodes computed to recalculate with the new width
      diagramStore.setTopicNodeWidth(width)
    })
  )

  // Listen for node width changes in multi-flow maps
  // Store widths for visual balance calculation
  unsubscribers.push(
    eventBus.on('multi_flow_map:node_width_changed', ({ nodeId, width }) => {
      if (diagramStore.type !== 'multi_flow_map' || !nodeId || width === null) {
        return
      }

      // Store the node width for visual balance
      diagramStore.setNodeWidth(nodeId, width)
    })
  )
})

onUnmounted(() => {
  eventBus.off('concept_map:link_drop', handleConceptMapLinkDrop)
  eventBus.off('concept_map:label_cleared', handleConceptMapLabelCleared)
  // Clear context menu setup timeout if still pending
  if (contextMenuSetupTimeoutId) {
    clearTimeout(contextMenuSetupTimeoutId)
    contextMenuSetupTimeoutId = null
  }
  // Clear fit-from-nodes-change timeout
  if (fitFromNodesChangeTimeoutId) {
    clearTimeout(fitFromNodesChangeTimeoutId)
    fitFromNodesChangeTimeoutId = null
  }
  // Remove context menu listener
  if (contextMenuElement && contextMenuHandler) {
    contextMenuElement.removeEventListener('contextmenu', contextMenuHandler)
    contextMenuElement = null
    contextMenuHandler = null
  }
  // Clean up all subscriptions
  unsubscribers.forEach((unsub) => unsub())
  unsubscribers.length = 0
})

// Expose methods for parent components
defineExpose({
  fitToFullCanvas,
  fitWithPanel,
  fitDiagram,
  fitForExport,
  isFittedForPanel,
})

// ============================================================================
// Template Constants (expose config values for template use)
// ============================================================================

const zoomConfig = {
  min: ZOOM.MIN,
  max: ZOOM.MAX,
  default: ZOOM.DEFAULT,
}

const gridConfig = {
  snapSize: [...GRID.SNAP_SIZE] as [number, number],
  backgroundGap: GRID.BACKGROUND_GAP,
  backgroundDotSize: GRID.BACKGROUND_DOT_SIZE,
}
</script>

<template>
  <div
    ref="canvasContainer"
    class="diagram-canvas w-full h-full"
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
        :node-types="nodeTypes"
        :edge-types="edgeTypes"
        :default-viewport="{ x: 0, y: 0, zoom: zoomConfig.default }"
        :min-zoom="zoomConfig.min"
        :max-zoom="zoomConfig.max"
        :snap-to-grid="true"
        :snap-grid="gridConfig.snapSize"
        :nodes-draggable="!props.handToolActive"
        :nodes-connectable="false"
        :elements-selectable="!props.handToolActive"
        :pan-on-scroll="false"
        :zoom-on-scroll="true"
        :zoom-on-double-click="false"
        :pan-on-drag="props.handToolActive ? [0, 1, 2] : [1, 2]"
        :class="[
          'bg-gray-50 dark:bg-gray-900',
          diagramStore.type !== null &&
          ['circle_map', 'bubble_map', 'double_bubble_map'].includes(diagramStore.type)
            ? 'circle-map-canvas'
            : '',
          diagramStore.type === 'concept_map' ? 'concept-map-canvas' : '',
        ]"
        :style="{ backgroundColor: backgroundColor }"
        @pane-click="handlePaneClick"
        @nodes-initialized="handleNodesInitialized"
        @viewport-change="handleViewportChange"
      >
        <!-- Background pattern -->
        <Background
          v-if="showBackground"
          :gap="gridConfig.backgroundGap"
          :size="gridConfig.backgroundDotSize"
          pattern-color="#e5e7eb"
        />

        <!-- Minimap for overview -->
        <MiniMap
          v-if="showMinimap"
          position="bottom-left"
          :pannable="true"
          :zoomable="true"
        />

        <!-- Brace overlay for brace maps (draws unified curly braces) -->
        <BraceOverlay />

        <!-- Bridge overlay for bridge maps (draws vertical lines, triangles, and dimension label) -->
        <BridgeOverlay />

        <!-- Tree map overlay: alternative dimensions at bottom (like archive tree-renderer) -->
        <TreeMapOverlay />

        <!-- Learning sheet overlay: dashed line + answers below diagram (半成品图示 mode) -->
        <LearningSheetOverlay />
      </VueFlow>
    </div>

    <!-- Custom context menu -->
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
  </div>
</template>

<style>
/* Vue Flow base styles */
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/minimap/dist/style.css';

.diagram-canvas {
  position: relative;
}

.vue-flow-wrapper {
  transition: filter 0.2s ease;
}

.vue-flow-wrapper.wireframe-mode {
  filter: grayscale(1);
}

/* All diagrams: hide Vue Flow's default blue selection box, use pulse glow animation instead */
.diagram-canvas .vue-flow__nodesselection,
.diagram-canvas .vue-flow__nodesselection-rect {
  display: none !important;
}

/* Default node selection: pulse glow animation (same as circle map, concept map) */
.vue-flow__node.selected {
  box-shadow: none !important;
  animation: pulseGlow 2s ease-in-out infinite;
}

/* Circle nodes: circular wrapper so any outline follows circle shape; pulse animation when selected */
.vue-flow__node-circle {
  border-radius: 50% !important;
  overflow: visible;
}

/* ============================================
   CIRCLE NODE SELECTION ANIMATION OPTIONS
   ============================================
   Uncomment ONE of the options below to use it.
   Each option provides a different visual style for selected circle nodes.
   ============================================ */

/* OPTION 1: Pulsing Glow (Animated) - Smooth pulsing effect */
/* Creates a breathing/pulsing animation that draws attention */
@keyframes pulseGlow {
  0%,
  100% {
    filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
      drop-shadow(0 0 4px rgba(102, 126, 234, 0.4));
  }
  50% {
    filter: drop-shadow(0 0 16px rgba(102, 126, 234, 0.9))
      drop-shadow(0 0 8px rgba(102, 126, 234, 0.7));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: pulseGlow 2s ease-in-out infinite;
}

/* OPTION 2: Clean Ring Border - Minimalist approach */
/* Simple, clean ring that doesn't distract from content */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 0 3px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 0 1px rgba(102, 126, 234, 0.4));
}
*/

/* OPTION 3: Scale + Glow - Subtle size increase with glow */
/* Node slightly grows and glows when selected */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
  transform: scale(1.05);
}
*/

/* OPTION 4: Gradient Border Glow - Animated gradient ring */
/* Creates a rotating gradient effect around the border */
/*
@keyframes gradientRotate {
  0% {
    filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
      drop-shadow(0 0 4px rgba(147, 51, 234, 0.6));
  }
  50% {
    filter: drop-shadow(0 0 12px rgba(147, 51, 234, 0.8))
      drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
  }
  100% {
    filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
      drop-shadow(0 0 4px rgba(147, 51, 234, 0.6));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: gradientRotate 3s ease-in-out infinite;
}
*/

/* OPTION 5: Expanding Shadow - Growing shadow effect */
/* Shadow expands outward creating depth */
/*
@keyframes expandShadow {
  0% {
    filter: drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
  }
  100% {
    filter: drop-shadow(0 0 20px rgba(102, 126, 234, 0.9))
      drop-shadow(0 0 10px rgba(102, 126, 234, 0.7));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: expandShadow 1.5s ease-out forwards;
}
*/

/* OPTION 6: Color Shift + Glow - Subtle color change */
/* Node color shifts slightly warmer with glow */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.6))
    brightness(1.1) saturate(1.1);
}
*/

/* OPTION 7: Ripple Effect - Concentric expanding circles */
/* Creates a ripple animation effect */
/*
@keyframes ripple {
  0% {
    filter: drop-shadow(0 0 0 rgba(102, 126, 234, 0));
  }
  50% {
    filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
      drop-shadow(0 0 16px rgba(102, 126, 234, 0.3));
  }
  100% {
    filter: drop-shadow(0 0 16px rgba(102, 126, 234, 0.4))
      drop-shadow(0 0 24px rgba(102, 126, 234, 0.2));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: ripple 2s ease-out infinite;
}
*/

/* OPTION 8: Golden Accent - Warm golden glow */
/* Elegant golden/yellow accent instead of blue */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(234, 179, 8, 0.8))
    drop-shadow(0 0 4px rgba(234, 179, 8, 0.6));
}
*/

/* OPTION 9: Dual Ring - Two concentric rings */
/* Clean double-ring effect for emphasis */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 0 4px rgba(102, 126, 234, 0.3))
    drop-shadow(0 0 0 2px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 8px rgba(102, 126, 234, 0.6));
}
*/

/* OPTION 10: Subtle Pulse - Very gentle pulsing */
/* Minimal animation, less distracting */
/*
@keyframes subtlePulse {
  0%, 100% {
    filter: drop-shadow(0 0 10px rgba(102, 126, 234, 0.7));
  }
  50% {
    filter: drop-shadow(0 0 14px rgba(102, 126, 234, 0.8));
  }
}
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  animation: subtlePulse 3s ease-in-out infinite;
}
*/

/* OPTION 11: Original Blue Glow (Current) - Static blue glow */
/* The original implementation - no animation */
/*
.vue-flow__node-circle.selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.8))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.6));
}
*/

/* Smooth transitions */
.vue-flow__node {
  transition:
    box-shadow 0.2s ease,
    filter 0.2s ease,
    transform 0.2s ease;
}

/* Boundary node styling - ensure it's visible and not clipped */
.vue-flow__node-boundary {
  overflow: visible !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  z-index: -1 !important;
}

/* Ensure boundary node doesn't interfere with other nodes */
.vue-flow__node-boundary:hover {
  box-shadow: none !important;
}

/* Boundary nodes should never show selection */
.vue-flow__node-boundary.selected {
  box-shadow: none !important;
  filter: none !important;
  animation: none !important;
}

/* Multi-flow map node selection - matches circle map approach */
/* Use :has() selector to target wrapper when it contains multi-flow-map-node component */
/* This is the SAME approach as circle map - target by node type classes */
.vue-flow__node-flow.selected:has(.multi-flow-map-node),
.vue-flow__node-topic.selected:has(.multi-flow-map-node) {
  box-shadow: none !important;
  filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.4)) !important;
  animation: pulseGlow 2s ease-in-out infinite !important;
}

/* Fallback: Target by ID patterns if :has() not supported (older browsers) */
.vue-flow__node-flow[id^='cause-'].selected,
.vue-flow__node-flow[id^='effect-'].selected,
.vue-flow__node-topic[id='event'].selected {
  border: 2px solid var(--primary-color, #3b82f6);
}

/* Workshop editing indicators */
.vue-flow__node.workshop-editing {
  position: relative;
  border: 3px solid var(--editor-color, #ff6b6b) !important;
  box-shadow: 0 0 8px rgba(255, 107, 107, 0.4);
  animation: workshop-pulse 2s ease-in-out infinite;
}

.vue-flow__node.workshop-editing::before {
  content: attr(data-editor-emoji);
  position: absolute;
  top: -12px;
  right: -12px;
  width: 24px;
  height: 24px;
  background: var(--editor-color, #ff6b6b);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  z-index: 1000;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  border: 2px solid white;
}

.vue-flow__node.workshop-editing::after {
  content: attr(data-editor-username) ' ' attr(data-editor-emoji) ' editing';
  position: absolute;
  top: -40px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--editor-color, #ff6b6b);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 1000;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
}

.vue-flow__node.workshop-editing:hover::after {
  opacity: 1;
}

@keyframes workshop-pulse {
  0%,
  100% {
    box-shadow: 0 0 8px rgba(255, 107, 107, 0.4);
  }
  50% {
    box-shadow: 0 0 16px rgba(255, 107, 107, 0.6);
  }
}

/* Workshop editing indicators */
.vue-flow__node.workshop-editing {
  position: relative;
  border: 3px solid var(--editor-color, #ff6b6b) !important;
  box-shadow: 0 0 8px rgba(255, 107, 107, 0.4);
  animation: workshop-pulse 2s ease-in-out infinite;
}

.vue-flow__node.workshop-editing::before {
  content: attr(data-editor-emoji);
  position: absolute;
  top: -12px;
  right: -12px;
  width: 24px;
  height: 24px;
  background: var(--editor-color, #ff6b6b);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  z-index: 1000;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  border: 2px solid white;
}

.vue-flow__node.workshop-editing::after {
  content: attr(data-editor-username) ' ' attr(data-editor-emoji) ' editing';
  position: absolute;
  top: -40px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--editor-color, #ff6b6b);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 1000;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.2s;
}

.vue-flow__node.workshop-editing:hover::after {
  opacity: 1;
}

@keyframes workshop-pulse {
  0%,
  100% {
    box-shadow: 0 0 8px rgba(255, 107, 107, 0.4);
  }
  50% {
    box-shadow: 0 0 16px rgba(255, 107, 107, 0.6);
  }
}

.vue-flow__node-flow[id^='cause-'].selected,
.vue-flow__node-flow[id^='effect-'].selected,
.vue-flow__node-topic[id='event'].selected {
  box-shadow: none !important;
  filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.6))
    drop-shadow(0 0 4px rgba(102, 126, 234, 0.4)) !important;
  animation: pulseGlow 2s ease-in-out infinite !important;
}
</style>
