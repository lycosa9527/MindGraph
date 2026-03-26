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
import { computed, markRaw, nextTick, onMounted, onUnmounted, provide, ref, watch } from 'vue'

import { Background } from '@vue-flow/background'
import { Position, VueFlow, getBezierPath, useVueFlow } from '@vue-flow/core'
import { MiniMap } from '@vue-flow/minimap'

import { ExportToCommunityModal } from '@/components/canvas'
import {
  getDefaultDiagramName,
  useBranchMoveDrag,
  useDiagramExport,
  useDiagramSpecForSave,
  useLanguage,
} from '@/composables'
import { PALETTE_CONCEPT_DRAG_MIME } from '@/composables/nodePalette/constants'
import type { DropTarget } from '@/composables/useBranchMoveDrag'
import {
  CONCEPT_MAP_GENERATING_KEY,
  useConceptMapRelationship,
} from '@/composables/useConceptMapRelationship'
import { eventBus } from '@/composables/useEventBus'
import { useTheme } from '@/composables/useTheme'
import { DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR } from '@/config/presentationHighlighter'
import { ANIMATION, FIT_PADDING, GRID, PANEL, ZOOM } from '@/config/uiConfig'
import { useDiagramStore, useLLMResultsStore, usePanelsStore, useUIStore } from '@/stores'
import { getFlowTopicCenteredPosition } from '@/stores/specLoader/flowMap'
import type { MindGraphNode, PresentationHighlightStroke } from '@/types'
import {
  getTopicRootConceptTargetId,
  normalizeAllConceptMapTopicRootLabels,
} from '@/utils/conceptMapTopicRootEdge'

import BraceOverlay from './BraceOverlay.vue'
import BridgeOverlay from './BridgeOverlay.vue'
import ContextMenu from './ContextMenu.vue'
import LearningSheetOverlay from './LearningSheetOverlay.vue'
import PresentationHighlightOverlay from './PresentationHighlightOverlay.vue'
import TreeMapOverlay from './TreeMapOverlay.vue'
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
  /** Node ids another user is editing — disable drag for these */
  collabLockedNodeIds?: string[]
  /** Override panOnDrag button array (e.g. [0,1,2] for mobile touch) */
  panOnDragButtons?: number[] | null
  /** Presentation / fullscreen mode — enables highlighter overlay */
  presentationMode?: boolean
  /** Scales laser glow, spotlight hole, and highlighter stroke (Ctrl± in presentation) */
  presentationPointerSizeScale?: number
}

const props = withDefaults(defineProps<Props>(), {
  showBackground: true,
  showMinimap: false,
  fitViewOnInit: true,
  handToolActive: false,
  collabLockedNodeIds: () => [],
  panOnDragButtons: null,
  presentationMode: false,
  presentationPointerSizeScale: 1,
})

const presentationHighlightStrokes = defineModel<PresentationHighlightStroke[]>(
  'presentationHighlightStrokes',
  { default: () => [] },
)

const presentationTool = defineModel<'laser' | 'spotlight' | 'highlighter'>('presentationTool', {
  default: 'laser',
})

const presentationHighlighterColor = defineModel<string>('presentationHighlighterColor', {
  default: DEFAULT_PRESENTATION_HIGHLIGHTER_COLOR,
})

const presentationHighlighterActive = computed(
  () => props.presentationMode && presentationTool.value === 'highlighter',
)

/**
 * Vue Flow pan-on-drag uses mouse button indices: 0=left, 1=middle, 2=right.
 * Default [1,2] pans with middle+right; right-drag steals the gesture from context menu.
 * In presentation mode, drop right button so right-click opens the menu; pan with middle (or left+middle when hand tool is on).
 */
const effectivePanOnDrag = computed((): number[] => {
  const base =
    props.panOnDragButtons ??
    (props.handToolActive ? [0, 1, 2] : [1, 2])
  if (!props.presentationMode) {
    return base
  }
  const withoutRight = base.filter((b) => b !== 2)
  return withoutRight.length > 0 ? withoutRight : [1]
})

// Emits
const emit = defineEmits<{
  (e: 'nodeClick', node: MindGraphNode): void
  (e: 'nodeDoubleClick', node: MindGraphNode): void
  (e: 'nodeDragStop', node: MindGraphNode): void
  (e: 'selectionChange', nodes: MindGraphNode[]): void
  (e: 'paneClick'): void
  (e: 'clearPresentationHighlighter'): void
  (e: 'exitPresentation'): void
  (e: 'fitPresentationView'): void
}>()

// Stores
const diagramStore = useDiagramStore()
const llmResultsStore = useLLMResultsStore()
const panelsStore = usePanelsStore()
const uiStore = useUIStore()

