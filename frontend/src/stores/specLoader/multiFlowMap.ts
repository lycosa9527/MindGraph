/**
 * Multi-Flow Map Loader
 * Uses mindmap branch color palette for causes and effects (like double bubble map).
 */
import {
  DEFAULT_CENTER_X,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_HEIGHT,
  DEFAULT_NODE_WIDTH,
  DEFAULT_SIDE_SPACING,
  DEFAULT_VERTICAL_SPACING,
  MULTI_FLOW_FLOW_NODE_LABEL_MAX_WIDTH,
  MULTI_FLOW_MAP_TOPIC_WIDTH,
  MULTI_FLOW_TOPIC_FONT_SIZE,
  MULTI_FLOW_TOPIC_LABEL_MAX_WIDTH,
  MULTI_FLOW_TOPIC_PADDING_X,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'
import { DIAGRAM_NODE_FONT_STACK } from '@/utils/diagramNodeFontStack'
import {
  MULTI_FLOW_EVENT_NODE_ID,
  MULTI_FLOW_UID_DATA_KEY,
  isMultiFlowCauseNode,
  isMultiFlowEffectNode,
  readMultiFlowIndex,
  stampMultiFlowData,
  takeMultiFlowMapStableId,
} from '@/utils/multiFlowMapIdentity'

import {
  diagramLabelLikelyNeedsRenderedMeasure,
  measureRenderedDiagramLabelWidth,
  measureTextWidth,
} from './textMeasurement'
import { estimateTextWidthFallbackPx } from './textMeasurementFallback'
import type { SpecLoaderResult } from './types'

/** FlowNode font size (matches FlowNode.vue defaultStyle) */
const FLOW_NODE_FONT_SIZE = 13
/** FlowNode horizontal padding: px-5 = 20px each side */
const FLOW_NODE_PADDING_X = 40

function measureLabelInnerWidth(
  text: string,
  fontSize: number,
  fontWeight: string | undefined,
  fontFamily: string,
  isTopic: boolean
): number {
  const trimmed = text.trim() || ' '
  const fallback = estimateTextWidthFallbackPx(trimmed, fontSize, { isTopic })
  if (typeof document === 'undefined') {
    return fallback
  }
  const weight = fontWeight === 'bold' ? 'bold' : 'normal'
  const measured = diagramLabelLikelyNeedsRenderedMeasure(trimmed)
    ? measureRenderedDiagramLabelWidth(trimmed, fontSize, { fontFamily, fontWeight: weight })
    : measureTextWidth(trimmed, fontSize, { fontFamily, fontWeight: weight })
  return measured > 0 ? measured : fallback
}

/**
 * Event-pill width from label + TopicNodeDiagram padding / wrap cap.
 * Auto-complete must not keep the 90px "事件" slot when the event title is long.
 */
export function estimateMultiFlowTopicWidth(
  text: string,
  style?: { fontSize?: number; fontWeight?: string | number; fontFamily?: string }
): number {
  const fs = typeof style?.fontSize === 'number' ? style.fontSize : MULTI_FLOW_TOPIC_FONT_SIZE
  const fontWeight = style?.fontWeight
  const fontFamily = style?.fontFamily ?? DIAGRAM_NODE_FONT_STACK
  const isBold = fontWeight === undefined || fontWeight === 'bold' || fontWeight === 700
  const nowrapInner = measureLabelInnerWidth(
    text,
    fs,
    isBold ? 'bold' : 'normal',
    fontFamily,
    true
  )
  const innerForLayout = Math.min(nowrapInner, MULTI_FLOW_TOPIC_LABEL_MAX_WIDTH)
  return Math.max(MULTI_FLOW_MAP_TOPIC_WIDTH, Math.ceil(innerForLayout + MULTI_FLOW_TOPIC_PADDING_X))
}

/**
 * Compute adaptive width for a cause/effect node from its text and typography.
 * Uses the same inner wrap cap as FlowNode so layout matches auto-wrapped labels.
 */
function computeFlowNodeWidth(node: DiagramNode): number {
  const fs = typeof node.style?.fontSize === 'number' ? node.style.fontSize : FLOW_NODE_FONT_SIZE
  const fontWeight = node.style?.fontWeight
  const fontFamily = node.style?.fontFamily ?? DIAGRAM_NODE_FONT_STACK
  const nowrapInner = measureLabelInnerWidth(
    node.text ?? '',
    fs,
    fontWeight === 'bold' ? 'bold' : 'normal',
    fontFamily,
    fontWeight === 'bold'
  )
  const innerForLayout = Math.min(nowrapInner, MULTI_FLOW_FLOW_NODE_LABEL_MAX_WIDTH)
  return Math.max(DEFAULT_NODE_WIDTH, Math.ceil(innerForLayout + FLOW_NODE_PADDING_X))
}

/**
 * Recalculate multi-flow map layout from existing nodes
 * Called when nodes are added/deleted to update positions.
 * Keeps live node ids; restamps cause/effect index only.
 *
 * @param nodes - Current diagram nodes
 * @param topicNodeWidth - Optional actual width of topic node (for dynamic width adjustment)
 * @param _nodeWidths - Unused, kept for call-site compatibility
 * @param nodeDimensions - DOM-measured node dimensions (height used for vertical stacking)
 * @returns Recalculated nodes with updated positions
 */
export function recalculateMultiFlowMapLayout(
  nodes: DiagramNode[],
  topicNodeWidth: number | null = null,
  _nodeWidths: Record<string, number> = {},
  nodeDimensions: Record<string, { width: number; height: number }> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return []
  }

  // Extract event, causes, and effects from current nodes
  const eventNode = nodes.find((n) => n.id === MULTI_FLOW_EVENT_NODE_ID || n.type === 'topic')
  const causeNodes = nodes
    .filter((n) => isMultiFlowCauseNode(n))
    .sort((a, b) => readMultiFlowIndex(a) - readMultiFlowIndex(b))
  const effectNodes = nodes
    .filter((n) => isMultiFlowEffectNode(n))
    .sort((a, b) => readMultiFlowIndex(a) - readMultiFlowIndex(b))

  const event = eventNode?.text || ''

  // Layout constants
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const sideSpacing = DEFAULT_SIDE_SPACING
  const nodeWidth = DEFAULT_NODE_WIDTH
  const verticalGap = DEFAULT_VERTICAL_SPACING - 40 // 20px gap between nodes

  const getH = (id: string): number => {
    const pinia = nodeDimensions[id]?.height
    return pinia ?? DEFAULT_NODE_HEIGHT
  }

  const actualTopicWidth =
    topicNodeWidth ?? estimateMultiFlowTopicWidth(event, eventNode?.style)

  // Calculate uniform width for visual balance using text measurement.
  // Pinia DOM widths are NOT used for width because font-loading timing can
  // capture stale/wrong widths that lock in via the style.width feedback loop.
  let maxCauseWidth = nodeWidth
  let maxEffectWidth = nodeWidth

  causeNodes.forEach((node) => {
    maxCauseWidth = Math.max(maxCauseWidth, computeFlowNodeWidth(node))
  })

  effectNodes.forEach((node) => {
    maxEffectWidth = Math.max(maxEffectWidth, computeFlowNodeWidth(node))
  })

  // Use the maximum of both columns for visual balance
  const uniformColumnWidth = Math.max(maxCauseWidth, maxEffectWidth)

  // Calculate five columns for visual balance:
  // 1. Cause column width: uniformColumnWidth
  // 2. Left arrow column (spacing): arrowSpacing
  // 3. Topic column width: actualTopicWidth
  // 4. Right arrow column (spacing): arrowSpacing
  // 5. Effect column width: uniformColumnWidth

  // Horizontal gap between topic edges and cause/effect columns (same on both sides).
  const arrowSpacing = sideSpacing * 0.7

  // Calculate edges based on balanced columns
  const topicLeftEdge = centerX - actualTopicWidth / 2
  const topicRightEdge = centerX + actualTopicWidth / 2

  // Stack a column of node IDs vertically, centered at centerY, using actual heights.
  function stackColumnYPositions(ids: string[]): number[] {
    const heights = ids.map((id) => getH(id))
    const totalHeight = heights.reduce((a, h) => a + h, 0) + (ids.length - 1) * verticalGap
    let y = centerY - totalHeight / 2
    return heights.map((h) => {
      const top = y
      y += h + verticalGap
      return top
    })
  }

  const causeIds = causeNodes.map((node) => node.id)
  const effectIds = effectNodes.map((node) => node.id)
  const causeYPositions = stackColumnYPositions(causeIds)
  const effectYPositions = stackColumnYPositions(effectIds)

  const result: DiagramNode[] = []

  // Event node - preserve style from original
  const eventStyle = eventNode?.style ? { ...eventNode.style } : undefined
  result.push({
    id: MULTI_FLOW_EVENT_NODE_ID,
    text: event,
    type: 'topic',
    position: { x: topicLeftEdge, y: centerY - getH(MULTI_FLOW_EVENT_NODE_ID) / 2 },
    ...(eventStyle && { style: eventStyle }),
  })

  // Causes — keep ids; restamp column index for color / stack order.
  causeNodes.forEach((node, index) => {
    const color = getMindmapBranchColor(index)
    const causeStyle = {
      ...(node.style || {}),
      width: uniformColumnWidth,
      minWidth: uniformColumnWidth,
      backgroundColor: color.fill,
      borderColor: color.border,
    }
    result.push({
      ...node,
      id: node.id,
      text: node.text,
      type: 'flow',
      position: {
        x: topicLeftEdge - arrowSpacing - uniformColumnWidth,
        y: causeYPositions[index],
      },
      data: stampMultiFlowData('cause', index, {
        ...node.data,
        [MULTI_FLOW_UID_DATA_KEY]: node.id,
      }),
      style: causeStyle,
    })
  })

  // Effects — keep ids; restamp column index for color / stack order.
  effectNodes.forEach((node, index) => {
    const color = getMindmapBranchColor(index)
    const effectStyle = {
      ...(node.style || {}),
      width: uniformColumnWidth,
      minWidth: uniformColumnWidth,
      backgroundColor: color.fill,
      borderColor: color.border,
    }
    result.push({
      ...node,
      id: node.id,
      text: node.text,
      type: 'flow',
      position: {
        x: topicRightEdge + arrowSpacing,
        y: effectYPositions[index],
      },
      data: stampMultiFlowData('effect', index, {
        ...node.data,
        [MULTI_FLOW_UID_DATA_KEY]: node.id,
      }),
      style: effectStyle,
    })
  })

  return result
}

