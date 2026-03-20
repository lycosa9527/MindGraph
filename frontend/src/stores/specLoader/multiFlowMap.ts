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
  MULTI_FLOW_MAP_TOPIC_WIDTH,
} from '@/composables/diagrams/layoutConfig'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection, DiagramNode } from '@/types'

import { measureTextWidth } from './textMeasurement'
import type { SpecLoaderResult } from './types'

/** FlowNode font size (matches FlowNode.vue defaultStyle) */
const FLOW_NODE_FONT_SIZE = 13
/** FlowNode horizontal padding: px-5 = 20px each side */
const FLOW_NODE_PADDING_X = 40

/**
 * Compute adaptive width for a cause/effect node from its text.
 * Used when nodeWidths has no stored width (e.g. newly added from palette).
 */
function computeFlowNodeWidth(text: string): number {
  const trimmed = (text || '').trim() || ' '
  const textW = typeof document !== 'undefined' ? measureTextWidth(trimmed, FLOW_NODE_FONT_SIZE) : 0
  return Math.max(DEFAULT_NODE_WIDTH, Math.ceil(textW + FLOW_NODE_PADDING_X))
}

/**
 * Recalculate multi-flow map layout from existing nodes
 * Called when nodes are added/deleted to update positions and re-index IDs
 * Preserves node text content
 *
 * @param nodes - Current diagram nodes
 * @param topicNodeWidth - Optional actual width of topic node (for dynamic width adjustment)
 * @param nodeWidths - Optional map of nodeId -> width for visual balance
 * @returns Recalculated nodes with updated positions and sequential IDs
 */
