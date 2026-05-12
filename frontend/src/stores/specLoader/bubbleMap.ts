/**
 * Bubble Map Loader
 *
 * Layout: fixed canvas center (DEFAULT_CENTER_X/Y); topic at center with text-adaptive radius;
 * attribute bubbles on a ring. Single-line, no truncation; circles grow to fit text.
 * Uses mindmap branch color palette for each attribute (like double bubble map).
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_CONTEXT_RADIUS,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'
import { bubbleMapChildrenRadius, polarToPosition } from '@/composables/diagrams/useRadialLayout'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'

import {
  CONTEXT_FONT_SIZE,
  TOPIC_FONT_SIZE,
  calculateBubbleMapRadius,
  computeTopicRadiusForCircleMap,
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelHeight,
  measureRenderedDiagramLabelWidth,
} from './textMeasurement'
import type { SpecLoaderResult } from './types'

function defaultContextBubbleRadiusFromText(text: string): number {
  const trimmed = (text || '').trim() || ' '
  return Math.max(
    DEFAULT_CONTEXT_RADIUS,
    calculateBubbleMapRadius(
      trimmed,
      CONTEXT_FONT_SIZE,
      10,
      DEFAULT_CONTEXT_RADIUS,
      false,
      false,
      DIAGRAM_NODE_FONT_STACK
    )
  )
}

/**
 * Context bubble radius from node text and typography (not DOM box), so font-only edits resize circles.
 */
function bubbleContextRadiusFromNode(node: DiagramNode): number {
  const trimmed = (node.text ?? '').trim() || ' '
  const fs =
    typeof node.style?.fontSize === 'number' ? node.style.fontSize : CONTEXT_FONT_SIZE
  const measureBold = node.style?.fontWeight === 'bold'
  const fontFamily = node.style?.fontFamily ?? DIAGRAM_NODE_FONT_STACK
  const labelOpts = {
    fontWeight: (measureBold ? 'bold' : 'normal') as 'bold' | 'normal',
    fontFamily,
  }

  if (typeof document !== 'undefined' && diagramLabelLikelyNeedsRenderedMeasure(trimmed)) {
    const w = measureRenderedDiagramLabelWidth(trimmed, fs, labelOpts)
    const h = measureRenderedDiagramLabelHeight(trimmed, fs, 1_000_000, labelOpts)
    const diagonal = Math.sqrt(w * w + h * h)
    const radius = Math.ceil(diagonal / 2 + 10)
    return Math.max(DEFAULT_CONTEXT_RADIUS, radius)
  }

  return Math.max(
    DEFAULT_CONTEXT_RADIUS,
    calculateBubbleMapRadius(
      trimmed,
      fs,
      10,
      DEFAULT_CONTEXT_RADIUS,
      false,
      measureBold,
      fontFamily
    )
  )
}

/**
 * Recalculate bubble map layout from existing nodes.
 * Fixed center (DEFAULT_CENTER_X/Y); topic radius from text; topic always at center.
 */
