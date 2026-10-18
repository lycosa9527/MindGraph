import type { DiagramNode } from '@/types'

import {
  recalculateBraceMapLayout,
  recalculateBridgeMapLayout,
  recalculateBubbleMapLayout,
  recalculateCircleMapLayout,
} from '../specLoader'
import type { DiagramContext } from './types'

/**
 * Circle, bubble, brace, and bridge paints come from a layout pass.
 * Delete used to splice the node and leave every survivor on its old
 * coordinate, so the stored diagram still had a hole.
 */
const PACKED_ON_DELETE = new Set(['circle_map', 'bubble_map', 'brace_map', 'bridge_map'])

function laidOutNodes(ctx: DiagramContext): DiagramNode[] | null {
  const data = ctx.data.value
  const diagramType = ctx.type.value
  if (!data?.nodes || !diagramType) return null
  const dimensions = ctx.nodeDimensions.value
  if (diagramType === 'circle_map') return recalculateCircleMapLayout(data.nodes, dimensions)
  if (diagramType === 'bubble_map') return recalculateBubbleMapLayout(data.nodes, dimensions)
  if (diagramType === 'brace_map') {
    return recalculateBraceMapLayout(data.nodes, data.connections ?? [], dimensions)
  }
  if (diagramType === 'bridge_map') return recalculateBridgeMapLayout(data.nodes, dimensions)
  return null
}

function samePoint(
  left: { x: number; y: number } | undefined,
  right: { x: number; y: number }
): boolean {
  return left != null && left.x === right.x && left.y === right.y
}

/** Drop measurements for removed ids and write the packed layout back onto the store. */
export function commitDeleteLayout(ctx: DiagramContext, removedIds: readonly string[]): void {
  const data = ctx.data.value
  if (!data?.nodes || removedIds.length === 0) return

  let dimensionsChanged = false
  for (const id of removedIds) {
    if (!(id in ctx.nodeDimensions.value)) continue
    delete ctx.nodeDimensions.value[id]
    dimensionsChanged = true
  }

  const diagramType = ctx.type.value
  if (!diagramType || !PACKED_ON_DELETE.has(diagramType)) {
    if (dimensionsChanged) ctx.layoutRecalcTrigger.value += 1
    return
  }

  const laidOut = laidOutNodes(ctx)
  if (!laidOut || laidOut.length === 0) return
  const byId = new Map(laidOut.map((node) => [node.id, node]))
  let moved = false
  const nextNodes = data.nodes.map((node) => {
    const laid = byId.get(node.id)
    if (!laid?.position) return node
    const positionMatches = samePoint(node.position, laid.position)
    if (positionMatches && laid.data === node.data) return node
    moved = true
    return {
      ...node,
      position: { x: laid.position.x, y: laid.position.y },
      ...(laid.data ? { data: laid.data } : {}),
    }
  })
  if (moved) data.nodes = nextNodes
  if (moved || dimensionsChanged) ctx.layoutRecalcTrigger.value += 1
}
