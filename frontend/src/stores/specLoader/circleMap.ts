/**
 * Circle Map Loader
 * Circle maps have: central topic circle, context circles around it, outer boundary ring
 * NO connection lines between nodes (unlike bubble maps)
 * Fixed font size; circles grown from text (one line, no wrap, no truncate).
 * Uses mindmap branch color palette for each context (like double bubble map).
 */
import { DEFAULT_CONTEXT_RADIUS } from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import { CONTEXT_FONT_SIZE, TOPIC_FONT_SIZE } from './textMeasurement'
import type { SpecLoaderResult } from './types'
import { calculateCircleMapLayout, estimateContextCircleDiameter } from './utils'

/**
 * Recalculate circle map layout from existing nodes.
 * Uses Pinia nodeDimensions (DOM) when available so KaTeX/markdown matches real size;
 * otherwise falls back to text metrics (same as initial load).
 */
export function recalculateCircleMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return []
  }

  const topicNode = nodes.find((n) => n.type === 'topic' || n.type === 'center')
  const contextNodes = nodes
    .filter((n) => n.type === 'bubble' && n.id.startsWith('context-'))
    .sort((a, b) => {
      const i = parseInt(a.id.replace(/^context-/, ''), 10)
      const j = parseInt(b.id.replace(/^context-/, ''), 10)
      return i - j
    })
  const nodeCount = contextNodes.length
  const contextTexts = contextNodes.map((n) => n.text)
  const topicText = topicNode?.text ?? ''

  let topicROverride: number | undefined
  if (topicNode) {
    const m = nodeDimensions[topicNode.id]
    if (m && m.width > 0 && m.height > 0) {
      topicROverride = Math.max(m.width, m.height) / 2
    }
  }

  let uniformContextROverride: number | undefined
  if (contextNodes.length > 0) {
    let maxR = DEFAULT_CONTEXT_RADIUS
    for (const node of contextNodes) {
      const measured = nodeDimensions[node.id]
      const r =
        measured && measured.width > 0 && measured.height > 0
          ? Math.max(measured.width, measured.height) / 2
          : estimateContextCircleDiameter(node.text || ' ') / 2
      maxR = Math.max(maxR, r)
    }
    uniformContextROverride = maxR
  }

  const layout = calculateCircleMapLayout(nodeCount, contextTexts, topicText, {
    topicR: topicROverride,
    uniformContextR: uniformContextROverride,
  })
  const uniformContextDiameter = layout.uniformContextR * 2
  const topicSize = layout.topicR * 2

  const result: DiagramNode[] = []

  // Outer boundary node (giant outer circle)
  result.push({
    id: 'outer-boundary',
    text: '',
    type: 'boundary',
    position: {
      x: Math.round(layout.centerX - layout.outerCircleR),
      y: Math.round(layout.centerY - layout.outerCircleR),
    },
    style: { width: layout.outerCircleR * 2, height: layout.outerCircleR * 2 },
  })

  if (topicNode) {
    const topicStyle = {
      ...(topicNode.style || {}),
      size: topicSize,
      fontSize: TOPIC_FONT_SIZE,
      noWrap: true,
    }
    result.push({
      id: 'topic',
      text: topicNode.text,
      type: 'center',
      position: {
        x: Math.round(layout.centerX - layout.topicR),
        y: Math.round(layout.centerY - layout.topicR),
      },
      style: topicStyle,
    })
  }

  if (nodeCount > 0) {
    contextNodes.forEach((node, index) => {
      const angleDeg = (index * 360) / nodeCount - 90
      const angleRad = (angleDeg * Math.PI) / 180
      const contextRadius = layout.uniformContextR
      const x = Math.round(
        layout.centerX + layout.childrenRadius * Math.cos(angleRad) - contextRadius
      )
      const y = Math.round(
        layout.centerY + layout.childrenRadius * Math.sin(angleRad) - contextRadius
      )
      const color = getMindmapBranchColor(index)

      const contextStyle = {
        ...(node.style || {}),
        size: uniformContextDiameter,
        fontSize: CONTEXT_FONT_SIZE,
        backgroundColor: color.fill,
        borderColor: color.border,
      }
      result.push({
        id: `context-${index}`,
        text: node.text,
        type: 'bubble',
        position: { x, y },
        data: { ...node.data, groupIndex: index },
        style: contextStyle,
      })
    })
  }

  return result
}

/**
 * Load circle map spec into diagram nodes and connections.
 * Fixed font; circles from text; topic and context noWrap.
 */
export function loadCircleMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  if (!spec || typeof spec !== 'object') {
    return { nodes: [], connections: [] }
  }

  const topic = (spec.topic as string) || ''
  const context = Array.isArray(spec.context) ? (spec.context as string[]) : []
  const nodeCount = context.length

  const layout = calculateCircleMapLayout(nodeCount, context, topic)
  const uniformContextDiameter = layout.uniformContextR * 2
  const topicSize = layout.topicR * 2

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Outer boundary node (giant outer circle)
  nodes.push({
    id: 'outer-boundary',
    text: '',
    type: 'boundary',
    position: {
      x: Math.round(layout.centerX - layout.outerCircleR),
      y: Math.round(layout.centerY - layout.outerCircleR),
    },
    style: { width: layout.outerCircleR * 2, height: layout.outerCircleR * 2 },
  })

  nodes.push({
    id: 'topic',
    text: topic,
    type: 'center',
    position: {
      x: Math.round(layout.centerX - layout.topicR),
      y: Math.round(layout.centerY - layout.topicR),
    },
    data: { estimatedWidth: topicSize, estimatedHeight: topicSize },
    style: { size: topicSize, fontSize: TOPIC_FONT_SIZE, noWrap: true },
  })

  if (nodeCount > 0) {
    context.forEach((ctx, index) => {
      const angleDeg = (index * 360) / nodeCount - 90
      const angleRad = (angleDeg * Math.PI) / 180
      const contextRadius = layout.uniformContextR
      const x = Math.round(
        layout.centerX + layout.childrenRadius * Math.cos(angleRad) - contextRadius
      )
      const y = Math.round(
        layout.centerY + layout.childrenRadius * Math.sin(angleRad) - contextRadius
      )
      const color = getMindmapBranchColor(index)

      nodes.push({
        id: `context-${index}`,
        text: ctx,
        type: 'bubble',
        position: { x, y },
        data: {
          groupIndex: index,
          estimatedWidth: uniformContextDiameter,
          estimatedHeight: uniformContextDiameter,
        },
        style: {
          size: uniformContextDiameter,
          fontSize: CONTEXT_FONT_SIZE,
          backgroundColor: color.fill,
          borderColor: color.border,
        },
      })
    })
  }

  return {
    nodes,
    connections,
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
