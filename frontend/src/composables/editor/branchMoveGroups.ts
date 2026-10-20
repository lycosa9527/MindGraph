import { isBraceMapPartNode, isBraceMapReservedId } from '@/utils/braceMapIdentity'
import { isBridgeMapPairNode } from '@/utils/bridgeMapIdentity'
import { isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import {
  isFlowMapStepNode,
  isFlowMapSubstepNode,
  isLeftoverFlowMapId,
} from '@/utils/flowMapIdentity'
import { isMindMapBranchId } from '@/utils/mindMapLocation'
import { isMultiFlowCauseNode, isMultiFlowEffectNode } from '@/utils/multiFlowMapIdentity'
import {
  isLeftoverTreeMapId,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
} from '@/utils/treeMapIdentity'

/** Tree map: categories are top-level drop targets. */
export function isTopLevelTreeMapNode(
  nodeId: string,
  nodes?: readonly { id?: string; type?: string; data?: Record<string, unknown> }[] | null
): boolean {
  const node = nodes?.find((n) => n.id === nodeId)
  return Boolean(node && isTreeMapCategoryNode(node))
}

/**
 * Hierarchical drop targets after identity migrate: live mind-map branches
 * are UUIDs (or leftover ``branch-*``). Do not key off the leftover prefix.
 */
export function isHierarchicalDropCandidate(
  diagramType: string,
  nodeId: string,
  topicId: string,
  nodes?: readonly { id?: string; type?: string; data?: Record<string, unknown> }[] | null
): boolean {
  if (!nodeId || nodeId === topicId) return false
  if (diagramType === 'tree_map') {
    const node = nodes?.find((n) => n.id === nodeId)
    if (node) return isTreeMapCategoryNode(node) || isTreeMapLeafNode(node)
    return isLeftoverTreeMapId(nodeId)
  }
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    return isMindMapBranchId(nodeId, nodes)
  }
  return false
}

/**
 * Classify a node into a swap group. Nodes in the same group can be swapped.
 * Returns null if the node is not draggable (e.g. topic nodes).
 */
export function getSwapGroup(
  diagramType: string,
  nodeId: string,
  nodes?: { id?: string; type?: string; data?: Record<string, unknown> }[]
): string | null {
  const node = nodes?.find((n) => n.id === nodeId)
  switch (diagramType) {
    case 'mindmap':
    case 'mind_map':
      return isMindMapBranchId(nodeId, nodes) ? 'branch' : null
    case 'tree_map':
      if (node && (isTreeMapCategoryNode(node) || isTreeMapLeafNode(node))) return 'tree-node'
      return null
    case 'bubble_map':
      return node && isBubbleMapAttributeNode(node) ? 'bubble' : null
    case 'circle_map':
      return node && isCircleMapContextNode(node) ? 'context' : null
    case 'double_bubble_map': {
      const role = node ? readDoubleBubbleRole(node) : null
      if (role === 'similarity') return 'similarity'
      if (role === 'leftDiff' || role === 'rightDiff') return 'diff'
      return null
    }
    case 'flow_map': {
      if (node && (isFlowMapStepNode(node) || isFlowMapSubstepNode(node))) return 'flow-node'
      return isLeftoverFlowMapId(nodeId) ? 'flow-node' : null
    }
    case 'multi_flow_map':
      if (node && isMultiFlowCauseNode(node)) return 'cause'
      if (node && isMultiFlowEffectNode(node)) return 'effect'
      return null
    case 'brace_map':
      if (
        isBraceMapReservedId(nodeId) ||
        nodeId.startsWith('label-') ||
        nodeId.startsWith('dimension-')
      ) {
        return null
      }
      if (node && isBraceMapPartNode(node)) return 'brace'
      return node ? 'brace' : null
    case 'bridge_map':
      return node && isBridgeMapPairNode(node) ? 'pair' : null
    default:
      return null
  }
}

/** Whether the diagram type uses hierarchical move (vs simple swap). */
export function usesHierarchicalMove(diagramType: string): boolean {
  return diagramType === 'mindmap' || diagramType === 'mind_map' || diagramType === 'tree_map'
}

/** Get the topic node ID for hierarchical-move diagram types. */
export function getTopicId(diagramType: string): string {
  if (diagramType === 'tree_map') return 'tree-topic'
  return 'topic'
}
