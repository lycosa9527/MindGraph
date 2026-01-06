/**
 * Vue Flow Type Definitions for MindGraph
 * Maps diagram types to Vue Flow node/edge structures
 */
import type { Edge, Node, NodeProps } from '@vue-flow/core'

import type { Connection, DiagramNode, DiagramType, NodeStyle } from './diagram'

// Custom node types for different diagram components
export type MindGraphNodeType =
  | 'topic' // Central topic node (non-draggable)
  | 'bubble' // Circular attribute node
  | 'branch' // Mind map branch node
  | 'flow' // Flow map step node
  | 'brace' // Brace map part node
  | 'bridge' // Bridge map pair node
  | 'tree' // Tree map category node
  | 'circle' // Circle map context node
  | 'boundary' // Circle map outer boundary ring (non-interactive)
  | 'label' // Classification dimension label

// Custom edge types
export type MindGraphEdgeType =
  | 'curved' // For mind maps, tree maps
  | 'straight' // For flow maps
  | 'brace' // For brace maps (bracket shape)
  | 'bridge' // For bridge maps (analogy connection)

// Node data structure for Vue Flow
export interface MindGraphNodeData {
  label: string
  nodeType: MindGraphNodeType
  diagramType: DiagramType
  style?: NodeStyle
  parentId?: string
  isDraggable?: boolean
  isSelectable?: boolean
  originalNode?: DiagramNode
  // Additional properties for specific diagram types
  stepNumber?: number // For flow maps
  pairIndex?: number // For bridge maps
  position?: 'top' | 'bottom' // For bridge maps
  // Allow additional custom properties
  [key: string]: unknown
}

// Vue Flow node with MindGraph data
export type MindGraphNode = Node<MindGraphNodeData>

// Edge data structure for Vue Flow
export interface MindGraphEdgeData {
  label?: string
  edgeType: MindGraphEdgeType
  style?: {
    strokeColor?: string
    strokeWidth?: number
    strokeDasharray?: string
  }
  // Additional properties for specific diagram types
  animated?: boolean // For flow maps
  isRelation?: boolean // For bridge maps
  isBridge?: boolean // For bridge maps
  // Allow additional custom properties
  [key: string]: unknown
}

// Vue Flow edge with MindGraph data
export type MindGraphEdge = Edge<MindGraphEdgeData>

// Props for custom node components
export type MindGraphNodeProps = NodeProps<MindGraphNodeData>

// Converter functions
export function diagramNodeToVueFlowNode(
  node: DiagramNode,
  diagramType: DiagramType,
  position?: { x: number; y: number }
): MindGraphNode {
  // For circle maps, use 'circle' type for topic and bubble nodes (perfect circles)
  const isCircleMap = diagramType === 'circle_map'
  
  const nodeTypeMap: Record<string, MindGraphNodeType> = {
    topic: isCircleMap ? 'circle' : 'topic',
    center: isCircleMap ? 'circle' : 'topic',
    child: 'branch',
    bubble: isCircleMap ? 'circle' : 'bubble',
    branch: 'branch',
    left: 'branch',
    right: 'branch',
    boundary: 'boundary',
    flow: 'flow',
    brace: 'brace',
  }

  const mappedType = nodeTypeMap[node.type] || 'branch'
  // Topic, center, and boundary nodes are not draggable
  const isDraggable = !['topic', 'center', 'boundary'].includes(node.type)
  // Boundary nodes are not selectable
  const isSelectable = node.type !== 'boundary'

  // Determine nodeType for data (used by CircleNode to differentiate topic vs context)
  let dataNodeType: MindGraphNodeType = mappedType
  if (isCircleMap && (node.type === 'topic' || node.type === 'center')) {
    dataNodeType = 'topic' // Keep 'topic' in data for CircleNode styling
  }

  // Boundary nodes should render behind other nodes
  const zIndex = node.type === 'boundary' ? -1 : undefined

  // For boundary nodes, set width/height on the node object directly
  // This tells Vue Flow the actual dimensions of the node
  const nodeWidth = node.type === 'boundary' ? node.style?.width : undefined
  const nodeHeight = node.type === 'boundary' ? node.style?.height : undefined

  return {
    id: node.id,
    type: mappedType,
    position: position || node.position || { x: 0, y: 0 },
    zIndex,
    width: nodeWidth,
    height: nodeHeight,
    data: {
      label: node.text,
      nodeType: dataNodeType,
      diagramType,
      style: node.style,
      parentId: node.parentId,
      isDraggable,
      isSelectable,
      originalNode: node,
    },
    draggable: isDraggable,
    selectable: isSelectable,
  }
}

export function connectionToVueFlowEdge(
  connection: Connection,
  edgeType: MindGraphEdgeType = 'curved'
): MindGraphEdge {
  return {
    id: connection.id,
    source: connection.source,
    target: connection.target,
    type: edgeType,
    label: connection.label,
    data: {
      label: connection.label,
      edgeType,
      style: connection.style,
    },
  }
}

export function vueFlowNodeToDiagramNode(node: MindGraphNode): DiagramNode {
  const typeMap: Record<MindGraphNodeType, string> = {
    topic: 'topic',
    bubble: 'bubble',
    branch: 'child',
    flow: 'flow',
    brace: 'brace',
    boundary: 'boundary',
    bridge: 'branch',
    tree: 'branch',
    circle: 'bubble',
    label: 'label',
  }

  const data = node.data
  const nodeType = data?.nodeType ?? 'branch'

  return {
    id: node.id,
    text: data?.label ?? '',
    type: typeMap[nodeType] as DiagramNode['type'],
    position: { x: node.position.x, y: node.position.y },
    style: data?.style,
    parentId: data?.parentId,
  }
}

// Layout configuration for different diagram types
export interface DiagramLayoutConfig {
  type: DiagramType
  centerX: number
  centerY: number
  nodeSpacing: number
  levelSpacing: number
}

// Default layout configurations
export const DEFAULT_LAYOUT_CONFIGS: Partial<Record<DiagramType, Partial<DiagramLayoutConfig>>> = {
  bubble_map: {
    nodeSpacing: 120,
    levelSpacing: 80,
  },
  circle_map: {
    nodeSpacing: 100,
    levelSpacing: 60,
  },
  mindmap: {
    nodeSpacing: 80,
    levelSpacing: 180,
  },
  tree_map: {
    nodeSpacing: 60,
    levelSpacing: 100,
  },
  flow_map: {
    nodeSpacing: 200,
    levelSpacing: 80,
  },
  brace_map: {
    nodeSpacing: 60,
    levelSpacing: 200,
  },
  bridge_map: {
    nodeSpacing: 150,
    levelSpacing: 100,
  },
}
