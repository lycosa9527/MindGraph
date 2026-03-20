/**
 * conceptMapHandles - Smart handle selection for concept map edges
 * Chooses the most adjacent handles based on relative node positions
 * so connection lines stay clean when users drag nodes around
 */
import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode, MindGraphEdge } from '@/types'

type Position = 'top' | 'bottom' | 'left' | 'right'

interface HandleResult {
  sourcePosition: Position
  targetPosition: Position
  sourceHandle: string
  targetHandle: string
}

const TOPIC_NODE_WIDTH = 120
const TOPIC_NODE_HEIGHT = 50

function getNodeCenter(node: DiagramNode): { x: number; y: number } {
  const isTopic = node.type === 'topic' || node.type === 'center'
  const w = isTopic ? TOPIC_NODE_WIDTH : DEFAULT_NODE_WIDTH
  const h = isTopic ? TOPIC_NODE_HEIGHT : DEFAULT_NODE_HEIGHT
  const x = (node.position?.x ?? 0) + w / 2
  const y = (node.position?.y ?? 0) + h / 2
  return { x, y }
}

/** Get center of a concept map node for arrowhead computation. */
export function getConceptMapNodeCenter(node: DiagramNode): { x: number; y: number } {
  return getNodeCenter(node)
}

/**
 * Compute optimal handle positions for an edge based on relative node positions.
 * Picks the source/target sides that face each other for the cleanest path.
 */
export function computeOptimalConnectionHandles(
  nodes: DiagramNode[],
  sourceId: string,
  targetId: string
): HandleResult | null {
  const sourceNode = nodes.find((n) => n.id === sourceId)
  const targetNode = nodes.find((n) => n.id === targetId)
  if (!sourceNode || !targetNode) return null

  const sc = getNodeCenter(sourceNode)
  const tc = getNodeCenter(targetNode)

  const dx = tc.x - sc.x
  const dy = tc.y - sc.y

  const angle = Math.atan2(dy, dx)
  const deg = (angle * 180) / Math.PI

  let sourcePosition: Position
  let targetPosition: Position

  if (deg >= -45 && deg < 45) {
    sourcePosition = 'right'
    targetPosition = 'left'
  } else if (deg >= 45 && deg < 135) {
    sourcePosition = 'bottom'
    targetPosition = 'top'
  } else if (deg >= 135 || deg < -135) {
    sourcePosition = 'left'
    targetPosition = 'right'
  } else {
    sourcePosition = 'top'
    targetPosition = 'bottom'
  }

  return {
    sourcePosition,
    targetPosition,
    sourceHandle: `source-${sourcePosition}`,
    targetHandle: `target-${targetPosition}`,
  }
}

/**
 * Augment a connection with optimal handle positions for concept_map.
 */
export function augmentConnectionWithOptimalHandles(
  conn: Connection,
  nodes: DiagramNode[]
): Connection {
  const handles = computeOptimalConnectionHandles(nodes, conn.source, conn.target)
  if (!handles) return conn

  return {
    ...conn,
    sourcePosition: handles.sourcePosition,
    targetPosition: handles.targetPosition,
    sourceHandle: handles.sourceHandle,
    targetHandle: handles.targetHandle,
  }
}

/**
 * CmapTools-style default arrowhead: arrow on target when link goes upward or same Y,
 * no arrow when link goes downward or parallel (target below source).
 * Returns 'target' for arrow on new node side, 'none' otherwise.
 */
export function computeDefaultArrowheadForConceptMap(
  sourceCenter: { x: number; y: number },
  targetCenter: { x: number; y: number }
): 'target' | 'none' {
  return targetCenter.y <= sourceCenter.y ? 'target' : 'none'
}

function edgeHasTargetArrow(edge: MindGraphEdge): boolean {
  const dir = edge.data?.arrowheadDirection
  return dir === 'target' || dir === 'both'
}

function edgeHasSourceArrow(edge: MindGraphEdge): boolean {
  const dir = edge.data?.arrowheadDirection
  return dir === 'source' || dir === 'both'
}

type Side = 'left' | 'right' | 'top' | 'bottom'

function extractSide(handle: string): Side {
  if (handle.includes('left')) return 'left'
  if (handle.includes('right')) return 'right'
  if (handle.includes('top')) return 'top'
  return 'bottom'
}

/**
 * Average the spatial coordinate of connected nodes that's relevant to the
 * handle side. For L/R handles, compare Y positions; for T/B, compare X.
 */
