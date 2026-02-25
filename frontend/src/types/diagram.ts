/**
 * Diagram Types - Type definitions for MindGraph diagrams
 */

export type DiagramType =
  | 'circle_map'
  | 'bubble_map'
  | 'double_bubble_map'
  | 'tree_map'
  | 'brace_map'
  | 'flow_map'
  | 'multi_flow_map'
  | 'bridge_map'
  | 'concept_map'
  | 'mindmap'
  | 'mind_map'
  | 'diagram'

export type NodeType =
  | 'topic'
  | 'child'
  | 'bubble'
  | 'branch'
  | 'center'
  | 'left'
  | 'right'
  | 'boundary' // Circle map outer boundary ring
  | 'flow' // Flow map step node
  | 'flowSubstep' // Flow map substep node
  | 'brace' // Brace map part node
  | 'label' // Classification dimension label

export interface NodeStyle {
  backgroundColor?: string
  borderColor?: string
  textColor?: string
  fontSize?: number
  fontFamily?: string
  fontWeight?: 'normal' | 'bold'
  fontStyle?: 'normal' | 'italic'
  textDecoration?: 'none' | 'underline' | 'line-through' | 'underline line-through'
  borderWidth?: number
  borderRadius?: number
  // Dimension overrides (for boundary nodes and circle nodes)
  width?: number
  height?: number
  size?: number // Uniform size for perfect circles (diameter)
  minWidth?: number // Minimum width (for multi-flow map visual balance)
  noWrap?: boolean // Prevent text wrapping in circle/bubble nodes
}

export interface Position {
  x: number
  y: number
}

// Base node interface - flat structure with child IDs
export interface DiagramNode {
  id: string
  text: string
  type: NodeType
  position?: Position
  style?: NodeStyle
  childIds?: string[] // Child node IDs for flat storage
  parentId?: string
  data?: Record<string, unknown> // Custom data for specific diagram types
}

// Hierarchical node for tree operations - children are actual nodes
export interface HierarchicalNode extends Omit<DiagramNode, 'childIds'> {
  children?: HierarchicalNode[]
}

// Extended node type for tree layout operations with positions
export interface LayoutNode extends HierarchicalNode {
  x?: number
  y?: number
  children?: LayoutNode[]
}

export interface Connection {
  id: string
  source: string
  target: string
  label?: string
  edgeType?: string // Optional edge type override (e.g., 'step', 'tree', 'straight')
  sourcePosition?: 'top' | 'bottom' | 'left' | 'right' // Handle position on source node
  targetPosition?: 'top' | 'bottom' | 'left' | 'right' // Handle position on target node
  sourceHandle?: string // Specific handle ID on source node
  targetHandle?: string // Specific handle ID on target node
  style?: {
    strokeColor?: string
    strokeWidth?: number
    strokeDasharray?: string
  }
}

export interface DiagramData {
  type: DiagramType
  nodes: DiagramNode[]
  connections: Connection[]
  metadata?: {
    title?: string
    description?: string
    createdAt?: string
    updatedAt?: string
  }
  /** Per-node custom style overrides (persisted across sessions) */
  _node_styles?: Record<string, NodeStyle>
  /** Custom positions set by user dragging (distinct from auto-layout) */
  _customPositions?: Record<string, Position>
  /** Index signature for dynamic property access (e.g., 'attributes', 'steps', etc.) */
  [key: string]: unknown
}

export interface HistoryEntry {
  data: DiagramData
  timestamp: number
  action: string
}

export interface DiagramSession {
  sessionId: string
  type: DiagramType
  data: DiagramData
  createdAt: string
  updatedAt: string
}

/**
 * DiagramSpec is an alias for DiagramData, used in operations/history
 * for compatibility with legacy code patterns.
 */
export type DiagramSpec = DiagramData
