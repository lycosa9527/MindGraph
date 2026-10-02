import { isPlaceholderText } from '@/composables/editor/placeholderText'
import type { Connection, DiagramNode } from '@/types'
import { BRACE_DIMENSION_LABEL_ID } from '@/utils/braceMapIdentity'
import {
  isBridgeMapPairNode,
  readBridgePairIndex,
  readBridgePairSide,
} from '@/utils/bridgeMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import {
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import {
  FLOW_TOPIC_NODE_ID,
  isFlowMapStepNode,
  isFlowMapSubstepNode,
  readFlowParentStepId,
  readFlowStepIndex,
  readFlowSubstepIndex,
} from '@/utils/flowMapIdentity'
import { readMultiFlowRole } from '@/utils/multiFlowMapIdentity'
import {
  TREE_DIMENSION_LABEL_ID,
  TREE_TOPIC_NODE_ID,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeCategoryIndex,
  readTreeLeafIndex,
  readTreeParentCategoryId,
} from '@/utils/treeMapIdentity'

export interface MindMapExplainContext {
  diagramType: string
  topic: string
  topLevelBranches: string[]
  ancestorPath: string[]
  siblingBranches: string[]
  childBranches: string[]
  selectedNode: string
  /** Thinking-map role sent to the explain prompt. Empty on a mind map center. */
  nodeRole: string
}

function uniqueIds(ids: string[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const id of ids) {
    if (!id || seen.has(id)) continue
    seen.add(id)
    result.push(id)
  }
  return result
}

function centerNodeIdsFor(diagramType: string | null | undefined): readonly string[] {
  switch (diagramType) {
    case 'double_bubble_map':
      return ['left-topic', 'right-topic']
    case 'tree_map':
      return ['tree-topic']
    case 'brace_map':
      return ['brace-whole']
    case 'flow_map':
      return ['flow-topic']
    case 'multi_flow_map':
      return ['event']
    case 'bridge_map':
      return ['dimension-label']
    default:
      return ['topic']
  }
}

function resolveCenters(
  nodes: DiagramNode[],
  diagramType: string | null | undefined
): DiagramNode[] {
  const found = centerNodeIdsFor(diagramType)
    .map((id) => nodes.find((node) => node.id === id))
    .filter((node): node is DiagramNode => Boolean(node))
  if (found.length > 0) return found
  return nodes.filter(
    (node) => node.type === 'topic' || node.type === 'center' || node.type === 'whole'
  )
}

/** Center used to place the explain research panel beside the diagram. */
export function findExplainCenterNode<T extends { id: string }>(
  nodes: readonly T[],
  diagramType: string | null | undefined
): T | undefined {
  for (const id of centerNodeIdsFor(diagramType)) {
    const hit = nodes.find((node) => node.id === id)
    if (hit) return hit
  }
  return undefined
}

function linkedChildIds(
  parentId: string,
  connections: Connection[],
  centerIds: ReadonlySet<string>,
  includeInboundToCenter: boolean
): string[] {
  const ids = connections.filter((link) => link.source === parentId).map((link) => link.target)
  if (includeInboundToCenter && centerIds.has(parentId)) {
    for (const link of connections) {
      if (link.target === parentId) ids.push(link.source)
    }
  }
  return uniqueIds(ids)
}

function parentIdOf(
  nodeId: string,
  connections: Connection[],
  centerIds: ReadonlySet<string>
): string | null {
  const incoming = connections.find((link) => link.target === nodeId)
  if (incoming?.source) return incoming.source
  const towardCenter = connections.find(
    (link) => link.source === nodeId && centerIds.has(link.target)
  )
  return towardCenter?.target ?? null
}

function flatContentIds(nodes: DiagramNode[], centerIds: ReadonlySet<string>): string[] {
  return nodes
    .filter((node) => !centerIds.has(node.id) && node.type !== 'boundary')
    .map((node) => node.id)
}

function usableLabel(text: string): string {
  const trimmed = text.trim()
  if (!trimmed || isPlaceholderText(trimmed)) return ''
  return trimmed
}

function labelsForIds(ids: string[], nodeMap: Map<string, DiagramNode>): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const id of ids) {
    const label = usableLabel(nodeMap.get(id)?.text ?? '')
    if (!label || seen.has(label)) continue
    seen.add(label)
    result.push(label)
  }
  return result
}

