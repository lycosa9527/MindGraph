/**
 * Circle Map Loader
 * Circle maps have: central topic circle, context circles around it, outer boundary ring
 * NO connection lines between nodes (unlike bubble maps)
 * Fixed font size; circles grown from text. Topics wrap at the shared column width.
 * Uses mindmap branch color palette for each context (like double bubble map).
 */
import { DEFAULT_CONTEXT_RADIUS } from '@/composables/diagrams/layoutConfig'
import { mirrorString, mirrorStringList, readSecondaryMirror } from '@/diagramBilingual/mirror'
import type { Connection, DiagramNode } from '@/types'
import {
  CIRCLE_BOUNDARY_NODE_ID,
  CIRCLE_MAP_UID_DATA_KEY,
  CIRCLE_TOPIC_NODE_ID,
  isCircleMapContextNode,
  readCircleContextIndex,
  stampCircleContextData,
  takeCircleMapStableId,
} from '@/utils/circleMapIdentity'
import {
  CIRCLE_MAP_OVAL_WIDTH_RATIO,
  type NodeShape,
  shapePackHalfExtent,
} from '@/utils/nodeShapeStyle'
import { thinkingMapStampedBranchColor } from '@/utils/thinkingMapChrome'

import {
  CONTEXT_FONT_SIZE,
  TOPIC_FONT_SIZE,
  computeTopicRadiusForCircleMap,
} from './textMeasurement'
import type { SpecLoaderResult } from './types'
import { calculateCircleMapLayout, estimateContextCircleDiameter } from './utils'

function isCircleBoxShape(shape: NodeShape | undefined): boolean {
  return shape === 'rectangle' || shape === 'rounded'
}

function circleDiskRadius(
  shape: NodeShape | undefined,
  measured: { width: number; height: number } | undefined
): number | undefined {
  if (!measured || measured.width <= 0 || measured.height <= 0) return undefined
  if (shape === 'oval') return measured.height / 2
  return Math.max(measured.width, measured.height) / 2
}

function circleNodeHalfExtents(
  shape: NodeShape | undefined,
  visualR: number
): { halfX: number; halfY: number } {
  if (shape === 'oval') {
    return { halfX: visualR * CIRCLE_MAP_OVAL_WIDTH_RATIO, halfY: visualR }
  }
  return { halfX: visualR, halfY: visualR }
}

