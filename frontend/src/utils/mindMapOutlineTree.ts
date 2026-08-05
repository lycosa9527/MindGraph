import { sortMindMapChildIds, sortMindMapTopicChildIds } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode } from '@/types'

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
  return (
    node.type === 'topic' || node.type === 'center' || node.id === 'topic' || node.id === 'root'
  )
}

/** Connection-list order (same contract as mindMapStylePreservation). */
function buildChildrenMap(connections: Connection[]): Map<string, string[]> {
  const children = new Map<string, string[]>()
  for (const conn of connections) {
    const list = children.get(conn.source)
    if (list) list.push(conn.target)
    else children.set(conn.source, [conn.target])
  }
  return children
}

function nodeY(nodeById: Map<string, DiagramNode>, nodeId: string): number {
  return nodeById.get(nodeId)?.position?.y ?? 0
}

function siblingsHavePositions(
  childIds: string[],
  nodeById: Map<string, DiagramNode>
): boolean {
  return childIds.every((id) => nodeById.get(id)?.position != null)
}

/** Top→bottom on canvas (ascending Y). Stable for equal Y via connection order. */
function sortChildIdsByCanvasY(
  childIds: string[],
  nodeById: Map<string, DiagramNode>
): string[] {
  if (childIds.length <= 1) return childIds
  if (!siblingsHavePositions(childIds, nodeById)) {
    return sortMindMapChildIds(childIds)
  }
  return childIds
    .slice()
    .sort((a, b) => {
      const dy = nodeY(nodeById, a) - nodeY(nodeById, b)
      if (dy !== 0) return dy
      return childIds.indexOf(a) - childIds.indexOf(b)
    })
}

/**
 * Topic children in clockwise reading order: right column top→bottom, then
 * left column bottom→top. Matches layout `mindMapBranchesClockwiseOrder` and
 * presentation deep traversal (connection order can drift under sticky Y).
 */
function sortTopicLevelChildIds(
  childIds: string[],
  nodeById: Map<string, DiagramNode>
): string[] {
  const right = childIds.filter((id) => id.startsWith('branch-r-'))
  const left = childIds.filter((id) => id.startsWith('branch-l-'))
  const other = childIds.filter((id) => !id.startsWith('branch-r-') && !id.startsWith('branch-l-'))

  if (right.length === 0 && left.length === 0) {
    return sortChildIdsByCanvasY(sortMindMapTopicChildIds(childIds), nodeById)
  }

  // Left stack is top→bottom on canvas; reverse for clockwise continuation.
  const leftClockwise = sortChildIdsByCanvasY(left, nodeById).slice().reverse()

  return [
    ...sortChildIdsByCanvasY(right, nodeById),
    ...leftClockwise,
    ...sortChildIdsByCanvasY(other, nodeById),
  ]
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

  return sortChildIdsByCanvasY(childIds, nodeById)
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

/** Flatten outline tree to id + text rows (pre-order), for sync assertions. */
export function flattenMindMapOutline(
  nodes: MindMapOutlineNode[]
): Array<{ id: string; text: string; depth: number }> {
  const rows: Array<{ id: string; text: string; depth: number }> = []
  function walk(list: MindMapOutlineNode[]): void {
    for (const node of list) {
      rows.push({ id: node.id, text: node.text, depth: node.depth })
      walk(node.children)
    }
  }
  walk(nodes)
  return rows
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
