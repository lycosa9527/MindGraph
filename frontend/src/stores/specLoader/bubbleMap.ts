/**
 * Bubble Map Loader
 *
 * Layout: fixed canvas center (DEFAULT_CENTER_X/Y); topic at center with text-adaptive radius;
 * attribute bubbles on a ring. Long labels use the mind-map branch wrap (browser metrics,
 * script-aware column, balanced lines) and the circle grows to that block.
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_CONTEXT_RADIUS,
  DEFAULT_TOPIC_RADIUS,
} from '@/composables/diagrams/layoutConfig'
import { bubbleMapChildrenRadius, polarToPosition } from '@/composables/diagrams/useRadialLayout'
import { mirrorString, mirrorStringList, readSecondaryMirror } from '@/diagramBilingual/mirror'
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
  MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
  MIND_MAP_TEXT_LINE_HEIGHT,
  measureThinkingMapLabelBlockPx,
} from '@/utils/mindMapTextWrap'
import {
  CIRCLE_MAP_OVAL_WIDTH_RATIO,
  type NodeShape,
  shapePackHalfExtent,
} from '@/utils/nodeShapeStyle'
import { thinkingMapStampedBranchColor } from '@/utils/thinkingMapChrome'

import {
  CONTEXT_FONT_SIZE,
  TOPIC_FONT_SIZE,
  calculateBubbleMapRadius,
  computeTopicRadiusForCircleMap,
  diagramLabelLikelyNeedsRenderedMeasure,
  growRadiusForSecondary,
  measureRenderedDiagramLabelHeight,
  measureRenderedDiagramLabelWidth,
} from './textMeasurement'
import { estimateTextWidthFallbackPx } from './textMeasurementFallback'
import type { SpecLoaderResult } from './types'

/** Matches CircleNode `px-2` / `py-1` on attribute labels. */
const ATTRIBUTE_LABEL_PAD_X = 16
const ATTRIBUTE_LABEL_PAD_Y = 8
const ATTRIBUTE_RADIUS_PADDING = 10

function attributeMeasureOpts(
  measureBold: boolean,
  fontFamily: string | undefined
): { fontWeight: 'bold' | 'normal'; fontFamily: string | undefined } {
  return {
    fontWeight: measureBold ? 'bold' : 'normal',
    fontFamily,
  }
}

function attributeBubbleRadius(
  text: string,
  fontSize: number,
  measureBold: boolean,
  fontFamily: string | undefined,
  secondary?: string
): number {
  const trimmed = (text || '').trim() || ' '
  const measureOpts = attributeMeasureOpts(measureBold, fontFamily)
  const block = measureThinkingMapLabelBlockPx(
    trimmed,
    fontSize,
    MIND_MAP_BRANCH_MAX_TEXT_WIDTH,
    measureOpts
  )
  const staysOneLine = !trimmed.includes('\n') && block.lineCount <= 1
  let radius: number
  if (staysOneLine) {
    if (typeof document !== 'undefined' && diagramLabelLikelyNeedsRenderedMeasure(trimmed)) {
      const width = measureRenderedDiagramLabelWidth(trimmed, fontSize, measureOpts)
      const height = measureRenderedDiagramLabelHeight(trimmed, fontSize, 1_000_000, measureOpts)
      const usedWidth =
        width || estimateTextWidthFallbackPx(trimmed, fontSize, { isTopic: measureBold })
      const usedHeight = height || fontSize * MIND_MAP_TEXT_LINE_HEIGHT
      radius = Math.ceil(
        Math.sqrt(usedWidth * usedWidth + usedHeight * usedHeight) / 2 + ATTRIBUTE_RADIUS_PADDING
      )
    } else {
      radius = calculateBubbleMapRadius(
        trimmed,
        fontSize,
        ATTRIBUTE_RADIUS_PADDING,
        DEFAULT_CONTEXT_RADIUS,
        false,
        measureBold,
        fontFamily
      )
    }
  } else {
    const lineWidth = block.width
    let boxHeight = block.height
    if (typeof document !== 'undefined' && diagramLabelLikelyNeedsRenderedMeasure(trimmed)) {
      const renderedHeight = measureRenderedDiagramLabelHeight(
        trimmed,
        fontSize,
        lineWidth,
        measureOpts
      )
      if (renderedHeight > boxHeight) boxHeight = renderedHeight
    }
    const boxWidth = lineWidth + ATTRIBUTE_LABEL_PAD_X
    boxHeight += ATTRIBUTE_LABEL_PAD_Y
    radius = Math.ceil(
      Math.sqrt(boxWidth * boxWidth + boxHeight * boxHeight) / 2 + ATTRIBUTE_RADIUS_PADDING
    )
  }
  return growRadiusForSecondary(Math.max(DEFAULT_CONTEXT_RADIUS, radius), secondary, fontSize)
}

