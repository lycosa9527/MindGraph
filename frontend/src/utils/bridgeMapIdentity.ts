/**
 * Bridge-map identity: live ``node.id`` is a UUID (dimension label stays fixed).
 * ``pairIndex`` + ``position`` are the current pair address only.
 */
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import {
  type ThinkingMapMigrateResult,
  migrateLeftoverSlotIds,
  readStampedNumber,
  readStampedString,
  takeThinkingMapStableId,
  thinkingMapAliasesFromKeys,
} from '@/utils/thinkingMapStableId'

export const BRIDGE_DIMENSION_LABEL_ID = 'dimension-label'
export const BRIDGE_MAP_UID_DATA_KEY = 'bridgeMapUid'
export const BRIDGE_MAP_LEGACY_ID_DATA_KEY = 'bridgeMapLegacyId'
export const BRIDGE_MAP_RESERVED_IDS = [BRIDGE_DIMENSION_LABEL_ID] as const

export type BridgePairSide = 'left' | 'right'

const PAIR_LEFTOVER = /^pair-(\d+)-(left|right)$/

export function isBridgeMapReservedId(nodeId: string | undefined | null): boolean {
  return nodeId === BRIDGE_DIMENSION_LABEL_ID
}

export function isLeftoverBridgeMapId(nodeId: string | undefined | null): boolean {
  return Boolean(nodeId && PAIR_LEFTOVER.test(nodeId))
}

export function parseLeftoverBridgePairRef(
  nodeId: string
): { pairIndex: number; side: BridgePairSide } | null {
  const match = PAIR_LEFTOVER.exec(nodeId)
  if (!match) return null
  return { pairIndex: parseInt(match[1], 10), side: match[2] as BridgePairSide }
}

export function isBridgeMapPairNode(node: {
  id?: string
  data?: Record<string, unknown>
}): boolean {
  if (isBridgeMapReservedId(node.id)) return false
  if (typeof node.data?.pairIndex === 'number') return true
  return isLeftoverBridgeMapId(node.id)
}

export function readBridgePairIndex(node: { id?: string; data?: Record<string, unknown> }): number {
  const stamped = readStampedNumber(node.data, 'pairIndex')
  if (stamped >= 0) return stamped
  return parseLeftoverBridgePairRef(node.id ?? '')?.pairIndex ?? -1
}

export function readBridgePairSide(node: {
  id?: string
  data?: Record<string, unknown>
}): BridgePairSide | null {
  const stamped = node.data?.position
  if (stamped === 'left' || stamped === 'right') return stamped
  return parseLeftoverBridgePairRef(node.id ?? '')?.side ?? null
}

export function takeBridgeMapStableId(claimed: Set<string>, preferred?: string | null): string {
  return takeThinkingMapStableId(claimed, isLeftoverBridgeMapId, preferred)
}

export function stampBridgePairData(
  pairIndex: number,
  side: BridgePairSide,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    pairIndex,
    position: side,
    diagramType: 'bridge_map',
  }
}

export function findBridgePairSide<T extends { id?: string; data?: Record<string, unknown> }>(
  nodes: readonly T[],
  pairIndex: number,
  side: BridgePairSide
): T | undefined {
  return nodes.find(
    (node) =>
      isBridgeMapPairNode(node) &&
      readBridgePairIndex(node) === pairIndex &&
      readBridgePairSide(node) === side
  )
}

export function bridgeMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  return thinkingMapAliasesFromKeys(nodes, BRIDGE_MAP_UID_DATA_KEY, BRIDGE_MAP_LEGACY_ID_DATA_KEY)
}

export function resolveBridgeMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = bridgeMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverBridgeMapId(mapped)) return mapped
  const leftover = parseLeftoverBridgePairRef(cleaned)
  if (!leftover) return null
  return findBridgePairSide(nodes, leftover.pairIndex, leftover.side)?.id ?? null
}

function leftoverBridgeRef(node: DiagramNode): {
  pairIndex: number
  side: BridgePairSide
} | null {
  const fromId = parseLeftoverBridgePairRef(node.id ?? '')
  if (fromId) return fromId
  const legacy = readStampedString(node.data, BRIDGE_MAP_LEGACY_ID_DATA_KEY)
  return legacy ? parseLeftoverBridgePairRef(legacy) : null
}

function stampBridgeNode(node: DiagramNode): DiagramNode {
  if (isBridgeMapReservedId(node.id) || !isBridgeMapPairNode(node)) return node
  const leftover = leftoverBridgeRef(node)
  const stampedIndex = readBridgePairIndex(node)
  const pairIndex = stampedIndex >= 0 ? stampedIndex : (leftover?.pairIndex ?? -1)
  const side = readBridgePairSide(node) ?? leftover?.side
  if (!side) return node
  const uid = readStampedString(node.data, BRIDGE_MAP_UID_DATA_KEY) ?? node.id
  return {
    ...node,
    data: {
      ...stampBridgePairData(
        pairIndex >= 0 ? pairIndex : (leftover?.pairIndex ?? 0),
        side,
        node.data
      ),
      [BRIDGE_MAP_UID_DATA_KEY]: uid,
    },
  }
}

export function migrateBridgeMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult {
  return migrateLeftoverSlotIds(
    nodes,
    connections,
    nodeStyles,
    BRIDGE_MAP_RESERVED_IDS,
    isLeftoverBridgeMapId,
    BRIDGE_MAP_UID_DATA_KEY,
    BRIDGE_MAP_LEGACY_ID_DATA_KEY,
    stampBridgeNode
  )
}