function circleNodePackR(
  shape: NodeShape | undefined,
  visualR: number,
  measured: { width: number; height: number } | undefined
): number {
  if (shape === 'underline' && measured && measured.width > 0 && measured.height > 0) {
    return shapePackHalfExtent('underline', measured.width / 2, measured.height / 2)
  }
  if (shape === 'oval') return visualR * CIRCLE_MAP_OVAL_WIDTH_RATIO
  if (isCircleBoxShape(shape)) {
    return shapePackHalfExtent(shape, visualR, visualR)
  }
  return visualR
}

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
    .filter((n) => isCircleMapContextNode(n))
    .sort((a, b) => readCircleContextIndex(a) - readCircleContextIndex(b))
  const nodeCount = contextNodes.length
  const contextTexts = contextNodes.map((n) => n.text)
  const contextSecondary = contextNodes.map((n) => n.textSecondary ?? '')
  const topicText = topicNode?.text ?? ''

  let topicROverride: number | undefined
  if (topicNode && topicNode.style?.nodeShape !== 'underline') {
    const topicStyle = topicNode.style
    const textTopicR = computeTopicRadiusForCircleMap(topicText || ' ', {
      secondary: topicNode.textSecondary,
      fontSize: typeof topicStyle?.fontSize === 'number' ? topicStyle.fontSize : undefined,
      fontWeight: typeof topicStyle?.fontWeight === 'string' ? topicStyle.fontWeight : undefined,
      fontFamily: typeof topicStyle?.fontFamily === 'string' ? topicStyle.fontFamily : undefined,
    })
    const diskR = circleDiskRadius(topicStyle?.nodeShape, nodeDimensions[topicNode.id])
    topicROverride = Math.max(textTopicR, diskR ?? 0)
  }

  const circleContexts = contextNodes.filter((node) => node.style?.nodeShape !== 'underline')
  let uniformContextROverride: number | undefined
  if (circleContexts.length > 0) {
    let maxR = DEFAULT_CONTEXT_RADIUS
    for (const node of circleContexts) {
      const textR = estimateContextCircleDiameter(node.text || ' ', node.textSecondary) / 2
      const diskR = circleDiskRadius(node.style?.nodeShape, nodeDimensions[node.id])
      maxR = Math.max(maxR, textR, diskR ?? 0)
    }
    uniformContextROverride = maxR
  }

  const layoutBase = calculateCircleMapLayout(nodeCount, contextTexts, topicText, {
    topicSecondary: topicNode?.textSecondary,
    contextSecondary,
    topicR: topicROverride,
    uniformContextR: uniformContextROverride,
  })
  const topicPackR = topicNode
    ? circleNodePackR(topicNode.style?.nodeShape, layoutBase.topicR, nodeDimensions[topicNode.id])
    : layoutBase.topicR
  let contextPackR = layoutBase.uniformContextR
  if (contextNodes.length > 0) {
    const hasCircleBody = contextNodes.some((node) => node.style?.nodeShape !== 'underline')
    contextPackR = hasCircleBody ? layoutBase.uniformContextR : 0
    for (const node of contextNodes) {
      contextPackR = Math.max(
        contextPackR,
        circleNodePackR(node.style?.nodeShape, layoutBase.uniformContextR, nodeDimensions[node.id])
      )
    }
    if (contextPackR <= 0) contextPackR = layoutBase.uniformContextR
  }
  const layout =
    topicPackR === layoutBase.topicR && contextPackR === layoutBase.uniformContextR
      ? layoutBase
      : calculateCircleMapLayout(nodeCount, contextTexts, topicText, {
          topicR: topicROverride,
          uniformContextR: uniformContextROverride,
          topicPackR,
          contextPackR,
        })
  const uniformContextDiameter = layout.uniformContextR * 2
  const topicSize = layout.topicR * 2

  const result: DiagramNode[] = []

  // Outer boundary node (giant outer circle)
  result.push({
    id: CIRCLE_BOUNDARY_NODE_ID,
    text: '',
    type: 'boundary',
    position: {
      x: Math.round(layout.centerX - layout.outerCircleR),
      y: Math.round(layout.centerY - layout.outerCircleR),
    },
    style: { width: layout.outerCircleR * 2, height: layout.outerCircleR * 2 },
  })

  if (topicNode) {
    const topicUnderline = topicNode.style?.nodeShape === 'underline'
    const topicMeasured = nodeDimensions[topicNode.id]
    const topicPacked =
      topicUnderline && topicMeasured != null && topicMeasured.width > 0 && topicMeasured.height > 0
    const topicHalves = topicPacked
      ? { halfX: topicMeasured.width / 2, halfY: topicMeasured.height / 2 }
      : circleNodeHalfExtents(topicNode.style?.nodeShape, layout.topicR)
    const topicHalfX = topicHalves.halfX
    const topicHalfY = topicHalves.halfY
    const { size: _topicSize, ...topicRest } = topicNode.style || {}
    const topicStyle = topicPacked
      ? {
          ...topicRest,
          fontSize: topicNode.style?.fontSize ?? TOPIC_FONT_SIZE,
        }
      : {
          ...topicRest,
          size: topicSize,
          fontSize: topicNode.style?.fontSize ?? TOPIC_FONT_SIZE,
        }
    result.push({
      ...topicNode,
      id: CIRCLE_TOPIC_NODE_ID,
      text: topicNode.text,
      type: 'center',
      position: {
        x: Math.round(layout.centerX - topicHalfX),
        y: Math.round(layout.centerY - topicHalfY),
      },
      style: topicStyle,
    })
  }

  if (nodeCount > 0) {
    contextNodes.forEach((node, index) => {
      const angleDeg = (index * 360) / nodeCount - 90
      const angleRad = (angleDeg * Math.PI) / 180
      const contextUnderline = node.style?.nodeShape === 'underline'
      const contextMeasured = nodeDimensions[node.id]
      const contextPacked =
        contextUnderline &&
        contextMeasured != null &&
        contextMeasured.width > 0 &&
        contextMeasured.height > 0
      const contextHalves = contextPacked
        ? { halfX: contextMeasured.width / 2, halfY: contextMeasured.height / 2 }
        : circleNodeHalfExtents(node.style?.nodeShape, layout.uniformContextR)
      const contextHalfX = contextHalves.halfX
      const contextHalfY = contextHalves.halfY
      const x = Math.round(
        layout.centerX + layout.childrenRadius * Math.cos(angleRad) - contextHalfX
      )
      const y = Math.round(
        layout.centerY + layout.childrenRadius * Math.sin(angleRad) - contextHalfY
      )
      const color = thinkingMapStampedBranchColor(index)
      const { size: _contextSize, ...contextRest } = node.style || {}
      const contextStyle = contextPacked
        ? {
            ...contextRest,
            fontSize: node.style?.fontSize ?? CONTEXT_FONT_SIZE,
            backgroundColor: node.style?.backgroundColor || color.fill,
            borderColor: node.style?.borderColor || color.border,
          }
        : {
            ...contextRest,
            size: uniformContextDiameter,
            fontSize: node.style?.fontSize ?? CONTEXT_FONT_SIZE,
            backgroundColor: node.style?.backgroundColor || color.fill,
            borderColor: node.style?.borderColor || color.border,
          }
      result.push({
        ...node,
        id: node.id,
        text: node.text,
        type: 'bubble',
        position: { x, y },
        data: stampCircleContextData(index, {
          ...node.data,
          [CIRCLE_MAP_UID_DATA_KEY]: node.id,
        }),
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
  const mirror = readSecondaryMirror(spec)
  const topicSecondary = mirrorString(mirror, 'topic')
  const contextSecondary = mirrorStringList(mirror, 'context')

  const layout = calculateCircleMapLayout(nodeCount, context, topic, {
    topicSecondary,
    contextSecondary,
  })
  const uniformContextDiameter = layout.uniformContextR * 2
  const topicSize = layout.topicR * 2

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []
  const claimedIds = new Set<string>([CIRCLE_TOPIC_NODE_ID, CIRCLE_BOUNDARY_NODE_ID])

  // Outer boundary node (giant outer circle)
  nodes.push({
    id: CIRCLE_BOUNDARY_NODE_ID,
    text: '',
    type: 'boundary',
    position: {
      x: Math.round(layout.centerX - layout.outerCircleR),
      y: Math.round(layout.centerY - layout.outerCircleR),
    },
    style: { width: layout.outerCircleR * 2, height: layout.outerCircleR * 2 },
  })

  nodes.push({
    id: CIRCLE_TOPIC_NODE_ID,
    text: topic,
    ...(topicSecondary ? { textSecondary: topicSecondary } : {}),
    type: 'center',
    position: {
      x: Math.round(layout.centerX - layout.topicR),
      y: Math.round(layout.centerY - layout.topicR),
    },
    data: { estimatedWidth: topicSize, estimatedHeight: topicSize },
    style: { size: topicSize, fontSize: TOPIC_FONT_SIZE },
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
      const color = thinkingMapStampedBranchColor(index)
      const contextId = takeCircleMapStableId(claimedIds)

      nodes.push({
        id: contextId,
        text: ctx,
        ...(contextSecondary[index] ? { textSecondary: contextSecondary[index] } : {}),
        type: 'bubble',
        position: { x, y },
        data: stampCircleContextData(index, {
          [CIRCLE_MAP_UID_DATA_KEY]: contextId,
          estimatedWidth: uniformContextDiameter,
          estimatedHeight: uniformContextDiameter,
        }),
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
