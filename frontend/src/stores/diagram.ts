/**
 * Diagram Store - Pinia store for diagram state management
 * Migrated from StateManager.diagram
 * Enhanced with Vue Flow integration
 *
 * Phase 3 enhancements:
 * - Custom positions tracking (_customPositions)
 * - Per-node style overrides (_node_styles)
 * - Event emission for diagram changes
 * - State-to-Event bridge for global EventBus integration
 */
import { computed, ref } from 'vue'

import { defineStore } from 'pinia'

import {
  augmentConnectionWithOptimalHandles,
  computeDefaultArrowheadForConceptMap,
  getConceptMapNodeCenter,
  splitMixedArrowHandleGroups,
} from '@/composables/diagrams/conceptMapHandles'
import {
  DEFAULT_CENTER_X,
  DEFAULT_NODE_WIDTH,
  MULTI_FLOW_MAP_TOPIC_WIDTH,
} from '@/composables/diagrams/layoutConfig'
import { eventBus } from '@/composables/useEventBus'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type {
  Connection,
  DiagramData,
  DiagramNode,
  DiagramType,
  HistoryEntry,
  MindGraphEdge,
  MindGraphEdgeType,
  MindGraphNode,
  NodeStyle,
  Position,
} from '@/types'
import {
  connectionToVueFlowEdge,
  diagramNodeToVueFlowNode,
  vueFlowNodeToDiagramNode,
} from '@/types/vueflow'

import { useConceptMapRelationshipStore } from './conceptMapRelationship'
import { useInlineRecommendationsStore } from './inlineRecommendations'
import {
  distributeBranchesClockwise,
  findBranchByNodeId,
  getDefaultTemplate,
  loadMindMapSpec,
  loadSpecForDiagramType,
  nodesAndConnectionsToMindMapSpec,
  normalizeMindMapHorizontalSymmetry,
  recalculateBraceMapLayout,
  recalculateBubbleMapLayout,
  recalculateCircleMapLayout,
  recalculateMultiFlowMapLayout,
} from './specLoader'
import { LEARNING_SHEET_PLACEHOLDER } from './specLoader/utils'

// Event types for diagram store events
export type DiagramEventType =
  | 'diagram:node_added'
  | 'diagram:node_updated'
  | 'diagram:nodes_deleted'
  | 'diagram:selection_changed'
  | 'diagram:position_changed'
  | 'diagram:style_changed'
  | 'diagram:operation_completed'
  | 'diagram:layout_reset'
  | 'diagram:orientation_changed'

export interface DiagramEvent {
  type: DiagramEventType
  payload?: unknown
  timestamp: number
}

// Event subscribers
type EventCallback = (event: DiagramEvent) => void
const eventSubscribers = new Map<DiagramEventType | '*', Set<EventCallback>>()

// Helper to emit events (both internal subscribers and global EventBus)
function emitEvent(type: DiagramEventType, payload?: unknown): void {
  const event: DiagramEvent = { type, payload, timestamp: Date.now() }

  // Notify internal subscribers (for backward compatibility)
  eventSubscribers.get(type)?.forEach((cb) => cb(event))
  eventSubscribers.get('*')?.forEach((cb) => cb(event))

  // Emit via global EventBus for cross-component communication
  // Map internal event types to EventBus event types
  switch (type) {
    case 'diagram:node_added':
      eventBus.emit('diagram:node_added', { node: payload, category: undefined })
      break
    case 'diagram:node_updated':
      eventBus.emit('diagram:node_updated', payload as { nodeId: string; updates: unknown })
      break
    case 'diagram:nodes_deleted':
      eventBus.emit('diagram:nodes_deleted', payload as { nodeIds: string[] })
      break
    case 'diagram:selection_changed':
      eventBus.emit('state:selection_changed', payload as { selectedNodes: string[] })
      eventBus.emit('interaction:selection_changed', payload as { selectedNodes: string[] })
      break
    case 'diagram:position_changed':
      eventBus.emit(
        'diagram:position_saved',
        payload as { nodeId: string; position: { x: number; y: number } }
      )
      break
    case 'diagram:operation_completed':
      eventBus.emit(
        'diagram:operation_completed',
        payload as { operation: string; details?: unknown }
      )
      break
    case 'diagram:layout_reset':
      eventBus.emit('diagram:positions_cleared', {})
      break
  }
}

// Subscribe to events
export function subscribeToDiagramEvents(
  eventType: DiagramEventType | '*',
  callback: EventCallback
): () => void {
  let subscribers = eventSubscribers.get(eventType)
  if (!subscribers) {
    subscribers = new Set()
    eventSubscribers.set(eventType, subscribers)
  }
  subscribers.add(callback)

  // Return unsubscribe function
  return () => {
    eventSubscribers.get(eventType)?.delete(callback)
  }
}

const VALID_DIAGRAM_TYPES: DiagramType[] = [
  'bubble_map',
  'bridge_map',
  'tree_map',
  'circle_map',
  'double_bubble_map',
  'flow_map',
  'brace_map',
  'multi_flow_map',
  'concept_map',
  'mindmap',
  'mind_map',
  'diagram',
]

const MAX_HISTORY_SIZE = 50

// Helper to determine edge type based on diagram type
function getEdgeTypeForDiagram(diagramType: DiagramType | null): MindGraphEdgeType {
  // Mindmaps use curved edges (same bezier style as concept map)
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    return 'curved'
  }
  if (!diagramType) return 'curved'

  const edgeTypeMap: Partial<Record<DiagramType, MindGraphEdgeType>> = {
    bubble_map: 'radial', // Center-to-center straight lines for radial layout
    double_bubble_map: 'curved', // Bezier curves like mindmap for smooth connections
    tree_map: 'step', // T/L shaped orthogonal connectors
    flow_map: 'straight',
    multi_flow_map: 'straight',
    brace_map: 'brace',
    bridge_map: 'bridge',
  }

  return edgeTypeMap[diagramType] || 'curved'
}

/** Left/right curve extent from center (for mind map branch tracking) */
export interface MindMapCurveExtents {
  left: number
  right: number
}

function getMindMapCurveExtents(nodes: DiagramNode[], centerX: number): MindMapCurveExtents {
  const leftNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-l-'))
  const rightNodes = nodes.filter((n) => n.type === 'branch' && n.id.startsWith('branch-r-'))
  const getCenterX = (n: DiagramNode) =>
    (n.position?.x ?? 0) + ((n.data?.estimatedWidth as number) || DEFAULT_NODE_WIDTH) / 2
  const left = leftNodes.length > 0 ? centerX - Math.min(...leftNodes.map(getCenterX)) : 0
  const right = rightNodes.length > 0 ? Math.max(...rightNodes.map(getCenterX)) - centerX : 0
  return { left, right }
}

// Default placeholder texts that should not be used as title
const PLACEHOLDER_TEXTS = [
  '主题',
  '中心主题',
  '根主题',
  '事件',
  'Topic',
  'Central Topic',
  'Root',
  'Event',
]

