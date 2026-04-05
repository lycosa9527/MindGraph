/**
 * Tree map topic: measured box (matches TopicNode pill + InlineEditableText wrap).
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_PADDING,
  NODE_MIN_DIMENSIONS,
} from '@/composables/diagrams/layoutConfig'
import type { DiagramNode } from '@/types'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelHeight,
  measureRenderedDiagramLabelWidth,
  measureTextDimensions,
  measureTextWidth,
} from './textMeasurement'

/** Max text width cap for topic (matches TopicNode.vue TOPIC_MAX_TEXT_WIDTH) */
export const TREE_MAP_TOPIC_TEXT_BASE_MAX_WIDTH = 300
const BALANCE_PADDING = 5
/** Matches tree_map theme topic font (getNodeStyle topic fallback 18) */
export const TREE_MAP_TOPIC_FONT_SIZE = 18
/** Matches TopicNode px-6 / py-4 */
export const TREE_MAP_TOPIC_PADDING_X = 24
export const TREE_MAP_TOPIC_PADDING_Y = 16
/** Matches theme topicStrokeWidth */
export const TREE_MAP_TOPIC_BORDER_WIDTH = 3

function computeBalancedMaxWidth(text: string): number {
  const cap = TREE_MAP_TOPIC_TEXT_BASE_MAX_WIDTH
  if (typeof document === 'undefined') return cap
  const tw = measureTextWidth(text, TREE_MAP_TOPIC_FONT_SIZE, { fontWeight: 'bold' })
  if (tw <= cap) return cap
  const numLines = Math.ceil(tw / cap)
  return Math.min(Math.ceil(tw / numLines) + BALANCE_PADDING, cap)
}

export function measureTreeMapTopicDimensions(text: string): { width: number; height: number } {
  const t = (text || '').trim() || ' '
  const b = TREE_MAP_TOPIC_BORDER_WIDTH
  const measureOpts = { fontWeight: 'bold' as const }
  const adaptiveMaxW = computeBalancedMaxWidth(t)

  if (diagramLabelLikelyNeedsRenderedMeasure(t)) {
    const contentW = measureRenderedDiagramLabelWidth(t, TREE_MAP_TOPIC_FONT_SIZE, measureOpts)
    const contentH = measureRenderedDiagramLabelHeight(
      t,
      TREE_MAP_TOPIC_FONT_SIZE,
      adaptiveMaxW,
      measureOpts
    )
    return {
      width: Math.max(
        contentW + 2 * TREE_MAP_TOPIC_PADDING_X + 2 * b,
        NODE_MIN_DIMENSIONS.topic.minWidth
      ),
      height: Math.max(
        Math.ceil(contentH) + 2 * TREE_MAP_TOPIC_PADDING_Y + 2 * b,
        NODE_MIN_DIMENSIONS.topic.minHeight
      ),
    }
  }

  const dims = measureTextDimensions(t, TREE_MAP_TOPIC_FONT_SIZE, {
    fontWeight: 'bold',
    paddingX: TREE_MAP_TOPIC_PADDING_X,
    paddingY: TREE_MAP_TOPIC_PADDING_Y,
    maxWidth: adaptiveMaxW,
  })
  return {
    width: Math.max(dims.width + 2 * b, NODE_MIN_DIMENSIONS.topic.minWidth),
    height: Math.max(dims.height + 2 * b, NODE_MIN_DIMENSIONS.topic.minHeight),
  }
}

/** Center topic horizontally; keep top Y from layout */
export function treeMapTopicPositionFromLayout(
  topicWidth: number,
  topicY: number = DEFAULT_PADDING
): { x: number; y: number } {
  return { x: DEFAULT_CENTER_X - topicWidth / 2, y: topicY }
}

export const TREE_MAP_TOPIC_LAYOUT_DEFAULT_HEIGHT = DEFAULT_NODE_HEIGHT

/**
 * Apply measured topic size and shift categories/leaves/dimension label when height changes.
 */
export function applyTreeMapTopicLayoutToNodes(
  nodes: DiagramNode[],
  topicIndex: number,
  mergedTopic: DiagramNode
): DiagramNode[] {
  const oldNode = nodes[topicIndex]
  const dims = measureTreeMapTopicDimensions(mergedTopic.text)
  const oldH = oldNode.style?.height ?? DEFAULT_NODE_HEIGHT
  const deltaY = dims.height - oldH
  const topicY = oldNode.position?.y ?? DEFAULT_PADDING
  const next = [...nodes]
  next[topicIndex] = {
    ...mergedTopic,
    style: { ...oldNode.style, ...mergedTopic.style, width: dims.width, height: dims.height },
    position: { x: DEFAULT_CENTER_X - dims.width / 2, y: topicY },
  }
  if (deltaY === 0) {
    return next
  }
  for (let i = 0; i < next.length; i++) {
    if (i === topicIndex) continue
    const n = next[i]
    if (
      n.id === 'dimension-label' ||
      /^tree-cat-\d+$/.test(n.id ?? '') ||
      /^tree-leaf-\d+-\d+$/.test(n.id ?? '')
    ) {
      const py = n.position?.y ?? 0
      const px = n.position?.x ?? 0
      next[i] = {
        ...n,
        position: { x: px, y: py + deltaY },
      }
    }
  }
  return next
}

/** Saved diagrams without topic dimensions: measure once on load */
export function ensureTreeMapTopicLayout(nodes: DiagramNode[]): DiagramNode[] {
  const topicIdx = nodes.findIndex((n) => n.id === 'tree-topic' && n.type === 'topic')
  if (topicIdx === -1) return nodes
  const topic = nodes[topicIdx]
  if (topic.style?.width != null && topic.style?.height != null) {
    return nodes
  }
  return applyTreeMapTopicLayoutToNodes(nodes, topicIdx, topic)
}
