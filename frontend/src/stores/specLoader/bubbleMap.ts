/**
 * Bubble Map Loader
 */
import {
  DEFAULT_BUBBLE_RADIUS,
  DEFAULT_PADDING,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'

/**
 * Load bubble map spec into diagram nodes and connections
 *
 * @param spec - Bubble map spec with topic and attributes array
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadBubbleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  if (!spec || typeof spec !== 'object') {
    return { nodes: [], connections: [] }
  }

  const topic = (spec.topic as string) || ''
  const attributes = Array.isArray(spec.attributes) ? (spec.attributes as string[]) : []

  // Layout constants from layoutConfig
  const uniformAttributeR = DEFAULT_BUBBLE_RADIUS
  const topicR = DEFAULT_TOPIC_RADIUS
  const padding = DEFAULT_PADDING

  // Dynamic layout calculation (matching old JS: topicR + uniformAttributeR + 50)
  const nodeCount = attributes.length
  const targetDistance = topicR + uniformAttributeR + 50

  // Circumferential constraint for many nodes
  const spacingMultiplier = nodeCount <= 3 ? 2.0 : nodeCount <= 6 ? 2.05 : 2.1
  const circumferentialMinRadius =
    nodeCount > 0 ? (uniformAttributeR * nodeCount * spacingMultiplier) / (2 * Math.PI) : 0

  // Use the larger of both constraints (minimum 100px)
  const childrenRadius = Math.max(targetDistance, circumferentialMinRadius, 100)

  // Dynamic canvas center
  const centerX = childrenRadius + uniformAttributeR + padding
  const centerY = childrenRadius + uniformAttributeR + padding

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Topic node - perfect circle (uses CircleNode)
  nodes.push({
    id: 'topic',
    text: topic,
    type: 'topic',
    position: { x: centerX - topicR, y: centerY - topicR },
  })

  // Attribute bubbles arranged in a circle
  // Start from top (-90 degrees) with even angle distribution
  // Handle division by zero case
  if (nodeCount > 0) {
    attributes.forEach((attr, index) => {
      const angleDeg = (index * 360) / nodeCount - 90 // Start from top
      const angleRad = (angleDeg * Math.PI) / 180

      // Position at childrenRadius from center
      const x = centerX + childrenRadius * Math.cos(angleRad) - uniformAttributeR
      const y = centerY + childrenRadius * Math.sin(angleRad) - uniformAttributeR

      nodes.push({
        id: `bubble-${index}`,
        text: attr,
        type: 'bubble',
        position: { x, y },
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
