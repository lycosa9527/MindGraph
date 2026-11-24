/**
 * Screen-space + handle layouts for brace-map contextual add.
 * The whole sits on the left; parts and deeper nodes grow to the right,
 * and siblings stack top to bottom in connection order.
 */
import type { Connection } from '@/types'
import {
  BRACE_DIMENSION_LABEL_ID,
  isBraceMapPartNode,
  isBraceMapWholeNode,
} from '@/utils/braceMapIdentity'

export type BraceMapAddAction = 'child-append' | 'sibling-before' | 'sibling-after'

export type BraceMapAddSelectionKind = 'whole' | 'member'

export type BraceMapAddHandleLayout = {
  action: BraceMapAddAction
  left: number
  top: number
}

export type BraceMapAddRect = {
  left: number
  top: number
  right: number
  bottom: number
  width: number
  height: number
}

export function resolveBraceMapAddSelectionKind(node: {
  id?: string
  type?: string
}): BraceMapAddSelectionKind | null {
  if (!node.id || node.id === BRACE_DIMENSION_LABEL_ID || node.type === 'label') return null
  if (isBraceMapWholeNode(node)) return 'whole'
  if (isBraceMapPartNode(node)) return 'member'
  return null
}

/** Outgoing targets in connection-array order. That order is the sibling order. */
export function braceChildIds(
  parentId: string,
  connections: ReadonlyArray<Pick<Connection, 'source' | 'target'>>
): string[] {
  const ids: string[] = []
  for (const edge of connections) {
    if (edge.source === parentId) ids.push(edge.target)
  }
  return ids
}

export function braceParentId(
  nodeId: string,
  connections: ReadonlyArray<Pick<Connection, 'source' | 'target'>>
): string | null {
  for (const edge of connections) {
    if (edge.target === nodeId) return edge.source
  }
  return null
}

/**
 * Place + handles around the selected brace node.
 * - Whole: + on the right appends a part.
 * - Member: + above/below inserts a sibling; + on the right adds the next level.
 */
export function layoutBraceMapAddHandles(
  kind: BraceMapAddSelectionKind,
  rect: BraceMapAddRect
): BraceMapAddHandleLayout[] {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  if (kind === 'whole') {
    return [{ action: 'child-append', left: rect.right, top: cy }]
  }
  return [
    { action: 'sibling-before', left: cx, top: rect.top },
    { action: 'child-append', left: rect.right, top: cy },
    { action: 'sibling-after', left: cx, top: rect.bottom },
  ]
}
