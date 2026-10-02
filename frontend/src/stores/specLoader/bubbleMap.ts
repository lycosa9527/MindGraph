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
import { thinkingMapStampedBranchColor } from '@/utils/thinkingMapChrome'
import type { Connection, DiagramNode } from '@/types'
import {
  BUBBLE_MAP_UID_DATA_KEY,
  BUBBLE_TOPIC_NODE_ID,
  isBubbleMapAttributeNode,
  readBubbleGroupIndex,
  stampBubbleAttributeData,
  takeBubbleMapStableId,
} from '@/utils/bubbleMapIdentity'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  CIRCLE_MAP_OVAL_WIDTH_RATIO,
  type NodeShape,
  shapePackHalfExtent,
} from '@/utils/nodeShapeStyle'

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
function bubbleShapePacksAsBox(shape: NodeShape | undefined): boolean {
  return shape === 'rectangle' || shape === 'rounded' || shape === 'underline'
}

function bubbleNodeHalfExtents(
  shape: NodeShape | undefined,
  visualR: number
): { halfX: number; halfY: number } {
  if (shape === 'oval') {
    return { halfX: visualR * CIRCLE_MAP_OVAL_WIDTH_RATIO, halfY: visualR }
  }
  return { halfX: visualR, halfY: visualR }
}

function bubbleOutlinePackR(
  shape: NodeShape | undefined,
  visualR: number,
  measured: { width: number; height: number } | undefined
): number {
  if (shape === 'underline' && measured && measured.width > 0 && measured.height > 0) {
    return shapePackHalfExtent('underline', measured.width / 2, measured.height / 2)
  }
  if (shape === 'oval') return visualR * CIRCLE_MAP_OVAL_WIDTH_RATIO
  if (shape === 'rectangle' || shape === 'rounded') {
    return shapePackHalfExtent(shape, visualR, visualR)
  }
  return visualR
}

function bubbleContextRadiusFromNode(node: DiagramNode): number {
  const trimmed = (node.text ?? '').trim() || ' '
  const fs = typeof node.style?.fontSize === 'number' ? node.style.fontSize : CONTEXT_FONT_SIZE
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
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) return []

  const topicNode = nodes.find((n) => n.type === 'topic' || n.type === 'center')
  const bubbleNodes = nodes
    .filter((n) => isBubbleMapAttributeNode(n))
    .sort((a, b) => readBubbleGroupIndex(a) - readBubbleGroupIndex(b))
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

  const topicPackR = bubbleOutlinePackR(
    topicStyle?.nodeShape,
    topicR,
    topicNode ? nodeDimensions[topicNode.id] : undefined
  )
  let childPackR = 0
  for (const node of bubbleNodes) {
    childPackR = Math.max(
      childPackR,
      bubbleOutlinePackR(node.style?.nodeShape, uniformRadius, nodeDimensions[node.id])
    )
  }
  if (childPackR <= 0) childPackR = uniformRadius
  const packCustom =
    topicPackR !== topicR ||
    childPackR !== uniformRadius ||
    bubbleShapePacksAsBox(topicStyle?.nodeShape) ||
    bubbleNodes.some((node) => bubbleShapePacksAsBox(node.style?.nodeShape))
  const childrenRadius = bubbleMapChildrenRadius(
    nodeCount,
    topicR,
    uniformRadius,
    uniformRadius,
    50,
    packCustom ? { packAsBox: true, topicPackR, childPackR } : undefined
  )

  const result: DiagramNode[] = []

  if (topicNode) {
    const { noWrap: _noWrap, size: _topicSize, ...restStyle } = topicNode.style ?? {}
    const topicUnderline = topicStyle?.nodeShape === 'underline'
    const topicMeasured = nodeDimensions[topicNode.id]
    const topicPacked =
      topicUnderline && topicMeasured != null && topicMeasured.width > 0 && topicMeasured.height > 0
    const topicHalves = topicPacked
      ? { halfX: topicMeasured.width / 2, halfY: topicMeasured.height / 2 }
      : bubbleNodeHalfExtents(topicStyle?.nodeShape, topicR)
    const topicHalfX = topicHalves.halfX
    const topicHalfY = topicHalves.halfY
    result.push({
      ...topicNode,
      position: { x: Math.round(centerX - topicHalfX), y: Math.round(centerY - topicHalfY) },
      style: topicPacked
        ? {
            ...restStyle,
            fontSize: restStyle.fontSize ?? TOPIC_FONT_SIZE,
          }
        : {
            ...restStyle,
            size: topicR * 2,
            fontSize: restStyle.fontSize ?? TOPIC_FONT_SIZE,
          },
    })
  }

  bubbleNodes.forEach((node, index) => {
    const bubbleUnderline = node.style?.nodeShape === 'underline'
    const bubbleMeasured = nodeDimensions[node.id]
    const bubblePacked =
      bubbleUnderline &&
      bubbleMeasured != null &&
      bubbleMeasured.width > 0 &&
      bubbleMeasured.height > 0
    const bubbleHalves = bubblePacked
      ? { halfX: bubbleMeasured.width / 2, halfY: bubbleMeasured.height / 2 }
      : bubbleNodeHalfExtents(node.style?.nodeShape, uniformRadius)
    const bubbleHalfX = bubbleHalves.halfX
    const bubbleHalfY = bubbleHalves.halfY
    const { x, y } = polarToPosition(
      index,
      nodeCount,
      centerX,
      centerY,
      childrenRadius,
      bubbleHalfX,
      bubbleHalfY
    )
    const pos = { x: Math.round(x), y: Math.round(y) }
    const color = thinkingMapStampedBranchColor(index)
    const { size: _bubbleSize, ...bubbleRest } = node.style ?? {}
    result.push({
      ...node,
      position: pos,
      data: stampBubbleAttributeData(index, {
        ...node.data,
        [BUBBLE_MAP_UID_DATA_KEY]: node.id,
      }),
      style: bubblePacked
        ? {
            ...bubbleRest,
            fontSize: node.style?.fontSize ?? CONTEXT_FONT_SIZE,
            noWrap: true,
            backgroundColor: node.style?.backgroundColor || color.fill,
            borderColor: node.style?.borderColor || color.border,
          }
        : {
            ...bubbleRest,
            size: uniformRadius * 2,
            fontSize: node.style?.fontSize ?? CONTEXT_FONT_SIZE,
            noWrap: true,
            backgroundColor: node.style?.backgroundColor || color.fill,
            borderColor: node.style?.borderColor || color.border,
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

  const claimedIds = new Set<string>([BUBBLE_TOPIC_NODE_ID])

  nodes.push({
    id: BUBBLE_TOPIC_NODE_ID,
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
      const color = thinkingMapStampedBranchColor(index)
      const bubbleId = takeBubbleMapStableId(claimedIds)
      nodes.push({
        id: bubbleId,
        text: attr,
        type: 'bubble',
        position: { x: Math.round(x), y: Math.round(y) },
        data: stampBubbleAttributeData(index, { [BUBBLE_MAP_UID_DATA_KEY]: bubbleId }),
        style: {
          size: uniformDiameter,
          fontSize: CONTEXT_FONT_SIZE,
          noWrap: true,
          backgroundColor: color.fill,
          borderColor: color.border,
        },
      })

      connections.push({
        id: `edge-${BUBBLE_TOPIC_NODE_ID}-${bubbleId}`,
        source: BUBBLE_TOPIC_NODE_ID,
        target: bubbleId,
        style: { strokeColor: color.border },
      })
    })
  }

  return { nodes, connections }
}
