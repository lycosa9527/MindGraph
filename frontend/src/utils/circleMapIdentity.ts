/**
 * Circle-map identity: live ``node.id`` is a UUID (topic / boundary stay fixed).
 * ``groupIndex`` is the current ring address only.
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

export const CIRCLE_TOPIC_NODE_ID = 'topic'
export const CIRCLE_BOUNDARY_NODE_ID = 'outer-boundary'
export const CIRCLE_MAP_UID_DATA_KEY = 'circleMapUid'
export const CIRCLE_MAP_LEGACY_ID_DATA_KEY = 'circleMapLegacyId'
export const CIRCLE_MAP_RESERVED_IDS = [CIRCLE_TOPIC_NODE_ID, CIRCLE_BOUNDARY_NODE_ID] as const

const CONTEXT_LEFTOVER = /^context-(\d+)$/

export function isCircleMapReservedId(nodeId: string | undefined | null): boolean {
  return nodeId === CIRCLE_TOPIC_NODE_ID || nodeId === CIRCLE_BOUNDARY_NODE_ID
}

export function isLeftoverCircleMapId(nodeId: string | undefined | null): boolean {
  return Boolean(nodeId && CONTEXT_LEFTOVER.test(nodeId))
}

export function parseLeftoverCircleContextIndex(nodeId: string): number {
  const match = CONTEXT_LEFTOVER.exec(nodeId)
  return match ? parseInt(match[1], 10) : -1
}

export function isCircleMapContextNode(node: { id?: string; type?: string }): boolean {
  if (isCircleMapReservedId(node.id)) return false
  if (node.type === 'bubble') return true
  return isLeftoverCircleMapId(node.id)
}

export function readCircleContextIndex(node: {
  id?: string
  data?: Record<string, unknown>
}): number {
  const group = readStampedNumber(node.data, 'groupIndex')
  if (group >= 0) return group
  return parseLeftoverCircleContextIndex(node.id ?? '')
}

export function takeCircleMapStableId(claimed: Set<string>, preferred?: string | null): string {
  return takeThinkingMapStableId(claimed, isLeftoverCircleMapId, preferred)
}

export function stampCircleContextData(
  groupIndex: number,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    groupIndex,
    [CIRCLE_MAP_UID_DATA_KEY]: extra?.[CIRCLE_MAP_UID_DATA_KEY],
  }
}

export function circleMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  return thinkingMapAliasesFromKeys(nodes, CIRCLE_MAP_UID_DATA_KEY, CIRCLE_MAP_LEGACY_ID_DATA_KEY)
}

export function resolveCircleMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = circleMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverCircleMapId(mapped)) return mapped
  const leftover = parseLeftoverCircleContextIndex(cleaned)
  if (leftover < 0) return null
  const found = nodes.find(
    (node) => isCircleMapContextNode(node) && readCircleContextIndex(node) === leftover
  )
  return found?.id ?? null
}

function leftoverCircleIndex(node: DiagramNode): number {
  const fromId = parseLeftoverCircleContextIndex(node.id ?? '')
  if (fromId >= 0) return fromId
  const legacy = readStampedString(node.data, CIRCLE_MAP_LEGACY_ID_DATA_KEY)
  return legacy ? parseLeftoverCircleContextIndex(legacy) : -1
}

function stampCircleNode(node: DiagramNode): DiagramNode {
  if (isCircleMapReservedId(node.id) || !isCircleMapContextNode(node)) return node
  const stamped = readCircleContextIndex(node)
  const index = stamped >= 0 ? stamped : leftoverCircleIndex(node)
  const uid = readStampedString(node.data, CIRCLE_MAP_UID_DATA_KEY) ?? node.id
  return {
    ...node,
    data: {
      ...stampCircleContextData(index >= 0 ? index : 0, node.data),
      [CIRCLE_MAP_UID_DATA_KEY]: uid,
    },
  }
}

export function migrateCircleMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult {
  return migrateLeftoverSlotIds(
    nodes,
    connections,
    nodeStyles,
    CIRCLE_MAP_RESERVED_IDS,
    isLeftoverCircleMapId,
    CIRCLE_MAP_UID_DATA_KEY,
    CIRCLE_MAP_LEGACY_ID_DATA_KEY,
    stampCircleNode
  )
}
