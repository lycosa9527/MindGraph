import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import type { DiagramNode, DiagramType, NodeStyle } from '@/types'
import { isBraceMapPartNode } from '@/utils/braceMapIdentity'
import { BRIDGE_DIMENSION_LABEL_ID, isBridgeMapPairNode } from '@/utils/bridgeMapIdentity'
import { BUBBLE_TOPIC_NODE_ID, isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { CIRCLE_TOPIC_NODE_ID, isCircleMapContextNode } from '@/utils/circleMapIdentity'
import { isFlowMapStepNode, isFlowMapSubstepNode } from '@/utils/flowMapIdentity'
import { MULTI_FLOW_EVENT_NODE_ID } from '@/utils/multiFlowMapIdentity'
import {
  TREE_DIMENSION_LABEL_ID,
  TREE_TOPIC_NODE_ID,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
} from '@/utils/treeMapIdentity'

import type { DiagramContext } from './types'

const TYPOGRAPHY_STYLE_KEYS = [
  'fontSize',
  'fontWeight',
  'fontFamily',
  'fontStyle',
  'textDecoration',
] as const satisfies readonly (keyof NodeStyle)[]

export function nodeStylePatchHasTypography(style: Partial<NodeStyle> | undefined): boolean {
  if (!style) return false
  return TYPOGRAPHY_STYLE_KEYS.some((key) => style[key] !== undefined)
}

/** Stable watch sources for inline typography on thinking-map node hosts. */
export function typographyStyleWatchDeps(
  style: Pick<NodeStyle, (typeof TYPOGRAPHY_STYLE_KEYS)[number]> | undefined | null
): readonly [
  NodeStyle['fontSize'],
  NodeStyle['fontWeight'],
  NodeStyle['fontFamily'],
  NodeStyle['fontStyle'],
  NodeStyle['textDecoration'],
] {
  return [
    style?.fontSize,
    style?.fontWeight,
    style?.fontFamily,
    style?.fontStyle,
    style?.textDecoration,
  ]
}

function isLayoutDimensionLabel(nodeId: string): boolean {
  return (
    nodeId === TREE_DIMENSION_LABEL_ID ||
    nodeId === BRIDGE_DIMENSION_LABEL_ID ||
    nodeId === 'dimension-label'
  )
}

function thinkingMapTypographyRelayoutEligible(
  diagramType: DiagramType,
  nodeId: string,
  node: DiagramNode
): boolean {
  if (node.type === 'boundary') {
    return false
  }
  if (node.type === 'label' && !isLayoutDimensionLabel(nodeId)) {
    return false
  }
  switch (diagramType) {
    case 'multi_flow_map':
      return (
        nodeId === MULTI_FLOW_EVENT_NODE_ID ||
        node.type === 'topic' ||
        node.type === 'flow' ||
        node.type === 'center'
      )
    case 'bubble_map':
      return (
        nodeId === BUBBLE_TOPIC_NODE_ID ||
        isBubbleMapAttributeNode(node) ||
        node.type === 'bubble' ||
        node.type === 'child'
      )
    case 'circle_map':
      return (
        nodeId === CIRCLE_TOPIC_NODE_ID ||
        node.type === 'topic' ||
        node.type === 'center' ||
        isCircleMapContextNode(node)
      )
    case 'flow_map':
      return (
        nodeId === 'flow-topic' ||
        isFlowMapStepNode(node) ||
        isFlowMapSubstepNode(node) ||
        node.type === 'flow'
      )
    case 'brace_map':
      return (
        nodeId === 'brace-whole' ||
        nodeId === 'dimension-label' ||
        isBraceMapPartNode(node) ||
        node.type === 'brace'
      )
    case 'double_bubble_map':
      return true
    case 'tree_map':
      return (
        nodeId === TREE_TOPIC_NODE_ID ||
        nodeId === TREE_DIMENSION_LABEL_ID ||
        isTreeMapCategoryNode(node) ||
        isTreeMapLeafNode(node) ||
        node.type === 'topic' ||
        node.type === 'branch'
      )
    case 'bridge_map':
      return (
        nodeId === BRIDGE_DIMENSION_LABEL_ID ||
        node.type === 'topic' ||
        node.type === 'center' ||
        isBridgeMapPairNode(node)
      )
    default:
      return false
  }
}

/**
 * Drop cached DOM size and schedule layout when thinking-map inline typography changes.
 * Multi-flow and double-bubble keep their dedicated relayout channels.
 */
export function applyThinkingMapTypographyRelayout(
  ctx: DiagramContext,
  nodeId: string,
  oldNode: DiagramNode,
  stylePatch: Partial<NodeStyle> | undefined
): void {
  const diagramType = ctx.type.value
  if (!diagramType || !isThinkingMapDiagramType(diagramType)) {
    return
  }
  if (!nodeStylePatchHasTypography(stylePatch)) {
    return
  }
  if (!thinkingMapTypographyRelayoutEligible(diagramType, nodeId, oldNode)) {
    return
  }

  delete ctx.nodeDimensions.value[nodeId]

  if (diagramType === 'multi_flow_map') {
    ctx.multiFlowMapRecalcTrigger.value++
    ctx.layoutRecalcTrigger.value++
    return
  }

  if (diagramType === 'double_bubble_map') {
    ctx.viewBus.emit('diagram:double_bubble_relayout_requested', {})
    return
  }

  ctx.layoutRecalcTrigger.value++
}
