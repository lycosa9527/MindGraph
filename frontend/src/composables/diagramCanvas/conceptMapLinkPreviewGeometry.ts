import { Position } from '@vue-flow/core'

export const TOPIC_NODE_WIDTH = 120
export const TOPIC_NODE_HEIGHT = 50
export const CONCEPT_NODE_WIDTH = 120
export const CONCEPT_NODE_HEIGHT = 50
/** Mind map branch-move drop preview sizing (matches topic vs branch defaults). */
export const BRANCH_MOVE_NODE_WIDTH = 120
export const BRANCH_MOVE_NODE_HEIGHT = 50

export const PILL_HALF_WIDTH = 40
export const PILL_HALF_HEIGHT = 18

export function getConceptNodeCenter(node: {
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

export function getPositionsFromAngle(
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

export function getEdgePoint(
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

export function getConceptNodeEdgePoint(
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
