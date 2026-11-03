/**
 * Flow U-turn.
 * The arrow leaves the outer side of the last step, runs past it,
 * drops, then comes back into the first step of the next row.
 */
import { FLOW_TURN_OUTSET_PX } from '@/composables/diagrams/layoutConfig'

export interface FlowTurnPath {
  edgePath: string
  labelX: number
  labelY: number
}

export function flowTurnEdgePath(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  side: 'left' | 'right',
  arrowOffset: number
): FlowTurnPath {
  const outward = side === 'right' ? 1 : -1
  const outerX = side === 'right' ? Math.max(sourceX, targetX) : Math.min(sourceX, targetX)
  const railX = outerX + outward * FLOW_TURN_OUTSET_PX
  const span = Math.abs(targetX - railX)
  const endX = span > arrowOffset ? targetX - Math.sign(targetX - railX) * arrowOffset : targetX
  return {
    edgePath: `M ${sourceX} ${sourceY} L ${railX} ${sourceY} L ${railX} ${targetY} L ${endX} ${targetY}`,
    labelX: railX,
    labelY: (sourceY + targetY) / 2,
  }
}