export function recalculateMultiFlowMapLayout(
  nodes: DiagramNode[],
  topicNodeWidth: number | null = null,
  nodeWidths: Record<string, number> = {}
): DiagramNode[] {
  if (!Array.isArray(nodes) || nodes.length === 0) {
    return []
  }

  // Extract event, causes, and effects from current nodes
  const eventNode = nodes.find((n) => n.id === 'event' || n.type === 'topic')
  const causeNodes = nodes
    .filter((n) => n.id?.startsWith('cause-'))
    .sort((a, b) => {
      const aIndex = parseInt(a.id?.replace('cause-', '') || '0', 10)
      const bIndex = parseInt(b.id?.replace('cause-', '') || '0', 10)
      return aIndex - bIndex
    })
  const effectNodes = nodes
    .filter((n) => n.id?.startsWith('effect-'))
    .sort((a, b) => {
      const aIndex = parseInt(a.id?.replace('effect-', '') || '0', 10)
      const bIndex = parseInt(b.id?.replace('effect-', '') || '0', 10)
      return aIndex - bIndex
    })

  const event = eventNode?.text || ''
  const causes = causeNodes.map((n) => n.text)
  const effects = effectNodes.map((n) => n.text)

  // Layout constants
  const centerX = DEFAULT_CENTER_X
  const centerY = DEFAULT_CENTER_Y
  const sideSpacing = DEFAULT_SIDE_SPACING
  const verticalSpacing = DEFAULT_VERTICAL_SPACING + 10 // 70px
  const nodeWidth = DEFAULT_NODE_WIDTH
  const nodeHeight = DEFAULT_NODE_HEIGHT

  // Use actual topic node width if provided, otherwise use multi-flow map specific default
  const actualTopicWidth = topicNodeWidth || MULTI_FLOW_MAP_TOPIC_WIDTH

  // Calculate uniform width for visual balance
  // Find max width among all cause and effect nodes
  // Use stored width when available (after user edit), otherwise compute from text
  let maxCauseWidth = nodeWidth
  let maxEffectWidth = nodeWidth

  causeNodes.forEach((node, index) => {
    const storedWidth = nodeWidths[`cause-${index}`] || nodeWidths[node.id || '']
    const width = storedWidth ?? computeFlowNodeWidth(node.text ?? '')
    maxCauseWidth = Math.max(maxCauseWidth, width)
  })

  effectNodes.forEach((node, index) => {
    const storedWidth = nodeWidths[`effect-${index}`] || nodeWidths[node.id || '']
    const width = storedWidth ?? computeFlowNodeWidth(node.text ?? '')
    maxEffectWidth = Math.max(maxEffectWidth, width)
  })

  // Use the maximum of both columns for visual balance
  const uniformColumnWidth = Math.max(maxCauseWidth, maxEffectWidth)

  // Calculate five columns for visual balance:
  // 1. Cause column width: uniformColumnWidth
  // 2. Left arrow column (spacing): leftArrowSpacing
  // 3. Topic column width: actualTopicWidth
  // 4. Right arrow column (spacing): rightArrowSpacing
  // 5. Effect column width: uniformColumnWidth

  // Balance the arrow columns (left and right) to be visually equal
  // User measured: right arrow appears ~1cm (38px) longer, so reduce right spacing
  // Reduced by 30%: left 200px -> 140px, right 162px -> 113px (maintaining compensation)
  const leftArrowSpacing = sideSpacing * 0.7
  const rightArrowSpacing = (sideSpacing - 38) * 0.7 // Compensate for visual difference (1cm ≈ 38px at 96 DPI)

  // Calculate edges based on balanced columns
  const topicLeftEdge = centerX - actualTopicWidth / 2
  const topicRightEdge = centerX + actualTopicWidth / 2

  const result: DiagramNode[] = []

  // Event node - preserve style from original
  const eventStyle = eventNode?.style ? { ...eventNode.style } : undefined
  result.push({
    id: 'event',
    text: event,
    type: 'topic',
    position: { x: topicLeftEdge, y: centerY - nodeHeight / 2 },
    ...(eventStyle && { style: eventStyle }),
  })

  // Causes - re-index with sequential IDs (cause-0, cause-1, etc.)
  const causeStartY = centerY - ((causes.length - 1) * verticalSpacing) / 2
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
      id: `cause-${index}`,
      text: node.text,
      type: 'flow',
      position: {
        x: topicLeftEdge - leftArrowSpacing - uniformColumnWidth,
        y: causeStartY + index * verticalSpacing - nodeHeight / 2,
      },
      data: { ...node.data, groupIndex: index },
      style: causeStyle,
    })
  })

  // Effects - re-index with sequential IDs (effect-0, effect-1, etc.)
  const effectStartY = centerY - ((effects.length - 1) * verticalSpacing) / 2
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
      id: `effect-${index}`,
      text: node.text,
      type: 'flow',
      position: {
        x: topicRightEdge + rightArrowSpacing,
        y: effectStartY + index * verticalSpacing - nodeHeight / 2,
      },
      data: { ...node.data, groupIndex: index },
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
  const topicWidth = MULTI_FLOW_MAP_TOPIC_WIDTH

  const nodes: DiagramNode[] = []
  const connections: Connection[] = []

  // Event node - use multi-flow map specific width
  nodes.push({
    id: 'event',
    text: event,
    type: 'topic',
    position: { x: centerX - topicWidth / 2, y: centerY - nodeHeight / 2 },
  })

  // Causes
  const causeStartY = centerY - ((causes.length - 1) * verticalSpacing) / 2
  causes.forEach((cause, index) => {
    const color = getMindmapBranchColor(index)
    nodes.push({
      id: `cause-${index}`,
      text: cause,
      type: 'flow',
      position: {
        x: centerX - sideSpacing - nodeWidth / 2,
        y: causeStartY + index * verticalSpacing - nodeHeight / 2,
      },
      data: { groupIndex: index },
      style: {
        backgroundColor: color.fill,
        borderColor: color.border,
      },
    })
    connections.push({
      id: `edge-cause-${index}`,
      source: `cause-${index}`,
      target: 'event',
      sourceHandle: 'right',
      targetHandle: `left-${index}`,
      style: { strokeColor: color.border },
    })
  })

  // Effects
  const effectStartY = centerY - ((effects.length - 1) * verticalSpacing) / 2
  effects.forEach((effect, index) => {
    const color = getMindmapBranchColor(index)
    nodes.push({
      id: `effect-${index}`,
      text: effect,
      type: 'flow',
      position: {
        x: centerX + sideSpacing - nodeWidth / 2,
        y: effectStartY + index * verticalSpacing - nodeHeight / 2,
      },
      data: { groupIndex: index },
      style: {
        backgroundColor: color.fill,
        borderColor: color.border,
      },
    })
    connections.push({
      id: `edge-effect-${index}`,
      source: 'event',
      target: `effect-${index}`,
      sourceHandle: `right-${index}`,
      targetHandle: 'left',
      style: { strokeColor: color.border },
    })
  })

  return { nodes, connections }
}
