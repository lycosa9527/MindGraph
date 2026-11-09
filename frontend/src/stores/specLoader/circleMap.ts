/**
 * Circle Map Loader
 * Circle maps have: central topic circle, context circles around it, outer boundary ring
 * NO connection lines between nodes (unlike bubble maps)
 * Fixed font size; circles grown from text. Topics wrap at the shared column width.
 * Uses mindmap branch color palette for each context (like double bubble map).
 */
import { DEFAULT_CONTEXT_RADIUS } from '@/composables/diagrams/layoutConfig'
import { mirrorString, mirrorStringList, readSecondaryMirror } from '@/diagramBilingual/mirror'
import type { Connection, DiagramNode, MindMapAdornmentsByPath } from '@/types'
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
  polarToPosition,
  ringNodeDiskRadius,
  ringNodeOutlinePackR,
  ringNodePlacement,
} from '@/utils/layout/radial'
import { textWithIconAdornment } from '@/utils/mindMapAdornments'
import { thinkingMapStampedBranchColor } from '@/utils/thinkingMapChrome'

import { learningSheetLayoutSecondary, learningSheetLayoutText } from './mindMapLearningSheet'
import {
  CONTEXT_FONT_SIZE,
  TOPIC_FONT_SIZE,
  computeTopicRadiusForCircleMap,
} from './textMeasurement'
import type { SpecLoaderResult } from './types'
import {
  calculateCircleMapLayout,
  circleMapRingGeometry,
  estimateContextCircleDiameter,
  resolveCircleMapRadii,
} from './utils'

/**
 * Recalculate circle map layout from existing nodes.
 * Uses Pinia nodeDimensions (DOM) when available so KaTeX/markdown matches real size;
 * otherwise falls back to text metrics (same as initial load).
 */
export function recalculateCircleMapLayout(
  nodes: DiagramNode[],
  nodeDimensions: Record<string, { width: number; height: number }> = {},
  adornments: MindMapAdornmentsByPath = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return []
  }

  const topicNode = nodes.find((n) => n.type === 'topic' || n.type === 'center')
  const contextNodes = nodes
    .filter((n) => isCircleMapContextNode(n))
    .sort((a, b) => readCircleContextIndex(a) - readCircleContextIndex(b))
  const nodeCount = contextNodes.length
  const contextTexts = contextNodes.map((n) => learningSheetLayoutText(n))
  const contextSecondary = contextNodes.map((n) => learningSheetLayoutSecondary(n))
  const topicText = topicNode ? learningSheetLayoutText(topicNode) : ''

  let topicROverride: number | undefined
  if (topicNode && topicNode.style?.nodeShape !== 'underline') {
    const topicStyle = topicNode.style
    const textTopicR = computeTopicRadiusForCircleMap(
      textWithIconAdornment(topicText || ' ', adornments[topicNode.id]),
      {
        secondary: learningSheetLayoutSecondary(topicNode),
        fontSize: typeof topicStyle?.fontSize === 'number' ? topicStyle.fontSize : undefined,
        fontWeight: typeof topicStyle?.fontWeight === 'string' ? topicStyle.fontWeight : undefined,
        fontFamily: typeof topicStyle?.fontFamily === 'string' ? topicStyle.fontFamily : undefined,
      }
    )
    const diskR = ringNodeDiskRadius(topicStyle?.nodeShape, nodeDimensions[topicNode.id])
    topicROverride = Math.max(textTopicR, diskR ?? 0)
  }

  const circleContexts = contextNodes.filter((node) => node.style?.nodeShape !== 'underline')
  let uniformContextROverride: number | undefined
  if (circleContexts.length > 0) {
    let maxR = DEFAULT_CONTEXT_RADIUS
    for (const node of circleContexts) {
      const nodeStyle = node.style
      const textR =
        estimateContextCircleDiameter(
          textWithIconAdornment(learningSheetLayoutText(node) || ' ', adornments[node.id]),
          learningSheetLayoutSecondary(node),
          {
            fontSize: typeof nodeStyle?.fontSize === 'number' ? nodeStyle.fontSize : undefined,
            fontWeight:
              typeof nodeStyle?.fontWeight === 'string' ? nodeStyle.fontWeight : undefined,
            fontFamily:
              typeof nodeStyle?.fontFamily === 'string' ? nodeStyle.fontFamily : undefined,
          }
        ) / 2
      const diskR = ringNodeDiskRadius(node.style?.nodeShape, nodeDimensions[node.id])
      maxR = Math.max(maxR, textR, diskR ?? 0)
    }
    uniformContextROverride = maxR
  }

  const { topicR, uniformContextR } = resolveCircleMapRadii(contextTexts, topicText, {
    topicSecondary: topicNode ? learningSheetLayoutSecondary(topicNode) : undefined,
    contextSecondary,
    topicR: topicROverride,
    uniformContextR: uniformContextROverride,
  })
  const topicPackR = topicNode
    ? ringNodeOutlinePackR(topicNode.style?.nodeShape, topicR, nodeDimensions[topicNode.id])
    : topicR
  let contextPackR = uniformContextR
  if (contextNodes.length > 0) {
    const hasCircleBody = contextNodes.some((node) => node.style?.nodeShape !== 'underline')
    contextPackR = hasCircleBody ? uniformContextR : 0
    for (const node of contextNodes) {
      contextPackR = Math.max(
        contextPackR,
        ringNodeOutlinePackR(node.style?.nodeShape, uniformContextR, nodeDimensions[node.id])
      )
    }
    if (contextPackR <= 0) contextPackR = uniformContextR
  }
  const layout = {
    ...circleMapRingGeometry(nodeCount, topicPackR, contextPackR),
    topicR,
    uniformContextR,
  }
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
    const {
      halfX: topicHalfX,
      halfY: topicHalfY,
      packed: topicPacked,
    } = ringNodePlacement(topicNode.style?.nodeShape, layout.topicR, nodeDimensions[topicNode.id])
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
      const {
        halfX,
        halfY,
        packed: contextPacked,
      } = ringNodePlacement(node.style?.nodeShape, layout.uniformContextR, nodeDimensions[node.id])
      const slot = polarToPosition(
        index,
        nodeCount,
        layout.centerX,
        layout.centerY,
        layout.childrenRadius,
        halfX,
        halfY
      )
      const x = Math.round(slot.x)
      const y = Math.round(slot.y)
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
      const contextRadius = layout.uniformContextR
      const slot = polarToPosition(
        index,
        nodeCount,
        layout.centerX,
        layout.centerY,
        layout.childrenRadius,
        contextRadius,
        contextRadius
      )
      const x = Math.round(slot.x)
      const y = Math.round(slot.y)
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
