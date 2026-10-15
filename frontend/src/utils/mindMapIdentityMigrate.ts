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
import { stableMindMapIdentityId } from '@/utils/mindMapStableId'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export const MINDMAP_LEGACY_ID_DATA_KEY = 'mindMapLegacyId'
export const MINDMAP_ALIAS_IDS_DATA_KEY = 'mindMapAliasIds'

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

function nextIdentityId(
  claimed: Set<string>,
  preferred: string | null,
  leftoverId: string
): string {
  if (preferred && !claimed.has(preferred) && !isLeftoverMindMapBranchId(preferred)) {
    claimed.add(preferred)
    return preferred
  }
  if (isLeftoverMindMapBranchId(leftoverId)) {
    const stable = stableMindMapIdentityId(leftoverId)
    if (!claimed.has(stable)) {
      claimed.add(stable)
      return stable
    }
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
    const identity = nextIdentityId(claimed, readMindMapNodeUid(node), node.id)
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

function claimAlias(aliases: Record<string, string>, key: string, nodeId: string): void {
  const cleaned = key.trim()
  if (!cleaned || aliases[cleaned] != null) return
  aliases[cleaned] = nodeId
}

export function readMindMapAliasIds(data: Record<string, unknown> | null | undefined): string[] {
  const raw = data?.[MINDMAP_ALIAS_IDS_DATA_KEY]
  if (!Array.isArray(raw)) return []
  const out: string[] = []
  const seen = new Set<string>()
  for (const item of raw) {
    if (typeof item !== 'string') continue
    const cleaned = item.trim()
    if (!cleaned || seen.has(cleaned)) continue
    seen.add(cleaned)
    out.push(cleaned)
  }
  return out
}

/** Keep peer ids on the live branch so a later position-only patch still matches. */
export function rememberMindMapPeerIds(
  data: Record<string, unknown>,
  peerIds: readonly string[],
  liveId: string
): Record<string, unknown> {
  const current = readMindMapAliasIds(data)
  const seen = new Set(current)
  seen.add(liveId)
  const next = [...current]
  for (const peer of peerIds) {
    const cleaned = peer.trim()
    if (!cleaned || seen.has(cleaned) || cleaned === liveId) continue
    seen.add(cleaned)
    next.push(cleaned)
  }
  if (next.length === 0) return data
  return { ...data, [MINDMAP_ALIAS_IDS_DATA_KEY]: next }
}

/** A position-only echo has no branch identity and must not create a node. */
export function mindMapPatchCarriesBranchIdentity(node: Record<string, unknown>): boolean {
  if (typeof node.text === 'string' && node.text.trim()) return true
  if (typeof node.textSecondary === 'string' && node.textSecondary.trim()) return true
  if (typeof node.type === 'string' && node.type.trim()) return true
  return node.data != null && typeof node.data === 'object'
}

/** Union the survivor's peer ids with the raw id from a retargeted collab patch. */
export function stampCollabMindMapPeers(
  previousData: Record<string, unknown> | null | undefined,
  incomingData: Record<string, unknown> | null | undefined,
  rawId: string,
  patchData: Record<string, unknown> | null | undefined,
  liveId: string
): Record<string, unknown> {
  const patchUid = patchData?.[MINDMAP_NODE_UID_DATA_KEY]
  return rememberMindMapPeerIds(
    {
      ...(previousData ?? {}),
      ...(incomingData ?? {}),
      [MINDMAP_NODE_UID_DATA_KEY]: liveId,
    },
    [rawId, typeof patchUid === 'string' ? patchUid : '', ...readMindMapAliasIds(previousData)],
    liveId
  )
}

export function mindMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  const aliases: Record<string, string> = {}
  for (const node of nodes) {
    if (!node.id) continue
    claimAlias(aliases, node.id, node.id)
    const uid = readMindMapNodeUid(node)
    if (uid) claimAlias(aliases, uid, node.id)
    const legacy = node.data?.[MINDMAP_LEGACY_ID_DATA_KEY]
    if (typeof legacy === 'string') claimAlias(aliases, legacy, node.id)
    for (const alias of readMindMapAliasIds(node.data)) {
      claimAlias(aliases, alias, node.id)
    }
  }
  return aliases
}

function uniqueLabelId(hint: string, nodes: readonly DiagramNode[]): string | null {
  const matches = nodes.filter((node) => nodeResolveLabel(node) === hint)
  if (matches.length !== 1) return null
  return matches[0]?.id ?? null
}

function identityTokens(node: DiagramNode): string[] {
  if (!node.id || node.id === 'topic') return []
  const raw: string[] = []
  if (isLeftoverMindMapBranchId(node.id)) {
    raw.push(`L:${node.id}`)
  } else {
    raw.push(`U:${node.id}`)
  }
  const legacy = node.data?.[MINDMAP_LEGACY_ID_DATA_KEY]
  const uid = readMindMapNodeUid(node)
  if (typeof legacy === 'string' && legacy.trim()) raw.push(`L:${legacy.trim()}`)
  if (uid) raw.push(`U:${uid}`)
  for (const alias of readMindMapAliasIds(node.data)) {
    raw.push(isLeftoverMindMapBranchId(alias) ? `L:${alias}` : `U:${alias}`)
  }
  const tokens: string[] = []
  const present = new Set<string>()
  for (const token of raw) {
    if (present.has(token)) continue
    present.add(token)
    tokens.push(token)
  }
  return tokens
}

function duplicateIndexGroups(nodes: readonly DiagramNode[]): Map<number, number[]> {
  const parent = nodes.map((_, index) => index)
  const find = (index: number): number => {
    let cursor = index
    while (parent[cursor] !== cursor) {
      parent[cursor] = parent[parent[cursor] ?? cursor] ?? cursor
      cursor = parent[cursor] ?? cursor
    }
    return cursor
  }
  const union = (left: number, right: number): void => {
    const rootLeft = find(left)
    const rootRight = find(right)
    if (rootLeft === rootRight) return
    if (rootLeft < rootRight) parent[rootRight] = rootLeft
    else parent[rootLeft] = rootRight
  }
  const seen = new Map<string, number>()
  nodes.forEach((node, index) => {
    for (const token of identityTokens(node)) {
      const previous = seen.get(token)
      if (previous == null) seen.set(token, index)
      else union(previous, index)
    }
  })
  const groups = new Map<number, number[]>()
  nodes.forEach((_, index) => {
    const root = find(index)
    const bucket = groups.get(root)
    if (bucket) bucket.push(index)
    else groups.set(root, [index])
  })
  return groups
}

function rewriteStylesKeepSurvivor(
  styles: Record<string, NodeStyle> | undefined,
  idMap: MindMapIdentityIdMap
): Record<string, NodeStyle> | undefined {
  if (!styles) return undefined
  const next: Record<string, NodeStyle> = {}
  for (const [key, value] of Object.entries(styles)) {
    if (!idMap[key]) next[key] = value
  }
  for (const [key, value] of Object.entries(styles)) {
    const mapped = idMap[key]
    if (mapped && !next[mapped]) next[mapped] = value
  }
  return next
}

/**
 * One node per leftover id / uid. A second collab identity of the same branch
 * is dropped and its edges are pointed at the survivor.
 */
function dedupeMindMapConnections(connections: Connection[]): Connection[] {
  const seenEdges = new Set<string>()
  const next: Connection[] = []
  let dropped = false
  for (const connection of connections) {
    const edgeKey = `${connection.source}\0${connection.target}\0${connection.edgeType ?? ''}`
    if (seenEdges.has(edgeKey)) {
      dropped = true
      continue
    }
    seenEdges.add(edgeKey)
    next.push(connection)
  }
  return dropped ? next : connections
}

export function collapseDuplicateMindMapNodes(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): MindMapIdentityMigrateResult {
  const uniqueConnections = dedupeMindMapConnections(connections)
  const groups = duplicateIndexGroups(nodes)
  const idMap: MindMapIdentityIdMap = {}
  const drop = new Set<number>()
  const peersBySurvivor = new Map<number, string[]>()
  for (const indexes of groups.values()) {
    if (indexes.length < 2) continue
    const survivorIndex = indexes[0] ?? 0
    const survivorId = nodes[survivorIndex]?.id
    if (!survivorId) continue
    for (const index of indexes.slice(1)) {
      const dropped = nodes[index]
      const droppedId = dropped?.id
      if (!dropped || !droppedId || droppedId === survivorId) continue
      idMap[droppedId] = survivorId
      drop.add(index)
      const peers = peersBySurvivor.get(survivorIndex) ?? []
      peers.push(droppedId)
      const uid = readMindMapNodeUid(dropped)
      if (uid) peers.push(uid)
      peers.push(...readMindMapAliasIds(dropped.data))
      peersBySurvivor.set(survivorIndex, peers)
    }
  }
  if (drop.size === 0) {
    return { nodes, connections: uniqueConnections, idMap, nodeStyles }
  }
  const nextNodes = nodes.flatMap((node, index) => {
    if (drop.has(index)) return []
    const peers = peersBySurvivor.get(index)
    if (!peers?.length) return [node]
    return [
      {
        ...node,
        data: rememberMindMapPeerIds({ ...(node.data ?? {}) }, peers, node.id),
      },
    ]
  })
  const seenEdges = new Set<string>()
  const nextConnections: Connection[] = []
  for (const connection of uniqueConnections) {
    const source = idMap[connection.source] ?? connection.source
    const target = idMap[connection.target] ?? connection.target
    const edgeKey = `${source}\0${target}\0${connection.edgeType ?? ''}`
    if (seenEdges.has(edgeKey)) continue
    seenEdges.add(edgeKey)
    nextConnections.push({
      ...connection,
      source,
      target,
      id: rewriteEdgeId(connection.id, idMap),
    })
  }
  return {
    nodes: nextNodes,
    connections: nextConnections,
    idMap,
    nodeStyles: rewriteStylesKeepSurvivor(nodeStyles, idMap),
  }
}

/**
 * Live canvas id for a collab patch. A second UUID that still carries the
 * same leftover id or uid updates the existing branch instead of appending.
 */
export function resolveMindMapPatchTargetId(
  hint: string | null | undefined,
  data: Record<string, unknown> | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  const cleaned = hint?.trim() ?? ''
  const aliases = mindMapIdentityAliases(nodes)
  const mapped = cleaned ? aliases[cleaned] : undefined
  if (mapped && mapped !== cleaned && !isLeftoverMindMapBranchId(mapped)) return mapped
  const tokens: unknown[] = [data?.[MINDMAP_LEGACY_ID_DATA_KEY], data?.[MINDMAP_NODE_UID_DATA_KEY]]
  const listed = data?.[MINDMAP_ALIAS_IDS_DATA_KEY]
  if (Array.isArray(listed)) tokens.push(...listed)
  for (const token of tokens) {
    if (typeof token !== 'string' || !token.trim()) continue
    const live = aliases[token.trim()]
    if (live && live !== cleaned && !isLeftoverMindMapBranchId(live)) return live
  }
  if (mapped && !isLeftoverMindMapBranchId(mapped)) return mapped
  return null
}

/** Resolve id / uid / leftover invented id to the live canvas id (no label match). */
export function resolveMindMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = mindMapIdentityAliases(nodes)[cleaned]
  if (!mapped || isLeftoverMindMapBranchId(mapped)) return null
  return mapped
}

/** Resolve id / uid / leftover invented id / unique label to the live canvas id. */
export function resolveMindMapIdentityId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = resolveMindMapAliasId(cleaned, nodes) ?? uniqueLabelId(cleaned, nodes)
  if (mapped && isLeftoverMindMapBranchId(mapped)) return null
  return mapped
}
