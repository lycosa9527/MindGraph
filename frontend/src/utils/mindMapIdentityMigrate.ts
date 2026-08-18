/**
 * Rewrite positional mind-map ids (`branch-r-1-0`) to stable identity ids
 * (existing `data.mindMapUid`, or a newly minted UUID).
 */
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import {
  MINDMAP_DEPTH_DATA_KEY,
  MINDMAP_SIDE_DATA_KEY,
  type MindMapSide,
  isLeftoverMindMapBranchId,
  mindMapBranchDataFields,
  mindMapNodeDepth,
  mindMapNodeSide,
  parsePositionalMindMapBranchId,
} from '@/utils/mindMapLocation'
import { MINDMAP_NODE_UID_DATA_KEY, readMindMapNodeUid } from '@/utils/mindMapNodeUid'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export const MINDMAP_LEGACY_ID_DATA_KEY = 'mindMapLegacyId'

export type MindMapIdentityIdMap = Record<string, string>

export type MindMapIdentityMigrateResult = {
  nodes: DiagramNode[]
  connections: Connection[]
  idMap: MindMapIdentityIdMap
  nodeStyles?: Record<string, NodeStyle>
}

function claimedIdentityIds(nodes: readonly DiagramNode[]): Set<string> {
  const claimed = new Set<string>()
  for (const node of nodes) {
    if (isLeftoverMindMapBranchId(node.id)) continue
    claimed.add(node.id)
    const uid = readMindMapNodeUid(node)
    if (uid) claimed.add(uid)
  }
  return claimed
}

function nextIdentityId(claimed: Set<string>, preferred: string | null): string {
  if (preferred && !claimed.has(preferred)) {
    claimed.add(preferred)
    return preferred
  }
  let minted = safeRandomUUID()
  while (claimed.has(minted)) {
    minted = safeRandomUUID()
  }
  claimed.add(minted)
  return minted
}

function rewriteStyleKeys(
  styles: Record<string, NodeStyle> | undefined,
  idMap: MindMapIdentityIdMap
): Record<string, NodeStyle> | undefined {
  if (!styles) return undefined
  const next: Record<string, NodeStyle> = {}
  for (const [key, value] of Object.entries(styles)) {
    next[idMap[key] ?? key] = value
  }
  return next
}

function stampLocation(
  node: DiagramNode,
  connections: Connection[],
  nodes: DiagramNode[]
): DiagramNode {
  const side = mindMapNodeSide(node.id, { node, nodes, connections })
  const depth = mindMapNodeDepth(node.id, { node, nodes, connections })
  if (!side && !node.data?.[MINDMAP_SIDE_DATA_KEY] && !node.data?.[MINDMAP_DEPTH_DATA_KEY]) {
    return node
  }
  return {
    ...node,
    data: {
      ...node.data,
      ...(side ? mindMapBranchDataFields(side, depth) : { [MINDMAP_DEPTH_DATA_KEY]: depth }),
    },
  }
}

/**
 * Convert positional branch ids to identity ids. Already-stable ids are kept.
 * Returns the same arrays when nothing positional remains.
 */
export function migrateMindMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): MindMapIdentityMigrateResult {
  const idMap: MindMapIdentityIdMap = {}
  const claimed = claimedIdentityIds(nodes)
  let changed = false

  const nextNodes = nodes.map((node) => {
    if (!isLeftoverMindMapBranchId(node.id)) {
      return node
    }
    const identity = nextIdentityId(claimed, readMindMapNodeUid(node))
    idMap[node.id] = identity
    changed = true
    const parsed = parsePositionalMindMapBranchId(node.id)
    const side: MindMapSide | null = parsed ? (parsed.side === 'l' ? 'left' : 'right') : null
    return {
      ...node,
      id: identity,
      data: {
        ...node.data,
        [MINDMAP_NODE_UID_DATA_KEY]: identity,
        [MINDMAP_LEGACY_ID_DATA_KEY]: node.id,
        ...(side ? mindMapBranchDataFields(side, parsed?.depth ?? 1) : {}),
      },
    }
  })

  if (!changed) {
    const stamped = nextNodes.map((node) => stampLocation(node, connections, nextNodes))
    return { nodes: stamped, connections, idMap, nodeStyles }
  }

  const nextConnections = connections.map((connection) => ({
    ...connection,
    source: idMap[connection.source] ?? connection.source,
    target: idMap[connection.target] ?? connection.target,
    id: rewriteEdgeId(connection.id, idMap),
  }))

  const stamped = nextNodes.map((node) => stampLocation(node, nextConnections, nextNodes))
  return {
    nodes: stamped,
    connections: nextConnections,
    idMap,
    nodeStyles: rewriteStyleKeys(nodeStyles, idMap),
  }
}

function rewriteEdgeId(edgeId: string, idMap: MindMapIdentityIdMap): string {
  let next = edgeId
  for (const [oldId, newId] of Object.entries(idMap)) {
    if (next.includes(oldId)) {
      next = next.split(oldId).join(newId)
    }
  }
  return next
}

export function remapIdList(
  ids: readonly string[] | null | undefined,
  idMap: MindMapIdentityIdMap
): string[] {
  if (!ids) return []
  return ids.map((id) => idMap[id] ?? id)
}

export function remapOptionalId(
  nodeId: string | null | undefined,
  idMap: MindMapIdentityIdMap
): string | null {
  if (!nodeId) return null
  return idMap[nodeId] ?? nodeId
}

function nodeResolveLabel(node: DiagramNode): string {
  const direct = typeof node.text === 'string' ? node.text.trim() : ''
  if (direct) return direct
  const label = node.data?.label
  return typeof label === 'string' ? label.trim() : ''
}

export function mindMapIdentityAliases(
  nodes: readonly DiagramNode[]
): Record<string, string> {
  const aliases: Record<string, string> = {}
  for (const node of nodes) {
    if (!node.id) continue
    aliases[node.id] = node.id
    const uid = readMindMapNodeUid(node)
    if (uid) aliases[uid] = node.id
    const legacy = node.data?.[MINDMAP_LEGACY_ID_DATA_KEY]
    if (typeof legacy === 'string' && legacy.trim()) {
      aliases[legacy.trim()] = node.id
    }
  }
  return aliases
}

function uniqueLabelId(hint: string, nodes: readonly DiagramNode[]): string | null {
  const matches = nodes.filter((node) => nodeResolveLabel(node) === hint)
  if (matches.length !== 1) return null
  return matches[0]?.id ?? null
}

/** Resolve id / uid / leftover invented id / unique label to the live canvas id. */
export function resolveMindMapIdentityId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = mindMapIdentityAliases(nodes)[cleaned] ?? uniqueLabelId(cleaned, nodes)
  if (mapped && isLeftoverMindMapBranchId(mapped)) return null
  return mapped
}
