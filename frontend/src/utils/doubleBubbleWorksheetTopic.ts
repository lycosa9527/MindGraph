/**
 * Worksheet / export topic line for double-bubble maps: Compare "A" and "B".
 */
import type { DiagramNode } from '@/types'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
} from '@/utils/doubleBubbleMapIdentity'

function topicLabel(node: DiagramNode | undefined): string {
  if (!node) return ''
  return String(node.text ?? (node.data as { label?: string } | undefined)?.label ?? '').trim()
}

export function readDoubleBubbleTopicPair(
  nodes: readonly DiagramNode[] | null | undefined
): { left: string; right: string } | null {
  if (!nodes?.length) return null
  const left = topicLabel(nodes.find((node) => node.id === DOUBLE_BUBBLE_LEFT_TOPIC_ID))
  const right = topicLabel(nodes.find((node) => node.id === DOUBLE_BUBBLE_RIGHT_TOPIC_ID))
  if (!left && !right) return null
  return { left, right }
}

/** Returns null when the diagram has no usable topic pair. */
export function formatDoubleBubbleWorksheetTopic(
  nodes: readonly DiagramNode[] | null | undefined,
  format: (left: string, right: string) => string
): string | null {
  const pair = readDoubleBubbleTopicPair(nodes)
  if (!pair) return null
  if (pair.left && pair.right) return format(pair.left, pair.right)
  return pair.left || pair.right
}