function buildAncestorPath(
  nodeId: string,
  connections: Connection[],
  nodeMap: Map<string, DiagramNode>,
  centerIds: ReadonlySet<string>
): string[] {
  const path: string[] = []
  let current = parentIdOf(nodeId, connections, centerIds)
  while (current && !centerIds.has(current)) {
    const label = usableLabel(nodeMap.get(current)?.text ?? '')
    if (label) {
      path.unshift(label)
    }
    current = parentIdOf(current, connections, centerIds)
  }
  return path
}

const MAX_BRANCHES = 16

export function collectMindMapExplainContext(
  nodes: DiagramNode[],
  connections: Connection[],
  selectedNodeId: string,
  diagramType: string | null | undefined = 'mindmap'
): MindMapExplainContext | null {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const selected = nodeMap.get(selectedNodeId)
  if (!selected) return null

  const selectedNode = usableLabel(selected.text ?? '')
  if (!selectedNode) return null

  const centers = resolveCenters(nodes, diagramType)
  const centerIds = new Set(centers.map((node) => node.id))
  const selectedIsCenter = centerIds.has(selectedNodeId)
  const topic =
    centers
      .map((node) => usableLabel(node.text ?? ''))
      .filter(Boolean)
      .join(' / ') || (selectedIsCenter ? selectedNode : '')

  const inboundToCenter = diagramType === 'multi_flow_map'
  const linkedTopLevel = uniqueIds(
    centers.flatMap((node) => linkedChildIds(node.id, connections, centerIds, inboundToCenter))
  )
  const flat = linkedTopLevel.length === 0
  const topLevelIds = flat ? flatContentIds(nodes, centerIds) : linkedTopLevel
  const topLevelBranches = labelsForIds(topLevelIds, nodeMap).slice(0, MAX_BRANCHES)

  const ancestorPath = selectedIsCenter
    ? []
    : buildAncestorPath(selectedNodeId, connections, nodeMap, centerIds)

  const parentId = selectedIsCenter
    ? null
    : flat
      ? (centers[0]?.id ?? null)
      : parentIdOf(selectedNodeId, connections, centerIds)
  const siblingSource = flat
    ? topLevelIds
    : parentId
      ? linkedChildIds(parentId, connections, centerIds, inboundToCenter)
      : []
  const siblingBranches =
    parentId === null
      ? []
      : labelsForIds(
          siblingSource.filter((id) => id !== selectedNodeId),
          nodeMap
        ).slice(0, MAX_BRANCHES)

  const childSource =
    selectedIsCenter && flat
      ? topLevelIds
      : linkedChildIds(selectedNodeId, connections, centerIds, inboundToCenter)
  const childBranches = labelsForIds(childSource, nodeMap).slice(0, MAX_BRANCHES)
  const resolvedType = diagramType === 'mind_map' ? 'mindmap' : (diagramType ?? 'mindmap')
  const role = explainNodeRole(selected, resolvedType, selectedIsCenter, ancestorPath.length)
  const grouped = regroupThinkingMapLists(
    nodes,
    connections,
    selectedNodeId,
    selectedNode,
    resolvedType
  )

  return {
    diagramType: resolvedType,
    topic,
    topLevelBranches: grouped?.topLevelBranches ?? topLevelBranches,
    ancestorPath: grouped ? grouped.ancestorPath : ancestorPath,
    siblingBranches: grouped?.siblingBranches ?? siblingBranches,
    childBranches:
      !grouped && resolvedType === 'brace_map' && selectedIsCenter
        ? []
        : (grouped?.childBranches ?? childBranches),
    selectedNode,
    nodeRole: grouped?.nodeRole || role,
  }
}

function explainNodeRole(
  node: DiagramNode,
  diagramType: string,
  selectedIsCenter: boolean,
  ancestorCount: number
): string {
  if (diagramType === 'circle_map') {
    if (selectedIsCenter) return 'topic'
    return isCircleMapContextNode(node) ? 'context' : ''
  }
  if (diagramType === 'bubble_map') return selectedIsCenter ? 'topic' : 'attribute'
  if (diagramType === 'tree_map') {
    if (node.id === TREE_DIMENSION_LABEL_ID) return 'dimension'
    if (selectedIsCenter) return 'topic'
    if (isTreeMapLeafNode(node) || ancestorCount > 0) return 'item'
    if (isTreeMapCategoryNode(node) || ancestorCount === 0) return 'category'
  }
  if (diagramType === 'brace_map') {
    if (node.id === BRACE_DIMENSION_LABEL_ID) return 'dimension'
    if (selectedIsCenter) return 'whole'
    return ancestorCount > 0 ? 'subpart' : 'part'
  }
  if (diagramType === 'flow_map') {
    if (selectedIsCenter) return 'topic'
    return isFlowMapSubstepNode(node) ? 'substep' : 'step'
  }
  if (diagramType === 'bridge_map') {
    if (selectedIsCenter) return 'relating_factor'
    const side = readBridgePairSide(node)
    if (side === 'left') return 'analogy_left'
    if (side === 'right') return 'analogy_right'
    return 'analogy'
  }
  if (diagramType === 'concept_map') return selectedIsCenter ? 'topic' : 'concept'
  if (diagramType === 'mindmap') {
    if (selectedIsCenter) return 'topic'
    return ancestorCount > 0 ? 'child' : 'branch'
  }
  return ''
}

