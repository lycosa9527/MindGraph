import { sortMindMapChildIds } from '@/config/mindMapGeometry'
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

function nodeX(nodeById: Map<string, DiagramNode>, nodeId: string): number | null {
  const pos = nodeById.get(nodeId)?.position
  if (!pos || typeof pos.x !== 'number') return null
  return pos.x
}

function topicAndChildrenHavePositions(
  childIds: string[],
  nodeById: Map<string, DiagramNode>,
  topicId: string
): boolean {
  if (nodeX(nodeById, topicId) === null || nodeById.get(topicId)?.position?.y == null) {
    return false
  }
  return childIds.every((id) => {
    const n = nodeById.get(id)
    return n?.position != null && typeof n.position.x === 'number' && typeof n.position.y === 'number'
  })
}

/**
 * Geometric clockwise: right of topic top→bottom, then left bottom→top.
 * Side is ``x >= topic.x`` → right.
 */
function sortTopicLevelChildIdsBySide(
  childIds: string[],
  nodeById: Map<string, DiagramNode>,
  topicId: string
): string[] {
  const tx = nodeX(nodeById, topicId)
  if (tx === null) {
    return sortChildIdsByCanvasY(childIds, nodeById)
  }
  const right: string[] = []
  const left: string[] = []
  for (const id of childIds) {
    const x = nodeX(nodeById, id)
    if (x === null || x >= tx) right.push(id)
    else left.push(id)
  }
  return [
    ...sortChildIdsByCanvasY(right, nodeById),
    ...sortChildIdsByCanvasY(left, nodeById).slice().reverse(),
  ]
}

/**
 * Polar clockwise from 12 o'clock (matches Python ``_sort_ids_clockwise_from_topic``).
 * Angle 0 = above topic; increases through right → bottom → left.
 */
function sortIdsClockwiseFromTopic(
  childIds: string[],
  nodeById: Map<string, DiagramNode>,
  topicId: string
): string[] {
  if (childIds.length <= 1) return childIds.slice()
  const topic = nodeById.get(topicId)
  const tx = topic?.position?.x
  const ty = topic?.position?.y
  if (typeof tx !== 'number' || typeof ty !== 'number') {
    return sortChildIdsByCanvasY(childIds, nodeById)
  }
  const tau = Math.PI * 2
  return childIds.slice().sort((a, b) => {
    const posA = nodeById.get(a)?.position
    const posB = nodeById.get(b)?.position
    const ax = posA?.x
    const ay = posA?.y
    const bx = posB?.x
    const by = posB?.y
    const angleA =
      typeof ax === 'number' && typeof ay === 'number'
        ? ((Math.atan2(ax - tx, -(ay - ty)) % tau) + tau) % tau
        : tau
    const angleB =
      typeof bx === 'number' && typeof by === 'number'
        ? ((Math.atan2(bx - tx, -(by - ty)) % tau) + tau) % tau
        : tau
    if (angleA !== angleB) return angleA - angleB
    return childIds.indexOf(a) - childIds.indexOf(b)
  })
}

/**
 * Topic children in clockwise reading order: right column top→bottom, then
 * left column bottom→top. Matches layout `mindMapBranchesClockwiseOrder` and
 * presentation deep traversal (connection order can drift under sticky Y).
 *
 * Prefer geometric side-of-topic when positions exist; else ``branch-r-`` /
 * ``branch-l-`` prefixes; else polar from topic (12 o'clock).
 */
function sortTopicLevelChildIds(
  childIds: string[],
  nodeById: Map<string, DiagramNode>,
  topicId: string
): string[] {
  if (topicAndChildrenHavePositions(childIds, nodeById, topicId)) {
    return sortTopicLevelChildIdsBySide(childIds, nodeById, topicId)
  }

  const right = childIds.filter((id) => id.startsWith('branch-r-'))
  const left = childIds.filter((id) => id.startsWith('branch-l-'))
  const other = childIds.filter((id) => !id.startsWith('branch-r-') && !id.startsWith('branch-l-'))

  if (right.length === 0 && left.length === 0) {
    return sortIdsClockwiseFromTopic(childIds, nodeById, topicId)
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

  const parent = nodeById.get(parentId)
  const isTopicParent =
    parentId === 'topic' ||
    parentId === 'root' ||
    parent?.type === 'topic' ||
    parent?.type === 'center'
  if (isTopicParent) {
    return sortTopicLevelChildIds(childIds, nodeById, parentId)
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

/**
 * Stable sibling-order key for numbering cache.
 * Same sort as {@link buildMindMapOutlineTree}; ignores raw x/y float noise.
 */
export function mindMapOutlineOrderFingerprint(
  nodes: DiagramNode[],
  connections: Connection[]
): string {
  if (!nodes.length) return ''
  const nodeById = new Map(nodes.map((node) => [node.id, node]))
  const childrenMap = buildChildrenMap(connections)
  const parts: string[] = []
  for (const [parentId, childIds] of childrenMap) {
    const ordered = sortOutlineChildIds(parentId, childIds, nodeById)
    parts.push(`${parentId}:${ordered.join(',')}`)
  }
  parts.sort()
  return parts.join('|')
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
