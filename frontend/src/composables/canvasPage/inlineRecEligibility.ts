import { INLINE_RECOMMENDATIONS_SUPPORTED_TYPES } from '@/composables/nodePalette/constants'
import type { Connection } from '@/types'
import { isBraceMapPartNode } from '@/utils/braceMapIdentity'
import { isBridgeMapPairNode } from '@/utils/bridgeMapIdentity'
import { isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { isFlowMapStepNode, isFlowMapSubstepNode } from '@/utils/flowMapIdentity'
import { isMultiFlowCauseNode, isMultiFlowEffectNode } from '@/utils/multiFlowMapIdentity'
import { isTreeMapCategoryNode, isTreeMapLeafNode } from '@/utils/treeMapIdentity'

/**
 * Whether a node can show inline recommendations (Tab while editing).
 * `diagramType` should match store: mind_map normalized to mindmap where applicable.
 * For `concept_map`, pass `connections` so the default root concept (topic-linked) is excluded.
 */
export function isNodeEligibleForInlineRec(
  diagramType: string | null | undefined,
  node: { id?: string; type?: string; data?: { nodeType?: string } },
  connections?: Connection[] | null
): boolean {
  const dt = diagramType === 'mind_map' ? 'mindmap' : diagramType
  if (!dt || !(INLINE_RECOMMENDATIONS_SUPPORTED_TYPES as readonly string[]).includes(dt))
    return false
  const nid = node.id ?? ''
  if (dt === 'flow_map') {
    return isFlowMapStepNode(node) || isFlowMapSubstepNode(node)
  }
  if (dt === 'tree_map') {
    return nid === 'dimension-label' || isTreeMapCategoryNode(node) || isTreeMapLeafNode(node)
  }
  if (dt === 'brace_map') {
    return nid === 'dimension-label' || isBraceMapPartNode(node)
  }
  if (dt === 'circle_map') {
    return isCircleMapContextNode(node)
  }
  if (dt === 'bubble_map') {
    return isBubbleMapAttributeNode(node)
  }
  if (dt === 'double_bubble_map') {
    return readDoubleBubbleRole(node) != null
  }
  if (dt === 'multi_flow_map') {
    return isMultiFlowCauseNode(node) || isMultiFlowEffectNode(node)
  }
  if (dt === 'bridge_map') {
    return nid === 'dimension-label' || isBridgeMapPairNode(node)
  }
  if (dt === 'concept_map') {
    const d = node.data
    if (
      nid === 'topic' ||
      nid === 'center' ||
      nid === 'root' ||
      d?.nodeType === 'topic' ||
      node.type === 'topic' ||
      node.type === 'center'
    ) {
      return false
    }
    const rootTid = connections ? getTopicRootConceptTargetId(connections) : null
    if (rootTid && nid === rootTid) {
      return false
    }
    return true
  }
  return false
}
