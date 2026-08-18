/**
 * Mind-map location derived from the tree — not from positional node ids.
 * `data.mindMapSide` / `data.mindMapDepth` are stamped at layout; positional
 * `branch-{l|r}-{depth}-{idx}` ids remain a fallback for unsaved specs.
 */
import type { Connection, DiagramNode } from '@/types'

export const MINDMAP_SIDE_DATA_KEY = 'mindMapSide'
export const MINDMAP_DEPTH_DATA_KEY = 'mindMapDepth'
export const MINDMAP_TOPIC_ID = 'topic'

export const POSITIONAL_MINDMAP_BRANCH_ID_RE = /^branch-([lr])-(\d+)-(\d+)$/
/** Old voice/template invented ids (`branch_0`, `sub_0_1`) — not UUIDs. */
export const INVENTED_MINDMAP_PREFIX_ID_RE = /^(?:[A-Za-z][\w]*_\d+(?:_\d+)*|branch-\d+)$/

export type MindMapSide = 'left' | 'right'
export type MindMapSideChar = 'l' | 'r'

export type PositionalMindMapBranchId = {
  side: MindMapSideChar
  depth: number
  globalIndex: number
}

type NodeDataLike = Record<string, unknown> | null | undefined

type NodeLike = {
  id?: string
  type?: string
  data?: NodeDataLike
}

type ConnectionLike = Pick<Connection, 'source' | 'target' | 'sourceHandle'>

export function isPositionalMindMapBranchId(nodeId: string): boolean {
  return POSITIONAL_MINDMAP_BRANCH_ID_RE.test(nodeId)
}

/** True when ``nodeId`` is a leftover invented address, not a stable UUID. */
export function isLeftoverMindMapBranchId(nodeId: string): boolean {
  return isPositionalMindMapBranchId(nodeId) || INVENTED_MINDMAP_PREFIX_ID_RE.test(nodeId)
}

export function parsePositionalMindMapBranchId(
  nodeId: string
): PositionalMindMapBranchId | null {
  const match = POSITIONAL_MINDMAP_BRANCH_ID_RE.exec(nodeId)
  if (!match) return null
  return {
    side: match[1] as MindMapSideChar,
    depth: Number.parseInt(match[2], 10),
    globalIndex: Number.parseInt(match[3], 10),
  }
}

export function mindMapSideFromChar(side: MindMapSideChar): MindMapSide {
  return side === 'l' ? 'left' : 'right'
}

export function mindMapSideToChar(side: MindMapSide): MindMapSideChar {
  return side === 'left' ? 'l' : 'r'
}

export function isMindMapTopicId(nodeId: string | undefined): boolean {
  return nodeId === MINDMAP_TOPIC_ID
}

export function isMindMapBranchNode(node: NodeLike | null | undefined): boolean {
  if (!node) return false
  if (node.id === MINDMAP_TOPIC_ID) return false
  if (node.type === 'branch') return true
  if (typeof node.id === 'string' && isPositionalMindMapBranchId(node.id)) return true
  return false
}

export function isMindMapBranchId(
  nodeId: string | undefined,
  nodes?: readonly NodeLike[] | null
): boolean {
  if (!nodeId || nodeId === MINDMAP_TOPIC_ID) return false
  if (isPositionalMindMapBranchId(nodeId)) return true
  if (!nodes) return false
  const node = nodes.find((item) => item.id === nodeId)
  return isMindMapBranchNode(node)
}

export function readMindMapSide(data: NodeDataLike): MindMapSide | null {
  const raw = data?.[MINDMAP_SIDE_DATA_KEY]
  if (raw === 'left' || raw === 'right') return raw
  return null
}

export function readMindMapDepth(data: NodeDataLike): number | null {
  const raw = data?.[MINDMAP_DEPTH_DATA_KEY]
  if (typeof raw !== 'number' || !Number.isInteger(raw) || raw < 1) return null
  return raw
}

function nodeDataFromUnknown(nodeOrData: NodeLike | NodeDataLike): NodeDataLike {
  if (!nodeOrData || typeof nodeOrData !== 'object') return undefined
  if ('data' in nodeOrData && (nodeOrData.data !== undefined || 'id' in nodeOrData)) {
    const nested = nodeOrData.data
    if (nested == null) return nested
    if (typeof nested === 'object') return nested as Record<string, unknown>
    return undefined
  }
  return nodeOrData as Record<string, unknown>
}

export function mindMapSideFromHandle(handle: string | undefined): MindMapSide | null {
  if (!handle) return null
  if (handle.startsWith('mindmap-left')) return 'left'
  if (handle.startsWith('mindmap-right')) return 'right'
  return null
}

function parentOfMap(connections: readonly ConnectionLike[]): Map<string, string> {
  const parentOf = new Map<string, string>()
  for (const connection of connections) {
    parentOf.set(connection.target, connection.source)
  }
  return parentOf
}

function l1AncestorId(nodeId: string, parentOf: Map<string, string>): string | null {
  let current: string | undefined = nodeId
  let lastBranch: string | null = null
  while (current && current !== MINDMAP_TOPIC_ID) {
    lastBranch = current
    current = parentOf.get(current)
  }
  return lastBranch
}

