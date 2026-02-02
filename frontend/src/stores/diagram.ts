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
import { MULTI_FLOW_MAP_TOPIC_WIDTH } from '@/composables/diagrams/layoutConfig'

import {
  getDefaultTemplate,
  loadSpecForDiagramType,
  recalculateCircleMapLayout,
  recalculateMultiFlowMapLayout,
} from './specLoader'

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
  // Mindmaps use straight edges with dynamic handles
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    return 'straight'
  }
  if (!diagramType) return 'curved'

  const edgeTypeMap: Partial<Record<DiagramType, MindGraphEdgeType>> = {
    bubble_map: 'radial', // Center-to-center straight lines for radial layout
    double_bubble_map: 'radial', // Center-to-center straight lines for radial layout
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
    const diagramType = type.value
    if (!data.value?.nodes || !diagramType) return []

    // For circle maps, recalculate layout to ensure boundary and positions are correct
    // This makes the layout adaptive when nodes are added/deleted
    if (diagramType === 'circle_map') {
      const recalculatedNodes = recalculateCircleMapLayout(data.value.nodes)
      return recalculatedNodes.map((node) => diagramNodeToVueFlowNode(node, diagramType))
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

    // For mindmaps, ensure branch counts are passed through from node.data
    // (They should already be set by specLoader, but ensure they're preserved)
    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      return data.value.nodes.map((node) => {
        const vueFlowNode = diagramNodeToVueFlowNode(node, diagramType)
        // Branch counts should already be in node.data from specLoader
        // This ensures they're preserved in vueFlowNode.data
        return vueFlowNode
      })
    }

    return data.value.nodes.map((node) => diagramNodeToVueFlowNode(node, diagramType))
  })

  const vueFlowEdges = computed<MindGraphEdge[]>(() => {
    // Circle maps have NO edges (no connection lines)
    if (type.value === 'circle_map') return []

    if (!data.value?.connections) return []
    const defaultEdgeType = getEdgeTypeForDiagram(type.value)
    return data.value.connections.map((conn) => {
      // Use connection's edgeType if specified, otherwise use diagram default
      const edgeType = (conn.edgeType as MindGraphEdgeType) || defaultEdgeType
      return connectionToVueFlowEdge(conn, edgeType)
    })
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
    } else {
      // Standard add for other diagram types
      data.value.nodes.push(node)
    }

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

    // For multi-flow maps, rebuild layout after deletion to re-index IDs
    if (type.value === 'multi_flow_map') {
      // Clear the deleted node's width from nodeWidths
      setNodeWidth(nodeId, null)
      
      // Remove the node first
      data.value.nodes.splice(index, 1)
      
      // Rebuild nodeWidths mapping to match new sequential IDs after re-indexing
      // Map old nodes to their widths before recalculation
      const oldCauseNodes = data.value.nodes.filter((n) => n.id.startsWith('cause-')).sort((a, b) => {
        const aIndex = parseInt(a.id.replace('cause-', ''), 10)
        const bIndex = parseInt(b.id.replace('cause-', ''), 10)
        return aIndex - bIndex
      })
      const oldEffectNodes = data.value.nodes.filter((n) => n.id.startsWith('effect-')).sort((a, b) => {
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
      
      // Update nodes and connections
      data.value.nodes = recalculatedNodes
      data.value.connections = recalculatedConnections
      
      // Trigger layout recalculation
      multiFlowMapRecalcTrigger.value++
    } else {
      // Standard deletion for other diagram types
      data.value.nodes.splice(index, 1)

      // Also remove connections involving this node
      if (data.value.connections) {
        data.value.connections = data.value.connections.filter(
          (c) => c.source !== nodeId && c.target !== nodeId
        )
      }
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

    // Update connections
    data.value.connections = edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.data?.label,
      style: edge.data?.style,
    }))
  }

  /**
   * Load diagram from API spec response
   * Converts API spec format to DiagramData format
   * Uses specLoader for diagram-type-specific conversion
   */
  function loadFromSpec(spec: Record<string, unknown>, diagramTypeValue: DiagramType): boolean {
    if (!spec || !diagramTypeValue) return false

    // Set diagram type
    if (!setDiagramType(diagramTypeValue)) return false

    // Use spec loader for diagram-type-specific conversion
    const result = loadSpecForDiagramType(spec, diagramTypeValue)

    // Initialize multi-flow map topic width if needed
    if (diagramTypeValue === 'multi_flow_map') {
      topicNodeWidth.value = MULTI_FLOW_MAP_TOPIC_WIDTH
    }

    // Create diagram data
    data.value = {
      type: diagramTypeValue,
      nodes: result.nodes,
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

    return true
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
    // Extract steps and substeps from current nodes
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
      steps,
      substeps,
      orientation: newOrientation,
    }

    loadFromSpec(newSpec, 'flow_map')
    pushHistory(`Toggle orientation to ${newOrientation}`)
    emitEvent('diagram:orientation_changed', { orientation: newOrientation })
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

    // Getters
    canUndo,
    canRedo,
    nodeCount,
    hasSelection,
    selectedNodeData,
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

    // Spec loading
    loadFromSpec,
    loadDefaultTemplate,
    mergeGranularUpdate,

    // Flow map orientation
    toggleFlowMapOrientation,

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