export function recalculateBubbleMapLayout(
  nodes: DiagramNode[],
  _nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) return []

  const topicNode = nodes.find((n) => n.type === 'topic' || n.type === 'center')
  const bubbleNodes = nodes
    .filter((n) => n.type === 'bubble' || n.type === 'child')
    .sort((a, b) => {
      const i = parseInt(a.id.replace(/^bubble-/, ''), 10)
      const j = parseInt(b.id.replace(/^bubble-/, ''), 10)
      if (Number.isNaN(i) || Number.isNaN(j)) return 0
      return i - j
    })
  const nodeCount = bubbleNodes.length
  const topicText = topicNode?.text ?? ''
  const topicStyle = topicNode?.style
  const topicR = Math.max(
    DEFAULT_TOPIC_RADIUS,
    computeTopicRadiusForCircleMap(topicText || ' ', {
      fontSize: typeof topicStyle?.fontSize === 'number' ? topicStyle.fontSize : undefined,
      fontWeight: topicStyle?.fontWeight,
      fontFamily: topicStyle?.fontFamily,
    })
  )
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y

  const radii = bubbleNodes.map((n) => bubbleContextRadiusFromNode(n))
  const uniformRadius =
    bubbleNodes.length > 0 ? Math.max(DEFAULT_CONTEXT_RADIUS, ...radii) : DEFAULT_CONTEXT_RADIUS

  const childrenRadius = bubbleMapChildrenRadius(nodeCount, topicR, uniformRadius, uniformRadius)

  const result: DiagramNode[] = []

  if (topicNode) {
    const { noWrap: _noWrap, ...restStyle } = topicNode.style ?? {}
    result.push({
      ...topicNode,
      position: { x: Math.round(centerX - topicR), y: Math.round(centerY - topicR) },
      style: {
        ...restStyle,
        size: topicR * 2,
        fontSize: restStyle.fontSize ?? TOPIC_FONT_SIZE,
      },
    })
  }

  bubbleNodes.forEach((node, index) => {
    const { x, y } = polarToPosition(
      index,
      nodeCount,
      centerX,
      centerY,
      childrenRadius,
      uniformRadius,
      uniformRadius
    )
    const pos = { x: Math.round(x), y: Math.round(y) }
    const color = getMindmapBranchColor(index)
    result.push({
      ...node,
      position: pos,
      data: { ...node.data, groupIndex: index },
      style: {
        ...node.style,
        size: uniformRadius * 2,
        fontSize: node.style?.fontSize ?? CONTEXT_FONT_SIZE,
        noWrap: true,
        backgroundColor: color.fill,
        borderColor: color.border,
      },
    })
  })

  return result
}

/**
 * Load bubble map spec into diagram nodes and connections.
 * Fixed center; topic radius from text (single-line, no truncation); topic always at center.
 */
export function loadBubbleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  if (!spec || typeof spec !== 'object') {
    return { nodes: [], connections: [] }
  }

  const topic = (spec.topic as string) || ''
  const attributes = Array.isArray(spec.attributes) ? (spec.attributes as string[]) : []

  const topicR = Math.max(DEFAULT_TOPIC_RADIUS, computeTopicRadiusForCircleMap(topic || ' '))
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const nodeCount = attributes.length

  const radii = attributes.map((attr) => defaultContextBubbleRadiusFromText(attr))
  const uniformRadius =
    nodeCount > 0 ? Math.max(DEFAULT_CONTEXT_RADIUS, ...radii) : DEFAULT_CONTEXT_RADIUS

  const childrenRadius = bubbleMapChildrenRadius(nodeCount, topicR, uniformRadius, uniformRadius)

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  nodes.push({
    id: 'topic',
    text: topic,
    type: 'topic',
    position: { x: Math.round(centerX - topicR), y: Math.round(centerY - topicR) },
    style: {
      size: topicR * 2,
      fontSize: TOPIC_FONT_SIZE,
    },
  })

  if (nodeCount > 0) {
    const uniformDiameter = uniformRadius * 2
    attributes.forEach((attr, index) => {
      const { x, y } = polarToPosition(
        index,
        nodeCount,
        centerX,
        centerY,
        childrenRadius,
        uniformRadius,
        uniformRadius
      )
      const color = getMindmapBranchColor(index)
      nodes.push({
        id: `bubble-${index}`,
        text: attr,
        type: 'bubble',
        position: { x: Math.round(x), y: Math.round(y) },
        data: { groupIndex: index },
        style: {
          size: uniformDiameter,
          fontSize: CONTEXT_FONT_SIZE,
          noWrap: true,
          backgroundColor: color.fill,
          borderColor: color.border,
        },
      })

      connections.push({
        id: `edge-topic-bubble-${index}`,
        source: 'topic',
        target: `bubble-${index}`,
        style: { strokeColor: color.border },
      })
    })
  }

  return { nodes, connections }
}