function regroupThinkingMapLists(
  nodes: DiagramNode[],
  connections: Connection[],
  selectedNodeId: string,
  selectedLabel: string,
  diagramType: string
): Pick<
  MindMapExplainContext,
  'topLevelBranches' | 'ancestorPath' | 'siblingBranches' | 'childBranches' | 'nodeRole'
> | null {
  if (diagramType === 'multi_flow_map')
    return regroupMultiFlow(nodes, selectedNodeId, selectedLabel)
  if (diagramType === 'double_bubble_map')
    return regroupDoubleBubble(nodes, selectedNodeId, selectedLabel)
  if (diagramType === 'bridge_map') return regroupBridge(nodes, selectedNodeId, selectedLabel)
  if (diagramType === 'tree_map') return regroupTree(nodes, selectedNodeId, selectedLabel)
  if (diagramType === 'flow_map') return regroupFlow(nodes, selectedNodeId, selectedLabel)
  if (diagramType === 'concept_map') return regroupConcept(nodes, connections, selectedNodeId)
  return null
}

function labelsOf(nodes: DiagramNode[]): string[] {
  return labelsForIds(
    nodes.map((node) => node.id),
    new Map(nodes.map((node) => [node.id, node]))
  ).slice(0, MAX_BRANCHES)
}

function withoutSelf(labels: string[], selectedLabel: string): string[] {
  return labels.filter((label) => label !== selectedLabel)
}

function regroupMultiFlow(
  nodes: DiagramNode[],
  selectedNodeId: string,
  selectedLabel: string
): Pick<
  MindMapExplainContext,
  'topLevelBranches' | 'ancestorPath' | 'siblingBranches' | 'childBranches' | 'nodeRole'
> | null {
  const causes = labelsOf(nodes.filter((node) => readMultiFlowRole(node) === 'cause'))
  const effects = labelsOf(nodes.filter((node) => readMultiFlowRole(node) === 'effect'))
  if (causes.length === 0 && effects.length === 0) return null
  const selected = nodes.find((node) => node.id === selectedNodeId)
  const rawRole = selected ? readMultiFlowRole(selected) : null
  const nodeRole = rawRole ?? (selectedNodeId === 'event' ? 'event' : '')
  let peers: string[] = []
  if (nodeRole === 'cause') peers = withoutSelf(causes, selectedLabel)
  if (nodeRole === 'effect') peers = withoutSelf(effects, selectedLabel)
  return {
    topLevelBranches: causes,
    ancestorPath: [],
    siblingBranches: peers,
    childBranches: effects,
    nodeRole,
  }
}

function regroupDoubleBubble(
  nodes: DiagramNode[],
  selectedNodeId: string,
  selectedLabel: string
): Pick<
  MindMapExplainContext,
  'topLevelBranches' | 'ancestorPath' | 'siblingBranches' | 'childBranches' | 'nodeRole'
> | null {
  const similarities = labelsOf(nodes.filter((node) => readDoubleBubbleRole(node) === 'similarity'))
  const leftDiffs = labelsOf(nodes.filter((node) => readDoubleBubbleRole(node) === 'leftDiff'))
  const rightDiffs = labelsOf(nodes.filter((node) => readDoubleBubbleRole(node) === 'rightDiff'))
  if (similarities.length === 0 && leftDiffs.length === 0 && rightDiffs.length === 0) return null
  const selected = nodes.find((node) => node.id === selectedNodeId)
  const raw = selected ? readDoubleBubbleRole(selected) : null
  let nodeRole = ''
  if (selectedNodeId === DOUBLE_BUBBLE_LEFT_TOPIC_ID) nodeRole = 'left_topic'
  else if (selectedNodeId === DOUBLE_BUBBLE_RIGHT_TOPIC_ID) nodeRole = 'right_topic'
  else if (raw === 'similarity') nodeRole = 'similarity'
  else if (raw === 'leftDiff') nodeRole = 'left_diff'
  else if (raw === 'rightDiff') nodeRole = 'right_diff'
  const sameRole =
    nodeRole === 'similarity'
      ? similarities
      : nodeRole === 'left_diff'
        ? leftDiffs
        : nodeRole === 'right_diff'
          ? rightDiffs
          : []
  const leftSide = nodeRole === 'left_diff' ? [] : leftDiffs.map((label) => `左：${label}`)
  const rightSide = nodeRole === 'right_diff' ? [] : rightDiffs.map((label) => `右：${label}`)
  const differences = [...leftSide, ...rightSide]
  return {
    topLevelBranches:
      nodeRole === 'similarity' ? similarities : withoutSelf(similarities, selectedLabel),
    ancestorPath: [],
    siblingBranches: withoutSelf(sameRole, selectedLabel),
    childBranches: differences.slice(0, MAX_BRANCHES),
    nodeRole,
  }
}

