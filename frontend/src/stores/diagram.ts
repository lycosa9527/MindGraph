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
} from '@/composables/diagrams/conceptMapHandles'
import {
  DEFAULT_CENTER_X,
  DEFAULT_NODE_WIDTH,
  MULTI_FLOW_MAP_TOPIC_WIDTH,
} from '@/composables/diagrams/layoutConfig'
import { eventBus } from '@/composables/useEventBus'
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
import {
  LEARNING_SHEET_PLACEHOLDER,
} from './specLoader/utils'

import { useConceptMapRelationshipStore } from './conceptMapRelationship'

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
      const firstLevelBranchCount = connections.filter(
        (c) => c.source === 'topic'
      ).length

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

    // Brace map: recalculate layout when nodes/connections change
    if (diagramType === 'brace_map') {
      const layoutNodes = recalculateBraceMapLayout(
        data.value.nodes,
        data.value.connections ?? []
      )
      return layoutNodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        vueFlowNode.selected = selectedNodes.value.includes(node.id)
        return vueFlowNode
      })
    }

    return data.value.nodes.map((node) => {
      const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
      vueFlowNode.selected = selectedNodes.value.includes(node.id)
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
      const groups = new Map<string, MindGraphEdge[]>()
      for (const edge of edges) {
        const key = `${edge.target}:${edge.targetHandle ?? ''}`
        if (!groups.has(key)) groups.set(key, [])
        groups.get(key)!.push(edge)
      }
      for (const group of groups.values()) {
        const allHaveTarget = group.every(
          (e) =>
            (e.data?.arrowheadDirection === 'target' ||
              e.data?.arrowheadDirection === 'both')
        )
        group.forEach((edge, i) => {
          if (!edge.data) return
          const dir = edge.data.arrowheadDirection
          const hasTarget = dir === 'target' || dir === 'both'
          if (allHaveTarget) {
            edge.data = {
              ...edge.data,
              drawTargetArrowhead: i === 0,
            }
          } else {
            edge.data = {
              ...edge.data,
              drawTargetArrowhead: hasTarget,
            }
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
      (type.value === 'brace_map' ||
        type.value === 'tree_map' ||
        type.value === 'bridge_map') &&
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
    if (!data.value?.nodes || !isLearningSheet.value) return

    const d = data.value as Record<string, unknown>

    data.value.nodes.forEach((node, idx) => {
      const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      if (nodeData?.hidden === true && nodeData?.hiddenAnswer) {
        const originalText = nodeData.hiddenAnswer
        data.value!.nodes[idx] = {
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
    if (!data.value?.nodes) return

    const d = data.value as Record<string, unknown>

    data.value.nodes.forEach((node, idx) => {
      const nodeData = node.data as { hidden?: boolean; hiddenAnswer?: string } | undefined
      if (nodeData?.hidden === true && nodeData?.hiddenAnswer) {
        data.value!.nodes[idx] = {
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
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-effect-${effectIndex}`,
          source: 'event',
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
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
        })
      })

      effectNodes.forEach((effectNode, effectIndex) => {
        recalculatedConnections.push({
          id: `edge-effect-${effectIndex}`,
          source: 'event',
          target: effectNode.id,
          sourceHandle: `right-${effectIndex}`,
          targetHandle: 'left',
        })
      })

      // Update nodes and connections (all connection IDs change)
      data.value.nodes = recalculatedNodes
      data.value.connections = recalculatedConnections
      useConceptMapRelationshipStore().clearAll()

      // Trigger layout recalculation
      multiFlowMapRecalcTrigger.value++
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
    const layoutNodes = recalculateBraceMapLayout(
      data.value.nodes,
      data.value.connections ?? []
    )
    data.value.nodes = layoutNodes

    return true
  }

  /**
   * Remove brace map part/subpart nodes and their descendants.
   */
  function removeBraceMapNodes(nodeIds: string[]): number {
    if (type.value !== 'brace_map' || !data.value?.nodes) return 0

    const targetIds = new Set(data.value.connections?.map((c) => c.target) ?? [])
    const rootId = data.value.nodes.find((n) => n.type === 'topic')?.id
      ?? data.value.nodes.find((n) => !targetIds.has(n.id))?.id
    if (!rootId) return 0

    const childrenMap = new Map<string, string[]>()
    data.value.connections?.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      childrenMap.get(c.source)!.push(c.target)
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
      children: [
        { text: `${childText} 1` },
        { text: `${childText} 2` },
      ],
    }

    const allBranches = [
      ...spec.rightBranches,
      ...spec.leftBranches.slice().reverse(),
    ]
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
    nodeIds.forEach((id) => {
      clearCustomPosition(id)
      clearNodeStyle(id)
      removeFromSelection(id)
    })
    pushHistory('Delete nodes')
    emitEvent('diagram:nodes_deleted', { nodeIds })
    return deletedCount
  }

  function reset(): void {
    type.value = null
    sessionId.value = null
    data.value = null
    selectedNodes.value = []
    history.value = []
    historyIndex.value = -1
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
    if (!data.value?.nodes) return

    const isTopic = (node: DiagramNode) => node.type === 'topic' || node.type === 'center'

    data.value.nodes.forEach((node) => {
      if (node.type === 'boundary') return

      const useTopic = isTopic(node)
      const mergedStyle: Partial<NodeStyle> = {
        ...(node.style || {}),
        backgroundColor: useTopic ? preset.topicBackgroundColor : preset.backgroundColor,
        textColor: useTopic ? preset.topicTextColor : preset.textColor,
        borderColor: useTopic ? preset.topicBorderColor : preset.borderColor,
      }
      const nodeIndex = data.value!.nodes.findIndex((n) => n.id === node.id)
      if (nodeIndex !== -1) {
        data.value!.nodes[nodeIndex] = {
          ...data.value!.nodes[nodeIndex],
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
    const simIndices = [...new Set(
      nodes
        .filter((n) => /^similarity-\d+$/.test(n.id))
        .map((n) => parseInt(n.id.replace('similarity-', ''), 10))
    )].sort((a, b) => a - b)
    const leftDiffIndices = [...new Set(
      nodes
        .filter((n) => /^left-diff-\d+$/.test(n.id))
        .map((n) => parseInt(n.id.replace('left-diff-', ''), 10))
    )].sort((a, b) => a - b)
    const rightDiffIndices = [...new Set(
      nodes
        .filter((n) => /^right-diff-\d+$/.test(n.id))
        .map((n) => parseInt(n.id.replace('right-diff-', ''), 10))
    )].sort((a, b) => a - b)
    const similarities = simIndices.map(
      (i) => String(nodes.find((n) => n.id === `similarity-${i}`)?.text ?? '').trim()
    )
    const leftDifferences = leftDiffIndices.map(
      (i) => String(nodes.find((n) => n.id === `left-diff-${i}`)?.text ?? '').trim()
    )
    const rightDifferences = rightDiffIndices.map(
      (i) => String(nodes.find((n) => n.id === `right-diff-${i}`)?.text ?? '').trim()
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
    const simRadii = simIndices.map((i) => getRadius(nodes.find((n) => n.id === `similarity-${i}`)!))
    if (simRadii.some((r) => r != null)) _doubleBubbleMapNodeSizes['simRadii'] = simRadii
    const leftDiffRadii = leftDiffIndices.map((i) =>
      getRadius(nodes.find((n) => n.id === `left-diff-${i}`)!)
    )
    if (leftDiffRadii.some((r) => r != null)) _doubleBubbleMapNodeSizes['leftDiffRadii'] = leftDiffRadii
    const rightDiffRadii = rightDiffIndices.map((i) =>
      getRadius(nodes.find((n) => n.id === `right-diff-${i}`)!)
    )
    if (rightDiffRadii.some((r) => r != null)) _doubleBubbleMapNodeSizes['rightDiffRadii'] = rightDiffRadii

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
    const orientation =
      (data.value as Record<string, unknown>).orientation ?? 'horizontal'
    return { title, steps, substeps, orientation }
  }

  /**
   * Add a new step to flow map.
   */
  function addFlowMapStep(text: string): boolean {
    const spec = buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as string[]
    steps.push(text)
    loadFromSpec({ ...spec, steps }, 'flow_map')
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
    loadFromSpec({ ...spec, substeps }, 'flow_map')
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

    const categoryIdsToRemove = new Set(
      nodeIds.filter((id) => /^tree-cat-\d+$/.test(id))
    )

    const root = spec.root as {
      id?: string
      text: string
      children?: Array<{ id?: string; text: string; children?: Array<{ id?: string; text: string }> }>
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
        ...cat,
        children: (cat.children ?? []).filter((leaf) => {
          if (idsToRemove.has(leaf.id ?? '')) {
            deletedCount++
            return false
          }
          return true
        }),
      }))

    if (deletedCount === 0) return 0

    const newSpec = {
      ...spec,
      root: { ...root, children: newCategories },
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
   * Add a new category to tree map.
   */
  function addTreeMapCategory(text: string): boolean {
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false
    const root = spec.root as { text: string; children?: Array<{ text: string; children?: unknown[] }> }
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
    const root = spec.root as { children?: Array<{ id?: string; text: string; children?: Array<{ text: string }> }> }
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
      const nodeMap = new Map(data.value.nodes.map((n) => [n.id, n]))

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
      const connMap = new Map(
        (data.value.connections || []).map((c) => [`${c.source}-${c.target}`, c])
      )

      for (const updatedConn of updatedConnections) {
        const source = updatedConn.source as string
        const target = updatedConn.target as string
        if (!source || !target) continue

        const key = `${source}-${target}`
        const existingIndex = (data.value.connections || []).findIndex(
          (c) => c.source === source && c.target === target
        )

        if (existingIndex >= 0) {
          // Update existing connection
          data.value.connections![existingIndex] = {
            ...data.value.connections![existingIndex],
            ...updatedConn,
          } as Connection
        } else {
          // Add new connection
          if (!data.value.connections) {
            data.value.connections = []
          }
          data.value.connections.push(updatedConn as unknown as Connection)
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
    removeTreeMapNodes,

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
