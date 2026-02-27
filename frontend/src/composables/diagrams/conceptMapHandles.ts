/**
 * conceptMapHandles - Smart handle selection for concept map edges
 * Chooses the most adjacent handles based on relative node positions
 * so connection lines stay clean when users drag nodes around
 */
import { DEFAULT_NODE_HEIGHT, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'

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