// Concept map AI relationship (provide for CurvedEdge)
const {
  generateRelationship,
  generatingConnectionIds,
  regenerateForNodeIfNeeded,
  dismissAllOptions,
} = useConceptMapRelationship()
provide(CONCEPT_MAP_GENERATING_KEY, generatingConnectionIds)

// Theme for background color
const { backgroundColor } = useTheme({
  diagramType: computed(() => diagramStore.type),
})

const { currentLanguage, t } = useLanguage()

// Export composable
function getExportTitle(): string {
  const topicText = diagramStore.getTopicNodeText()
  if (topicText) return topicText
  return (
    diagramStore.effectiveTitle || getDefaultDiagramName(diagramStore.type, currentLanguage.value)
  )
}

const getExportSpec = useDiagramSpecForSave()

const { exportByFormat } = useDiagramExport({
  getContainer: () => vueFlowWrapper.value,
  getDiagramSpec: getExportSpec,
  getTitle: getExportTitle,
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

// Export to community modal
const showExportToCommunityModal = ref(false)
function getExportContainer(): HTMLElement | null {
  return vueFlowWrapper.value
}

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
  if (connId) {
    diagramStore.pushHistory('Add link')
  }
  // When AI mode is on: always generate relationship—for new links or existing ones
  if (llmResultsStore.selectedModel) {
    const idToUse = connId ?? findConnectionBetween(payload.sourceId, payload.targetId)?.id
    if (idToUse) {
      generateRelationship(idToUse, payload.sourceId, payload.targetId)
    }
  }
}

function findConnectionBetween(
  sourceId: string,
  targetId: string
): { id: string; source: string; target: string } | null {
  const connections = diagramStore.data?.connections ?? []
  const conn = connections.find(
    (c) =>
      (c.source === sourceId && c.target === targetId) ||
      (c.source === targetId && c.target === sourceId)
  )
  return conn?.id ? { id: conn.id, source: conn.source, target: conn.target } : null
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

// Branch move drag (mind map long-press to move branch)
const branchMove = useBranchMoveDrag()
provide('branchMove', branchMove)

// Computed nodes and edges from store
const storeNodes = computed(() => diagramStore.vueFlowNodes)
const storeEdges = computed(() => diagramStore.vueFlowEdges)
// Filter out dragged branch during branch move
const nodes = computed(() => {
  const hidden = branchMove.state.value.hiddenIds
  let list = storeNodes.value
  if (hidden.size > 0) {
    list = list.filter((n) => !hidden.has(n.id))
  }
  const locked = props.collabLockedNodeIds
  if (locked.length === 0) {
    return list
  }
  const lockedSet = new Set(locked)
  return list.map((n) => (lockedSet.has(n.id) ? { ...n, draggable: false } : n))
})
// For brace maps, hide individual edges since BraceOverlay draws the braces
const edges = computed(() => {
  if (diagramStore.type === 'brace_map') {
    return []
  }
  const hidden = branchMove.state.value.hiddenIds
  if (hidden.size === 0) return storeEdges.value
  return storeEdges.value.filter((e) => !hidden.has(e.source) && !hidden.has(e.target))
})

// Handle node changes (position updates, etc.)
onNodesChange((changes) => {
  const fitTriggeringTypes = ['position', 'dimensions', 'remove', 'add'] as const
  let hasFitTriggeringChange = false

  changes.forEach((change) => {
    if (change.type === 'position' && change.position) {
      // During drag, update position but don't mark as custom yet
      diagramStore.updateNodePosition(change.id, change.position, false)
      if (diagramStore.type === 'concept_map') {
        diagramStore.updateConnectionArrowheadsForNode(change.id)
      }
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

// Handle node click
onNodeClick(({ node }) => {
  diagramStore.selectNodes(node.id)
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
  if (diagramStore.type === 'concept_map') {
    diagramStore.updateConnectionArrowheadsForNode(node.id)
  }
  diagramStore.pushHistory('Move node')
  emit('nodeDragStop', node as unknown as MindGraphNode)
})

// Concept map link drag state
const CONCEPT_LINK_DATA_TYPE = 'application/mindgraph-concept-link'
const linkDragSourceId = ref<string | null>(null)
const linkDragCursor = ref<{ x: number; y: number } | null>(null)
/** When hovering over an existing node during link drag, its id; null when over empty space */
const linkDragTargetNodeId = ref<string | null>(null)

const TOPIC_NODE_WIDTH = 120
const TOPIC_NODE_HEIGHT = 50
const CONCEPT_NODE_WIDTH = 120
const CONCEPT_NODE_HEIGHT = 50

function getConceptNodeCenter(node: {
  position?: { x: number; y: number }
  data?: { nodeType?: string }
  type?: string
}): { x: number; y: number } {
  const pos = node.position ?? { x: 0, y: 0 }
  const isTopic = node.data?.nodeType === 'topic' || node.type === 'topic' || node.type === 'center'
  const w = isTopic ? TOPIC_NODE_WIDTH : CONCEPT_NODE_WIDTH
  const h = isTopic ? TOPIC_NODE_HEIGHT : CONCEPT_NODE_HEIGHT
  return { x: pos.x + w / 2, y: pos.y + h / 2 }
}

function getPositionsFromAngle(
  dx: number,
  dy: number
): {
  source: (typeof Position)[keyof typeof Position]
  target: (typeof Position)[keyof typeof Position]
} {
  const angle = Math.atan2(dy, dx)
  const deg = (angle * 180) / Math.PI
  if (deg >= -45 && deg < 45) return { source: Position.Right, target: Position.Left }
  if (deg >= 45 && deg < 135) return { source: Position.Bottom, target: Position.Top }
  if (deg >= 135 || deg < -135) return { source: Position.Left, target: Position.Right }
  return { source: Position.Top, target: Position.Bottom }
}

const PILL_HALF_WIDTH = 40
const PILL_HALF_HEIGHT = 18

function getEdgePoint(
  center: { x: number; y: number },
  targetPos: (typeof Position)[keyof typeof Position],
  halfWidth: number,
  halfHeight: number
): { x: number; y: number } {
  switch (targetPos) {
    case Position.Left:
      return { x: center.x - halfWidth, y: center.y }
    case Position.Right:
      return { x: center.x + halfWidth, y: center.y }
    case Position.Top:
      return { x: center.x, y: center.y - halfHeight }
    case Position.Bottom:
      return { x: center.x, y: center.y + halfHeight }
    default:
      return center
  }
}

const BRANCH_MOVE_NODE_WIDTH = 120
const BRANCH_MOVE_NODE_HEIGHT = 50

function getBranchMoveCircleStyle(state: {
  cursorPos: { x: number; y: number } | null
  nodeStartPos: { x: number; y: number; width: number; height: number } | null
  animationPhase: string
  branchColor: { fill: string; border: string }
}): Record<string, string> {
  if (!state.cursorPos) return { display: 'none' }
  const nodeStart = state.nodeStartPos
  const isShrinking = state.animationPhase === 'shrinking' && nodeStart
  const pos = isShrinking ? nodeStart : null
  const left = isShrinking && pos ? pos.x : state.cursorPos.x - 12
  const top = isShrinking && pos ? pos.y : state.cursorPos.y - 12
  const width = isShrinking && pos ? pos.width : 24
  const height = isShrinking && pos ? pos.height : 24
  const borderRadius = isShrinking ? '9999px' : '50%'
  return {
    position: 'absolute',
    left: left + 'px',
    top: top + 'px',
    width: width + 'px',
    height: height + 'px',
    borderRadius,
    backgroundColor: state.branchColor.fill,
    border: `2px solid ${state.branchColor.border}`,
    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
    transition:
      state.animationPhase === 'shrinking'
        ? 'left 0.28s ease-out, top 0.28s ease-out, width 0.28s ease-out, height 0.28s ease-out, border-radius 0.28s ease-out'
        : 'none',
  }
}

const DROP_PREVIEW_SCALE = 1.2

interface NodeWithDimensions {
  dimensions?: { width?: number; height?: number }
  measured?: { width?: number; height?: number }
  style?: { width?: number | string; height?: number | string }
}

function getTargetNodeDimensions(
  node: {
    id?: string
    style?: { width?: number | string; height?: number | string }
  } & NodeWithDimensions
): { width: number; height: number } {
  const defaultW =
    node.id === 'topic' || node.id === 'tree-topic' ? TOPIC_NODE_WIDTH : BRANCH_MOVE_NODE_WIDTH
  const defaultH =
    node.id === 'topic' || node.id === 'tree-topic' ? TOPIC_NODE_HEIGHT : BRANCH_MOVE_NODE_HEIGHT
  const w =
    node.dimensions?.width ??
    node.measured?.width ??
    (typeof node.style?.width === 'number' ? node.style.width : null) ??
    (typeof node.style?.width === 'string' ? parseFloat(node.style.width) || defaultW : defaultW)
  const h =
    node.dimensions?.height ??
    node.measured?.height ??
    (typeof node.style?.height === 'number' ? node.style.height : null) ??
    (typeof node.style?.height === 'string' ? parseFloat(node.style.height) || defaultH : defaultH)
  return { width: Number(w) || defaultW, height: Number(h) || defaultH }
}

function getDropTargetStyle(target: DropTarget): Record<string, string> {
  const nodes = getNodes.value
  const node = nodes.find((n) => n.id === target.nodeId) as
    | ({ position?: { x: number; y: number } } & NodeWithDimensions)
    | undefined
  if (!node?.position) return { display: 'none' }

  const { width: nodeW, height: nodeH } = getTargetNodeDimensions(node)
  const previewW = Math.round(nodeW * DROP_PREVIEW_SCALE)
  const previewH = Math.round(nodeH * DROP_PREVIEW_SCALE)
  const offsetX = (previewW - nodeW) / 2
  const offsetY = (previewH - nodeH) / 2

  return {
    position: 'absolute',
    left: node.position.x - offsetX + 'px',
    top: node.position.y - offsetY + 'px',
    width: previewW + 'px',
    height: previewH + 'px',
    border: '2px dashed #3b82f6',
    borderRadius: '9999px',
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    pointerEvents: 'none',
  }
}

function getConceptNodeEdgePoint(
  node: {
    position?: { x: number; y: number }
    data?: { nodeType?: string }
    type?: string
  },
  targetPos: (typeof Position)[keyof typeof Position]
): { x: number; y: number } {
  const center = getConceptNodeCenter(node)
  const isTopic = node.data?.nodeType === 'topic' || node.type === 'topic' || node.type === 'center'
  const halfW = (isTopic ? TOPIC_NODE_WIDTH : CONCEPT_NODE_WIDTH) / 2
  const halfH = (isTopic ? TOPIC_NODE_HEIGHT : CONCEPT_NODE_HEIGHT) / 2
  return getEdgePoint(center, targetPos, halfW, halfH)
}

const linkPreviewPath = computed(() => {
  if (!linkDragSourceId.value || !linkDragCursor.value || diagramStore.type !== 'concept_map')
    return null
  const nodes = diagramStore.data?.nodes ?? []
  const sourceNode = nodes.find((n) => n.id === linkDragSourceId.value)
  if (!sourceNode?.position) return null
  const sourceCenter = getConceptNodeCenter(sourceNode)
  const cursor = linkDragCursor.value
  const targetNodeId = linkDragTargetNodeId.value
  const targetNode = targetNodeId ? nodes.find((n) => n.id === targetNodeId) : null
  let targetAtEdge: { x: number; y: number }
  let sourcePos: (typeof Position)[keyof typeof Position]
  let targetPos: (typeof Position)[keyof typeof Position]
  if (targetNode?.position) {
    const targetCenter = getConceptNodeCenter(targetNode)
    const dx = targetCenter.x - sourceCenter.x
    const dy = targetCenter.y - sourceCenter.y
    const positions = getPositionsFromAngle(dx, dy)
    sourcePos = positions.source
    targetPos = positions.target
    targetAtEdge = getConceptNodeEdgePoint(targetNode, targetPos)
  } else {
    const dx = cursor.x - sourceCenter.x
    const dy = cursor.y - sourceCenter.y
    const positions = getPositionsFromAngle(dx, dy)
    sourcePos = positions.source
    targetPos = positions.target
    targetAtEdge = getEdgePoint(cursor, targetPos, PILL_HALF_WIDTH, PILL_HALF_HEIGHT)
  }
  const [edgePath] = getBezierPath({
    sourceX: sourceCenter.x,
    sourceY: sourceCenter.y,
    sourcePosition: sourcePos,
    targetX: targetAtEdge.x,
    targetY: targetAtEdge.y,
    targetPosition: targetPos,
    curvature: 0.25,
  })
  return edgePath
})

/** CmapTools-style: show arrow on target when link goes upward or same Y */
const linkPreviewShowArrow = computed(() => {
  if (!linkDragSourceId.value || !linkDragCursor.value || diagramStore.type !== 'concept_map')
    return false
  const nodes = diagramStore.data?.nodes ?? []
  const sourceNode = nodes.find((n) => n.id === linkDragSourceId.value)
  if (!sourceNode?.position) return false
  const sourceCenter = getConceptNodeCenter(sourceNode)
  const targetNodeId = linkDragTargetNodeId.value
  const targetNode = targetNodeId ? nodes.find((n) => n.id === targetNodeId) : null
  const targetCenter = targetNode?.position
    ? getConceptNodeCenter(targetNode)
    : linkDragCursor.value
  return targetCenter.y <= sourceCenter.y
})

function handleConceptMapDragOver(event: DragEvent) {
  if (diagramStore.type !== 'concept_map') return
  const types = event.dataTransfer?.types ?? []
  const hasLinkData = types.includes(CONCEPT_LINK_DATA_TYPE)
  const hasPaletteConcept = types.includes(PALETTE_CONCEPT_DRAG_MIME)
  if ((hasLinkData || hasPaletteConcept) && event.dataTransfer) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }
  if (hasLinkData && linkDragSourceId.value) {
    const flowPos = screenToFlowCoordinate({ x: event.clientX, y: event.clientY })
    linkDragCursor.value = { x: flowPos.x, y: flowPos.y }
    const nodeEl = (event.target as HTMLElement).closest('.vue-flow__node')
    const targetId = nodeEl?.getAttribute('data-id') ?? null
    linkDragTargetNodeId.value = targetId && targetId !== linkDragSourceId.value ? targetId : null
  }
}

function handleConceptMapDrop(event: DragEvent) {
  if (diagramStore.type !== 'concept_map') return

  const paletteData = event.dataTransfer?.getData(PALETTE_CONCEPT_DRAG_MIME)
  if (paletteData) {
    event.preventDefault()
    const target = event.target as HTMLElement
    if (target.closest('.vue-flow__node')) return
    try {
      const parsed = JSON.parse(paletteData) as {
        text: string
        relationship_label?: string
      }
      const text = parsed.text
      const rootLinkLabel = (parsed.relationship_label ?? '').trim()
      const flowPos = screenToFlowCoordinate({
        x: event.clientX,
        y: event.clientY,
      })
      diagramStore.addNode({
        id: '',
        text: text || t('diagram.defaultNewConcept'),
        type: 'branch',
        position: { x: flowPos.x - 50, y: flowPos.y - 18 },
      })
      const nodesAfter = diagramStore.data?.nodes ?? []
      const newId = nodesAfter[nodesAfter.length - 1]?.id
      const rootId = getTopicRootConceptTargetId(diagramStore.data?.connections)
      if (newId && rootId) {
        diagramStore.addConnection(rootId, newId, rootLinkLabel)
      }
      diagramStore.pushHistory(newId && rootId ? 'Add concept and link from root' : 'Add concept')
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
    text: t('diagram.defaultNewConcept'),
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
      text: t('diagram.defaultNewConcept'),
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
    dismissAllOptions()
    eventBus.emit('canvas:pane_clicked', {})
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
function handleConceptMapLinkDragStart(payload: { sourceId: string }) {
  linkDragSourceId.value = payload.sourceId
  linkDragCursor.value = null
}

function handleConceptMapLinkDragEnd() {
  linkDragSourceId.value = null
  linkDragCursor.value = null
  linkDragTargetNodeId.value = null
}

onMounted(() => {
  eventBus.on('concept_map:link_drop', handleConceptMapLinkDrop)
  eventBus.on('concept_map:label_cleared', handleConceptMapLabelCleared)
  eventBus.on('concept_map:link_drag_start', handleConceptMapLinkDragStart)
  eventBus.on('concept_map:link_drag_end', handleConceptMapLinkDragEnd)
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
    text: t('diagram.defaultNewConcept'),
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

/** Top padding for fit view - concept map adds space for menu icon above main topic node */
function getFitViewTopPx(): number {
  return diagramStore.type === 'concept_map'
    ? FIT_PADDING.TOP_UI_HEIGHT_PX + FIT_PADDING.MAIN_TOPIC_MENU_ICON_PX
    : FIT_PADDING.TOP_UI_HEIGHT_PX
}

/** Bottom padding for fit view - tree map adds space for alternative_dimensions overlay below nodes */
function getFitViewBottomPx(): number {
  if (diagramStore.type !== 'tree_map') return FIT_PADDING.BOTTOM_UI_HEIGHT_PX
  const data = diagramStore.data
  if (!data || typeof data !== 'object' || !('alternative_dimensions' in data)) {
    return FIT_PADDING.BOTTOM_UI_HEIGHT_PX
  }
  const altDims = (data as { alternative_dimensions?: unknown }).alternative_dimensions
  const hasAltDims =
    Array.isArray(altDims) && altDims.some((d) => typeof d === 'string' && d.trim())
  return hasAltDims
    ? FIT_PADDING.BOTTOM_UI_HEIGHT_PX + FIT_PADDING.TREE_MAP_ALTERNATIVE_DIMENSIONS_EXTRA_PX
    : FIT_PADDING.BOTTOM_UI_HEIGHT_PX
}

/**
 * Fit diagram to full canvas (no panel space reserved)
 * Use when no panels are open or when you want the diagram centered on full screen
 */
function fitToFullCanvas(animate = true): void {
  if (getNodes.value.length === 0) return

  isFittedForPanel.value = false

  // Use Vue Flow's fitView with extra bottom padding for ZoomControls + AIModelSelector
  // Tree map: extra bottom when alternative_dimensions overlay is shown
  fitView({
    padding: {
      ...FIT_PADDING.STANDARD_WITH_BOTTOM_UI,
      top: `${getFitViewTopPx()}px`,
      bottom: `${getFitViewBottomPx()}px`,
    },
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
      padding: {
        ...FIT_PADDING.STANDARD_WITH_BOTTOM_UI,
        top: `${getFitViewTopPx()}px`,
        bottom: `${getFitViewBottomPx()}px`,
      },
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
  // Tree map: use pixel bottom when alternative_dimensions overlay is shown
  fitView({
    padding: {
      top: `${getFitViewTopPx()}px`,
      right: adjustedPadding,
      bottom: `${getFitViewBottomPx()}px`,
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

// Debounce double bubble rebuild when multiple node:text_updated fire (e.g. diff pair)
let doubleBubbleRebuildTimer: ReturnType<typeof setTimeout> | null = null
const DOUBLE_BUBBLE_REBUILD_DEBOUNCE_MS = 16

function scheduleDoubleBubbleRebuild(): void {
  if (doubleBubbleRebuildTimer) clearTimeout(doubleBubbleRebuildTimer)
  doubleBubbleRebuildTimer = setTimeout(() => {
    doubleBubbleRebuildTimer = null
    const spec = diagramStore.getDoubleBubbleSpecFromData()
    if (spec) {
      // Same-document layout refresh: must not emit diagram:loaded (inline Tab recs, palette, etc.)
      diagramStore.loadFromSpec(spec, 'double_bubble_map', { emitLoaded: false })
    }
  }, DOUBLE_BUBBLE_REBUILD_DEBOUNCE_MS)
}

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

  // Branch move replaces nodes programmatically; Vue Flow won't emit onNodesChange.
  // Delay fit until Vue has applied the new layout so curves/positions render correctly.
  unsubscribers.push(
    eventBus.on('diagram:branch_moved', () => {
      nextTick(() => {
        setTimeout(() => {
          eventBus.emit('view:fit_to_canvas_requested', { animate: true })
        }, ANIMATION.FIT_DELAY)
      })
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
      if (format === 'community') {
        showExportToCommunityModal.value = true
        setViewport(savedViewport, { duration: ANIMATION.DURATION_FAST })
      } else {
        await exportByFormat(format)
        setViewport(savedViewport, { duration: ANIMATION.DURATION_FAST })
      }
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

  // Listen for inline text updates from node components (and from inline_recommendation:applied)
  unsubscribers.push(
    eventBus.on('node:text_updated', ({ nodeId, text }) => {
      const node = diagramStore.data?.nodes?.find((n) => n.id === nodeId)
      const currentText = (node?.text ?? (node?.data as { label?: string })?.label ?? '').trim()
      const alreadyUpdated = currentText === text.trim()
      if (!alreadyUpdated) {
        diagramStore.pushHistory('Edit node text')
        if (
          diagramStore.type === 'flow_map' &&
          nodeId === 'flow-topic' &&
          diagramStore.data?.nodes?.find((n) => n.id === 'flow-topic')?.data?.orientation ===
            'vertical'
        ) {
          const topicNode = diagramStore.data?.nodes?.find((n) => n.id === 'flow-topic')
          const currentY = (topicNode?.position as { y?: number })?.y ?? 80
          const pos = getFlowTopicCenteredPosition(text, currentY)
          diagramStore.updateNode(nodeId, { text, position: pos })
        } else {
          diagramStore.updateNode(nodeId, { text })
        }
      }
      if (
        diagramStore.type === 'concept_map' &&
        diagramStore.data?.connections &&
        diagramStore.data.nodes
      ) {
        normalizeAllConceptMapTopicRootLabels(
          diagramStore.data.connections,
          diagramStore.data.nodes
        )
      }
      // Label agent: only when this event actually changed node text. Duplicate emissions
      // (same text as store) must not trigger AI — otherwise empty edges (e.g. palette→canvas
      // root links) get relationship streams without a real edit.
      if (diagramStore.type === 'concept_map' && !alreadyUpdated) {
        regenerateForNodeIfNeeded(nodeId)
      }
      // Double bubble map: debounced rebuild (avoids 2 rebuilds when diff pair updates)
      if (diagramStore.type === 'double_bubble_map') {
        scheduleDoubleBubbleRebuild()
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
  eventBus.off('concept_map:link_drag_start', handleConceptMapLinkDragStart)
  eventBus.off('concept_map:link_drag_end', handleConceptMapLinkDragEnd)
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
  if (doubleBubbleRebuildTimer) {
    clearTimeout(doubleBubbleRebuildTimer)
    doubleBubbleRebuildTimer = null
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

// ============================================================================
// Mobile touch: custom pinch-to-zoom AND single-finger pan.
// d3-drag on nodes calls stopImmediatePropagation, blocking d3-zoom from
// seeing multi-touch. d3-zoom's internal touch pan is also unreliable on
// mobile. We handle both gestures ourselves in the capture phase so they
// fire before d3-drag / d3-zoom bubble-phase handlers.
//   - Single finger on PANE  → canvas pan  (stopPropagation blocks d3-zoom)
//   - Single finger on NODE  → ignored here (d3-drag handles node drag)
//   - Two+ fingers anywhere  → pinch-zoom  (stopPropagation blocks d3-drag)
// ============================================================================
let mobileTouchCleanup: (() => void) | null = null

function setupMobileTouchZoom(): void {
  if (!canvasContainer.value) return
  const el = canvasContainer.value as HTMLElement

  let pinchStartDist = 0
  let pinchStartZoom = 1
  let pinchStartCenterX = 0
  let pinchStartCenterY = 0
  let pinchStartVpX = 0
  let pinchStartVpY = 0
  let isPinching = false

  let isPanning = false
  let panStartX = 0
  let panStartY = 0
  let panStartVpX = 0
  let panStartVpY = 0
  let panStartZoom = 1

  function isOnNode(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false
    return !!target.closest('.vue-flow__node')
  }

  function onTouchStart(e: TouchEvent): void {
    if (e.touches.length >= 2) {
      isPanning = false
      isPinching = true
      const t0 = e.touches[0]
      const t1 = e.touches[1]
      pinchStartDist = Math.hypot(
        t1.clientX - t0.clientX,
        t1.clientY - t0.clientY,
      )
      pinchStartCenterX = (t0.clientX + t1.clientX) / 2
      pinchStartCenterY = (t0.clientY + t1.clientY) / 2
      const vp = getViewport()
      pinchStartZoom = vp.zoom
      pinchStartVpX = vp.x
      pinchStartVpY = vp.y
      e.stopPropagation()
      return
    }

    if (e.touches.length === 1 && !isOnNode(e.target)) {
      if (branchMove.state.value.active) {
        branchMove.cancelDrag()
        return
      }
      isPanning = true
      const vp = getViewport()
      panStartX = e.touches[0].clientX
      panStartY = e.touches[0].clientY
      panStartVpX = vp.x
      panStartVpY = vp.y
      panStartZoom = vp.zoom
      e.stopPropagation()
    }
  }

  function onTouchMove(e: TouchEvent): void {
    if (isPinching && e.touches.length >= 2 && pinchStartDist > 0) {
      e.preventDefault()
      e.stopPropagation()

      const t0 = e.touches[0]
      const t1 = e.touches[1]
      const curDist = Math.hypot(
        t1.clientX - t0.clientX,
        t1.clientY - t0.clientY,
      )
      const curCenterX = (t0.clientX + t1.clientX) / 2
      const curCenterY = (t0.clientY + t1.clientY) / 2

      const scale = curDist / pinchStartDist
      const newZoom = Math.max(
        ZOOM.MIN,
        Math.min(ZOOM.MAX, pinchStartZoom * scale),
      )

      const rect = el.getBoundingClientRect()
      const anchorX = pinchStartCenterX - rect.left
      const anchorY = pinchStartCenterY - rect.top
      const flowX = (anchorX - pinchStartVpX) / pinchStartZoom
      const flowY = (anchorY - pinchStartVpY) / pinchStartZoom

      const panDx = curCenterX - pinchStartCenterX
      const panDy = curCenterY - pinchStartCenterY

      const newX = anchorX - flowX * newZoom + panDx
      const newY = anchorY - flowY * newZoom + panDy

      setViewport({ x: newX, y: newY, zoom: newZoom }, { duration: 0 })
      return
    }

    if (isPanning && e.touches.length === 1) {
      e.preventDefault()
      e.stopPropagation()

      const dx = e.touches[0].clientX - panStartX
      const dy = e.touches[0].clientY - panStartY
      setViewport(
        { x: panStartVpX + dx, y: panStartVpY + dy, zoom: panStartZoom },
        { duration: 0 },
      )
    }
  }

  function onTouchEnd(e: TouchEvent): void {
    if (e.touches.length < 2) {
      isPinching = false
      pinchStartDist = 0
    }
    if (e.touches.length === 0) {
      isPanning = false
    }
  }

  el.addEventListener('touchstart', onTouchStart, { capture: true, passive: true })
  el.addEventListener('touchmove', onTouchMove, { capture: true, passive: false })
  el.addEventListener('touchend', onTouchEnd, { capture: true, passive: true })

  mobileTouchCleanup = () => {
    el.removeEventListener('touchstart', onTouchStart, { capture: true } as EventListenerOptions)
    el.removeEventListener('touchmove', onTouchMove, { capture: true } as EventListenerOptions)
    el.removeEventListener('touchend', onTouchEnd, { capture: true } as EventListenerOptions)
  }
}

onMounted(() => {
  if (props.panOnDragButtons) {
    setupMobileTouchZoom()
  }
})

onUnmounted(() => {
  mobileTouchCleanup?.()
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
        :nodes-draggable="
          !props.handToolActive &&
          !presentationHighlighterActive &&
          diagramStore.type !== 'mindmap' &&
          diagramStore.type !== 'mind_map' &&
          diagramStore.type !== 'tree_map'
        "
        :nodes-connectable="false"
        :elements-selectable="!props.handToolActive && !presentationHighlighterActive"
        :pan-on-scroll="false"
        :zoom-on-scroll="true"
        :zoom-on-double-click="false"
        :pan-on-drag="effectivePanOnDrag"
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

        <!-- Presentation mode: temporary highlighter strokes (cleared on exit) -->
        <PresentationHighlightOverlay
          v-if="props.presentationMode"
          v-model="presentationHighlightStrokes"
          :active="presentationHighlighterActive"
          :current-color="presentationHighlighterColor"
          :pointer-size-scale="props.presentationPointerSizeScale"
        />

        <!-- Concept map: link preview while dragging from icon (line + pill at 60% opacity) -->
        <!-- Branch move: shrink animation from node to circle, then follow cursor -->
        <template #zoom-pane>
          <div
            v-if="branchMove.state.value.active && branchMove.state.value.cursorPos"
            class="branch-move-overlay pointer-events-none"
            style="position: absolute; inset: 0; z-index: 10"
          >
            <div
              class="branch-move-circle"
              :style="getBranchMoveCircleStyle(branchMove.state.value)"
            />
            <div
              v-if="branchMove.state.value.dropTarget"
              class="branch-move-drop-preview"
              :style="getDropTargetStyle(branchMove.state.value.dropTarget)"
            />
          </div>
          <svg
            v-if="linkPreviewPath && linkDragCursor && diagramStore.type === 'concept_map'"
            class="concept-map-link-preview pointer-events-none"
            style="
              position: absolute;
              inset: 0;
              width: 100%;
              height: 100%;
              overflow: visible;
              z-index: 10;
            "
          >
            <defs>
              <marker
                id="concept-map-link-preview-arrow"
                markerWidth="10"
                markerHeight="10"
                refX="8"
                refY="5"
                orient="auto"
                markerUnits="userSpaceOnUse"
              >
                <path
                  d="M0,0 L0,10 L10,5 z"
                  fill="#94a3b8"
                  opacity="0.6"
                />
              </marker>
            </defs>
            <path
              :d="linkPreviewPath"
              fill="none"
              stroke="#94a3b8"
              stroke-width="2"
              opacity="0.6"
              :marker-end="
                linkPreviewShowArrow ? 'url(#concept-map-link-preview-arrow)' : undefined
              "
            />
            <!-- Pill-shaped node preview only when over empty space (not over existing node) -->
            <rect
              v-if="!linkDragTargetNodeId"
              :x="linkDragCursor.x - 40"
              :y="linkDragCursor.y - 18"
              width="80"
              height="36"
              rx="18"
              ry="18"
              class="concept-map-link-preview-pill"
              opacity="0.6"
            />
          </svg>
        </template>
      </VueFlow>
    </div>

    <!-- Custom context menu -->
    <ContextMenu
      :visible="contextMenuVisible"
      :x="contextMenuX"
      :y="contextMenuY"
      :node="contextMenuNode"
      :target="contextMenuTarget"
      :presentation-mode="props.presentationMode"
      :presentation-tool="presentationTool"
      :presentation-highlighter-color="presentationHighlighterColor"
      @close="closeContextMenu"
      @paste="handleContextMenuPaste"
      @add-concept="handleContextMenuAddConcept"
      @presentation-tool-select="(id) => (presentationTool = id)"
      @clear-presentation-highlighter="emit('clearPresentationHighlighter')"
      @exit-presentation="emit('exitPresentation')"
      @fit-presentation-view="emit('fitPresentationView')"
      @presentation-highlighter-color-select="(stroke) => (presentationHighlighterColor = stroke)"
    />

    <!-- Export to community modal -->
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

/* Concept map link preview pill (matches ConceptNode styling) */
.concept-map-link-preview-pill {
  fill: #e3f2fd;
  stroke: #4e79a7;
  stroke-width: 2;
}
.dark .concept-map-link-preview-pill {
  fill: #1f2937;
  stroke: #5a8fc7;
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
  bottom: -22px;
  left: 50%;
  transform: translateX(-50%);
  background: transparent;
  color: #6b7280;
  font-size: 11px;
  line-height: 1.2;
  white-space: nowrap;
  z-index: 1000;
  pointer-events: none;
  opacity: 1;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vue-flow__node.collab-remote-selected {
  outline: 2px dashed #f97316 !important;
  outline-offset: 2px;
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
