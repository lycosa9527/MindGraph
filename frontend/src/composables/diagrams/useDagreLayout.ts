/**
 * useDagreLayout - Shared utility for dagre-based graph layout
 *
 * Dagre is a JavaScript library for laying out directed graphs.
 * This utility provides a clean interface for using dagre with VueFlow diagrams.
 *
 * Used by: flow_map, tree_map, brace_map, mindmap, concept_map (hierarchical diagrams)
 */
import dagre from '@dagrejs/dagre'

// ============================================================================
// Types
// ============================================================================

export type LayoutDirection = 'TB' | 'BT' | 'LR' | 'RL'

export interface DagreNodeInput {
  id: string
  width: number
  height: number
}

export interface DagreEdgeInput {
  source: string
  target: string
}

export interface DagreLayoutOptions {
  /** Direction of the layout: TB (top-bottom), BT, LR (left-right), RL */
  direction?: LayoutDirection
  /** Horizontal separation between nodes at the same rank */
  nodeSeparation?: number
  /** Vertical separation between ranks (levels) */
  rankSeparation?: number
  /** Horizontal separation between edges */
  edgeSeparation?: number
  /** Alignment of nodes within their rank: UL, UR, DL, DR */
  align?: 'UL' | 'UR' | 'DL' | 'DR'
  /** Ranking algorithm: network-simplex, tight-tree, longest-path */
  ranker?: 'network-simplex' | 'tight-tree' | 'longest-path'
  /** Margin around the graph */
  marginX?: number
  marginY?: number
}

export interface DagreNodePosition {
  id: string
  /** X position (top-left corner for VueFlow compatibility) */
  x: number
  /** Y position (top-left corner for VueFlow compatibility) */
  y: number
  /** Original width */
  width: number
  /** Original height */
  height: number
}

export interface DagreLayoutResult {
  /** Node positions with top-left corner coordinates (VueFlow compatible) */
  positions: Map<string, DagreNodePosition>
  /** Graph width after layout */
  width: number
  /** Graph height after layout */
  height: number
}

// ============================================================================
// Default Options
// ============================================================================

const DEFAULT_OPTIONS: Required<DagreLayoutOptions> = {
  direction: 'TB',
  nodeSeparation: 50,
  rankSeparation: 80,
  edgeSeparation: 10,
  align: 'UL',
  ranker: 'network-simplex',
  marginX: 20,
  marginY: 20,
}

// ============================================================================
// Layout Function
// ============================================================================

/**
 * Calculate layout positions for a directed graph using dagre
 *
 * @param nodes - Array of nodes with id, width, and height
 * @param edges - Array of edges with source and target node ids
 * @param options - Layout options (direction, spacing, etc.)
 * @returns Map of node positions with VueFlow-compatible coordinates (top-left corner)
 *
 * @example
 * ```ts
 * const nodes = [
 *   { id: 'step-1', width: 140, height: 50 },
 *   { id: 'substep-1a', width: 100, height: 40 },
 *   { id: 'substep-1b', width: 100, height: 40 },
 * ]
 * const edges = [
 *   { source: 'step-1', target: 'substep-1a' },
 *   { source: 'step-1', target: 'substep-1b' },
 * ]
 * const result = calculateDagreLayout(nodes, edges, { direction: 'LR' })
 * // result.positions.get('step-1') => { id: 'step-1', x: 20, y: 45, width: 140, height: 50 }
 * ```
 */
export function calculateDagreLayout(
  nodes: DagreNodeInput[],
  edges: DagreEdgeInput[],
  options: DagreLayoutOptions = {}
): DagreLayoutResult {
  // Merge with defaults
  const opts = { ...DEFAULT_OPTIONS, ...options }

  // Create a new directed graph
  const graph = new dagre.graphlib.Graph()

  // Set graph options
  graph.setGraph({
    rankdir: opts.direction,
    nodesep: opts.nodeSeparation,
    ranksep: opts.rankSeparation,
    edgesep: opts.edgeSeparation,
    align: opts.align,
    ranker: opts.ranker,
    marginx: opts.marginX,
    marginy: opts.marginY,
  })

  // Required for dagre
  graph.setDefaultEdgeLabel(() => ({}))

  // Add nodes
  for (const node of nodes) {
    graph.setNode(node.id, {
      width: node.width,
      height: node.height,
    })
  }

  // Add edges
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target)
  }

  // Run the layout algorithm
  dagre.layout(graph)

  // Extract positions (convert from center to top-left for VueFlow)
  const positions = new Map<string, DagreNodePosition>()

  for (const node of nodes) {
    const dagreNode = graph.node(node.id)
    if (dagreNode) {
      // Dagre returns center coordinates, convert to top-left
      positions.set(node.id, {
        id: node.id,
        x: dagreNode.x - node.width / 2,
        y: dagreNode.y - node.height / 2,
        width: node.width,
        height: node.height,
      })
    }
  }

  // Get graph dimensions
  const graphInfo = graph.graph()
  const width = graphInfo?.width || 0
  const height = graphInfo?.height || 0

  return {
    positions,
    width,
    height,
  }
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Create a simple chain of connected nodes (A -> B -> C)
 * Useful for flow maps where steps connect sequentially
 */
export function createChainEdges(nodeIds: string[]): DagreEdgeInput[] {
  const edges: DagreEdgeInput[] = []
  for (let i = 0; i < nodeIds.length - 1; i++) {
    edges.push({
      source: nodeIds[i],
      target: nodeIds[i + 1],
    })
  }
  return edges
}

/**
 * Create edges from a parent node to multiple child nodes
 * Useful for tree structures
 */
export function createParentChildEdges(parentId: string, childIds: string[]): DagreEdgeInput[] {
  return childIds.map((childId) => ({
    source: parentId,
    target: childId,
  }))
}

/**
 * Get a position from the result, with fallback coordinates
 */
export function getPosition(
  result: DagreLayoutResult,
  nodeId: string,
  fallbackX = 0,
  fallbackY = 0
): { x: number; y: number } {
  const pos = result.positions.get(nodeId)
  if (pos) {
    return { x: pos.x, y: pos.y }
  }
  return { x: fallbackX, y: fallbackY }
}
