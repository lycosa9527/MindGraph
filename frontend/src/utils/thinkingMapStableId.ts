/**
 * Shared mint / rewrite helpers for Thinking Map dual ids.
 * Per-map leftover regex and location stamps live in ``*Identity.ts``.
 */
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

export type ThinkingMapIdMap = Record<string, string>

export type ThinkingMapMigrateResult = {
  nodes: DiagramNode[]
  connections: Connection[]
  idMap: ThinkingMapIdMap
  nodeStyles?: Record<string, NodeStyle>
}

export function takeThinkingMapStableId(
  claimed: Set<string>,
  isLeftover: (id: string | undefined | null) => boolean,
  preferred?: string | null
): string {
  if (preferred && !isLeftover(preferred) && !claimed.has(preferred)) {
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

export function readStampedNumber(data: Record<string, unknown> | undefined, key: string): number {
  const stamped = data?.[key]
  return typeof stamped === 'number' && stamped >= 0 ? stamped : -1
}

export function readStampedString(
  data: Record<string, unknown> | undefined,
  key: string
): string | null {
  const value = data?.[key]
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

export function rewriteIdentityStyleKeys(
  styles: Record<string, NodeStyle> | undefined,
  idMap: ThinkingMapIdMap
): Record<string, NodeStyle> | undefined {
  if (!styles) return undefined
  const next: Record<string, NodeStyle> = {}
  for (const [key, value] of Object.entries(styles)) {
    next[idMap[key] ?? key] = value
  }
  return next
}

export function rewriteIdentityEdgeId(edgeId: string, idMap: ThinkingMapIdMap): string {
  let next = edgeId
  for (const [oldId, newId] of Object.entries(idMap)) {
    if (next.includes(oldId)) {
      next = next.split(oldId).join(newId)
    }
  }
  return next
}

export function rewriteIdentityConnections(
  connections: Connection[],
  idMap: ThinkingMapIdMap
): Connection[] {
  return connections.map((connection) => ({
    ...connection,
    source: idMap[connection.source] ?? connection.source,
    target: idMap[connection.target] ?? connection.target,
    id: rewriteIdentityEdgeId(connection.id, idMap),
  }))
}

export function thinkingMapAliasesFromKeys(
  nodes: readonly DiagramNode[],
  uidKey: string,
  legacyKey: string
): Record<string, string> {
  const aliases: Record<string, string> = {}
  for (const node of nodes) {
    if (!node.id) continue
    aliases[node.id] = node.id
    const uid = readStampedString(node.data, uidKey)
    if (uid) aliases[uid] = node.id
    const legacy = readStampedString(node.data, legacyKey)
    if (legacy) aliases[legacy] = node.id
  }
  return aliases
}

export function migrateLeftoverSlotIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles: Record<string, NodeStyle> | undefined,
  reservedIds: readonly string[],
  isLeftover: (id: string | undefined | null) => boolean,
  uidKey: string,
  legacyKey: string,
  stampNode: (node: DiagramNode) => DiagramNode
): ThinkingMapMigrateResult {
  const idMap: ThinkingMapIdMap = {}
  const claimed = new Set<string>(reservedIds)
  for (const node of nodes) {
    if (isLeftover(node.id)) continue
    if (node.id) claimed.add(node.id)
    const uid = readStampedString(node.data, uidKey)
    if (uid) claimed.add(uid)
  }

  let changed = false
  const remapped = nodes.map((node) => {
    if (!node.id || reservedIds.includes(node.id) || !isLeftover(node.id)) {
      return node
    }
    const identity = takeThinkingMapStableId(
      claimed,
      isLeftover,
      readStampedString(node.data, uidKey)
    )
    idMap[node.id] = identity
    changed = true
    return {
      ...node,
      id: identity,
      data: {
        ...node.data,
        [uidKey]: identity,
        [legacyKey]: node.id,
      },
    }
  })

  const nextConnections = changed ? rewriteIdentityConnections(connections, idMap) : connections
  const stamped = remapped.map(stampNode)
  return {
    nodes: stamped,
    connections: nextConnections,
    idMap,
    nodeStyles: changed ? rewriteIdentityStyleKeys(nodeStyles, idMap) : nodeStyles,
  }
}