function defaultContextBubbleRadiusFromText(text: string, secondary?: string): number {
  return attributeBubbleRadius(text, CONTEXT_FONT_SIZE, false, DIAGRAM_NODE_FONT_STACK, secondary)
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
  const fs = typeof node.style?.fontSize === 'number' ? node.style.fontSize : CONTEXT_FONT_SIZE
  const measureBold = node.style?.fontWeight === 'bold'
  const fontFamily = node.style?.fontFamily ?? DIAGRAM_NODE_FONT_STACK
  return attributeBubbleRadius(node.text ?? '', fs, measureBold, fontFamily, node.textSecondary)
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
  const topicSecondary = topicNode?.textSecondary
  const topicStyle = topicNode?.style
  const textTopicR = computeTopicRadiusForCircleMap(topicText || ' ', {
    fontSize: typeof topicStyle?.fontSize === 'number' ? topicStyle.fontSize : undefined,
    fontWeight: topicStyle?.fontWeight,
    fontFamily: topicStyle?.fontFamily,
    secondary: topicSecondary,
  })
  const topicMeasured = topicNode ? nodeDimensions[topicNode.id] : undefined
  let domTopicR = 0
  if (
    topicMeasured &&
    topicMeasured.width > 0 &&
    topicMeasured.height > 0 &&
    topicStyle?.nodeShape !== 'underline'
  ) {
    domTopicR =
      topicStyle?.nodeShape === 'oval'
        ? topicMeasured.height / 2
        : Math.max(topicMeasured.width, topicMeasured.height) / 2
  }
  const topicR = Math.max(DEFAULT_TOPIC_RADIUS, textTopicR, domTopicR)
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
    const { size: _bubbleSize, noWrap: _bubbleNoWrap, ...bubbleRest } = node.style ?? {}
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
            backgroundColor: node.style?.backgroundColor || color.fill,
            borderColor: node.style?.borderColor || color.border,
          }
        : {
            ...bubbleRest,
            size: uniformRadius * 2,
            fontSize: node.style?.fontSize ?? CONTEXT_FONT_SIZE,
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
  const mirror = readSecondaryMirror(spec)
  const topicSecondary = mirrorString(mirror, 'topic')
  const attributeSecondary = mirrorStringList(mirror, 'attributes')

  const topicR = Math.max(
    DEFAULT_TOPIC_RADIUS,
    computeTopicRadiusForCircleMap(topic || ' ', { secondary: topicSecondary })
  )
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const nodeCount = attributes.length

  const radii = attributes.map((attr, index) =>
    defaultContextBubbleRadiusFromText(attr, attributeSecondary[index])
  )
  const uniformRadius =
    nodeCount > 0 ? Math.max(DEFAULT_CONTEXT_RADIUS, ...radii) : DEFAULT_CONTEXT_RADIUS

  const childrenRadius = bubbleMapChildrenRadius(nodeCount, topicR, uniformRadius, uniformRadius)

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  const claimedIds = new Set<string>([BUBBLE_TOPIC_NODE_ID])

  nodes.push({
    id: BUBBLE_TOPIC_NODE_ID,
    text: topic,
    ...(topicSecondary ? { textSecondary: topicSecondary } : {}),
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
        ...(attributeSecondary[index] ? { textSecondary: attributeSecondary[index] } : {}),
        type: 'bubble',
        position: { x: Math.round(x), y: Math.round(y) },
        data: stampBubbleAttributeData(index, { [BUBBLE_MAP_UID_DATA_KEY]: bubbleId }),
        style: {
          size: uniformDiameter,
          fontSize: CONTEXT_FONT_SIZE,
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
