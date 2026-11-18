/**
 * Screen-space + handle layouts for double-bubble contextual add.
 * Similarity grows the middle column; difference always adds a left/right pair.
 */
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  type DoubleBubbleRole,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'

export type DoubleBubbleAddAction = 'similarity' | 'difference'

export type DoubleBubbleAddSelectionKind = DoubleBubbleRole | 'leftTopic' | 'rightTopic'

export type DoubleBubbleAddHandleLayout = {
  action: DoubleBubbleAddAction
  left: number
  top: number
}

export type DoubleBubbleAddRect = {
  left: number
  top: number
  right: number
  bottom: number
  width: number
  height: number
}

export function resolveDoubleBubbleAddSelectionKind(node: {
  id?: string
  data?: Record<string, unknown>
}): DoubleBubbleAddSelectionKind | null {
  const id = node.id ?? ''
  if (id === DOUBLE_BUBBLE_LEFT_TOPIC_ID) return 'leftTopic'
  if (id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID) return 'rightTopic'
  return readDoubleBubbleRole(node)
}

/**
 * Place + handles around the selected bubble.
 * - Similarity / difference bubbles: one + below.
 * - Left topic (A): left = difference, right = similarity (outer / toward center).
 * - Right topic (B): left = similarity, right = difference.
 */
export function layoutDoubleBubbleAddHandles(
  kind: DoubleBubbleAddSelectionKind,
  rect: DoubleBubbleAddRect
): DoubleBubbleAddHandleLayout[] {
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  switch (kind) {
    case 'similarity':
    case 'leftDiff':
    case 'rightDiff':
      return [
        {
          action: kind === 'similarity' ? 'similarity' : 'difference',
          left: cx,
          top: rect.bottom,
        },
      ]
    case 'leftTopic':
      return [
        { action: 'difference', left: rect.left, top: cy },
        { action: 'similarity', left: rect.right, top: cy },
      ]
    case 'rightTopic':
      return [
        { action: 'similarity', left: rect.left, top: cy },
        { action: 'difference', left: rect.right, top: cy },
      ]
  }
}
