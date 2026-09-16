/**
 * Node Palette placeholder helpers - detect and collect placeholder nodes for replacement
 */
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import { isLearningSheetBlankDisplayText } from '@/stores/specLoader/utils'
import type { DiagramType } from '@/types'
import {
  findBraceMapWholeId,
  isBraceMapPartNode,
  isBraceMapReservedId,
  readBraceGroupIndex,
} from '@/utils/braceMapIdentity'
import {
  isBridgeMapPairNode,
  readBridgePairIndex,
  readBridgePairSide,
} from '@/utils/bridgeMapIdentity'
import { isBubbleMapAttributeNode, readBubbleGroupIndex } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode, readCircleContextIndex } from '@/utils/circleMapIdentity'
import { isDoubleBubbleRoleNode, readDoubleBubbleIndex } from '@/utils/doubleBubbleMapIdentity'
import { readFlowStepIndex, readFlowSubstepIndex } from '@/utils/flowMapIdentity'
import { isMindMapBranchNode, isMindMapL1, mindMapNodeDepth } from '@/utils/mindMapLocation'
import {
  isMultiFlowCauseNode,
  isMultiFlowEffectNode,
  readMultiFlowIndex,
} from '@/utils/multiFlowMapIdentity'
import {
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeCategoryIndex,
  readTreeLeafIndex,
} from '@/utils/treeMapIdentity'

import { LEARNING_SHEET_PLACEHOLDER } from './constants'

export { LEARNING_SHEET_PLACEHOLDER }

export function isNodePlaceholder(text: string | undefined): boolean {
  if (!text || !text.trim()) return false
  const trimmed = text.trim()
  return isLearningSheetBlankDisplayText(trimmed) || isPlaceholderText(trimmed)
}

function normalizeDiagramType(dt: DiagramType | null): DiagramType | null {
  return dt === 'mind_map' ? 'mindmap' : dt
}

/**
 * Get placeholder content nodes for replacement, sorted by diagram slot order.
 * @param parentId - For stage 2: only return placeholders of this parent (part_id, category_id, branch id)
 * @param connections - Used to filter placeholders by parent
 */
type PlaceholderNode = {
  id: string
  text: string
  type?: string
  data?: Record<string, unknown>
}

