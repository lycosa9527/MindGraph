import { INLINE_RECOMMENDATIONS_SUPPORTED_TYPES } from '@/composables/nodePalette/constants'
import type { Connection } from '@/types'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

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
  if (dt === 'mindmap') {
    return (
      nid.startsWith('branch-l-1-') ||
      nid.startsWith('branch-r-1-') ||
      nid.startsWith('branch-l-2-') ||
      nid.startsWith('branch-r-2-')
    )
  }
  if (dt === 'flow_map') {
    return nid.startsWith('flow-step-') || nid.startsWith('flow-substep-')
  }
  if (dt === 'tree_map') {
    return nid === 'dimension-label' || /^tree-cat-\d+$/.test(nid) || /^tree-leaf-/.test(nid)
  }
  if (dt === 'brace_map') {
    return nid === 'dimension-label' || node.type === 'brace' || nid.startsWith('brace-')
  }
  if (dt === 'circle_map') {
    return nid.startsWith('context-')
  }
  if (dt === 'bubble_map') {
    return nid.startsWith('bubble-')
  }
  if (dt === 'double_bubble_map') {
    return (
      nid.startsWith('similarity-') || nid.startsWith('left-diff-') || nid.startsWith('right-diff-')
    )
  }
  if (dt === 'multi_flow_map') {
    return nid.startsWith('cause-') || nid.startsWith('effect-')
  }
  if (dt === 'bridge_map') {
    return (
      nid === 'dimension-label' ||
      (nid.startsWith('pair-') && (nid.endsWith('-left') || nid.endsWith('-right')))
    )
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