/**
 * Load multi-flow map spec into diagram nodes and connections
 *
 * @param spec - Multi-flow map spec with event, causes, and effects
 * @returns SpecLoaderResult with nodes and connections
 */
export function loadMultiFlowMapSpec(spec: Record<string, unknown>): SpecLoaderResult {
  const event = (spec.event as string) || ''
  const causes = (spec.causes as string[]) || []
  const effects = (spec.effects as string[]) || []

  // Layout constants from layoutConfig
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const sideSpacing = DEFAULT_SIDE_SPACING
  const verticalSpacing = DEFAULT_VERTICAL_SPACING + 10 // 70px
  const nodeWidth = DEFAULT_NODE_WIDTH
  const nodeHeight = DEFAULT_NODE_HEIGHT
  const topicWidth = estimateMultiFlowTopicWidth(event)

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Event node - use multi-flow map specific width
  const claimedIds = new Set<string>([MULTI_FLOW_EVENT_NODE_ID])

  nodes.push({
    id: MULTI_FLOW_EVENT_NODE_ID,
    text: event,
    type: 'topic',
    position: { x: centerX - topicWidth / 2, y: centerY - nodeHeight / 2 },
  })

  // Causes
  const causeStartY = centerY - ((causes.length - 1) * verticalSpacing) / 2
  causes.forEach((cause, index) => {
    const color = getMindmapBranchColor(index)
    const causeId = takeMultiFlowMapStableId(claimedIds)
    nodes.push({
      id: causeId,
      text: cause,
      type: 'flow',
      position: {
        x: centerX - sideSpacing - nodeWidth / 2,
        y: causeStartY + index * verticalSpacing - nodeHeight / 2,
      },
      data: stampMultiFlowData('cause', index, { [MULTI_FLOW_UID_DATA_KEY]: causeId }),
      style: {
        backgroundColor: color.fill,
        borderColor: color.border,
      },
    })
    connections.push({
      id: `edge-${causeId}-${MULTI_FLOW_EVENT_NODE_ID}`,
      source: causeId,
      target: MULTI_FLOW_EVENT_NODE_ID,
      sourceHandle: 'right',
      targetHandle: `left-${index}`,
      style: { strokeColor: color.border },
    })
  })

  // Effects
  const effectStartY = centerY - ((effects.length - 1) * verticalSpacing) / 2
  effects.forEach((effect, index) => {
    const color = getMindmapBranchColor(index)
    const effectId = takeMultiFlowMapStableId(claimedIds)
    nodes.push({
      id: effectId,
      text: effect,
      type: 'flow',
      position: {
        x: centerX + sideSpacing - nodeWidth / 2,
        y: effectStartY + index * verticalSpacing - nodeHeight / 2,
      },
      data: stampMultiFlowData('effect', index, { [MULTI_FLOW_UID_DATA_KEY]: effectId }),
      style: {
        backgroundColor: color.fill,
        borderColor: color.border,
      },
    })
    connections.push({
      id: `edge-${MULTI_FLOW_EVENT_NODE_ID}-${effectId}`,
      source: MULTI_FLOW_EVENT_NODE_ID,
      target: effectId,
      sourceHandle: `right-${index}`,
      targetHandle: 'left',
      style: { strokeColor: color.border },
    })
  })

  return { nodes, connections }
}
