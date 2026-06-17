import type { Connection, DiagramNode } from '@/types'

import { sortMindMapChildIds, sortMindMapTopicChildIds } from '@/config/mindMapGeometry'

export interface MindMapOutlineNode {
  id: string
  text: string
  depth: number
  children: MindMapOutlineNode[]
}

function getNodeText(node: DiagramNode): string {
  return String(node.text ?? (node.data as { label?: string } | undefined)?.label ?? '').trim()
}

function isMindMapRootNode(node: DiagramNode): boolean {
  return node.type === 'topic' || node.type === 'center' || node.id === 'topic' || node.id === 'root'
}

function buildChildrenMap(connections: Connection[]): Map<string, string[]> {
  const children = new Map<string, string[]>()
  for (const conn of connections) {
    const list = children.get(conn.source) ?? []
    list.push(conn.target)
    children.set(conn.source, list)
  }
  return children
}

function nodeY(nodeById: Map<string, DiagramNode>, nodeId: string): number {
  return nodeById.get(nodeId)?.position?.y ?? 0
}

/** Bidirectional mind map: right top→bottom, then left bottom→top (clockwise). */
function sortTopicLevelChildIds(
  childIds: string[],
  nodeById: Map<string, DiagramNode>
): string[] {
  const right = childIds.filter((id) => id.startsWith('branch-r-'))
  const left = childIds.filter((id) => id.startsWith('branch-l-'))
  const other = childIds.filter((id) => !id.startsWith('branch-r-') && !id.startsWith('branch-l-'))

  if (right.length === 0 && left.length === 0) {
    return sortMindMapTopicChildIds(childIds)
  }

  right.sort((a, b) => nodeY(nodeById, a) - nodeY(nodeById, b))
  left.sort((a, b) => nodeY(nodeById, b) - nodeY(nodeById, a))
  return [...right, ...left, ...other]
}

function sortOutlineChildIds(
  parentId: string,
  childIds: string[],
  nodeById: Map<string, DiagramNode>
): string[] {
  if (childIds.length <= 1) return childIds

  if (parentId === 'topic') {
    return sortTopicLevelChildIds(childIds, nodeById)
  }

  // Sub-branches on one side stack vertically — top to bottom matches canvas.
  const hasPositions = childIds.every((id) => nodeById.get(id)?.position != null)
  if (hasPositions) {
    return childIds.slice().sort((a, b) => nodeY(nodeById, a) - nodeY(nodeById, b))
  }

  return sortMindMapChildIds(childIds)
}

function buildNode(
  nodeId: string,
  nodeById: Map<string, DiagramNode>,
  childrenMap: Map<string, string[]>,
  depth: number
): MindMapOutlineNode | null {
  const node = nodeById.get(nodeId)
  if (!node) return null
  const childIds = sortOutlineChildIds(nodeId, childrenMap.get(nodeId) ?? [], nodeById)
  return {
    id: nodeId,
    text: getNodeText(node) || nodeId,
    depth,
    children: childIds
      .map((childId) => buildNode(childId, nodeById, childrenMap, depth + 1))
      .filter((child): child is MindMapOutlineNode => child != null),
  }
}

/** Build hierarchical outline tree from mind-map nodes and connections. */
export function buildMindMapOutlineTree(
  nodes: DiagramNode[],
  connections: Connection[]
): MindMapOutlineNode[] {
  if (!nodes.length) return []
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const childrenMap = buildChildrenMap(connections)
  const root =
    nodes.find(isMindMapRootNode) ??
    nodes.find((node) => !connections.some((conn) => conn.target === node.id))
  if (!root) return []
  const tree = buildNode(root.id, nodeById, childrenMap, 0)
  return tree ? [tree] : []
}