export function getPlaceholderNodes(
  diagramType: DiagramType | null,
  nodes: PlaceholderNode[],
  mode?: string | null,
  stage?: string | null,
  parentId?: string | null,
  connections?: Array<{ source: string; target: string }>
): Array<{ id: string; text: string }> {
  const dt = normalizeDiagramType(diagramType)
  if (!dt || !nodes.length) return []

  const isPlaceholder = (n: { text: string }) => isNodePlaceholder(n.text)

  switch (dt) {
    case 'circle_map':
      return nodes
        .filter((n) => isCircleMapContextNode(n) && isPlaceholder(n))
        .sort((a, b) => readCircleContextIndex(a) - readCircleContextIndex(b))
    case 'bubble_map':
      return nodes
        .filter((n) => isBubbleMapAttributeNode(n) && isPlaceholder(n))
        .sort((a, b) => readBubbleGroupIndex(a) - readBubbleGroupIndex(b))
    case 'multi_flow_map': {
      const isSlot = mode === 'effects' ? isMultiFlowEffectNode : isMultiFlowCauseNode
      return nodes
        .filter((n) => isSlot(n) && isPlaceholder(n))
        .sort((a, b) => readMultiFlowIndex(a) - readMultiFlowIndex(b))
    }
    case 'double_bubble_map':
      if (mode === 'differences') {
        const leftNodes = nodes
          .filter((n) => isDoubleBubbleRoleNode(n, 'leftDiff') && isPlaceholder(n))
          .sort((a, b) => readDoubleBubbleIndex(a) - readDoubleBubbleIndex(b))
        const rightNodes = nodes
          .filter((n) => isDoubleBubbleRoleNode(n, 'rightDiff') && isPlaceholder(n))
          .sort((a, b) => readDoubleBubbleIndex(a) - readDoubleBubbleIndex(b))
        return leftNodes.map((l, i) => ({
          id: `${l.id}|${rightNodes[i]?.id ?? ''}`,
          text: l.text,
        }))
      }
      return nodes
        .filter((n) => isDoubleBubbleRoleNode(n, 'similarity') && isPlaceholder(n))
        .sort((a, b) => readDoubleBubbleIndex(a) - readDoubleBubbleIndex(b))
    case 'flow_map': {
      if (stage === 'substeps') {
        let substepNodes = nodes.filter((n) => n.type === 'flowSubstep' && isPlaceholder(n))
        if (parentId && connections?.length) {
          const childIds = new Set(
            connections.filter((c) => c.source === parentId).map((c) => c.target)
          )
          substepNodes = substepNodes.filter((n) => childIds.has(n.id))
        }
        return substepNodes.sort(
          (a, b) =>
            readFlowStepIndex(a) - readFlowStepIndex(b) ||
            readFlowSubstepIndex(a) - readFlowSubstepIndex(b)
        )
      }
      return nodes
        .filter((n) => n.type === 'flow' && isPlaceholder(n))
        .sort((a, b) => readFlowStepIndex(a) - readFlowStepIndex(b))
    }
    case 'mindmap': {
      if (stage === 'children' && parentId && connections?.length) {
        const childIds = new Set(
          connections.filter((c) => c.source === parentId).map((c) => c.target)
        )
        const childBranches = nodes.filter(
          (n) => isMindMapBranchNode(n) && childIds.has(n.id) && isPlaceholder(n)
        )
        return childBranches.sort((a, b) => a.id.localeCompare(b.id))
      }
      const firstLevelBranches = nodes.filter((n) => {
        const isL1 = connections?.length
          ? isMindMapL1(n.id, connections)
          : mindMapNodeDepth(n.id, { node: n }) === 1
        return isL1 && isPlaceholder(n)
      })
      return firstLevelBranches.sort((a, b) => a.id.localeCompare(b.id))
    }
    case 'bridge_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      return nodes
        .filter(
          (n) => isBridgeMapPairNode(n) && readBridgePairSide(n) === 'left' && isPlaceholder(n)
        )
        .sort((a, b) => readBridgePairIndex(a) - readBridgePairIndex(b))
    }
    case 'tree_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      if (stage === 'children') {
        let leafNodes = nodes.filter((n) => isTreeMapLeafNode(n) && isPlaceholder(n))
        if (parentId && connections?.length) {
          const descendantIds = new Set<string>()
          const collect = (id: string) => {
            for (const c of connections) {
              if (c.source === id && !descendantIds.has(c.target)) {
                descendantIds.add(c.target)
                collect(c.target)
              }
            }
          }
          collect(parentId)
          leafNodes = leafNodes.filter((n) => descendantIds.has(n.id))
        }
        return leafNodes.sort(
          (a, b) =>
            readTreeCategoryIndex(a) - readTreeCategoryIndex(b) ||
            readTreeLeafIndex(a) - readTreeLeafIndex(b)
        )
      }
      return nodes
        .filter((n) => isTreeMapCategoryNode(n) && isPlaceholder(n))
        .sort((a, b) => readTreeCategoryIndex(a) - readTreeCategoryIndex(b))
    }
    case 'brace_map': {
      if (stage === 'dimensions') {
        const dimNode = nodes.find((n) => n.id === 'dimension-label')
        if (dimNode && (!dimNode.text?.trim() || isPlaceholder(dimNode))) {
          return [{ id: 'dimension-label', text: dimNode.text ?? '' }]
        }
        return []
      }
      if (stage === 'subparts') {
        let subpartNodes = nodes.filter(
          (n) => isBraceMapPartNode(n) && !isBraceMapReservedId(n.id) && isPlaceholder(n)
        )
        if (parentId && connections?.length) {
          const childIds = new Set(
            connections.filter((c) => c.source === parentId).map((c) => c.target)
          )
          subpartNodes = subpartNodes.filter((n) => childIds.has(n.id))
        } else if (connections?.length) {
          const rootTargets = new Set(connections.map((c) => c.target))
          const rootId = findBraceMapWholeId(nodes, connections)
          const partIds = new Set(
            connections.filter((c) => c.source === rootId).map((c) => c.target)
          )
          subpartNodes = subpartNodes.filter((n) => !partIds.has(n.id) && rootTargets.has(n.id))
        }
        return subpartNodes.sort((a, b) => readBraceGroupIndex(a) - readBraceGroupIndex(b))
      }
      const partNodes = nodes.filter((n) => {
        if (!isBraceMapPartNode(n) || isBraceMapReservedId(n.id) || !isPlaceholder(n)) return false
        if (!connections?.length) return true
        const rootId = findBraceMapWholeId(nodes, connections)
        return connections.some((c) => c.source === rootId && c.target === n.id)
      })
      return partNodes.sort((a, b) => readBraceGroupIndex(a) - readBraceGroupIndex(b))
    }
    case 'concept_map':
      return []
    default:
      return []
  }
}