function regroupBridge(
  nodes: DiagramNode[],
  selectedNodeId: string,
  selectedLabel: string
): Pick<
  MindMapExplainContext,
  'topLevelBranches' | 'ancestorPath' | 'siblingBranches' | 'childBranches' | 'nodeRole'
> | null {
  const pairs = nodes.filter((node) => isBridgeMapPairNode(node))
  if (pairs.length === 0) return null
  const byIndex = new Map<number, { left: string; right: string }>()
  for (const node of pairs) {
    const index = readBridgePairIndex(node)
    const side = readBridgePairSide(node)
    const label = usableLabel(node.text ?? '')
    if (!label || !side) continue
    const slot = byIndex.get(index) ?? { left: '', right: '' }
    slot[side] = label
    byIndex.set(index, slot)
  }
  const ordered = [...byIndex.entries()].sort((left, right) => left[0] - right[0])
  const pairLabels = ordered
    .map(([, pair]) =>
      pair.left && pair.right ? `${pair.left} / ${pair.right}` : pair.left || pair.right
    )
    .filter(Boolean)
    .slice(0, MAX_BRANCHES)
  const selected = nodes.find((node) => node.id === selectedNodeId)
  const side = selected ? readBridgePairSide(selected) : null
  const index = selected ? readBridgePairIndex(selected) : -1
  const pair = byIndex.get(index)
  const other = side === 'left' ? pair?.right : side === 'right' ? pair?.left : ''
  return {
    topLevelBranches: pairLabels,
    ancestorPath: [],
    siblingBranches: other && other !== selectedLabel ? [other] : [],
    childBranches: [],
    nodeRole: side === 'left' ? 'analogy_left' : side === 'right' ? 'analogy_right' : '',
  }
}

function byReadIndex(readIndex: (node: DiagramNode) => number) {
  return (left: DiagramNode, right: DiagramNode): number => {
    const delta = readIndex(left) - readIndex(right)
    if (delta !== 0) return delta
    return left.id.localeCompare(right.id)
  }
}

function regroupTree(
  nodes: DiagramNode[],
  selectedNodeId: string,
  selectedLabel: string
): Pick<
  MindMapExplainContext,
  'topLevelBranches' | 'ancestorPath' | 'siblingBranches' | 'childBranches' | 'nodeRole'
> | null {
  const categories = nodes
    .filter((node) => isTreeMapCategoryNode(node))
    .slice()
    .sort(byReadIndex(readTreeCategoryIndex))
  const leaves = nodes.filter((node) => isTreeMapLeafNode(node))
  if (categories.length === 0 && leaves.length === 0) return null
  const categoryLabels = labelsOf(categories)
  const selected = nodes.find((node) => node.id === selectedNodeId)
  if (selected?.id === TREE_TOPIC_NODE_ID) {
    return {
      topLevelBranches: categoryLabels,
      ancestorPath: [],
      siblingBranches: [],
      childBranches: [],
      nodeRole: 'topic',
    }
  }
  if (!selected || selected.id === TREE_DIMENSION_LABEL_ID) {
    return {
      topLevelBranches: categoryLabels,
      ancestorPath: [],
      siblingBranches: [],
      childBranches: [],
      nodeRole: 'dimension',
    }
  }
  if (isTreeMapCategoryNode(selected)) {
    const items = leaves
      .filter((leaf) => readTreeParentCategoryId(leaf) === selected.id)
      .slice()
      .sort(byReadIndex(readTreeLeafIndex))
    return {
      topLevelBranches: categoryLabels,
      ancestorPath: [],
      siblingBranches: withoutSelf(categoryLabels, selectedLabel),
      childBranches: labelsOf(items),
      nodeRole: 'category',
    }
  }
  if (!isTreeMapLeafNode(selected)) return null
  const parentId = readTreeParentCategoryId(selected)
  const parent = nodes.find((node) => node.id === parentId)
  const peers = leaves
    .filter((leaf) => readTreeParentCategoryId(leaf) === parentId)
    .slice()
    .sort(byReadIndex(readTreeLeafIndex))
  const parentLabel = parent ? usableLabel(parent.text ?? '') : ''
  return {
    topLevelBranches: categoryLabels,
    ancestorPath: parentLabel ? [parentLabel] : [],
    siblingBranches: withoutSelf(labelsOf(peers), selectedLabel),
    childBranches: [],
    nodeRole: 'item',
  }
}

