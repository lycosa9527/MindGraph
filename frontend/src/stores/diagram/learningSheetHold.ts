/**
 * Snapshot the box a node already occupies so 挖空 does not shrink thinking-map layout.
 */
import type { DiagramNode } from '@/types'

export function learningSheetHoldFields(
  nodeId: string,
  node: DiagramNode,
  nodeDimensions: Record<string, { width: number; height: number }>
): Record<string, number> {
  const measured = nodeDimensions[nodeId]
  const style = node.style
  const width =
    measured && measured.width > 0
      ? measured.width
      : typeof style?.width === 'number' && style.width > 0
        ? style.width
        : typeof style?.size === 'number' && style.size > 0
          ? style.size
          : undefined
  const height =
    measured && measured.height > 0
      ? measured.height
      : typeof style?.height === 'number' && style.height > 0
        ? style.height
        : typeof style?.size === 'number' && style.size > 0
          ? style.size
          : undefined
  const fields: Record<string, number> = {}
  if (width !== undefined) fields.learningSheetHoldWidth = width
  if (height !== undefined) fields.learningSheetHoldHeight = height
  return fields
}

export function withoutLearningSheetHold(data: Record<string, unknown>): Record<string, unknown> {
  const next = { ...data }
  delete next.learningSheetHoldWidth
  delete next.learningSheetHoldHeight
  return next
}