export const useDiagramStore = defineStore('diagram', () => {
  // State
  const type = ref<DiagramType | null>(null)
  const sessionId = ref<string | null>(null)
  const data = ref<DiagramData | null>(null)
  const selectedNodes = ref<string[]>([])
  const history = ref<HistoryEntry[]>([])
  const historyIndex = ref(-1)

  // Title management state
  const title = ref<string>('')
  const isUserEditedTitle = ref<boolean>(false)

  // Store topic node width for multi-flow map layout recalculation
  const topicNodeWidth = ref<number | null>(null)

  /** Original curve extents when mind map was loaded (for tracking drift) */
  const mindMapCurveExtentBaseline = ref<MindMapCurveExtents | null>(null)

  // Store node widths for multi-flow map visual balance
  // Maps nodeId -> width in pixels
  const nodeWidths = ref<Record<string, number>>({})

  // Force recalculation trigger for multi-flow map (increment to trigger reactive update)
  const multiFlowMapRecalcTrigger = ref(0)

  // Clipboard for copy/paste
  const copiedNodes = ref<DiagramNode[]>([])

  // Session edit count for teacher usage analytics (add/delete/change nodes)
  const sessionEditCount = ref(0)

  function resetSessionEditCount(): void {
    sessionEditCount.value = 0
  }

  // Getters
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)
  const nodeCount = computed(() => data.value?.nodes?.length ?? 0)
  const hasSelection = computed(() => selectedNodes.value.length > 0)
  const canPaste = computed(() => copiedNodes.value.length > 0)
  const selectedNodeData = computed(() => {
    if (!data.value?.nodes || selectedNodes.value.length === 0) return []
    return data.value.nodes.filter((node) => selectedNodes.value.includes(node.id))
  })

  const isLearningSheet = computed(() => {
    const d = data.value as { isLearningSheet?: boolean; is_learning_sheet?: boolean } | null
    return d?.isLearningSheet === true || d?.is_learning_sheet === true
  })

  const hiddenAnswers = computed(
    () => (data.value as { hiddenAnswers?: string[] } | null)?.hiddenAnswers ?? []
  )

  // Circle map layout: computed only from node data (NOT selection).
  // Prevents layout recalculation when selection changes (e.g. pane click),
  // which was causing children nodes to shift when clicking filename then canvas.
  const circleMapLayoutNodes = computed(() => {
    if (type.value !== 'circle_map' || !data.value?.nodes) return []
    return recalculateCircleMapLayout(data.value.nodes)
  })

  // Vue Flow computed properties
  const vueFlowNodes = computed<MindGraphNode[]>(() => {
    const diagramType = type.value
    if (!data.value?.nodes || !diagramType) return []

    // For circle maps, use cached layout (depends only on nodes). Apply selection
    // without re-running layout - prevents node shift on pane click / selection clear.
    if (diagramType === 'circle_map') {
      const layoutNodes = circleMapLayoutNodes.value
      return layoutNodes.map((node) => {
        const vf = diagramNodeToVueFlowNode(node, diagramType)
        vf.selected = selectedNodes.value.includes(node.id)
        vf.draggable = false
        return vf
      })
    }

    // For multi-flow maps, recalculate layout to ensure positions and IDs are correct
    // This makes the layout adaptive when nodes are added/deleted
    // Also recalculates when topic width or node widths change (via multiFlowMapRecalcTrigger)
    if (diagramType === 'multi_flow_map') {
      // Access trigger to make this computed reactive to width changes
      void multiFlowMapRecalcTrigger.value

      const recalculatedNodes = recalculateMultiFlowMapLayout(
        data.value.nodes,
        topicNodeWidth.value,
        nodeWidths.value
      )
      const causeNodes = recalculatedNodes.filter((n) => n.id.startsWith('cause-'))
      const effectNodes = recalculatedNodes.filter((n) => n.id.startsWith('effect-'))

      return recalculatedNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        // Set causeCount and effectCount for handle generation
        if (node.id === 'event' && vueFlowNode.data) {
          vueFlowNode.data.causeCount = causeNodes.length
          vueFlowNode.data.effectCount = effectNodes.length
        }
        // Apply uniform width for visual balance (causes and effects)
        if ((node.id.startsWith('cause-') || node.id.startsWith('effect-')) && node.style) {
          vueFlowNode.style = {
            ...vueFlowNode.style,
            width: node.style.width,
            minWidth: node.style.width,
          }
        }
        return vueFlowNode
      })
    }

    // For mindmaps, ensure topic has totalBranchCount for handle generation
    // (New branches must use the same quadrant handles on the topic)
    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      const connections = data.value.connections ?? []
      const firstLevelBranchCount = connections.filter((c) => c.source === 'topic').length

      return data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        if (node.id === 'topic' && vueFlowNode.data) {
          vueFlowNode.data.totalBranchCount = firstLevelBranchCount
        }
        return vueFlowNode
      })
    }

    // Bubble maps: recalculate layout (like circle map) for correct positions on every render.
    // Fixes stale positions from saved diagrams or initial render timing.
    if (diagramType === 'bubble_map') {
      const layoutNodes = recalculateBubbleMapLayout(data.value.nodes)
      return layoutNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    // Double bubble map: use stored positions (no recalc for now)
    if (diagramType === 'double_bubble_map') {
      return data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    // Flow map: disable drag for now
    if (diagramType === 'flow_map') {
      return data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    // Brace map: recalculate layout when nodes/connections change
    if (diagramType === 'brace_map') {
      const layoutNodes = recalculateBraceMapLayout(data.value.nodes, data.value.connections ?? [])
      return layoutNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    // Tree map: nodes not draggable in normal mode; only 1.5s hold triggers branch move
    if (diagramType === 'tree_map') {
      return data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        vueFlowNode.draggable = false
        return vueFlowNode
      })
    }

    // Concept map uses free-form drag; all other types use long-press swap
    const disableDrag = diagramType !== 'concept_map'
    return data.value.nodes.map((node) => {
      const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
      vueFlowNode.selected = selectedNodes.value.includes(node.id)
      if (disableDrag) vueFlowNode.draggable = false
      return vueFlowNode
    })
  })

  const vueFlowEdges = computed<MindGraphEdge[]>(() => {
    // Circle maps have NO edges (no connection lines)
    if (type.value === 'circle_map') return []

    if (!data.value?.connections) return []
    const defaultEdgeType = getEdgeTypeForDiagram(type.value)
    const diagramType = type.value
    const nodes = data.value.nodes ?? []

    const edges = data.value.connections.map((conn) => {
      const effectiveConn =
        diagramType === 'concept_map' ? augmentConnectionWithOptimalHandles(conn, nodes) : conn

      const edgeType = (effectiveConn.edgeType as MindGraphEdgeType) || defaultEdgeType
      const edge = connectionToVueFlowEdge(effectiveConn, edgeType)
      if (diagramType && edge.data) {
        edge.data = { ...edge.data, diagramType }
      }
      return edge
    })

    if (diagramType === 'concept_map' && edges.length > 0) {
      splitMixedArrowHandleGroups(edges, nodes)

      const targetGroups = new Map<string, MindGraphEdge[]>()
      for (const edge of edges) {
        const key = `${edge.target}:${edge.targetHandle ?? ''}`
        if (!targetGroups.has(key)) targetGroups.set(key, [])
        targetGroups.get(key)!.push(edge)
      }
      for (const group of targetGroups.values()) {
        const allHaveTarget = group.every(
          (e) => e.data?.arrowheadDirection === 'target' || e.data?.arrowheadDirection === 'both'
        )
        group.forEach((edge, i) => {
          if (!edge.data) return
          if (allHaveTarget) {
            edge.data = { ...edge.data, drawTargetArrowhead: i === 0 }
          } else {
            const hasTarget =
              edge.data.arrowheadDirection === 'target' ||
              edge.data.arrowheadDirection === 'both'
            edge.data = { ...edge.data, drawTargetArrowhead: hasTarget }
          }
        })
      }

      const sourceGroups = new Map<string, MindGraphEdge[]>()
      for (const edge of edges) {
        const key = `${edge.source}:${edge.sourceHandle ?? ''}`
        if (!sourceGroups.has(key)) sourceGroups.set(key, [])
        sourceGroups.get(key)!.push(edge)
      }
      for (const group of sourceGroups.values()) {
        const allHaveSource = group.every(
          (e) => e.data?.arrowheadDirection === 'source' || e.data?.arrowheadDirection === 'both'
        )
        group.forEach((edge, i) => {
          if (!edge.data) return
          if (allHaveSource) {
            edge.data = { ...edge.data, drawSourceArrowhead: i === 0 }
          } else {
            const hasSource =
              edge.data.arrowheadDirection === 'source' ||
              edge.data.arrowheadDirection === 'both'
            edge.data = { ...edge.data, drawSourceArrowhead: hasSource }
          }
        })
      }
    }

    return edges
  })

  // Actions
  function setDiagramType(newType: DiagramType): boolean {
    if (!VALID_DIAGRAM_TYPES.includes(newType)) {
      console.error(`Invalid diagram type: ${newType}`)
      return false
    }
    const oldType = type.value
    type.value = newType
    if (oldType !== newType) {
      eventBus.emit('diagram:type_changed', { diagramType: newType })
    }
    return true
  }

  function setSessionId(id: string): boolean {
    if (!id || typeof id !== 'string' || id.trim() === '') {
      console.error('Invalid session ID')
      return false
    }
    sessionId.value = id
    return true
  }

  function updateDiagram(
    updates: Partial<{ type: DiagramType; sessionId: string; data: DiagramData }>
  ): boolean {
    if (updates.type && !VALID_DIAGRAM_TYPES.includes(updates.type)) {
      console.error(`Invalid diagram type: ${updates.type}`)
      return false
    }

    if (updates.sessionId !== undefined) {
      if (typeof updates.sessionId !== 'string' || updates.sessionId.trim() === '') {
        console.error('Invalid session ID')
        return false
      }
    }

    if (updates.type) type.value = updates.type
    if (updates.sessionId) sessionId.value = updates.sessionId
    if (updates.data) data.value = updates.data

    return true
  }

  function selectNodes(nodeIds: string | string[]): boolean {
    const ids = Array.isArray(nodeIds) ? nodeIds : [nodeIds]

    if (ids.some((id) => typeof id !== 'string')) {
      console.error('Invalid node IDs - all IDs must be strings')
      return false
    }

    selectedNodes.value = ids
    emitEvent('diagram:selection_changed', { selectedNodes: ids })
    return true
  }

  function clearSelection(): void {
    selectedNodes.value = []
    emitEvent('diagram:selection_changed', { selectedNodes: [] })
  }

  function addToSelection(nodeId: string): void {
    if (!selectedNodes.value.includes(nodeId)) {
      selectedNodes.value.push(nodeId)
    }
  }

  function removeFromSelection(nodeId: string): void {
    const index = selectedNodes.value.indexOf(nodeId)
    if (index > -1) {
      selectedNodes.value.splice(index, 1)
    }
  }

  function pushHistory(action: string): void {
    if (!data.value) return

    // Remove any redo entries
    if (historyIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, historyIndex.value + 1)
    }

    // Add new entry
    const entry: HistoryEntry = {
      data: JSON.parse(JSON.stringify(data.value)),
      timestamp: Date.now(),
      action,
    }

    history.value.push(entry)

    // Limit history size
    if (history.value.length > MAX_HISTORY_SIZE) {
      history.value.shift()
    } else {
      historyIndex.value++
    }
  }

  function undo(): boolean {
    if (!canUndo.value) return false

    historyIndex.value--
    const entry = history.value[historyIndex.value]
    if (entry) {
      data.value = JSON.parse(JSON.stringify(entry.data))
      return true
    }
    return false
  }

  function redo(): boolean {
    if (!canRedo.value) return false

    historyIndex.value++
    const entry = history.value[historyIndex.value]
    if (entry) {
      data.value = JSON.parse(JSON.stringify(entry.data))
      return true
    }
    return false
  }

  function clearHistory(): void {
    history.value = []
    historyIndex.value = -1
  }

  function updateNode(nodeId: string, updates: Partial<DiagramNode>): boolean {
    if (!data.value?.nodes) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    data.value.nodes[nodeIndex] = {
      ...data.value.nodes[nodeIndex],
      ...updates,
    }

    // Sync dimension-label text to data.dimension for brace_map, tree_map, bridge_map
    if (
      nodeId === 'dimension-label' &&
      (type.value === 'brace_map' || type.value === 'tree_map' || type.value === 'bridge_map') &&
      'text' in updates
    ) {
      const d = data.value as Record<string, unknown>
      const text = updates.text ?? ''
      d.dimension = text
      if (type.value === 'bridge_map') {
        d.relating_factor = text
      }
    }

    emitEvent('diagram:node_updated', { nodeId, updates })
    return true
  }

  function emptyNodeForLearningSheet(nodeId: string): boolean {
    if (!data.value?.nodes || !isLearningSheet.value) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    const node = data.value.nodes[nodeIndex]
    const originalText = String(node.text ?? '').trim()
    if (!originalText || node.data?.hidden) return false

    const d = data.value as Record<string, unknown>
    const existingAnswers = (d.hiddenAnswers as string[] | undefined) ?? []
    d.hiddenAnswers = [...existingAnswers, originalText]

    data.value.nodes[nodeIndex] = {
      ...node,
      text: LEARNING_SHEET_PLACEHOLDER,
      data: {
        ...node.data,
        hidden: true,
        hiddenAnswer: originalText,
      },
    }

    emitEvent('diagram:node_updated', { nodeId, updates: { text: LEARNING_SHEET_PLACEHOLDER } })
    return true
  }

  function emptyNode(nodeId: string): boolean {
    if (!data.value?.nodes) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    data.value.nodes[nodeIndex] = {
      ...data.value.nodes[nodeIndex],
      text: '',
    }

    emitEvent('diagram:node_updated', { nodeId, updates: { text: '' } })
    return true
  }

  function setLearningSheetMode(enabled: boolean): void {
    if (!data.value) return
    const d = data.value as Record<string, unknown>
    d.isLearningSheet = enabled
    if (enabled && !d.hiddenAnswers) {
      d.hiddenAnswers = []
    }
  }

  /**
   * Switch to regular mode: show full node text but preserve hidden state so user can
   * toggle back to the same learning sheet later.
   */
  function restoreFromLearningSheetMode(): void {
    const dv = data.value
    if (!dv?.nodes || !isLearningSheet.value) return

    const d = dv as Record<string, unknown>

    dv.nodes.forEach((node, idx) => {
      const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      if (nodeData?.hidden === true && nodeData?.hiddenAnswer) {
        const originalText = nodeData.hiddenAnswer
        dv.nodes[idx] = {
          ...node,
          text: originalText,
          data: {
            ...node.data,
            hidden: true,
            hiddenAnswer: originalText,
          },
        }
        emitEvent('diagram:node_updated', { nodeId: node.id, updates: { text: originalText } })
      }
    })

    d.isLearningSheet = false
  }

  /**
   * Resume learning sheet view from preserved state (nodes with hiddenAnswer).
   * Used when user toggles 半成品图示 on and has a saved learning sheet from earlier.
   */
  function applyLearningSheetView(): void {
    const dv = data.value
    if (!dv?.nodes) return

    const d = dv as Record<string, unknown>

    dv.nodes.forEach((node, idx) => {
      const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      if (nodeData?.hidden === true && nodeData?.hiddenAnswer) {
        dv.nodes[idx] = {
          ...node,
          text: LEARNING_SHEET_PLACEHOLDER,
          data: {
            ...node.data,
            hidden: true,
            hiddenAnswer: nodeData.hiddenAnswer,
          },
        }
        emitEvent('diagram:node_updated', {
          nodeId: node.id,
          updates: { text: LEARNING_SHEET_PLACEHOLDER },
        })
      }
    })

    d.isLearningSheet = true
  }

  /**
   * True if diagram has preserved learning sheet state (can resume without creating new).
   */
  function hasPreservedLearningSheet(): boolean {
    if (!data.value?.nodes) return false
    return data.value.nodes.some(
      (n) => (n.data as { hidden?: boolean; hiddenAnswer?: string })?.hidden === true
    )
  }

  function addNode(node: DiagramNode): void {
    if (!data.value) {
      data.value = { type: type.value || 'mindmap', nodes: [], connections: [] }
    }

    // For multi-flow maps, determine if adding cause or effect based on node data or selection
    if (type.value === 'multi_flow_map') {
      // Check if node has category info (from voice agent or context menu)
      const category = (node as unknown as { category?: string }).category
      const isCause = category === 'causes' || node.id?.startsWith('cause-')
      const isEffect = category === 'effects' || node.id?.startsWith('effect-')

      // Determine category from selected node if not specified
      let targetCategory: 'causes' | 'effects' | null = null
      if (!category && selectedNodes.value.length > 0) {
        const selectedId = selectedNodes.value[0]
        if (selectedId.startsWith('cause-')) {
          targetCategory = 'causes'
        } else if (selectedId.startsWith('effect-')) {
          targetCategory = 'effects'
        }
      }

      // Ensure node has text
      if (!node.text) {
        if (isCause || targetCategory === 'causes') {
          node.text = 'New Cause'
        } else if (isEffect || targetCategory === 'effects') {
          node.text = 'New Effect'
        } else {
          node.text = 'New Cause' // Default
        }
      }

      // Add the node temporarily to get proper ID from recalculation
      data.value.nodes.push(node)

      // Recalculate layout to update positions and rebuild connections
      const recalculatedNodes = recalculateMultiFlowMapLayout(data.value.nodes)
      const recalculatedConnections: Connection[] = []
      const causeNodes = recalculatedNodes.filter((n) => n.id.startsWith('cause-'))
      const effectNodes = recalculatedNodes.filter((n) => n.id.startsWith('effect-'))

      causeNodes.forEach((causeNode, causeIndex) => {
        recalculatedConnections.push({
          id: `edge-cause-${causeIndex}`,
          source: causeNode.id,
          target: 'event',
          sourceHandle: 'right',
          targetHandle: `left-${causeIndex}`,
          style: { strokeColor: getMindmapBranchColor(causeIndex).border },
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-effect-${effectIndex}`,
          source: 'event',
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
          style: { strokeColor: getMindmapBranchColor(effectIndex).border },
        })
      })

      // Update nodes and connections
      data.value.nodes = recalculatedNodes
      data.value.connections = recalculatedConnections
    } else if (type.value === 'bubble_map' && node.id?.startsWith('bubble-')) {
      data.value.nodes.push(node)
      const recalculatedNodes = recalculateBubbleMapLayout(data.value.nodes)
      const bubbleNodes = recalculatedNodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
      )
      data.value.nodes = recalculatedNodes
      data.value.connections = bubbleNodes.map((_, i) => ({
        id: `edge-topic-bubble-${i}`,
        source: 'topic',
        target: `bubble-${i}`,
        style: { strokeColor: getMindmapBranchColor(i).border },
      }))
    } else if (type.value === 'concept_map') {
      // Concept map: ensure concept nodes have proper id and type
      const conceptNode: DiagramNode = {
        ...node,
        id: node.id || `concept-${Date.now()}-${data.value.nodes.length}`,
        type: node.type === 'topic' || node.type === 'center' ? node.type : 'branch',
        text: node.text || '新概念',
      }
      data.value.nodes.push(conceptNode)
      emitEvent('diagram:node_added', { node: conceptNode })
      return
    } else {
      // Standard add for other diagram types
      data.value.nodes.push(node)
    }

    emitEvent('diagram:node_added', { node })
  }

  function addConnection(sourceId: string, targetId: string, label?: string): string | null {
    if (!data.value?.nodes || !data.value.connections) return null

    const sourceExists = data.value.nodes.some((n) => n.id === sourceId)
    const targetExists = data.value.nodes.some((n) => n.id === targetId)
    if (!sourceExists || !targetExists) return null

    const duplicate = data.value.connections.some(
      (c) => c.source === sourceId && c.target === targetId
    )
    if (duplicate) return null

    const connId = `conn-${Date.now()}`
    const conn: Connection = {
      id: connId,
      source: sourceId,
      target: targetId,
      label: label || '',
    }
    if (type.value === 'concept_map') {
      const sourceNode = data.value.nodes.find((n) => n.id === sourceId)
      const targetNode = data.value.nodes.find((n) => n.id === targetId)
      if (sourceNode && targetNode) {
        const sc = getConceptMapNodeCenter(sourceNode)
        const tc = getConceptMapNodeCenter(targetNode)
        conn.arrowheadDirection = computeDefaultArrowheadForConceptMap(sc, tc)
      }
    }
    data.value.connections.push(conn)
    return connId
  }

  function updateConnectionLabel(connectionId: string, label: string): boolean {
    if (!data.value?.connections) return false

    const conn = data.value.connections.find((c) => c.id === connectionId)
    if (!conn) return false

    conn.label = label
    return true
  }

  function updateConnectionArrowheadsForNode(nodeId: string): void {
    if (type.value !== 'concept_map' || !data.value?.nodes || !data.value.connections) return
    const nodes = data.value.nodes
    const connections = data.value.connections.filter(
      (c) => c.source === nodeId || c.target === nodeId
    )
    for (const conn of connections) {
      if (conn.arrowheadLocked) continue
      const sourceNode = nodes.find((n) => n.id === conn.source)
      const targetNode = nodes.find((n) => n.id === conn.target)
      if (sourceNode && targetNode) {
        const sc = getConceptMapNodeCenter(sourceNode)
        const tc = getConceptMapNodeCenter(targetNode)
        conn.arrowheadDirection = computeDefaultArrowheadForConceptMap(sc, tc)
      }
    }
  }

  function toggleConnectionArrowhead(
    connectionId: string,
    segment: 'sourceSegment' | 'targetSegment'
  ): boolean {
    if (!data.value?.connections) return false

    const conn = data.value.connections.find((c) => c.id === connectionId)
    if (!conn) return false

    const current = conn.arrowheadDirection ?? 'none'
    const clickedSource = segment === 'sourceSegment'
    const next: 'none' | 'source' | 'target' | 'both' =
      current === 'none'
        ? clickedSource
          ? 'source'
          : 'target'
        : current === 'source'
          ? 'target'
          : current === 'target'
            ? 'both'
            : 'none'
    conn.arrowheadDirection = next
    conn.arrowheadLocked = true
    pushHistory('Toggle arrowhead')
    return true
  }

  function copySelectedNodes(): void {
    if (!data.value?.nodes || selectedNodes.value.length === 0) return
    const nodesToCopy = data.value.nodes.filter((n) => selectedNodes.value.includes(n.id))
    copiedNodes.value = nodesToCopy.map((node) => ({
      ...JSON.parse(JSON.stringify(node)),
      id: `copy-${node.id}-${Date.now()}`,
    }))
  }

  function pasteNodesAt(flowPosition: { x: number; y: number }): void {
    if (copiedNodes.value.length === 0) return
    const offset = 20
    copiedNodes.value.forEach((node, index) => {
      const newNode: DiagramNode = {
        ...JSON.parse(JSON.stringify(node)),
        id: `node-${Date.now()}-${index}`,
        position: {
          x: flowPosition.x + index * offset,
          y: flowPosition.y + index * offset,
        },
      }
      addNode(newNode)
    })
    pushHistory('粘贴节点')
  }

  function removeNode(nodeId: string): boolean {
    if (!data.value?.nodes) return false

    const index = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (index === -1) return false

    const node = data.value.nodes[index]

    // Protect topic/center nodes from deletion (matching old JS behavior)
    if (node.type === 'topic' || node.type === 'center') {
      console.warn('Main topic/center node cannot be deleted')
      return false
    }

    // For multi-flow maps, rebuild layout after deletion to re-index IDs
    if (type.value === 'multi_flow_map') {
      // Clear the deleted node's width from nodeWidths
      setNodeWidth(nodeId, null)

      // Remove the node first
      data.value.nodes.splice(index, 1)

      // Rebuild nodeWidths mapping to match new sequential IDs after re-indexing
      // Map old nodes to their widths before recalculation
      const oldCauseNodes = data.value.nodes
        .filter((n) => n.id.startsWith('cause-'))
        .sort((a, b) => {
          const aIndex = parseInt(a.id.replace('cause-', ''), 10)
          const bIndex = parseInt(b.id.replace('cause-', ''), 10)
          return aIndex - bIndex
        })
      const oldEffectNodes = data.value.nodes
        .filter((n) => n.id.startsWith('effect-'))
        .sort((a, b) => {
          const aIndex = parseInt(a.id.replace('effect-', ''), 10)
          const bIndex = parseInt(b.id.replace('effect-', ''), 10)
          return aIndex - bIndex
        })

      // Build new nodeWidths mapping with sequential IDs
      const newNodeWidths: Record<string, number> = {}
      oldCauseNodes.forEach((oldNode, newIndex) => {
        const oldWidth = nodeWidths.value[oldNode.id]
        if (oldWidth) {
          newNodeWidths[`cause-${newIndex}`] = oldWidth
        }
      })
      oldEffectNodes.forEach((oldNode, newIndex) => {
        const oldWidth = nodeWidths.value[oldNode.id]
        if (oldWidth) {
          newNodeWidths[`effect-${newIndex}`] = oldWidth
        }
      })

      // Update nodeWidths with re-indexed mapping
      nodeWidths.value = newNodeWidths

      // Recalculate layout to re-index IDs and rebuild connections
      // Pass topicNodeWidth and updated nodeWidths for proper layout
      const recalculatedNodes = recalculateMultiFlowMapLayout(
        data.value.nodes,
        topicNodeWidth.value,
        nodeWidths.value
      )
      const recalculatedConnections: Connection[] = []
      const causeNodes = recalculatedNodes.filter((n) => n.id.startsWith('cause-'))
      const effectNodes = recalculatedNodes.filter((n) => n.id.startsWith('effect-'))

      causeNodes.forEach((causeNode, causeIndex) => {
        recalculatedConnections.push({
          id: `edge-cause-${causeIndex}`,
          source: causeNode.id,
          target: 'event',
          sourceHandle: 'right',
          targetHandle: `left-${causeIndex}`,
          style: { strokeColor: getMindmapBranchColor(causeIndex).border },
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-effect-${effectIndex}`,
          source: 'event',
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
          style: { strokeColor: getMindmapBranchColor(effectIndex).border },
        })
      })

      // Update nodes and connections (all connection IDs change)
      data.value.nodes = recalculatedNodes
      data.value.connections = recalculatedConnections
      useConceptMapRelationshipStore().clearAll()

      // Trigger layout recalculation
      multiFlowMapRecalcTrigger.value++
    } else if (type.value === 'flow_map') {
      // Flow map: remove node (and substeps if step deleted), rebuild spec
      const idsToRemove = new Set<string>([nodeId])
      if (node.type === 'flow') {
        const stepMatch = nodeId.match(/flow-step-(\d+)/)
        if (stepMatch) {
          const stepIndex = stepMatch[1]
          data.value.nodes
            .filter((n) => n.id?.startsWith(`flow-substep-${stepIndex}-`))
            .forEach((n) => {
              if (n.id) idsToRemove.add(n.id)
            })
        }
      }
      data.value.nodes = data.value.nodes.filter((n) => !idsToRemove.has(n.id ?? ''))
      data.value.connections = (data.value.connections ?? []).filter(
        (c) => !idsToRemove.has(c.source) && !idsToRemove.has(c.target)
      )
      idsToRemove.forEach((id) => {
        clearCustomPosition(id)
        clearNodeStyle(id)
        removeFromSelection(id)
      })
      const spec = buildFlowMapSpecFromNodes()
      if (spec) {
        loadFromSpec(spec, 'flow_map')
      }
      emitEvent('diagram:nodes_deleted', { nodeIds: [...idsToRemove] })
      return true
    } else if (type.value === 'bubble_map' && nodeId.startsWith('bubble-')) {
      // Bubble map: remove node, re-index remaining bubbles, rebuild connections
      data.value.nodes.splice(index, 1)

      const bubbleNodes = data.value.nodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
      )
      bubbleNodes.forEach((bubbleNode, i) => {
        bubbleNode.id = `bubble-${i}`
      })
      data.value.connections = bubbleNodes.map((_, i) => ({
        id: `edge-topic-bubble-${i}`,
        source: 'topic',
        target: `bubble-${i}`,
        style: { strokeColor: getMindmapBranchColor(i).border },
      }))
      useConceptMapRelationshipStore().clearAll()
    } else {
      // Standard deletion for other diagram types
      if (data.value.connections) {
        const removedConnIds = data.value.connections
          .filter((c) => c.source === nodeId || c.target === nodeId)
          .map((c) => c.id)
          .filter((id): id is string => !!id)
        data.value.connections = data.value.connections.filter(
          (c) => c.source !== nodeId && c.target !== nodeId
        )
        const relStore = useConceptMapRelationshipStore()
        removedConnIds.forEach((id) => relStore.clearConnection(id))
      }
      data.value.nodes.splice(index, 1)
    }

    // Clean up custom positions and styles for deleted node
    clearCustomPosition(nodeId)
    clearNodeStyle(nodeId)

    // Remove from selection
    removeFromSelection(nodeId)

    emitEvent('diagram:nodes_deleted', { nodeIds: [nodeId] })
    return true
  }

  /**
   * Remove multiple bubble map attribute nodes at once.
   * Use for bulk delete to avoid re-indexing after each removal.
   */
  function removeBubbleMapNodes(nodeIds: string[]): number {
    if (type.value !== 'bubble_map' || !data.value?.nodes) return 0

    const idsToRemove = new Set(nodeIds.filter((id) => id.startsWith('bubble-')))
    if (idsToRemove.size === 0) return 0

    const deletedIds: string[] = []
    data.value.nodes = data.value.nodes.filter((n) => {
      if (idsToRemove.has(n.id)) {
        deletedIds.push(n.id)
        clearCustomPosition(n.id)
        clearNodeStyle(n.id)
        removeFromSelection(n.id)
        return false
      }
      return true
    })

    const bubbleNodes = data.value.nodes.filter(
      (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
    )
    bubbleNodes.forEach((bubbleNode, i) => {
      bubbleNode.id = `bubble-${i}`
    })
    data.value.connections = bubbleNodes.map((_, i) => ({
      id: `edge-topic-bubble-${i}`,
      source: 'topic',
      target: `bubble-${i}`,
      style: { strokeColor: getMindmapBranchColor(i).border },
    }))

    emitEvent('diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedIds.length
  }

  /**
   * Add a part node to brace map (Tab: add part under whole with 2 subparts; Enter: add subpart under selected part).
   * @param parentId - Parent node id (whole or part)
   * @param text - Part/subpart label
   * @param subpartTexts - Optional [text1, text2] for the two subparts when adding a part group
   */
  function addBraceMapPart(
    parentId: string,
    text?: string,
    subpartTexts?: [string, string]
  ): boolean {
    if (type.value !== 'brace_map' || !data.value?.nodes || !data.value?.connections) return false

    const parentNode = data.value.nodes.find((n) => n.id === parentId)
    if (!parentNode) return false

    const isAddingPart = parentId === 'topic' || parentNode.type === 'topic'
    const partText = text ?? (isAddingPart ? 'New Part' : 'New Subpart')
    const baseId = Date.now()
    const newId = `brace-part-${baseId}`

    addNode({
      id: newId,
      text: partText,
      type: 'brace',
      position: { x: 0, y: 0 },
    })
    addConnection(parentId, newId)

    if (isAddingPart) {
      const [sub1Text, sub2Text] = subpartTexts ?? ['New Subpart 1', 'New Subpart 2']
      const sub1Id = `brace-part-${baseId}-1`
      const sub2Id = `brace-part-${baseId}-2`
      addNode({
        id: sub1Id,
        text: sub1Text,
        type: 'brace',
        position: { x: 0, y: 0 },
      })
      addNode({
        id: sub2Id,
        text: sub2Text,
        type: 'brace',
        position: { x: 0, y: 0 },
      })
      addConnection(newId, sub1Id)
      addConnection(newId, sub2Id)
    }

    pushHistory('Add brace map part')
    emitEvent('diagram:node_added', { node: null })

    // Persist layout positions to diagram store to avoid overlapping and ensure correct display
    const layoutNodes = recalculateBraceMapLayout(data.value.nodes, data.value.connections ?? [])
    data.value.nodes = layoutNodes

    return true
  }

  /**
   * Remove brace map part/subpart nodes and their descendants.
   */
  function removeBraceMapNodes(nodeIds: string[]): number {
    if (type.value !== 'brace_map' || !data.value?.nodes) return 0

    const targetIds = new Set(data.value.connections?.map((c) => c.target) ?? [])
    const rootId =
      data.value.nodes.find((n) => n.type === 'topic')?.id ??
      data.value.nodes.find((n) => !targetIds.has(n.id))?.id
    if (!rootId) return 0

    const childrenMap = new Map<string, string[]>()
    data.value.connections?.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })

    function collectDescendants(id: string): Set<string> {
      const set = new Set<string>([id])
      for (const childId of childrenMap.get(id) ?? []) {
        for (const desc of collectDescendants(childId)) set.add(desc)
      }
      return set
    }

    const toRemove = new Set<string>()
    for (const id of nodeIds) {
      if (id === rootId || id === 'dimension-label') continue
      for (const desc of collectDescendants(id)) toRemove.add(desc)
    }
    if (toRemove.size === 0) return 0

    const deletedIds: string[] = []
    data.value.nodes = data.value.nodes.filter((n) => {
      if (toRemove.has(n.id)) {
        deletedIds.push(n.id)
        clearCustomPosition(n.id)
        clearNodeStyle(n.id)
        removeFromSelection(n.id)
        return false
      }
      return true
    })
    if (data.value.connections) {
      const removedConnIds = data.value.connections
        .filter((c) => toRemove.has(c.source) || toRemove.has(c.target))
        .map((c) => c.id)
        .filter((id): id is string => !!id)
      data.value.connections = data.value.connections.filter(
        (c) => !toRemove.has(c.source) && !toRemove.has(c.target)
      )
      const relStore = useConceptMapRelationshipStore()
      removedConnIds.forEach((id) => relStore.clearConnection(id))
    }

    emitEvent('diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedIds.length
  }

  /**
   * Add a new first-level branch to mindmap with 2 default children.
   * Uses smart distribution: first half → right, second half → left (clockwise).
   * E.g. 4 branches: 1,2 right; 3,4 left. 6 branches: 1,2,3 right; 6,5,4 left.
   * @param _side - Ignored; distribution is automatic for even spread
   * @param text - Branch label (default: 'New Branch')
   * @param childText - Base label for child nodes; children get "1" and "2" suffix (default: 'New Child')
   */
  function addMindMapBranch(
    _side: 'left' | 'right',
    text = 'New Branch',
    childText = 'New Child'
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const newBranch = {
      text,
      children: [{ text: `${childText} 1` }, { text: `${childText} 2` }],
    }

    const allBranches = [...spec.rightBranches, ...spec.leftBranches.slice().reverse()]
    allBranches.push(newBranch)
    const { rightBranches, leftBranches } = distributeBranchesClockwise(allBranches)

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches,
      rightBranches,
      preserveLeftRight: true,
    })

    data.value.nodes = result.nodes
    data.value.connections = result.connections
    const centerX = DEFAULT_CENTER_X
    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length after add branch', extentsAfter)
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }
    pushHistory('Add branch')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  /**
   * Add a child node under the selected branch/child in mindmap.
   * @param parentNodeId - ID of the branch or child to add under
   * @param text - Child label (default: 'New Child')
   */
  function addMindMapChild(parentNodeId: string, text = 'New Child'): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, parentNodeId)
    if (!found) return false

    const { branch } = found
    if (!branch.children) {
      branch.children = []
    }
    branch.children.push({ text })

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })

    data.value.nodes = result.nodes
    data.value.connections = result.connections
    const centerX = DEFAULT_CENTER_X
    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length after add child', extentsAfter)
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }
    pushHistory('Add child')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  /**
   * Remove mindmap nodes (and their descendants) by rebuilding spec.
   */
  function removeMindMapNodes(nodeIds: string[]): number {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return 0
    if (!data.value?.nodes || !data.value?.connections) return 0

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    const idsToRemove = new Set(nodeIds.filter((id) => id.startsWith('branch-')))

    const toRemoveWithParent: {
      nodeId: string
      parentArray: { text: string; children?: unknown[] }[]
      indexInParent: number
    }[] = []
    idsToRemove.forEach((nodeId) => {
      const found = findBranchByNodeId(spec.rightBranches, spec.leftBranches, nodeId)
      if (found) {
        toRemoveWithParent.push({
          nodeId,
          parentArray: found.parentArray,
          indexInParent: found.indexInParent,
        })
      }
    })

    const depth = (id: string) => parseInt(id.split('-')[2] ?? '0', 10)
    toRemoveWithParent.sort((a, b) => {
      const dA = depth(a.nodeId)
      const dB = depth(b.nodeId)
      if (dA !== dB) return dB - dA
      return b.indexInParent - a.indexInParent
    })
    toRemoveWithParent.forEach(({ parentArray, indexInParent }) => {
      parentArray.splice(indexInParent, 1)
    })

    const deletedCount = toRemoveWithParent.length
    if (deletedCount === 0) return 0

    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })

    data.value.nodes = result.nodes
    data.value.connections = result.connections
    const centerX = DEFAULT_CENTER_X
    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length after remove nodes', extentsAfter)
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }
    nodeIds.forEach((id) => {
      clearCustomPosition(id)
      clearNodeStyle(id)
      removeFromSelection(id)
    })
    pushHistory('Delete nodes')
    emitEvent('diagram:nodes_deleted', { nodeIds })
    return deletedCount
  }

  /**
   * Collect all node IDs in the subtree (root + descendants) for mind map.
   */
  function getMindMapDescendantIds(rootNodeId: string): Set<string> {
    const connections = data.value?.connections ?? []
    const childrenMap = new Map<string, string[]>()
    connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })
    const result = new Set<string>([rootNodeId])
    function collect(id: string): void {
      for (const childId of childrenMap.get(id) ?? []) {
        result.add(childId)
        collect(childId)
      }
    }
    collect(rootNodeId)
    return result
  }

  /**
   * Move a mind map branch to a new location (as child, sibling, or top-level).
   * Rebuilds spec and reloads; clears _customPositions, _node_styles, selectedNodes.
   */
  function moveMindMapBranch(
    branchNodeId: string,
    targetType: 'topic' | 'child' | 'sibling',
    targetId?: string,
    targetIndex?: number,
    cursorFlowX?: number
  ): boolean {
    if (type.value !== 'mindmap' && type.value !== 'mind_map') return false
    if (!data.value?.nodes || !data.value?.connections) return false

    console.log('[BranchMove] start', { branchNodeId, targetType, targetId })

    const centerX = DEFAULT_CENTER_X
    const extentsBefore = getMindMapCurveExtents(data.value.nodes, centerX)
    console.log('[BranchMove] curve length before', extentsBefore)

    if (mindMapCurveExtentBaseline.value == null) {
      mindMapCurveExtentBaseline.value = { ...extentsBefore }
      console.log(
        '[BranchMove] baseline captured (first move fallback)',
        mindMapCurveExtentBaseline.value
      )
    }

    const spec = nodesAndConnectionsToMindMapSpec(data.value.nodes, data.value.connections)
    console.log('[BranchMove] spec from nodes', {
      leftCount: spec.leftBranches.length,
      rightCount: spec.rightBranches.length,
      left: spec.leftBranches.map((b) => ({ text: b.text, childCount: b.children?.length ?? 0 })),
      right: spec.rightBranches.map((b) => ({ text: b.text, childCount: b.children?.length ?? 0 })),
    })
    const sourceFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, branchNodeId)
    if (!sourceFound) return false

    const { branch, parentArray, indexInParent } = sourceFound
    const descendantIds = getMindMapDescendantIds(branchNodeId)

    if (targetType === 'child' && targetId) {
      if (descendantIds.has(targetId)) return false
    }

    if (targetType === 'topic') {
      parentArray.splice(indexInParent, 1)
      const useLeft = cursorFlowX !== undefined && cursorFlowX < DEFAULT_CENTER_X
      if (useLeft) {
        spec.leftBranches.push(branch)
      } else {
        spec.rightBranches.push(branch)
      }
    } else if (targetType === 'child' && targetId) {
      const targetFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, targetId)
      if (!targetFound) return false
      parentArray.splice(indexInParent, 1)
      if (!targetFound.branch.children) targetFound.branch.children = []
      targetFound.branch.children.push(branch)
    } else if (targetType === 'sibling' && targetId !== undefined) {
      const targetFound = findBranchByNodeId(spec.rightBranches, spec.leftBranches, targetId)
      if (!targetFound) return false
      if (descendantIds.has(targetId)) return false

      const targetBranch = targetFound.branch
      const targetParentArray = targetFound.parentArray
      const targetIdx = targetFound.indexInParent

      const isSameParent = parentArray === targetParentArray

      if (isSameParent) {
        const [removed] = parentArray.splice(indexInParent, 1)
        const adjustedTargetIdx = indexInParent < targetIdx ? targetIdx - 1 : targetIdx
        const [removedTarget] = parentArray.splice(adjustedTargetIdx, 1)
        if (indexInParent < targetIdx) {
          parentArray.splice(indexInParent, 0, removedTarget)
          parentArray.splice(targetIdx, 0, removed)
        } else {
          parentArray.splice(targetIdx, 0, removed)
          parentArray.splice(indexInParent, 0, removedTarget)
        }
      } else {
        parentArray.splice(indexInParent, 1)
        targetParentArray.splice(targetIdx, 1)
        parentArray.splice(indexInParent, 0, targetBranch)
        targetParentArray.splice(targetIdx, 0, branch)
      }
    } else {
      return false
    }

    const sourceParent =
      parentArray === spec.leftBranches
        ? 'left-top'
        : parentArray === spec.rightBranches
          ? 'right-top'
          : 'child'
    const targetLabel =
      targetType === 'topic'
        ? `topic (${cursorFlowX !== undefined && cursorFlowX < DEFAULT_CENTER_X ? 'left' : 'right'})`
        : targetType === 'child'
          ? `child of ${targetId}`
          : `sibling of ${targetId}`
    console.log('[BranchMove] node moved', {
      branchNodeId,
      from: sourceParent,
      to: targetLabel,
    })

    console.log('[BranchMove] spec after move', {
      left: spec.leftBranches.map((b) => ({ text: b.text, childCount: b.children?.length ?? 0 })),
      right: spec.rightBranches.map((b) => ({ text: b.text, childCount: b.children?.length ?? 0 })),
    })
    const result = loadMindMapSpec({
      topic: spec.topic,
      leftBranches: spec.leftBranches,
      rightBranches: spec.rightBranches,
      preserveLeftRight: true,
    })

    const extentsAfter = getMindMapCurveExtents(result.nodes, centerX)
    console.log('[BranchMove] curve length after', extentsAfter)
    const baseline = mindMapCurveExtentBaseline.value
    console.log('[BranchMove] curve length change vs previous', {
      leftDelta: extentsAfter.left - extentsBefore.left,
      rightDelta: extentsAfter.right - extentsBefore.right,
    })
    if (baseline) {
      console.log('[BranchMove] curve length change vs original', {
        leftDelta: extentsAfter.left - baseline.left,
        rightDelta: extentsAfter.right - baseline.right,
      })
    }

    const branchPositions = result.nodes
      .filter((n): n is DiagramNode & { position: Position } =>
        Boolean(n.type === 'branch' && n.position)
      )
      .map((n) => ({ id: n.id, x: n.position.x, y: n.position.y }))
    console.log('[BranchMove] result positions', { branchPositions })

    // Replace data entirely (like loadFromSpec) so Vue Flow fully re-renders.
    // Mutation alone can leave Vue Flow with stale internal state.
    const current = data.value as Record<string, unknown>
    const { _layout, _customPositions, _node_styles, ...rest } = current
    data.value = {
      ...rest,
      type: type.value,
      nodes: result.nodes,
      connections: result.connections,
      _customPositions: {},
      _node_styles: {},
    } as DiagramData
    selectedNodes.value = []
    pushHistory('Move branch')
    emitEvent('diagram:operation_completed', { operation: 'move_branch' })
    eventBus.emit('diagram:loaded', { diagramType: type.value || 'mindmap' })
    // Programmatic node replace doesn't trigger onNodesChange; DiagramCanvas will fit after layout settles
    eventBus.emit('diagram:branch_moved', {})

    const targetDescendantIds =
      (targetType === 'sibling' && targetId) || (targetType === 'child' && targetId)
        ? getMindMapDescendantIds(targetId)
        : new Set<string>()
    ;[...descendantIds, ...targetDescendantIds].forEach((id) => {
      useInlineRecommendationsStore().invalidateForNode(id)
    })

    return true
  }

  function reset(): void {
    type.value = null
    sessionId.value = null
    data.value = null
    selectedNodes.value = []
    history.value = []
    historyIndex.value = -1
    mindMapCurveExtentBaseline.value = null
    useConceptMapRelationshipStore().clearAll()
    // Reset title state
    title.value = ''
    isUserEditedTitle.value = false
  }

  // ===== Custom Positions Tracking (Phase 3) =====

  /**
   * Save a custom position for a node (distinct from auto-layout)
   * Called when user manually drags a node
   */
  function saveCustomPosition(nodeId: string, x: number, y: number): void {
    if (!data.value) return

    // Initialize _customPositions if not exists
    if (!data.value._customPositions) {
      data.value._customPositions = {}
    }

    data.value._customPositions[nodeId] = { x, y }
    emitEvent('diagram:position_changed', { nodeId, position: { x, y }, isCustom: true })
  }

  /**
   * Check if a node has a custom (user-dragged) position
   */
  function hasCustomPosition(nodeId: string): boolean {
    return !!data.value?._customPositions?.[nodeId]
  }

  /**
   * Get the custom position for a node, if any
   */
  function getCustomPosition(nodeId: string): Position | undefined {
    return data.value?._customPositions?.[nodeId]
  }

  /**
   * Clear custom position for a specific node (reverts to auto-layout)
   */
  function clearCustomPosition(nodeId: string): void {
    if (data.value?._customPositions?.[nodeId]) {
      delete data.value._customPositions[nodeId]
    }
  }

  /**
   * Clear all custom positions (reset to auto-layout)
   */
  function resetToAutoLayout(): void {
    if (data.value) {
      data.value._customPositions = {}
      emitEvent('diagram:layout_reset', { type: type.value })
    }
  }

  // ===== Node Styles Management (Phase 3) =====

  /**
   * Save a custom style override for a specific node
   */
  function saveNodeStyle(nodeId: string, style: Partial<NodeStyle>): void {
    if (!data.value) return

    // Initialize _node_styles if not exists
    if (!data.value._node_styles) {
      data.value._node_styles = {}
    }

    // Merge with existing style
    data.value._node_styles[nodeId] = {
      ...(data.value._node_styles[nodeId] || {}),
      ...style,
    }

    emitEvent('diagram:style_changed', { nodeId, style: data.value._node_styles[nodeId] })
  }

  /**
   * Get the custom style for a node, if any
   */
  function getNodeStyle(nodeId: string): NodeStyle | undefined {
    return data.value?._node_styles?.[nodeId]
  }

  /**
   * Clear custom style for a specific node (reverts to theme defaults)
   */
  function clearNodeStyle(nodeId: string): void {
    if (data.value?._node_styles?.[nodeId]) {
      delete data.value._node_styles[nodeId]
      emitEvent('diagram:style_changed', { nodeId, style: null })
    }
  }

  /**
   * Clear all custom node styles (reset to theme defaults)
   */
  function clearAllNodeStyles(): void {
    if (data.value) {
      data.value._node_styles = {}
      emitEvent('diagram:style_changed', { all: true })
    }
  }

  /**
   * Apply a style preset to all nodes.
   * Topic/center nodes get accent colors; others get context colors.
   * Skips boundary nodes. Merges with existing node styles.
   */
  function applyStylePreset(preset: {
    backgroundColor: string
    textColor: string
    borderColor: string
    topicBackgroundColor: string
    topicTextColor: string
    topicBorderColor: string
  }): void {
    const nodes = data.value?.nodes
    if (!nodes) return

    const isTopic = (node: DiagramNode) => node.type === 'topic' || node.type === 'center'

    nodes.forEach((node) => {
      if (node.type === 'boundary') return

      const useTopic = isTopic(node)
      const mergedStyle: Partial<NodeStyle> = {
        ...(node.style || {}),
        backgroundColor: useTopic ? preset.topicBackgroundColor : preset.backgroundColor,
        textColor: useTopic ? preset.topicTextColor : preset.textColor,
        borderColor: useTopic ? preset.topicBorderColor : preset.borderColor,
      }
      const nodeIndex = nodes.findIndex((n) => n.id === node.id)
      if (nodeIndex !== -1) {
        const current = nodes[nodeIndex]
        nodes[nodeIndex] = {
          ...current,
          style: mergedStyle,
        }
      }
    })
    pushHistory('Apply style preset')
    emitEvent('diagram:style_changed', { preset: true })
  }

  // ===== Vue Flow integration actions =====

  /**
   * Update node position - also tracks as custom position when dragged
   */
  function updateNodePosition(
    nodeId: string,
    position: { x: number; y: number },
    isUserDrag: boolean = false
  ): boolean {
    if (!data.value?.nodes) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    data.value.nodes[nodeIndex] = {
      ...data.value.nodes[nodeIndex],
      position: { x: position.x, y: position.y },
    }

    // Track as custom position if user dragged
    if (isUserDrag) {
      saveCustomPosition(nodeId, position.x, position.y)
    }

    return true
  }

  function updateNodesFromVueFlow(vfNodes: MindGraphNode[]): void {
    const diagramData = data.value
    if (!diagramData) return

    vfNodes.forEach((vfNode) => {
      const nodeIndex = diagramData.nodes.findIndex((n) => n.id === vfNode.id)
      if (nodeIndex !== -1 && vfNode.data) {
        diagramData.nodes[nodeIndex] = {
          ...diagramData.nodes[nodeIndex],
          position: { x: vfNode.position.x, y: vfNode.position.y },
          text: vfNode.data.label,
        }
      }
    })
  }

  function syncFromVueFlow(nodes: MindGraphNode[], edges: MindGraphEdge[]): void {
    if (!data.value) {
      data.value = { type: type.value || 'mindmap', nodes: [], connections: [] }
    }

    // Update nodes
    data.value.nodes = nodes.map((vfNode) => vueFlowNodeToDiagramNode(vfNode))

    // Update connections (preserve arrowheadSegments for concept maps)
    data.value.connections = edges.map((edge) => {
      const existing = data.value?.connections?.find((c) => c.id === edge.id)
      const conn: Connection = {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.data?.label,
        style: edge.data?.style,
        sourceHandle: edge.sourceHandle ?? undefined,
        targetHandle: edge.targetHandle ?? undefined,
        sourcePosition: edge.sourcePosition,
        targetPosition: edge.targetPosition,
        arrowheadDirection: ((): Connection['arrowheadDirection'] => {
          const d = edge.data?.arrowheadDirection ?? existing?.arrowheadDirection
          return d === 'source' || d === 'target' || d === 'both' ? d : undefined
        })(),
      }
      return conn
    })
  }

  /**
   * Load diagram from API spec response
   * Converts API spec format to DiagramData format
   * Uses specLoader for diagram-type-specific conversion
   */
  function loadFromSpec(spec: Record<string, unknown>, diagramTypeValue: DiagramType): boolean {
    if (!spec || !diagramTypeValue) return false

    resetSessionEditCount()
    useConceptMapRelationshipStore().clearAll()

    // Set diagram type
    if (!setDiagramType(diagramTypeValue)) return false

    // Use spec loader for diagram-type-specific conversion
    const result = loadSpecForDiagramType(spec, diagramTypeValue)

    // Always recalculate bubble map positions on load (default template and saved).
    // Ensures stored positions match our layout logic; fixes wrong initial positions.
    let nodesToStore = result.nodes
    if (diagramTypeValue === 'bubble_map' && result.nodes.length > 0) {
      nodesToStore = recalculateBubbleMapLayout(result.nodes)
    }

    // Mindmap: normalize horizontal symmetry so left/right curves have equal length
    if (
      (diagramTypeValue === 'mindmap' || diagramTypeValue === 'mind_map') &&
      nodesToStore.length > 0
    ) {
      const topicNode = nodesToStore.find(
        (n) => n.id === 'topic' && (n.type === 'topic' || n.type === 'center')
      )
      const centerX =
        topicNode?.position != null
          ? topicNode.position.x + DEFAULT_NODE_WIDTH / 2
          : DEFAULT_CENTER_X
      normalizeMindMapHorizontalSymmetry(nodesToStore, centerX)
      mindMapCurveExtentBaseline.value = getMindMapCurveExtents(nodesToStore, centerX)
      console.log('[BranchMove] baseline captured (load)', mindMapCurveExtentBaseline.value)
    } else {
      mindMapCurveExtentBaseline.value = null
    }

    // Initialize multi-flow map topic width if needed
    if (diagramTypeValue === 'multi_flow_map') {
      topicNodeWidth.value = MULTI_FLOW_MAP_TOPIC_WIDTH
    }

    // Create diagram data
    data.value = {
      type: diagramTypeValue,
      nodes: nodesToStore,
      connections: result.connections,
      // Preserve spec metadata (for custom positions, styles, etc.)
      ...Object.fromEntries(
        Object.entries(spec).filter(
          ([key]) =>
            ![
              'nodes',
              'connections',
              'topic',
              'context',
              'attributes',
              'root',
              'whole',
              'steps',
              'pairs',
              'concepts',
              'event',
              'causes',
              'effects',
              'left',
              'right',
              'similarities',
              'leftDifferences',
              'rightDifferences',
              'leftBranches',
              'rightBranches',
              'analogies', // Bridge map analogies are converted to nodes, don't preserve array
            ].includes(key)
        )
      ),
      // Include layout metadata if available
      ...(result.metadata || {}),
    }

    eventBus.emit('diagram:loaded', { diagramType: diagramTypeValue })
    return true
  }

  /**
   * Build double-bubble-map type-specific spec from current nodes.
   * Used for add-node flow and text_updated reload/fit.
   */
  function getDoubleBubbleSpecFromData(): Record<string, unknown> | null {
    if (type.value !== 'double_bubble_map' || !data.value?.nodes?.length) return null
    const nodes = data.value.nodes
    let left = ''
    let right = ''
    const leftNode = nodes.find((n) => n.id === 'left-topic')
    const rightNode = nodes.find((n) => n.id === 'right-topic')
    if (leftNode) left = String(leftNode.text ?? '').trim()
    if (rightNode) right = String(rightNode.text ?? '').trim()
    const simIndices = [
      ...new Set(
        nodes
          .filter((n) => /^similarity-\d+$/.test(n.id))
          .map((n) => parseInt(n.id.replace('similarity-', ''), 10))
      ),
    ].sort((a, b) => a - b)
    const leftDiffIndices = [
      ...new Set(
        nodes
          .filter((n) => /^left-diff-\d+$/.test(n.id))
          .map((n) => parseInt(n.id.replace('left-diff-', ''), 10))
      ),
    ].sort((a, b) => a - b)
    const rightDiffIndices = [
      ...new Set(
        nodes
          .filter((n) => /^right-diff-\d+$/.test(n.id))
          .map((n) => parseInt(n.id.replace('right-diff-', ''), 10))
      ),
    ].sort((a, b) => a - b)
    const similarities = simIndices.map((i) =>
      String(nodes.find((n) => n.id === `similarity-${i}`)?.text ?? '').trim()
    )
    const leftDifferences = leftDiffIndices.map((i) =>
      String(nodes.find((n) => n.id === `left-diff-${i}`)?.text ?? '').trim()
    )
    const rightDifferences = rightDiffIndices.map((i) =>
      String(nodes.find((n) => n.id === `right-diff-${i}`)?.text ?? '').trim()
    )
    // Radii (style.size/2) for loader empty-node fallback
    const getRadius = (n: { style?: { size?: number; width?: number; height?: number } }) => {
      const s = n.style?.size
      if (s != null && s > 0) return s / 2
      const w = n.style?.width
      const h = n.style?.height
      if (w != null && h != null) return Math.min(w, h) / 2
      return undefined
    }
    const _doubleBubbleMapNodeSizes: Record<string, unknown> = {}
    if (leftNode) {
      const r = getRadius(leftNode)
      if (r != null) _doubleBubbleMapNodeSizes['leftTopicR'] = r
    }
    if (rightNode) {
      const r = getRadius(rightNode)
      if (r != null) _doubleBubbleMapNodeSizes['rightTopicR'] = r
    }
    const simRadii = simIndices.map((i) => {
      const nd = nodes.find((n) => n.id === `similarity-${i}`)
      return nd != null ? getRadius(nd) : undefined
    })
    if (simRadii.some((r) => r != null)) _doubleBubbleMapNodeSizes['simRadii'] = simRadii
    const leftDiffRadii = leftDiffIndices.map((i) => {
      const nd = nodes.find((n) => n.id === `left-diff-${i}`)
      return nd != null ? getRadius(nd) : undefined
    })
    if (leftDiffRadii.some((r) => r != null))
      _doubleBubbleMapNodeSizes['leftDiffRadii'] = leftDiffRadii
    const rightDiffRadii = rightDiffIndices.map((i) => {
      const nd = nodes.find((n) => n.id === `right-diff-${i}`)
      return nd != null ? getRadius(nd) : undefined
    })
    if (rightDiffRadii.some((r) => r != null))
      _doubleBubbleMapNodeSizes['rightDiffRadii'] = rightDiffRadii

    return {
      left,
      right,
      similarities,
      leftDifferences,
      rightDifferences,
      ...(Object.keys(_doubleBubbleMapNodeSizes).length > 0 ? { _doubleBubbleMapNodeSizes } : {}),
    }
  }

  /**
   * Add node(s) to a double bubble map group.
   * Similarity: adds one node (connects both topics).
   * Difference: adds a PAIR - one left-diff (topic A) and one right-diff (topic B).
   */
  function addDoubleBubbleMapNode(
    group: 'similarity' | 'leftDiff' | 'rightDiff',
    defaultText: string,
    pairText?: string
  ): boolean {
    const spec = getDoubleBubbleSpecFromData()
    if (!spec) return false

    const similarities = (spec.similarities as string[]) || []
    const leftDifferences = (spec.leftDifferences as string[]) || []
    const rightDifferences = (spec.rightDifferences as string[]) || []

    if (group === 'similarity') {
      spec.similarities = [...similarities, defaultText]
    } else {
      spec.leftDifferences = [...leftDifferences, defaultText]
      spec.rightDifferences = [...rightDifferences, pairText ?? defaultText]
    }

    return loadFromSpec(spec, 'double_bubble_map')
  }

  /**
   * Remove similarity/difference nodes from double bubble map.
   * Protects topic nodes. Rebuilds spec and reloads layout.
   */
  function removeDoubleBubbleMapNodes(nodeIds: string[]): number {
    const spec = getDoubleBubbleSpecFromData()
    if (!spec) return 0

    const simIndices = new Set(
      nodeIds
        .filter((id) => /^similarity-\d+$/.test(id))
        .map((id) => parseInt(id.replace('similarity-', ''), 10))
    )
    const leftDiffIndices = new Set(
      nodeIds
        .filter((id) => /^left-diff-\d+$/.test(id))
        .map((id) => parseInt(id.replace('left-diff-', ''), 10))
    )
    const rightDiffIndices = new Set(
      nodeIds
        .filter((id) => /^right-diff-\d+$/.test(id))
        .map((id) => parseInt(id.replace('right-diff-', ''), 10))
    )

    const similarities = ((spec.similarities as string[]) || []).filter(
      (_, i) => !simIndices.has(i)
    )
    const leftDifferences = ((spec.leftDifferences as string[]) || []).filter(
      (_, i) => !leftDiffIndices.has(i)
    )
    const rightDifferences = ((spec.rightDifferences as string[]) || []).filter(
      (_, i) => !rightDiffIndices.has(i)
    )

    spec.similarities = similarities
    spec.leftDifferences = leftDifferences
    spec.rightDifferences = rightDifferences

    loadFromSpec(spec, 'double_bubble_map')
    return simIndices.size + leftDiffIndices.size + rightDiffIndices.size
  }

  /**
   * Get diagram spec for saving (library, export).
   * For bubble_map, recalculates positions so saved spec has correct layout.
   */
  function getSpecForSave(): Record<string, unknown> | null {
    if (!data.value) return null
    let nodes = data.value.nodes
    if (type.value === 'bubble_map' && nodes.length > 0) {
      nodes = recalculateBubbleMapLayout(nodes)
    }
    const spec: Record<string, unknown> = {
      type: type.value,
      nodes,
      connections: data.value.connections,
      _customPositions: data.value._customPositions,
      _node_styles: data.value._node_styles,
    }
    // Flow map: persist orientation so it's restored when reopening
    if (type.value === 'flow_map') {
      const orientation = (data.value as Record<string, unknown>).orientation ?? 'horizontal'
      spec.orientation = orientation
    }
    const hiddenAnswers = (data.value as { hiddenAnswers?: string[] }).hiddenAnswers
    const d = data.value as { isLearningSheet?: boolean; is_learning_sheet?: boolean }
    const isLS = d?.isLearningSheet === true || d?.is_learning_sheet === true
    if (isLS) spec.is_learning_sheet = true
    if (hiddenAnswers?.length) spec.hiddenAnswers = hiddenAnswers
    return spec
  }

  /**
   * Toggle flow map orientation between vertical and horizontal
   * Re-runs the spec loader to recalculate positions
   */
  function toggleFlowMapOrientation(): void {
    if (!data.value || type.value !== 'flow_map') return

    // Toggle orientation
    const currentOrientation = (data.value as Record<string, unknown>).orientation as
      | 'horizontal'
      | 'vertical'
      | undefined
    const newOrientation = currentOrientation === 'horizontal' ? 'vertical' : 'horizontal'

    // Build spec from current data to reload with new orientation
    // Extract title from flow-topic node, steps and substeps from current nodes
    const topicNode = data.value.nodes.find((n) => n.id === 'flow-topic')
    const title = topicNode?.text ?? (data.value as Record<string, unknown>).title ?? ''
    const stepNodes = data.value.nodes.filter((n) => n.type === 'flow')
    const substepNodes = data.value.nodes.filter((n) => n.type === 'flowSubstep')

    // Build steps array
    const steps = stepNodes.map((node) => node.text)

    // Build substeps mapping
    const stepToSubsteps: Record<string, string[]> = {}
    substepNodes.forEach((node) => {
      // Parse stepIndex from substep id: flow-substep-{stepIndex}-{substepIndex}
      const match = node.id.match(/flow-substep-(\d+)-/)
      if (match) {
        const stepIndex = parseInt(match[1], 10)
        if (stepIndex < stepNodes.length) {
          const stepText = stepNodes[stepIndex].text
          if (!stepToSubsteps[stepText]) {
            stepToSubsteps[stepText] = []
          }
          stepToSubsteps[stepText].push(node.text)
        }
      }
    })

    // Build substeps array
    const substeps = Object.entries(stepToSubsteps).map(([step, subs]) => ({
      step,
      substeps: subs,
    }))

    // Reload with new orientation
    const newSpec = {
      title,
      steps,
      substeps,
      orientation: newOrientation,
    }

    loadFromSpec(newSpec, 'flow_map')
    pushHistory(`Toggle orientation to ${newOrientation}`)
    emitEvent('diagram:orientation_changed', { orientation: newOrientation })
  }

  /**
   * Build flow map spec from current nodes (steps and substeps).
   */
  function buildFlowMapSpecFromNodes(): Record<string, unknown> | null {
    if (!data.value || type.value !== 'flow_map') return null
    const topicNode = data.value.nodes.find((n) => n.id === 'flow-topic')
    const title = topicNode?.text ?? (data.value as Record<string, unknown>).title ?? ''
    const stepNodes = data.value.nodes.filter((n) => n.type === 'flow')
    const substepNodes = data.value.nodes.filter((n) => n.type === 'flowSubstep')
    const steps = stepNodes.map((node) => node.text)
    const stepToSubsteps: Record<string, string[]> = {}
    substepNodes.forEach((node) => {
      const match = node.id.match(/flow-substep-(\d+)-/)
      if (match) {
        const stepIndex = parseInt(match[1], 10)
        if (stepIndex < stepNodes.length) {
          const stepText = stepNodes[stepIndex].text
          if (!stepToSubsteps[stepText]) {
            stepToSubsteps[stepText] = []
          }
          stepToSubsteps[stepText].push(node.text)
        }
      }
    })
    const substeps = Object.entries(stepToSubsteps).map(([step, subs]) => ({
      step,
      substeps: subs,
    }))
    const orientation = (data.value as Record<string, unknown>).orientation ?? 'horizontal'
    return { title, steps, substeps, orientation }
  }

  /**
   * Add a new step to flow map.
   * @param text - Step label
   * @param defaultSubsteps - Optional 2 default substep labels (e.g. ['子步骤1', '子步骤2'])
   */
  function addFlowMapStep(text: string, defaultSubsteps?: [string, string]): boolean {
    const spec = buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as string[]
    steps.push(text)
    const substeps = spec.substeps as Array<{ step: string; substeps: string[] }>
    if (defaultSubsteps && defaultSubsteps.length >= 2) {
      substeps.push({ step: text, substeps: [defaultSubsteps[0], defaultSubsteps[1]] })
    }
    // Preserve orientation
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    loadFromSpec({ ...spec, steps, substeps, orientation }, 'flow_map')
    pushHistory('Add flow step')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  /**
   * Add a substep to an existing flow map step.
   */
  function addFlowMapSubstep(stepText: string, substepText: string): boolean {
    const spec = buildFlowMapSpecFromNodes()
    if (!spec) return false
    const substeps = spec.substeps as Array<{ step: string; substeps: string[] }>
    const entry = substeps.find((e) => e.step === stepText)
    if (entry) {
      entry.substeps.push(substepText)
    } else {
      substeps.push({ step: stepText, substeps: [substepText] })
    }
    // Preserve orientation (vertical must not revert to horizontal)
    const orientation = (data.value as Record<string, unknown>)?.orientation ?? spec.orientation
    loadFromSpec({ ...spec, substeps, orientation }, 'flow_map')
    pushHistory('Add flow substep')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  /**
   * Build tree map spec from current nodes.
   */
  function buildTreeMapSpecFromNodes(): Record<string, unknown> | null {
    if (!data.value || type.value !== 'tree_map') return null
    const nodes = data.value.nodes
    const rootNode = nodes.find((n) => n.id === 'tree-topic')
    if (!rootNode) return null
    const rootId = rootNode.id ?? 'tree-topic'
    const categoryNodes = nodes
      .filter((n) => /^tree-cat-\d+$/.test(n.id ?? ''))
      .sort(
        (a, b) =>
          parseInt((a.id ?? '0').replace('tree-cat-', ''), 10) -
          parseInt((b.id ?? '0').replace('tree-cat-', ''), 10)
      )
    const categories = categoryNodes.map((cat, catIndex) => {
      const leaves = nodes
        .filter((n) => {
          const m = (n.id ?? '').match(/^tree-leaf-(\d+)-(\d+)$/)
          return m && parseInt(m[1], 10) === catIndex
        })
        .sort(
          (a, b) =>
            parseInt((a.id ?? '0').split('-').pop() ?? '0', 10) -
            parseInt((b.id ?? '0').split('-').pop() ?? '0', 10)
        )
      return {
        id: cat.id,
        text: cat.text,
        children: leaves.map((l) => ({ id: l.id, text: l.text, children: [] })),
      }
    })
    const dimension = (data.value as Record<string, unknown>).dimension as string | undefined
    const altDims = (data.value as Record<string, unknown>).alternative_dimensions as
      | string[]
      | undefined
    return {
      root: {
        id: rootId,
        text: rootNode.text,
        children: categories,
      },
      dimension,
      alternative_dimensions: altDims,
    }
  }

  /**
   * Remove tree map category/leaf nodes. Deleting a category also removes its children.
   */
  function removeTreeMapNodes(nodeIds: string[]): number {
    if (type.value !== 'tree_map' || !data.value?.nodes) return 0
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return 0

    const idsToRemove = new Set(nodeIds)
    if (idsToRemove.has('tree-topic') || idsToRemove.has('dimension-label')) return 0

    const categoryIdsToRemove = new Set(nodeIds.filter((id) => /^tree-cat-\d+$/.test(id)))

    const root = spec.root as {
      id?: string
      text: string
      children?: Array<{
        id?: string
        text: string
        children?: Array<{ id?: string; text: string }>
      }>
    }
    const categories = root.children ?? []

    let deletedCount = 0
    const newCategories = categories
      .filter((cat) => {
        if (categoryIdsToRemove.has(cat.id ?? '')) {
          deletedCount += 1 + (cat.children?.length ?? 0)
          return false
        }
        return true
      })
      .map((cat) => ({
        text: cat.text,
        children: (cat.children ?? [])
          .filter((leaf) => {
            if (idsToRemove.has(leaf.id ?? '')) {
              deletedCount++
              return false
            }
            return true
          })
          .map((leaf) => ({ text: leaf.text })),
      }))

    if (deletedCount === 0) return 0

    const newSpec = {
      ...spec,
      root: { ...root, id: undefined, children: newCategories },
    }
    loadFromSpec(newSpec, 'tree_map')

    const deletedIds = [
      ...nodeIds,
      ...categories
        .filter((c) => categoryIdsToRemove.has(c.id ?? ''))
        .flatMap((c) => (c.children ?? []).map((l) => l.id).filter(Boolean) as string[]),
    ]
    deletedIds.forEach((id) => {
      clearCustomPosition(id)
      clearNodeStyle(id)
      removeFromSelection(id)
    })
    pushHistory('Delete nodes')
    emitEvent('diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedCount
  }

  /**
   * Get descendant node IDs for tree map.
   * - Category (tree-cat-X): category + all its leaves (traverse connection chain)
   * - Leaf (tree-leaf-X-Y): only that leaf (leaves have no semantic children; chain is layout-only)
   */
  function getTreeMapDescendantIds(nodeId: string): Set<string> {
    const result = new Set<string>([nodeId])
    if (/^tree-leaf-\d+-\d+$/.test(nodeId)) return result
    if (!data.value?.connections) return result
    const childrenMap = new Map<string, string[]>()
    data.value.connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })
    function collect(id: string): void {
      for (const childId of childrenMap.get(id) ?? []) {
        if (
          (childId.startsWith('tree-cat-') || childId.startsWith('tree-leaf-')) &&
          childId !== 'tree-topic'
        ) {
          result.add(childId)
          collect(childId)
        }
      }
    }
    collect(nodeId)
    return result
  }

  /**
   * Move a tree map category or leaf (swap or add to category).
   * Same semantics as mindmap: category on category = swap, leaf on category = add, leaf on leaf = swap.
   */
  function moveTreeMapBranch(
    nodeId: string,
    targetType: 'topic' | 'child' | 'sibling',
    targetId?: string
  ): boolean {
    if (type.value !== 'tree_map') return false
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false

    const root = spec.root as {
      id?: string
      text: string
      children?: Array<{
        id?: string
        text: string
        children?: Array<{ id?: string; text: string }>
      }>
    }
    const categories = root.children ?? []

    const isCategory = (id: string) => /^tree-cat-\d+$/.test(id)
    const isLeaf = (id: string) => /^tree-leaf-\d+-\d+$/.test(id)

    const findCategoryIndex = (id: string) => {
      const m = id.match(/^tree-cat-(\d+)$/)
      return m ? parseInt(m[1], 10) : -1
    }

    let sourceCatIdx = -1
    let sourceLeafIdx = -1
    let sourceItem: { id?: string; text: string; children?: unknown[] } | null = null

    if (isCategory(nodeId)) {
      sourceCatIdx = findCategoryIndex(nodeId)
      if (sourceCatIdx < 0 || sourceCatIdx >= categories.length) return false
      sourceItem = categories[sourceCatIdx]
    } else if (isLeaf(nodeId)) {
      const m = nodeId.match(/^tree-leaf-(\d+)-(\d+)$/)
      if (!m) return false
      sourceCatIdx = parseInt(m[1], 10)
      sourceLeafIdx = parseInt(m[2], 10)
      const cat = categories[sourceCatIdx]
      const leaves = cat?.children ?? []
      if (sourceLeafIdx < 0 || sourceLeafIdx >= leaves.length) return false
      sourceItem = leaves[sourceLeafIdx]
    } else {
      return false
    }
    if (!sourceItem) return false

    if (targetType === 'sibling' && targetId) {
      if (isCategory(nodeId) && isCategory(targetId)) {
        const targetCatIdx = findCategoryIndex(targetId)
        if (targetCatIdx < 0 || targetCatIdx >= categories.length) return false
        const [removed] = categories.splice(sourceCatIdx, 1)
        const adj = sourceCatIdx < targetCatIdx ? targetCatIdx - 1 : targetCatIdx
        const [removedTarget] = categories.splice(adj, 1)
        if (sourceCatIdx < targetCatIdx) {
          categories.splice(sourceCatIdx, 0, removedTarget)
          categories.splice(targetCatIdx, 0, removed)
        } else {
          categories.splice(targetCatIdx, 0, removed)
          categories.splice(sourceCatIdx, 0, removedTarget)
        }
      } else if (isLeaf(nodeId) && isLeaf(targetId)) {
        const tm = targetId.match(/^tree-leaf-(\d+)-(\d+)$/)
        if (!tm) return false
        const targetCatIdx = parseInt(tm[1], 10)
        const targetLeafIdx = parseInt(tm[2], 10)
        const srcCat = categories[sourceCatIdx]
        const tgtCat = categories[targetCatIdx]
        const srcLeaves = srcCat?.children ?? []
        const tgtLeaves = tgtCat?.children ?? []
        const srcLeaf = srcLeaves[sourceLeafIdx]
        const tgtLeaf = tgtLeaves[targetLeafIdx]
        if (!srcLeaf || !tgtLeaf) return false
        if (sourceCatIdx === targetCatIdx) {
          srcLeaves[sourceLeafIdx] = tgtLeaf
          srcLeaves[targetLeafIdx] = srcLeaf
        } else {
          srcLeaves.splice(sourceLeafIdx, 1)
          tgtLeaves.splice(targetLeafIdx, 1)
          srcLeaves.splice(sourceLeafIdx, 0, tgtLeaf)
          tgtLeaves.splice(targetLeafIdx, 0, srcLeaf)
        }
      } else {
        return false
      }
    } else if (targetType === 'child' && targetId && isCategory(targetId)) {
      if (!isLeaf(nodeId)) return false
      const targetCatIdx = findCategoryIndex(targetId)
      if (targetCatIdx < 0 || targetCatIdx >= categories.length) return false
      const srcCat = categories[sourceCatIdx]
      const tgtCat = categories[targetCatIdx]
      const srcLeaves = srcCat?.children ?? []
      const [removed] = srcLeaves.splice(sourceLeafIdx, 1)
      if (!tgtCat.children) tgtCat.children = []
      tgtCat.children.push(removed)
    } else if (targetType === 'topic' && targetId === 'tree-topic') {
      if (isLeaf(nodeId)) return false
      const [removed] = categories.splice(sourceCatIdx, 1)
      categories.push(removed)
    } else {
      return false
    }

    // Strip IDs so loadTreeMapSpec generates correct tree-cat-N / tree-leaf-N-M IDs
    // matching the new structure. Preserving old IDs causes buildTreeMapSpecFromNodes
    // to mis-associate leaves with their old categories on subsequent operations.
    const cleanCategories = categories.map((cat) => ({
      text: cat.text,
      children: (cat.children ?? []).map((leaf) => ({ text: leaf.text })),
    }))
    const newSpec = { ...spec, root: { ...root, id: undefined, children: cleanCategories } }
    loadFromSpec(newSpec, 'tree_map')
    if (data.value?._customPositions) data.value._customPositions = {}
    if (data.value?._node_styles) data.value._node_styles = {}
    selectedNodes.value = []
    pushHistory('Move branch')
    emitEvent('diagram:operation_completed', { operation: 'move_branch' })
    return true
  }

  /**
   * Add a new category to tree map.
   */
  function addTreeMapCategory(text: string): boolean {
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false
    const root = spec.root as {
      text: string
      children?: Array<{ text: string; children?: unknown[] }>
    }
    if (!root.children) {
      root.children = []
    }
    root.children.push({ text, children: [] })
    loadFromSpec(spec, 'tree_map')
    pushHistory('Add tree category')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  /**
   * Add a child (leaf) to a tree map category.
   */
  function addTreeMapChild(categoryId: string, text: string): boolean {
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false
    const root = spec.root as {
      children?: Array<{ id?: string; text: string; children?: Array<{ text: string }> }>
    }
    const categories = root.children ?? []
    const category = categories.find((c) => c.id === categoryId)
    if (!category) return false
    if (!category.children) {
      category.children = []
    }
    category.children.push({ text })
    loadFromSpec(spec, 'tree_map')
    pushHistory('Add tree child')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  /**
   * Load default template for a diagram type
   * Creates a blank canvas with placeholder text
   */
  function loadDefaultTemplate(diagramTypeValue: DiagramType): boolean {
    const template = getDefaultTemplate(diagramTypeValue)
    if (!template) return false
    return loadFromSpec(template, diagramTypeValue)
  }

  /**
   * Merge granular updates (only changed nodes/connections) into existing diagram.
   * Used for workshop collaboration to avoid overwriting concurrent edits.
   */
  function mergeGranularUpdate(
    updatedNodes?: Array<Record<string, unknown>>,
    updatedConnections?: Array<Record<string, unknown>>
  ): boolean {
    if (!data.value) return false

    // Merge updated nodes
    if (updatedNodes && updatedNodes.length > 0) {
      for (const updatedNode of updatedNodes) {
        const nodeId = updatedNode.id as string
        if (!nodeId) continue

        const existingIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
        if (existingIndex >= 0) {
          // Update existing node (merge properties)
          data.value.nodes[existingIndex] = {
            ...data.value.nodes[existingIndex],
            ...updatedNode,
          } as DiagramNode
        } else {
          // Add new node
          data.value.nodes.push(updatedNode as unknown as DiagramNode)
        }
      }
    }

    // Merge updated connections
    if (updatedConnections && updatedConnections.length > 0) {
      for (const updatedConn of updatedConnections) {
        const source = updatedConn.source as string
        const target = updatedConn.target as string
        if (!source || !target) continue

        let conns: Connection[]
        if (data.value.connections) {
          conns = data.value.connections
        } else {
          conns = []
          data.value.connections = conns
        }
        const existingIndex = conns.findIndex((c) => c.source === source && c.target === target)

        if (existingIndex >= 0) {
          const existing = conns[existingIndex]
          conns[existingIndex] = {
            ...existing,
            ...updatedConn,
          } as Connection
        } else {
          conns.push(updatedConn as unknown as Connection)
        }
      }
    }

    return true
  }

  // ===== Title Management =====

  /**
   * Get topic node text from current diagram
   * Returns null if no topic or if topic is default placeholder
   */
  function getTopicNodeText(): string | null {
    const topicNode = data.value?.nodes?.find(
      (n) => n.type === 'topic' || n.type === 'center' || n.id === 'root'
    )
    if (!topicNode?.text) return null
    const text = topicNode.text.trim()
    if (PLACEHOLDER_TEXTS.includes(text)) return null
    return text
  }

  /**
   * Computed: Get the effective title
   * Priority: user-edited title > topic node text > stored title
   */
  const effectiveTitle = computed(() => {
    if (isUserEditedTitle.value && title.value) {
      return title.value
    }
    const topicText = getTopicNodeText()
    if (topicText) {
      return topicText
    }
    return title.value
  })

  /**
   * Set the diagram title
   * @param newTitle - The new title
   * @param userEdited - Whether this was a manual user edit (disables auto-update)
   */
  function setTitle(newTitle: string, userEdited: boolean = false): void {
    title.value = newTitle
    if (userEdited) {
      isUserEditedTitle.value = true
    }
  }

  /**
   * Initialize title with default name (used when creating new diagram)
   * Resets userEdited flag to allow auto-updates
   */
  function initTitle(defaultTitle: string): void {
    title.value = defaultTitle
    isUserEditedTitle.value = false
  }

  /**
   * Reset title state (when creating new diagram or clearing)
   */
  function resetTitle(): void {
    title.value = ''
    isUserEditedTitle.value = false
  }

  /**
   * Check if title should auto-update from topic changes
   */
  function shouldAutoUpdateTitle(): boolean {
    return !isUserEditedTitle.value
  }

  /**
   * Set topic node width for multi-flow map layout recalculation
   */
  function setTopicNodeWidth(width: number | null): void {
    topicNodeWidth.value = width
    // Trigger recalculation by incrementing trigger
    if (type.value === 'multi_flow_map') {
      multiFlowMapRecalcTrigger.value++
    }
  }

  /**
   * Set node width for multi-flow map visual balance
   */
  function setNodeWidth(nodeId: string, width: number | null): void {
    if (width === null) {
      delete nodeWidths.value[nodeId]
    } else {
      nodeWidths.value[nodeId] = width
    }
    // Trigger recalculation for visual balance
    if (type.value === 'multi_flow_map') {
      multiFlowMapRecalcTrigger.value++
    }
  }

  /**
   * Get the set of node IDs that should be hidden when dragging a node.
   * Handles pair semantics (bridge_map, double_bubble_map) and
   * parent-child groups (flow_map steps+substeps, brace_map parts+subparts).
   */
  function getNodeGroupIds(nodeId: string): Set<string> {
    const result = new Set<string>([nodeId])
    const dt = type.value
    if (!dt || !data.value) return result

    if (dt === 'bridge_map') {
      const pairMatch = nodeId.match(/^pair-(\d+)-(left|right)$/)
      if (pairMatch) {
        const idx = pairMatch[1]
        result.add(`pair-${idx}-left`)
        result.add(`pair-${idx}-right`)
      }
    } else if (dt === 'double_bubble_map') {
      const leftMatch = nodeId.match(/^left-diff-(\d+)$/)
      const rightMatch = nodeId.match(/^right-diff-(\d+)$/)
      if (leftMatch) result.add(`right-diff-${leftMatch[1]}`)
      else if (rightMatch) result.add(`left-diff-${rightMatch[1]}`)
    } else if (dt === 'flow_map') {
      const stepMatch = nodeId.match(/^flow-step-(\d+)$/)
      if (stepMatch) {
        const stepIdx = stepMatch[1]
        data.value.nodes
          .filter((n) => n.id.startsWith(`flow-substep-${stepIdx}-`))
          .forEach((n) => result.add(n.id))
      }
    } else if (dt === 'brace_map' && data.value.connections) {
      const childrenMap = new Map<string, string[]>()
      data.value.connections.forEach((c) => {
        if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
        const srcList = childrenMap.get(c.source)
        if (srcList) srcList.push(c.target)
      })
      const collectChildren = (id: string): void => {
        for (const childId of childrenMap.get(id) ?? []) {
          result.add(childId)
          collectChildren(childId)
        }
      }
      collectChildren(nodeId)
    } else if (dt === 'mindmap' || dt === 'mind_map') {
      return getMindMapDescendantIds(nodeId)
    } else if (dt === 'tree_map') {
      return getTreeMapDescendantIds(nodeId)
    }

    return result
  }

  /**
   * Generic node swap for all diagram types except mindmap and tree_map
   * (which have their own dedicated moveMindMapBranch / moveTreeMapBranch).
   */
  function moveNodeBySwap(sourceId: string, targetId: string): boolean {
    const dt = type.value
    if (!dt || !data.value) return false

    let success = false
    switch (dt) {
      case 'bubble_map':
        success = swapBubbleMapNodes(sourceId, targetId)
        break
      case 'circle_map':
        success = swapCircleMapNodes(sourceId, targetId)
        break
      case 'double_bubble_map':
        success = swapDoubleBubbleMapNodes(sourceId, targetId)
        break
      case 'flow_map':
        return moveFlowMapNode(sourceId, targetId)
      case 'multi_flow_map':
        success = swapMultiFlowMapNodes(sourceId, targetId)
        break
      case 'brace_map':
        return moveBraceMapNode(sourceId, targetId)
      case 'bridge_map':
        success = swapBridgeMapPairs(sourceId, targetId)
        break
      default:
        return false
    }

    if (success) {
      if (data.value?._customPositions) data.value._customPositions = {}
      if (data.value?._node_styles) data.value._node_styles = {}
      selectedNodes.value = []
      pushHistory('Move node')
      emitEvent('diagram:operation_completed', { operation: 'move_branch' })
      eventBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  function swapBubbleMapNodes(sourceId: string, targetId: string): boolean {
    if (!data.value?.nodes) return false
    const srcIdx = parseInt(sourceId.replace('bubble-', ''), 10)
    const tgtIdx = parseInt(targetId.replace('bubble-', ''), 10)
    const bubbles = data.value.nodes
      .filter((n) => n.id.startsWith('bubble-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('bubble-', ''), 10) - parseInt(b.id.replace('bubble-', ''), 10)
      )
    if (srcIdx < 0 || srcIdx >= bubbles.length || tgtIdx < 0 || tgtIdx >= bubbles.length)
      return false
    const srcText = bubbles[srcIdx].text
    bubbles[srcIdx].text = bubbles[tgtIdx].text
    bubbles[tgtIdx].text = srcText
    const recalculatedNodes = recalculateBubbleMapLayout(data.value.nodes)
    const recalcBubbles = recalculatedNodes.filter(
      (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
    )
    data.value.nodes = recalculatedNodes
    data.value.connections = recalcBubbles.map((_, i) => ({
      id: `edge-topic-bubble-${i}`,
      source: 'topic',
      target: `bubble-${i}`,
      style: { strokeColor: getMindmapBranchColor(i).border },
    }))
    return true
  }

  function swapCircleMapNodes(sourceId: string, targetId: string): boolean {
    if (!data.value?.nodes) return false
    const srcIdx = parseInt(sourceId.replace('context-', ''), 10)
    const tgtIdx = parseInt(targetId.replace('context-', ''), 10)
    const contexts = data.value.nodes
      .filter((n) => n.id.startsWith('context-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('context-', ''), 10) - parseInt(b.id.replace('context-', ''), 10)
      )
    if (srcIdx < 0 || srcIdx >= contexts.length || tgtIdx < 0 || tgtIdx >= contexts.length)
      return false
    const topic = data.value.nodes.find((n) => n.id === 'topic')?.text ?? ''
    const contextTexts = contexts.map((n) => n.text)
    const tmp = contextTexts[srcIdx]
    contextTexts[srcIdx] = contextTexts[tgtIdx]
    contextTexts[tgtIdx] = tmp
    return loadFromSpec({ topic, context: contextTexts }, 'circle_map')
  }

  function parseDiffIndex(nodeId: string): number {
    const match = nodeId.match(/^(?:left|right)-diff-(\d+)$/)
    return match ? parseInt(match[1], 10) : -1
  }

  function swapDoubleBubbleMapNodes(sourceId: string, targetId: string): boolean {
    const spec = getDoubleBubbleSpecFromData()
    if (!spec) return false

    const similarities = spec.similarities as string[]
    const leftDiffs = spec.leftDifferences as string[]
    const rightDiffs = spec.rightDifferences as string[]

    const srcSimMatch = sourceId.match(/^similarity-(\d+)$/)
    const tgtSimMatch = targetId.match(/^similarity-(\d+)$/)

    if (srcSimMatch && tgtSimMatch) {
      const si = parseInt(srcSimMatch[1], 10)
      const ti = parseInt(tgtSimMatch[1], 10)
      if (si >= 0 && si < similarities.length && ti >= 0 && ti < similarities.length) {
        const tmp = similarities[si]
        similarities[si] = similarities[ti]
        similarities[ti] = tmp
        return loadFromSpec(spec, 'double_bubble_map')
      }
      return false
    }

    const srcDiffIdx = parseDiffIndex(sourceId)
    const tgtDiffIdx = parseDiffIndex(targetId)
    if (
      srcDiffIdx >= 0 &&
      tgtDiffIdx >= 0 &&
      srcDiffIdx < leftDiffs.length &&
      tgtDiffIdx < leftDiffs.length &&
      srcDiffIdx < rightDiffs.length &&
      tgtDiffIdx < rightDiffs.length
    ) {
      const tmpL = leftDiffs[srcDiffIdx]
      leftDiffs[srcDiffIdx] = leftDiffs[tgtDiffIdx]
      leftDiffs[tgtDiffIdx] = tmpL
      const tmpR = rightDiffs[srcDiffIdx]
      rightDiffs[srcDiffIdx] = rightDiffs[tgtDiffIdx]
      rightDiffs[tgtDiffIdx] = tmpR
      return loadFromSpec(spec, 'double_bubble_map')
    }
    return false
  }

  function swapFlowMapNodes(sourceId: string, targetId: string): boolean {
    const spec = buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as string[]
    const substepsList = spec.substeps as Array<{ step: string; substeps: string[] }>

    const srcStepMatch = sourceId.match(/^flow-step-(\d+)$/)
    const tgtStepMatch = targetId.match(/^flow-step-(\d+)$/)
    if (srcStepMatch && tgtStepMatch) {
      const si = parseInt(srcStepMatch[1], 10)
      const ti = parseInt(tgtStepMatch[1], 10)
      if (si >= 0 && si < steps.length && ti >= 0 && ti < steps.length) {
        const srcText = steps[si]
        const tgtText = steps[ti]
        const srcSubs = substepsList.find((e) => e.step === srcText)
        const tgtSubs = substepsList.find((e) => e.step === tgtText)
        steps[si] = tgtText
        steps[ti] = srcText
        if (srcSubs) srcSubs.step = srcText
        if (tgtSubs) tgtSubs.step = tgtText
        return loadFromSpec(spec, 'flow_map')
      }
      return false
    }

    const srcSubMatch = sourceId.match(/^flow-substep-(\d+)-(\d+)$/)
    const tgtSubMatch = targetId.match(/^flow-substep-(\d+)-(\d+)$/)
    if (srcSubMatch && tgtSubMatch) {
      const srcStep = parseInt(srcSubMatch[1], 10)
      const srcSub = parseInt(srcSubMatch[2], 10)
      const tgtStep = parseInt(tgtSubMatch[1], 10)
      const tgtSub = parseInt(tgtSubMatch[2], 10)
      if (srcStep < steps.length && tgtStep < steps.length) {
        const srcStepText = steps[srcStep]
        const tgtStepText = steps[tgtStep]
        const srcEntry = substepsList.find((e) => e.step === srcStepText)
        const tgtEntry = substepsList.find((e) => e.step === tgtStepText)
        if (
          srcEntry &&
          tgtEntry &&
          srcSub < srcEntry.substeps.length &&
          tgtSub < tgtEntry.substeps.length
        ) {
          const tmp = srcEntry.substeps[srcSub]
          srcEntry.substeps[srcSub] = tgtEntry.substeps[tgtSub]
          tgtEntry.substeps[tgtSub] = tmp
          return loadFromSpec(spec, 'flow_map')
        }
      }
      return false
    }
    return false
  }

  /**
   * Move a flow map node: reparent if substep → step,
   * otherwise swap. Handles adding a substep to another step group.
   */
  function moveFlowMapNode(sourceId: string, targetId: string): boolean {
    const spec = buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as string[]
    const substepsList = spec.substeps as Array<{ step: string; substeps: string[] }>

    const srcSubMatch = sourceId.match(/^flow-substep-(\d+)-(\d+)$/)
    const tgtStepMatch = targetId.match(/^flow-step-(\d+)$/)

    let success = false

    if (srcSubMatch && tgtStepMatch) {
      const srcStepIdx = parseInt(srcSubMatch[1], 10)
      const srcSubIdx = parseInt(srcSubMatch[2], 10)
      const tgtStepIdx = parseInt(tgtStepMatch[1], 10)

      if (srcStepIdx === tgtStepIdx) return false
      if (srcStepIdx >= steps.length || tgtStepIdx >= steps.length) return false

      const srcStepText = steps[srcStepIdx]
      const tgtStepText = steps[tgtStepIdx]
      const srcEntry = substepsList.find((e) => e.step === srcStepText)
      if (!srcEntry || srcSubIdx >= srcEntry.substeps.length) return false

      const [movedText] = srcEntry.substeps.splice(srcSubIdx, 1)

      const tgtEntry = substepsList.find((e) => e.step === tgtStepText)
      if (tgtEntry) {
        tgtEntry.substeps.push(movedText)
      } else {
        substepsList.push({ step: tgtStepText, substeps: [movedText] })
      }

      success = loadFromSpec(spec, 'flow_map')
    } else {
      success = swapFlowMapNodes(sourceId, targetId)
    }

    if (success) {
      if (data.value?._customPositions) data.value._customPositions = {}
      if (data.value?._node_styles) data.value._node_styles = {}
      selectedNodes.value = []
      pushHistory('Move node')
      emitEvent('diagram:operation_completed', { operation: 'move_branch' })
      eventBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  function swapMultiFlowMapNodes(sourceId: string, targetId: string): boolean {
    if (!data.value?.nodes) return false
    const causeNodes = data.value.nodes
      .filter((n) => n.id.startsWith('cause-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('cause-', ''), 10) - parseInt(b.id.replace('cause-', ''), 10)
      )
    const effectNodes = data.value.nodes
      .filter((n) => n.id.startsWith('effect-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('effect-', ''), 10) - parseInt(b.id.replace('effect-', ''), 10)
      )
    const eventNode = data.value.nodes.find((n) => n.id === 'event')

    const causes = causeNodes.map((n) => n.text)
    const effects = effectNodes.map((n) => n.text)

    const srcCause = sourceId.match(/^cause-(\d+)$/)
    const tgtCause = targetId.match(/^cause-(\d+)$/)
    if (srcCause && tgtCause) {
      const si = parseInt(srcCause[1], 10)
      const ti = parseInt(tgtCause[1], 10)
      if (si >= 0 && si < causes.length && ti >= 0 && ti < causes.length) {
        const tmp = causes[si]
        causes[si] = causes[ti]
        causes[ti] = tmp
        return loadFromSpec({ event: eventNode?.text ?? '', causes, effects }, 'multi_flow_map')
      }
      return false
    }

    const srcEffect = sourceId.match(/^effect-(\d+)$/)
    const tgtEffect = targetId.match(/^effect-(\d+)$/)
    if (srcEffect && tgtEffect) {
      const si = parseInt(srcEffect[1], 10)
      const ti = parseInt(tgtEffect[1], 10)
      if (si >= 0 && si < effects.length && ti >= 0 && ti < effects.length) {
        const tmp = effects[si]
        effects[si] = effects[ti]
        effects[ti] = tmp
        return loadFromSpec({ event: eventNode?.text ?? '', causes, effects }, 'multi_flow_map')
      }
      return false
    }
    return false
  }

  function swapBraceMapNodes(sourceId: string, targetId: string): boolean {
    if (!data.value?.nodes || !data.value?.connections) return false

    const targetIdSet = new Set(data.value.connections.map((c) => c.target))
    const rootId =
      data.value.nodes.find((n) => n.type === 'topic')?.id ??
      data.value.nodes.find((n) => !targetIdSet.has(n.id) && n.type !== 'label')?.id
    if (!rootId) return false

    const childrenMap = new Map<string, string[]>()
    data.value.connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })

    const srcParentConn = data.value.connections.find((c) => c.target === sourceId)
    const tgtParentConn = data.value.connections.find((c) => c.target === targetId)
    if (!srcParentConn || !tgtParentConn) return false

    const srcParent = srcParentConn.source
    const tgtParent = tgtParentConn.source
    const srcSiblings = childrenMap.get(srcParent) ?? []
    const tgtSiblings = childrenMap.get(tgtParent) ?? []
    const srcIdx = srcSiblings.indexOf(sourceId)
    const tgtIdx = tgtSiblings.indexOf(targetId)
    if (srcIdx < 0 || tgtIdx < 0) return false

    if (srcParent === tgtParent) {
      srcSiblings[srcIdx] = targetId
      srcSiblings[tgtIdx] = sourceId
    } else {
      srcSiblings[srcIdx] = targetId
      tgtSiblings[tgtIdx] = sourceId
    }

    const newConnections = data.value.connections.map((c) => {
      if (c.source === srcParent && c.target === sourceId) return { ...c, target: targetId }
      if (c.source === tgtParent && c.target === targetId) return { ...c, target: sourceId }
      if (c.source === sourceId) return { ...c, source: targetId }
      if (c.source === targetId) return { ...c, source: sourceId }
      if (c.target === sourceId) return { ...c, target: targetId }
      if (c.target === targetId) return { ...c, target: sourceId }
      return c
    })

    data.value.connections = newConnections

    const layoutNodes = recalculateBraceMapLayout(data.value.nodes, newConnections)
    data.value.nodes = layoutNodes
    return true
  }

  /**
   * Move a brace map node: reparent if source is deeper than target,
   * otherwise swap. Handles subpart → part as "add to group".
   */
  function moveBraceMapNode(sourceId: string, targetId: string): boolean {
    if (!data.value?.nodes || !data.value?.connections) return false

    const parentMap = new Map<string, string>()
    data.value.connections.forEach((c) => {
      parentMap.set(c.target, c.source)
    })

    function getDepth(nodeId: string): number {
      let depth = 0
      let current = nodeId
      while (parentMap.has(current)) {
        depth++
        const next = parentMap.get(current)
        if (next === undefined) break
        current = next
      }
      return depth
    }

    const srcDepth = getDepth(sourceId)
    const tgtDepth = getDepth(targetId)

    if (parentMap.get(sourceId) === targetId) return false

    let success = false

    if (srcDepth > tgtDepth) {
      const descendantIds = getNodeGroupIds(sourceId)
      if (descendantIds.has(targetId)) return false

      const oldParent = parentMap.get(sourceId)
      if (!oldParent) return false

      data.value.connections = data.value.connections.filter(
        (c) => !(c.source === oldParent && c.target === sourceId)
      )
      data.value.connections.push({
        id: `edge-${targetId}-${sourceId}`,
        source: targetId,
        target: sourceId,
      })

      const layoutNodes = recalculateBraceMapLayout(data.value.nodes, data.value.connections)
      data.value.nodes = layoutNodes
      success = true
    } else {
      success = swapBraceMapNodes(sourceId, targetId)
    }

    if (success) {
      if (data.value?._customPositions) data.value._customPositions = {}
      if (data.value?._node_styles) data.value._node_styles = {}
      selectedNodes.value = []
      pushHistory('Move node')
      emitEvent('diagram:operation_completed', { operation: 'move_branch' })
      eventBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  function swapBridgeMapPairs(sourceId: string, targetId: string): boolean {
    if (!data.value?.nodes) return false
    const srcMatch = sourceId.match(/^pair-(\d+)-(left|right)$/)
    const tgtMatch = targetId.match(/^pair-(\d+)-(left|right)$/)
    if (!srcMatch || !tgtMatch) return false

    const srcPairIdx = parseInt(srcMatch[1], 10)
    const tgtPairIdx = parseInt(tgtMatch[1], 10)
    if (srcPairIdx === tgtPairIdx) return false

    const pairIndices = [
      ...new Set(
        data.value.nodes
          .filter((n) => n.id.startsWith('pair-'))
          .map((n) => parseInt(n.id.match(/^pair-(\d+)/)?.[1] ?? '-1', 10))
          .filter((i) => i >= 0)
      ),
    ].sort((a, b) => a - b)

    if (!pairIndices.includes(srcPairIdx) || !pairIndices.includes(tgtPairIdx)) return false

    const rawDimension = (
      (data.value as Record<string, unknown>).dimension as string | undefined
    )?.trim()
    const rawFactor = (
      (data.value as Record<string, unknown>).relating_factor as string | undefined
    )?.trim()
    const dimension = rawDimension || rawFactor || ''
    const altDims = (data.value as Record<string, unknown>).alternative_dimensions as
      | string[]
      | undefined

    const bridgeNodes = data.value.nodes
    const analogies = pairIndices.map((i) => {
      const leftNode = bridgeNodes.find((n) => n.id === `pair-${i}-left`)
      const rightNode = bridgeNodes.find((n) => n.id === `pair-${i}-right`)
      return { left: leftNode?.text ?? '', right: rightNode?.text ?? '' }
    })

    const srcPos = pairIndices.indexOf(srcPairIdx)
    const tgtPos = pairIndices.indexOf(tgtPairIdx)
    const tmp = analogies[srcPos]
    analogies[srcPos] = analogies[tgtPos]
    analogies[tgtPos] = tmp

    const spec: Record<string, unknown> = {
      relating_factor: dimension,
      dimension,
      analogies,
    }
    if (altDims) spec.alternative_dimensions = altDims
    return loadFromSpec(spec, 'bridge_map')
  }

  return {
    // State
    type,
    sessionId,
    data,
    selectedNodes,
    history,
    historyIndex,
    title,
    isUserEditedTitle,
    sessionEditCount,
    resetSessionEditCount,

    // Getters
    canUndo,
    canRedo,
    nodeCount,
    hasSelection,
    canPaste,
    selectedNodeData,
    isLearningSheet,
    hiddenAnswers,
    effectiveTitle,

    // Vue Flow computed
    vueFlowNodes,
    vueFlowEdges,

    // Actions
    setDiagramType,
    setSessionId,
    updateDiagram,
    selectNodes,
    clearSelection,
    addToSelection,
    removeFromSelection,
    pushHistory,
    undo,
    redo,
    clearHistory,
    updateNode,
    emptyNodeForLearningSheet,
    emptyNode,
    setLearningSheetMode,
    restoreFromLearningSheetMode,
    applyLearningSheetView,
    hasPreservedLearningSheet,
    addNode,
    addConnection,
    updateConnectionLabel,
    toggleConnectionArrowhead,
    updateConnectionArrowheadsForNode,
    removeNode,
    removeBubbleMapNodes,
    addBraceMapPart,
    removeBraceMapNodes,
    addMindMapBranch,
    addMindMapChild,
    removeMindMapNodes,
    moveMindMapBranch,
    getMindMapDescendantIds,
    copySelectedNodes,
    pasteNodesAt,
    reset,

    // Vue Flow actions
    updateNodePosition,
    updateNodesFromVueFlow,
    syncFromVueFlow,

    // Custom positions (Phase 3)
    saveCustomPosition,
    hasCustomPosition,
    getCustomPosition,
    clearCustomPosition,
    resetToAutoLayout,

    // Node styles (Phase 3)
    saveNodeStyle,
    getNodeStyle,
    clearNodeStyle,
    clearAllNodeStyles,
    applyStylePreset,

    // Spec loading
    loadFromSpec,
    loadDefaultTemplate,
    mergeGranularUpdate,
    getSpecForSave,
    getDoubleBubbleSpecFromData,
    addDoubleBubbleMapNode,
    removeDoubleBubbleMapNodes,

    // Flow map
    addFlowMapStep,
    addFlowMapSubstep,
    toggleFlowMapOrientation,

    // Tree map
    addTreeMapCategory,
    addTreeMapChild,
    moveTreeMapBranch,
    getTreeMapDescendantIds,
    removeTreeMapNodes,

    // Generic node move (all diagram types)
    getNodeGroupIds,
    moveNodeBySwap,

    // Title management
    getTopicNodeText,
    setTitle,
    initTitle,
    resetTitle,
    shouldAutoUpdateTitle,
    setTopicNodeWidth,
    setNodeWidth,
  }
})