function regroupFlow(
  nodes: DiagramNode[],
  selectedNodeId: string,
  selectedLabel: string
): Pick<
  MindMapExplainContext,
  'topLevelBranches' | 'ancestorPath' | 'siblingBranches' | 'childBranches' | 'nodeRole'
> | null {
  const steps = nodes
    .filter((node) => node.id !== FLOW_TOPIC_NODE_ID && isFlowMapStepNode(node))
    .slice()
    .sort(byReadIndex(readFlowStepIndex))
  const substeps = nodes.filter((node) => isFlowMapSubstepNode(node))
  if (steps.length === 0 && substeps.length === 0) return null
  const stepLabels = labelsOf(steps)
  const selected = nodes.find((node) => node.id === selectedNodeId)
  if (!selected || selected.id === FLOW_TOPIC_NODE_ID) {
    return {
      topLevelBranches: stepLabels,
      ancestorPath: [],
      siblingBranches: [],
      childBranches: [],
      nodeRole: 'topic',
    }
  }
  if (isFlowMapSubstepNode(selected)) {
    const parentId = readFlowParentStepId(selected)
    const parent = nodes.find((node) => node.id === parentId)
    const peers = substeps
      .filter((node) => readFlowParentStepId(node) === parentId)
      .slice()
      .sort(byReadIndex(readFlowSubstepIndex))
    const parentLabel = parent ? usableLabel(parent.text ?? '') : ''
    return {
      topLevelBranches: stepLabels,
      ancestorPath: parentLabel ? [parentLabel] : [],
      siblingBranches: withoutSelf(labelsOf(peers), selectedLabel),
      childBranches: [],
      nodeRole: 'substep',
    }
  }
  const mine = substeps
    .filter((node) => readFlowParentStepId(node) === selected.id)
    .slice()
    .sort(byReadIndex(readFlowSubstepIndex))
  return {
    topLevelBranches: stepLabels,
    ancestorPath: [],
    siblingBranches: withoutSelf(stepLabels, selectedLabel),
    childBranches: labelsOf(mine),
    nodeRole: 'step',
  }
}

function relationPhrase(
  link: Connection,
  selectedNodeId: string,
  nodeMap: Map<string, DiagramNode>
): string {
  const label = (link.label ?? '').trim()
  const outbound = link.source === selectedNodeId
  const otherId = outbound ? link.target : link.source
  const other = usableLabel(nodeMap.get(otherId)?.text ?? '')
  if (!other) return ''
  if (!label) return other
  return outbound ? `${label} → ${other}` : `${other} —${label}→`
}

function regroupConcept(
  nodes: DiagramNode[],
  connections: Connection[],
  selectedNodeId: string
): Pick<
  MindMapExplainContext,
  'topLevelBranches' | 'ancestorPath' | 'siblingBranches' | 'childBranches' | 'nodeRole'
> | null {
  const concepts = nodes.filter((node) => node.id !== 'topic' && node.type !== 'boundary')
  if (concepts.length === 0) return null
  const nodeMap = new Map(nodes.map((node) => [node.id, node]))
  const selectedLabel = usableLabel(nodeMap.get(selectedNodeId)?.text ?? '')
  const relations = connections
    .filter((link) => link.source === selectedNodeId || link.target === selectedNodeId)
    .map((link) => relationPhrase(link, selectedNodeId, nodeMap))
    .filter(Boolean)
    .slice(0, MAX_BRANCHES)
  return {
    topLevelBranches: withoutSelf(labelsOf(concepts), selectedLabel),
    ancestorPath: [],
    siblingBranches: relations,
    childBranches: [],
    nodeRole: selectedNodeId === 'topic' ? 'topic' : 'concept',
  }
}
