/**
 * Bubble Map Loader
 *
 * Layout: first child at 0° (top, above topic); even distribution via polar positions.
 * Uses no-overlap formula for circumferential spacing.
 * Circles are text-adaptive (like old D3 bubble-map-renderer): min diameter from text measurement.
 */
import {
  DEFAULT_CONTEXT_RADIUS,
  DEFAULT_PADDING,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'
import { bubbleMapChildrenRadius, polarToPosition } from '@/composables/diagrams/useRadialLayout'
import type { Connection, DiagramNode } from '@/types'

import { CONTEXT_FONT_SIZE, computeMinDiameterForNoWrap } from './textMeasurement'
import type { SpecLoaderResult } from './types'

/**
 * Compute radius for each attribute from text (min diameter for no-wrap fit).
 * Matches old D3 bubble-map-renderer: circles grow to fit text.
 */
function radiusFromText(text: string): number {
  const diameter = computeMinDiameterForNoWrap(text || ' ', CONTEXT_FONT_SIZE, false)
  return Math.max(DEFAULT_CONTEXT_RADIUS, diameter / 2)
}

/**
 * Recalculate bubble map layout from existing nodes.
 * Uses text-adaptive circle sizes; ring radius from max radius for no-overlap.
 */
export function recalculateBubbleMapLayout(nodes: DiagramNode[]): DiagramNode[] {
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
  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING

  const radii = bubbleNodes.map((n) => radiusFromText(n.text))
  const uniformRadius = Math.max(DEFAULT_CONTEXT_RADIUS, ...radii)

  const childrenRadius = bubbleMapChildrenRadius(nodeCount, topicR, uniformRadius, uniformRadius)
  const centerX = childrenRadius + uniformRadius + padding
  const centerY = childrenRadius + uniformRadius + padding

  const result: DiagramNode[] = []

  if (topicNode) {
    result.push({
      ...topicNode,
      position: { x: centerX - topicR, y: centerY - topicR },
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
    result.push({
      ...node,
      position: pos,
      style: {
        ...node.style,
        size: uniformRadius * 2,
        fontSize: CONTEXT_FONT_SIZE,
        noWrap: true,
      },
    })
  })

  return result
}

/**
 * Load bubble map spec into diagram nodes and connections.
 * Circles are text-adaptive: each circle size from computeMinDiameterForNoWrap.
 */
export function loadBubbleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  if (!spec || typeof spec !== 'object') {
    return { nodes: [], connections: [] }
  }

  const topic = (spec.topic as string) || ''
  const attributes = Array.isArray(spec.attributes) ? (spec.attributes as string[]) : []

  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING
  const nodeCount = attributes.length

  const radii = attributes.map((attr) => radiusFromText(attr))
  const uniformRadius =
    nodeCount > 0 ? Math.max(DEFAULT_CONTEXT_RADIUS, ...radii) : DEFAULT_CONTEXT_RADIUS

  const childrenRadius = bubbleMapChildrenRadius(nodeCount, topicR, uniformRadius, uniformRadius)
  const centerX = childrenRadius + uniformRadius + padding
  const centerY = childrenRadius + uniformRadius + padding

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  nodes.push({
    id: 'topic',
    text: topic,
    type: 'topic',
    position: { x: centerX - topicR, y: centerY - topicR },
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
      nodes.push({
        id: `bubble-${index}`,
        text: attr,
        type: 'bubble',
        position: { x: Math.round(x), y: Math.round(y) },
        style: {
          size: uniformDiameter,
          fontSize: CONTEXT_FONT_SIZE,
          noWrap: true,
        },
      })

      connections.push({
        id: `edge-topic-bubble-${index}`,
        source: 'topic',
        target: `bubble-${index}`,
      })
    })
  }

  return { nodes, connections }
}
