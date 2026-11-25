/**
 * Drag-practice scoring.
 *
 * Flat sets may trade any unused member: circle contexts, bubble attributes,
 * double-bubble similarities, multi-flow causes, multi-flow effects.
 * Paired rows move only as a whole: double-bubble differences sit left and right;
 * a bridge analogy is the upper word and the lower word of the same bridge.
 * Hierarchies (mind map, tree, brace) trade a node only with its subtree, and
 * only while every descendant is still blank. Flow steps and concept-map nodes
 * stay on their own slot.
 */
import {
  findBridgePairSide,
  readBridgePairIndex,
  readBridgePairSide,
} from '@/utils/bridgeMapIdentity'
import { isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import {
  type DoubleBubbleRole,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import { isMindMapTreeConnection } from '@/utils/mindMapLocation'
import { readMultiFlowRole } from '@/utils/multiFlowMapIdentity'

export type DragPracticeNode = {
  id: string
  parentId?: string
  type?: string
  data?: Record<string, unknown>
}

export type DragPracticeConnection = {
  source: string
  target: string
  edgeType?: string
  sourceHandle?: string
}

const HIERARCHY = new Set(['mindmap', 'mind_map', 'tree_map', 'brace_map'])

function structuralParentId(
  nodeId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[]
): string | null {
  const node = nodes.find((item) => item.id === nodeId)
  const stamped = node?.parentId?.trim()
  if (stamped) return stamped
  const incoming = connections.filter(
    (edge) => edge.target === nodeId && isMindMapTreeConnection(edge)
  )
  if (incoming.length === 0) return null
  return incoming[0]?.source ?? null
}

/** Group key for blanks that may share answers. Unique key means exact slot. */
export function dragPracticeSlotGroup(
  diagramType: string | null | undefined,
  nodeId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[]
): string {
  const node = nodes.find((item) => item.id === nodeId)
  if (diagramType === 'circle_map') {
    if (node && isCircleMapContextNode(node)) return 'circle:context'
    return `node:${nodeId}`
  }
  if (diagramType === 'bubble_map') {
    if (node && isBubbleMapAttributeNode(node)) return 'bubble:attribute'
    return `node:${nodeId}`
  }
  if (diagramType === 'double_bubble_map') {
    const role = node ? readDoubleBubbleRole(node) : null
    if (role) return `role:${role}`
    return `node:${nodeId}`
  }
  if (diagramType === 'multi_flow_map') {
    const role = node ? readMultiFlowRole(node) : null
    if (role) return `role:${role}`
    return `node:${nodeId}`
  }
  if (diagramType === 'bridge_map') {
    // Stored "left" is the upper word and "right" is the lower word.
    // Those two make one vertical pair. Upper words never fill a lower blank.
    const side = node ? readBridgePairSide(node) : null
    if (side) return `bridge:${side}`
    return `node:${nodeId}`
  }
  if (diagramType && HIERARCHY.has(diagramType)) {
    const parentId = structuralParentId(nodeId, nodes, connections)
    if (parentId) return `parent:${parentId}`
  }
  return `node:${nodeId}`
}

function findNode(nodes: DragPracticeNode[], nodeId: string): DragPracticeNode | undefined {
  return nodes.find((item) => item.id === nodeId)
}

function oppositeDiffRole(role: DoubleBubbleRole | null): 'leftDiff' | 'rightDiff' | null {
  if (role === 'leftDiff') return 'rightDiff'
  if (role === 'rightDiff') return 'leftDiff'
  return null
}

/** The other side of the same comparison row, if this node is a difference. */
function differencePartnerId(nodeId: string, nodes: DragPracticeNode[]): string | null {
  const node = findNode(nodes, nodeId)
  if (!node) return null
  const opposite = oppositeDiffRole(readDoubleBubbleRole(node))
  const index = readDoubleBubbleIndex(node)
  if (!opposite || index < 0) return null
  const partner = nodes.find(
    (item) => readDoubleBubbleRole(item) === opposite && readDoubleBubbleIndex(item) === index
  )
  return partner?.id ?? null
}

/** The other word in this vertical bridge pair. Left is above the line, right is below. */
function bridgePartnerId(nodeId: string, nodes: DragPracticeNode[]): string | null {
  const node = findNode(nodes, nodeId)
  if (!node) return null
  const side = readBridgePairSide(node)
  const index = readBridgePairIndex(node)
  if (!side || index < 0) return null
  return findBridgePairSide(nodes, index, side === 'left' ? 'right' : 'left')?.id ?? null
}

function pairedPartnerId(
  diagramType: string | null | undefined,
  nodeId: string,
  nodes: DragPracticeNode[]
): string | null {
  if (diagramType === 'double_bubble_map') return differencePartnerId(nodeId, nodes)
  if (diagramType === 'bridge_map') return bridgePartnerId(nodeId, nodes)
  return null
}

function isPairedSide(
  diagramType: string | null | undefined,
  node: DragPracticeNode | undefined
): boolean {
  if (!node) return false
  if (diagramType === 'double_bubble_map') {
    const role = readDoubleBubbleRole(node)
    return role === 'leftDiff' || role === 'rightDiff'
  }
  if (diagramType === 'bridge_map') return readBridgePairSide(node) != null
  return false
}

function isBlankAndOpen(
  nodeId: string,
  blankIds: readonly string[],
  filledIds: readonly string[]
): boolean {
  return blankIds.includes(nodeId) && !filledIds.includes(nodeId)
}

function childIds(
  nodeId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[]
): string[] {
  const fromEdges = connections
    .filter((edge) => edge.source === nodeId && isMindMapTreeConnection(edge))
    .map((edge) => edge.target)
  if (fromEdges.length > 0) return fromEdges
  const fromParent = nodes.filter((node) => node.parentId === nodeId).map((node) => node.id)
  if (fromParent.length > 0) return fromParent
  return nodes.filter((node) => node.data?.parentCategoryId === nodeId).map((node) => node.id)
}

function treesAlign(
  sourceId: string,
  destId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[]
): boolean {
  const sourceChildren = childIds(sourceId, nodes, connections)
  const destChildren = childIds(destId, nodes, connections)
  if (sourceChildren.length !== destChildren.length) return false
  return sourceChildren.every((childId, index) =>
    treesAlign(childId, destChildren[index] ?? '', nodes, connections)
  )
}

function descendantsOpen(
  nodeId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[],
  blankIds: readonly string[],
  filledIds: readonly string[]
): boolean {
  return childIds(nodeId, nodes, connections).every(
    (childId) =>
      isBlankAndOpen(childId, blankIds, filledIds) &&
      descendantsOpen(childId, nodes, connections, blankIds, filledIds)
  )
}

/**
 * A paired chip may leave its row only when the whole pair can move.
 * A visible or already filled partner anchors that comparison.
 */
function pairCanMove(
  diagramType: string | null | undefined,
  sourceId: string,
  destId: string,
  nodes: DragPracticeNode[],
  blankIds: readonly string[],
  filledIds: readonly string[]
): boolean {
  if (sourceId === destId) return true
  const sourcePartner = pairedPartnerId(diagramType, sourceId, nodes)
  const destPartner = pairedPartnerId(diagramType, destId, nodes)
  if (!sourcePartner || !destPartner) return false
  return (
    isBlankAndOpen(sourcePartner, blankIds, filledIds) &&
    isBlankAndOpen(destPartner, blankIds, filledIds)
  )
}

function canTrade(
  diagramType: string | null | undefined,
  sourceId: string,
  destId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[],
  blankIds: readonly string[],
  filledIds: readonly string[]
): boolean {
  if (sourceId === destId) return true
  const source = findNode(nodes, sourceId)
  if (isPairedSide(diagramType, source)) {
    return pairCanMove(diagramType, sourceId, destId, nodes, blankIds, filledIds)
  }
  if (diagramType && HIERARCHY.has(diagramType)) {
    return (
      treesAlign(sourceId, destId, nodes, connections) &&
      descendantsOpen(sourceId, nodes, connections, blankIds, filledIds) &&
      descendantsOpen(destId, nodes, connections, blankIds, filledIds)
    )
  }
  return true
}

function swapAnswer(
  answers: Record<string, string>,
  sourceId: string,
  destId: string
): Record<string, string> {
  if (sourceId === destId) return answers
  const next = { ...answers }
  const sourceText = next[sourceId]
  next[sourceId] = next[destId]
  next[destId] = sourceText
  return next
}

function swapTree(
  answers: Record<string, string>,
  sourceId: string,
  destId: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[]
): Record<string, string> {
  let next = swapAnswer(answers, sourceId, destId)
  const sourceChildren = childIds(sourceId, nodes, connections)
  const destChildren = childIds(destId, nodes, connections)
  sourceChildren.forEach((childId, index) => {
    const destChild = destChildren[index]
    if (!destChild) return
    next = swapTree(next, childId, destChild, nodes, connections)
  })
  return next
}

export type DragPracticeDropMatch = {
  sourceId: string
  answers: Record<string, string>
}

/** Resolve a drop onto a blank using the diagram's own structure. */
export function dragPracticeResolveDrop(
  diagramType: string | null | undefined,
  nodeId: string,
  given: string,
  nodes: DragPracticeNode[],
  connections: DragPracticeConnection[],
  blankIds: readonly string[],
  filledIds: readonly string[],
  answers: Record<string, string>
): DragPracticeDropMatch | null {
  const text = given.trim()
  if (!text || !blankIds.includes(nodeId) || filledIds.includes(nodeId)) return null
  const group = dragPracticeSlotGroup(diagramType, nodeId, nodes, connections)
  const candidates = blankIds.filter((id) => {
    if (filledIds.includes(id)) return false
    if (dragPracticeSlotGroup(diagramType, id, nodes, connections) !== group) return false
    if (answers[id]?.trim() !== text) return false
    return canTrade(diagramType, id, nodeId, nodes, connections, blankIds, filledIds)
  })
  const sourceId = candidates.includes(nodeId) ? nodeId : candidates[0]
  if (!sourceId) return null
  let nextAnswers = answers
  if (sourceId !== nodeId) {
    const source = findNode(nodes, sourceId)
    if (isPairedSide(diagramType, source)) {
      nextAnswers = swapAnswer(answers, sourceId, nodeId)
      const sourcePartner = pairedPartnerId(diagramType, sourceId, nodes)
      const destPartner = pairedPartnerId(diagramType, nodeId, nodes)
      if (sourcePartner && destPartner) {
        nextAnswers = swapAnswer(nextAnswers, sourcePartner, destPartner)
      }
    } else if (diagramType && HIERARCHY.has(diagramType)) {
      nextAnswers = swapTree(answers, sourceId, nodeId, nodes, connections)
    } else {
      nextAnswers = swapAnswer(answers, sourceId, nodeId)
    }
  }
  return { sourceId, answers: nextAnswers }
}