function groupAvgCoord(
  edges: MindGraphEdge[],
  connField: 'source' | 'target',
  nodes: DiagramNode[],
  side: Side
): number {
  let sum = 0
  let count = 0
  for (const edge of edges) {
    const nodeId = connField === 'source' ? edge.source : edge.target
    const node = nodes.find((n) => n.id === nodeId)
    if (!node) continue
    const center = getNodeCenter(node)
    sum += side === 'left' || side === 'right' ? center.y : center.x
    count++
  }
  return count > 0 ? sum / count : 0
}

/**
 * Split edges that share a handle but have mixed arrow states into separate handles.
 *
 * Rules:
 * - All edges on a handle have arrows → share (keep same handle)
 * - All edges on a handle have NO arrows → share (keep same handle)
 * - Mixed → split into two offset handles (-2 and -3) on opposite sides of center
 *
 * The offset direction is chosen based on where the connected nodes are:
 * the group whose connected nodes are spatially "above/left" gets the -2 handle
 * (offset toward start), and the other gets -3 (offset toward end). This ensures
 * curves lean toward their endpoints and don't cross each other.
 */
export function splitMixedArrowHandleGroups(edges: MindGraphEdge[], nodes: DiagramNode[]): void {
  splitByTargetHandle(edges, nodes)
  splitBySourceHandle(edges, nodes)
}

function splitByTargetHandle(edges: MindGraphEdge[], nodes: DiagramNode[]): void {
  const groups = new Map<string, MindGraphEdge[]>()
  for (const edge of edges) {
    const key = `${edge.target}:${edge.targetHandle ?? ''}`
    if (!groups.has(key)) groups.set(key, [])
    const targetGroup = groups.get(key)
    if (targetGroup) {
      targetGroup.push(edge)
    }
  }

  for (const group of groups.values()) {
    if (group.length <= 1) continue
    const withArrow = group.filter(edgeHasTargetArrow)
    const withoutArrow = group.filter((e) => !edgeHasTargetArrow(e))
    if (withArrow.length === 0 || withoutArrow.length === 0) continue

    const side = extractSide(group[0].targetHandle ?? '')
    const arrowAvg = groupAvgCoord(withArrow, 'source', nodes, side)
    const noArrowAvg = groupAvgCoord(withoutArrow, 'source', nodes, side)

    const arrowSuffix = arrowAvg <= noArrowAvg ? '-2' : '-3'
    const noArrowSuffix = arrowAvg <= noArrowAvg ? '-3' : '-2'

    for (const edge of withArrow) {
      if (edge.targetHandle) edge.targetHandle = `${edge.targetHandle}${arrowSuffix}`
    }
    for (const edge of withoutArrow) {
      if (edge.targetHandle) edge.targetHandle = `${edge.targetHandle}${noArrowSuffix}`
    }
  }
}

function splitBySourceHandle(edges: MindGraphEdge[], nodes: DiagramNode[]): void {
  const groups = new Map<string, MindGraphEdge[]>()
  for (const edge of edges) {
    const key = `${edge.source}:${edge.sourceHandle ?? ''}`
    if (!groups.has(key)) groups.set(key, [])
    const targetGroup = groups.get(key)
    if (targetGroup) {
      targetGroup.push(edge)
    }
  }

  for (const group of groups.values()) {
    if (group.length <= 1) continue
    const withArrow = group.filter(edgeHasSourceArrow)
    const withoutArrow = group.filter((e) => !edgeHasSourceArrow(e))
    if (withArrow.length === 0 || withoutArrow.length === 0) continue

    const side = extractSide(group[0].sourceHandle ?? '')
    const arrowAvg = groupAvgCoord(withArrow, 'target', nodes, side)
    const noArrowAvg = groupAvgCoord(withoutArrow, 'target', nodes, side)

    const arrowSuffix = arrowAvg <= noArrowAvg ? '-2' : '-3'
    const noArrowSuffix = arrowAvg <= noArrowAvg ? '-3' : '-2'

    for (const edge of withArrow) {
      if (edge.sourceHandle) edge.sourceHandle = `${edge.sourceHandle}${arrowSuffix}`
    }
    for (const edge of withoutArrow) {
      if (edge.sourceHandle) edge.sourceHandle = `${edge.sourceHandle}${noArrowSuffix}`
    }
  }
}
