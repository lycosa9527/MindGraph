import { isPlaceholderText } from '@/composables/editor/placeholderText'
import type { Connection, DiagramNode } from '@/types'

export interface MindMapExplainContext {
  diagramType: string
  topic: string
  topLevelBranches: string[]
  ancestorPath: string[]
  siblingBranches: string[]
  childBranches: string[]
  selectedNode: string
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

  return {
    diagramType: diagramType === 'mind_map' ? 'mindmap' : (diagramType ?? 'mindmap'),
    topic,
    topLevelBranches,
    ancestorPath,
    siblingBranches,
    childBranches,
    selectedNode,
  }
}
