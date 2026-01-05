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

import { eventBus } from '@/composables/useEventBus'
import type {
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
  if (!eventSubscribers.has(eventType)) {
    eventSubscribers.set(eventType, new Set())
  }
  eventSubscribers.get(eventType)!.add(callback)

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
  'factor_analysis',
  'three_position_analysis',
  'perspective_analysis',
  'goal_analysis',
  'possibility_analysis',
  'result_analysis',
  'five_w_one_h',
  'whwm_analysis',
  'four_quadrant',
  'diagram',
]

const MAX_HISTORY_SIZE = 50

// Helper to determine edge type based on diagram type
function getEdgeTypeForDiagram(diagramType: DiagramType | null): MindGraphEdgeType {
  if (!diagramType) return 'curved'

  const edgeTypeMap: Partial<Record<DiagramType, MindGraphEdgeType>> = {
    flow_map: 'straight',
    multi_flow_map: 'straight',
    brace_map: 'brace',
    bridge_map: 'bridge',
  }

  return edgeTypeMap[diagramType] || 'curved'
}

export const useDiagramStore = defineStore('diagram', () => {
  // State
  const type = ref<DiagramType | null>(null)
  const sessionId = ref<string | null>(null)
  const data = ref<DiagramData | null>(null)
  const selectedNodes = ref<string[]>([])
  const history = ref<HistoryEntry[]>([])
  const historyIndex = ref(-1)

  // Getters
  const canUndo = computed(() => historyIndex.value > 0)
  const canRedo = computed(() => historyIndex.value < history.value.length - 1)
  const nodeCount = computed(() => data.value?.nodes?.length ?? 0)
  const hasSelection = computed(() => selectedNodes.value.length > 0)
  const selectedNodeData = computed(() => {
    if (!data.value?.nodes || selectedNodes.value.length === 0) return []
    return data.value.nodes.filter((node) => selectedNodes.value.includes(node.id))
  })

  // Vue Flow computed properties
  const vueFlowNodes = computed<MindGraphNode[]>(() => {
    if (!data.value?.nodes || !type.value) return []
    return data.value.nodes.map((node) => diagramNodeToVueFlowNode(node, type.value!))
  })

  const vueFlowEdges = computed<MindGraphEdge[]>(() => {
    if (!data.value?.connections) return []
    const edgeType = getEdgeTypeForDiagram(type.value)
    return data.value.connections.map((conn) => connectionToVueFlowEdge(conn, edgeType))
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

  function updateNode(nodeId: string, updates: Partial<DiagramNode>): boolean {
    if (!data.value?.nodes) return false

    const nodeIndex = data.value.nodes.findIndex((n) => n.id === nodeId)
    if (nodeIndex === -1) return false

    data.value.nodes[nodeIndex] = {
      ...data.value.nodes[nodeIndex],
      ...updates,
    }

    emitEvent('diagram:node_updated', { nodeId, updates })
    return true
  }

  function addNode(node: DiagramNode): void {
    if (!data.value) {
      data.value = { type: type.value || 'mindmap', nodes: [], connections: [] }
    }
    data.value.nodes.push(node)

    emitEvent('diagram:node_added', { node })
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

    data.value.nodes.splice(index, 1)

    // Also remove connections involving this node
    if (data.value.connections) {
      data.value.connections = data.value.connections.filter(
        (c) => c.source !== nodeId && c.target !== nodeId
      )
    }

    // Clean up custom positions and styles for deleted node
    clearCustomPosition(nodeId)
    clearNodeStyle(nodeId)

    // Remove from selection
    removeFromSelection(nodeId)

    emitEvent('diagram:nodes_deleted', { nodeIds: [nodeId] })
    return true
  }

  function reset(): void {
    type.value = null
    sessionId.value = null
    data.value = null
    selectedNodes.value = []
    history.value = []
    historyIndex.value = -1
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
    if (!data.value) return

    vfNodes.forEach((vfNode) => {
      const nodeIndex = data.value!.nodes.findIndex((n) => n.id === vfNode.id)
      if (nodeIndex !== -1 && vfNode.data) {
        data.value!.nodes[nodeIndex] = {
          ...data.value!.nodes[nodeIndex],
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

    // Update connections
    data.value.connections = edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.data?.label,
      style: edge.data?.style,
    }))
  }

  return {
    // State
    type,
    sessionId,
    data,
    selectedNodes,
    history,
    historyIndex,

    // Getters
    canUndo,
    canRedo,
    nodeCount,
    hasSelection,
    selectedNodeData,

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
    updateNode,
    addNode,
    removeNode,
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
  }
})