export function mindMapNodeDepthFromConnections(
  nodeId: string,
  connections: readonly ConnectionLike[]
): number | null {
  if (nodeId === MINDMAP_TOPIC_ID) return 0
  const parentOf = parentOfMap(connections)
  let depth = 0
  let current: string | undefined = nodeId
  while (current && current !== MINDMAP_TOPIC_ID) {
    const parent = parentOf.get(current)
    if (!parent) return depth > 0 ? depth : null
    depth += 1
    current = parent
  }
  return depth > 0 ? depth : null
}

export function isMindMapL1(
  nodeId: string,
  connections: readonly ConnectionLike[]
): boolean {
  if (nodeId === MINDMAP_TOPIC_ID) return false
  const parentOf = parentOfMap(connections)
  return parentOf.get(nodeId) === MINDMAP_TOPIC_ID
}

export function mindMapNodeSide(
  nodeId: string,
  options?: {
    node?: NodeLike | null
    nodes?: readonly NodeLike[] | null
    connections?: readonly ConnectionLike[] | null
  }
): MindMapSide | null {
  const node = options?.node ?? options?.nodes?.find((item) => item.id === nodeId)
  const stamped = readMindMapSide(node?.data)
  if (stamped) return stamped

  const connections = options?.connections
  if (connections && connections.length > 0) {
    const parentOf = parentOfMap(connections)
    const l1Id = l1AncestorId(nodeId, parentOf)
    if (l1Id) {
      const l1Node = options?.nodes?.find((item) => item.id === l1Id)
      const l1Stamped = readMindMapSide(l1Node?.data)
      if (l1Stamped) return l1Stamped
      const topicEdge = connections.find(
        (item) => item.source === MINDMAP_TOPIC_ID && item.target === l1Id
      )
      const fromHandle = mindMapSideFromHandle(topicEdge?.sourceHandle)
      if (fromHandle) return fromHandle
      const positionalL1 = parsePositionalMindMapBranchId(l1Id)
      if (positionalL1) return mindMapSideFromChar(positionalL1.side)
    }
  }

  const positional = parsePositionalMindMapBranchId(nodeId)
  if (positional) return mindMapSideFromChar(positional.side)
  return null
}

export function mindMapNodeDepth(
  nodeId: string,
  options?: {
    node?: NodeLike | null
    nodes?: readonly NodeLike[] | null
    connections?: readonly ConnectionLike[] | null
    nodeData?: NodeDataLike
  }
): number {
  const data = options?.nodeData ?? options?.node?.data
  const stamped = readMindMapDepth(data)
  if (stamped != null) return stamped

  if (options?.connections) {
    const walked = mindMapNodeDepthFromConnections(nodeId, options.connections)
    if (walked != null) return walked
  }

  const positional = parsePositionalMindMapBranchId(nodeId)
  return positional?.depth ?? 1
}

export function sortMindMapTopicChildIdsBySide(
  childIds: readonly string[],
  options?: {
    nodes?: readonly NodeLike[] | null
    connections?: readonly ConnectionLike[] | null
  }
): string[] {
  if (childIds.length <= 1) return [...childIds]
  const right: string[] = []
  const left: string[] = []
  const other: string[] = []
  for (const id of childIds) {
    const side = mindMapNodeSide(id, options)
    if (side === 'right') right.push(id)
    else if (side === 'left') left.push(id)
    else other.push(id)
  }
  if (right.length === 0 && left.length === 0) return [...childIds]
  return [...right, ...left, ...other]
}

export function mindMapLocationPathKey(
  nodeId: string,
  connections: readonly ConnectionLike[],
  options?: { nodes?: readonly NodeLike[] | null }
): string | null {
  if (nodeId === MINDMAP_TOPIC_ID) return MINDMAP_TOPIC_ID
  const side = mindMapNodeSide(nodeId, { connections, nodes: options?.nodes })
  if (!side) return null

  const parentOf = parentOfMap(connections)
  const childMap = new Map<string, string[]>()
  for (const connection of connections) {
    const kids = childMap.get(connection.source)
    if (kids) kids.push(connection.target)
    else childMap.set(connection.source, [connection.target])
  }

  const indices: number[] = []
  let current: string | undefined = nodeId
  while (current && current !== MINDMAP_TOPIC_ID) {
    const parent = parentOf.get(current)
    if (!parent) return null
    const siblings = childMap.get(parent) ?? []
    const idx = siblings.indexOf(current)
    if (idx < 0) return null
    indices.unshift(idx)
    current = parent
  }

  return `${mindMapSideToChar(side)}/${indices.join('/')}`
}

export function resolveMindMapDepthFromIdOrData(
  nodeId: string,
  nodeOrData?: NodeLike | NodeDataLike
): number {
  return mindMapNodeDepth(nodeId, {
    nodeData: nodeDataFromUnknown(nodeOrData),
    node: nodeOrData && typeof nodeOrData === 'object' && 'id' in nodeOrData ? nodeOrData : undefined,
  })
}

export function resolveMindMapSideFromIdOrData(
  nodeId: string | undefined,
  nodeOrData?: NodeLike | NodeDataLike
): MindMapSide | null {
  if (!nodeId) return null
  const node =
    nodeOrData && typeof nodeOrData === 'object' && 'id' in nodeOrData
      ? nodeOrData
      : { id: nodeId, data: nodeDataFromUnknown(nodeOrData) }
  return mindMapNodeSide(nodeId, { node })
}

export function mindMapBranchDataFields(
  side: MindMapSide,
  depth: number
): Record<string, unknown> {
  return {
    [MINDMAP_SIDE_DATA_KEY]: side,
    [MINDMAP_DEPTH_DATA_KEY]: depth,
  }
}
