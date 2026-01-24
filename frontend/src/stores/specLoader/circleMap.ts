/**
 * Circle Map Loader
 * Circle maps have: central topic circle, context circles around it, outer boundary ring
 * NO connection lines between nodes (unlike bubble maps)
 */
import type { Connection, DiagramNode } from '@/types'

import type { SpecLoaderResult } from './types'
import { calculateAdaptiveCircleSize, calculateCircleMapLayout } from './utils'

/**
 * Recalculate circle map layout from existing nodes
 * Called when nodes are added/deleted to update boundary and positions
 * Preserves adaptive sizes based on text content
 *
 * @param nodes - Current diagram nodes
 * @returns Recalculated nodes with updated positions
 */
export function recalculateCircleMapLayout(nodes: DiagramNode[]): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return []
  }

  // Find topic node and context nodes
  const topicNode = nodes.find((n) => n.type === 'topic' || n.type === 'center')
  const contextNodes = nodes.filter((n) => n.type === 'bubble' && n.id.startsWith('context-'))
  const nodeCount = contextNodes.length

  // Get context texts for adaptive sizing
  const contextTexts = contextNodes.map((n) => n.text)

  // Calculate layout based on current node count and context texts
  const layout = calculateCircleMapLayout(nodeCount, contextTexts)

  const result: DiagramNode[] = []

  // Outer boundary node (giant outer circle) - always recreate with correct size
  result.push({
    id: 'outer-boundary',
    text: '',
    type: 'boundary',
    position: { x: layout.centerX - layout.outerCircleR, y: layout.centerY - layout.outerCircleR },
    style: { width: layout.outerCircleR * 2, height: layout.outerCircleR * 2 },
  })

  // Topic node - centered with adaptive size
  if (topicNode) {
    const topicSize = calculateAdaptiveCircleSize(topicNode.text, true)
    const topicRadius = topicSize / 2
    result.push({
      id: 'topic',
      text: topicNode.text,
      type: 'center',
      position: { x: layout.centerX - topicRadius, y: layout.centerY - topicRadius },
      style: { size: topicSize },
    })
  }

  // Context nodes - evenly distributed around with adaptive size based on text length
  // Preserve existing sizes if already set, otherwise calculate adaptively
  // Handle division by zero case
  if (nodeCount > 0) {
    contextNodes.forEach((node, index) => {
      const angleDeg = (index * 360) / nodeCount - 90
      const angleRad = (angleDeg * Math.PI) / 180
      // Use existing size if set, otherwise calculate adaptive size based on text length
      const contextSize = node.style?.size || calculateAdaptiveCircleSize(node.text, false)
      const contextRadius = contextSize / 2
      const x = layout.centerX + layout.childrenRadius * Math.cos(angleRad) - contextRadius
      const y = layout.centerY + layout.childrenRadius * Math.sin(angleRad) - contextRadius

      result.push({
        id: `context-${index}`,
        text: node.text,
        type: 'bubble',
        position: { x, y },
        style: { size: contextSize },
      })
    })
  }

  return result
}

/**
 * Load circle map spec into diagram nodes and connections
 *
 * @param spec - Circle map spec with topic and context array
 * @returns SpecLoaderResult with nodes and empty connections array
 */
export function loadCircleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  if (!spec || typeof spec !== 'object') {
    return { nodes: [], connections: [] }
  }

  const topic = (spec.topic as string) || ''
  const context = Array.isArray(spec.context) ? (spec.context as string[]) : []
  const nodeCount = context.length

  // Calculate layout using shared utility with context texts for adaptive sizing
  const layout = calculateCircleMapLayout(nodeCount, context)

  const nodes: DiagramNode[] = []
  // Circle maps have NO connections (no lines between nodes)
  const connections: Connection[] = []

  // Outer boundary node (giant outer circle)
  nodes.push({
    id: 'outer-boundary',
    text: '',
    type: 'boundary',
    position: { x: layout.centerX - layout.outerCircleR, y: layout.centerY - layout.outerCircleR },
    style: { width: layout.outerCircleR * 2, height: layout.outerCircleR * 2 },
  })

  // Topic node - perfect circle at center
  // Use 'center' type which maps to 'circle' in vueflow
  const topicSize = calculateAdaptiveCircleSize(topic, true)
  const topicRadius = topicSize / 2
  nodes.push({
    id: 'topic',
    text: topic,
    type: 'center', // Maps to 'circle' node type for perfect circle rendering
    position: { x: layout.centerX - topicRadius, y: layout.centerY - topicRadius },
    style: { size: topicSize }, // Adaptive diameter based on text length
  })

  // Context nodes - perfect circles distributed around with adaptive size based on text length
  // Handle division by zero case
  if (nodeCount > 0) {
    context.forEach((ctx, index) => {
      const angleDeg = (index * 360) / nodeCount - 90
      const angleRad = (angleDeg * Math.PI) / 180
      // Calculate adaptive size for each context node based on text length
      const contextSize = calculateAdaptiveCircleSize(ctx, false)
      const contextRadius = contextSize / 2
      const x = layout.centerX + layout.childrenRadius * Math.cos(angleRad) - contextRadius
      const y = layout.centerY + layout.childrenRadius * Math.sin(angleRad) - contextRadius

      nodes.push({
        id: `context-${index}`,
        text: ctx,
        type: 'bubble', // Maps to 'circle' node type for circle maps
        position: { x, y },
        style: { size: contextSize }, // Adaptive diameter based on text length
      })
      // NO connection created - circle maps have no lines
    })
  }

  return {
    nodes,
    connections, // Empty - no connections for circle maps
    metadata: {
      _circleMapLayout: {
        centerX: layout.centerX,
        centerY: layout.centerY,
        topicR: layout.topicR,
        uniformContextR: layout.uniformContextR,
        childrenRadius: layout.childrenRadius,
        outerCircleR: layout.outerCircleR,
        innerRadius: layout.topicR + layout.uniformContextR + 5,
        outerRadius: layout.outerCircleR - layout.uniformContextR - 5,
      },
    },
  }
}
