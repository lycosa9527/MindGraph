/**
 * Brace-map identity: live ``node.id`` is a UUID (whole / label stay fixed).
 * Parentage lives on connections; leftover slot ids are aliases only.
 */
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import {
  type ThinkingMapMigrateResult,
  migrateLeftoverSlotIds,
  readStampedNumber,
  readStampedString,
  rewriteIdentityConnections,
  rewriteIdentityStyleKeys,
  takeThinkingMapStableId,
  thinkingMapAliasesFromKeys,
} from '@/utils/thinkingMapStableId'

export const BRACE_WHOLE_NODE_ID = 'brace-whole'
export const BRACE_LEFTOVER_WHOLE_ID = 'brace-0-0'
export const BRACE_DIMENSION_LABEL_ID = 'dimension-label'
export const BRACE_MAP_UID_DATA_KEY = 'braceMapUid'
export const BRACE_MAP_LEGACY_ID_DATA_KEY = 'braceMapLegacyId'
export const BRACE_MAP_RESERVED_IDS = [BRACE_WHOLE_NODE_ID, BRACE_DIMENSION_LABEL_ID] as const

const PART_LEFTOVER = /^brace-part-(\d+)$/
const SUBPART_LEFTOVER = /^brace-subpart-(\d+)-(\d+)$/
const DEPTH_LEFTOVER = /^brace-(\d+)-(\d+)$/
const TIMESTAMP_PART = /^brace-part-(\d+)(?:-(\d+))?$/

export function isBraceMapReservedId(nodeId: string | undefined | null): boolean {
  return nodeId === BRACE_WHOLE_NODE_ID || nodeId === BRACE_DIMENSION_LABEL_ID
}

export function isBraceMapWholeNode(node: { id?: string; type?: string }): boolean {
  return node.id === BRACE_WHOLE_NODE_ID || node.type === 'topic' || node.type === 'whole'
}

export function findBraceMapWholeId(
  nodes: ReadonlyArray<{ id?: string; type?: string }>,
  connections?: ReadonlyArray<{ target: string }> | null
): string | undefined {
  const reserved = nodes.find((node) => node.id === BRACE_WHOLE_NODE_ID)?.id
  if (reserved) return reserved
  const byType = nodes.find((node) => node.type === 'topic' || node.type === 'whole')?.id
  if (byType) return byType
  if (!connections?.length) return undefined
  const targets = new Set(connections.map((connection) => connection.target))
  return nodes.find((node) => node.id && !targets.has(node.id))?.id
}

export function isLeftoverBraceMapId(nodeId: string | undefined | null): boolean {
  if (!nodeId) return false
  return (
    PART_LEFTOVER.test(nodeId) ||
    SUBPART_LEFTOVER.test(nodeId) ||
    DEPTH_LEFTOVER.test(nodeId) ||
    TIMESTAMP_PART.test(nodeId)
  )
}

export function isBraceMapPartNode(node: { id?: string; type?: string }): boolean {
  if (isBraceMapReservedId(node.id)) return false
  if (node.type === 'brace') return true
  return isLeftoverBraceMapId(node.id)
}

export function readBraceGroupIndex(node: { id?: string; data?: Record<string, unknown> }): number {
  const group = readStampedNumber(node.data, 'groupIndex')
  if (group >= 0) return group
  const part = PART_LEFTOVER.exec(node.id ?? '')
  if (part) return parseInt(part[1], 10)
  const sub = SUBPART_LEFTOVER.exec(node.id ?? '')
  if (sub) return parseInt(sub[1], 10)
  return -1
}

export function takeBraceMapStableId(claimed: Set<string>, preferred?: string | null): string {
  return takeThinkingMapStableId(claimed, isLeftoverBraceMapId, preferred)
}

export function braceMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  return thinkingMapAliasesFromKeys(nodes, BRACE_MAP_UID_DATA_KEY, BRACE_MAP_LEGACY_ID_DATA_KEY)
}

export function resolveBraceMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = braceMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverBraceMapId(mapped)) return mapped
  const leftover = nodes.find(
    (node) => readStampedString(node.data, BRACE_MAP_LEGACY_ID_DATA_KEY) === cleaned
  )
  return leftover?.id ?? null
}

function stampBraceNode(node: DiagramNode): DiagramNode {
  if (isBraceMapReservedId(node.id) || !isBraceMapPartNode(node)) return node
  const uid = readStampedString(node.data, BRACE_MAP_UID_DATA_KEY) ?? node.id
  const groupIndex = readBraceGroupIndex(node)
  return {
    ...node,
    data: {
      ...node.data,
      ...(groupIndex >= 0 ? { groupIndex } : {}),
      [BRACE_MAP_UID_DATA_KEY]: uid,
    },
  }
}

export function migrateBraceMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult {
  const leftoverWholeMap: Record<string, string> = {}
  const withReservedWhole = nodes.map((node) => {
    if (node.id !== BRACE_LEFTOVER_WHOLE_ID) return node
    leftoverWholeMap[BRACE_LEFTOVER_WHOLE_ID] = BRACE_WHOLE_NODE_ID
    return {
      ...node,
      id: BRACE_WHOLE_NODE_ID,
      data: {
        ...node.data,
        [BRACE_MAP_UID_DATA_KEY]: BRACE_WHOLE_NODE_ID,
        [BRACE_MAP_LEGACY_ID_DATA_KEY]: BRACE_LEFTOVER_WHOLE_ID,
      },
    }
  })
  const rewrittenConnections =
    Object.keys(leftoverWholeMap).length > 0
      ? rewriteIdentityConnections(connections, leftoverWholeMap)
      : connections
  const rewrittenStyles =
    Object.keys(leftoverWholeMap).length > 0
      ? rewriteIdentityStyleKeys(nodeStyles, leftoverWholeMap)
      : nodeStyles
  return migrateLeftoverSlotIds(
    withReservedWhole,
    rewrittenConnections,
    rewrittenStyles,
    BRACE_MAP_RESERVED_IDS,
    isLeftoverBraceMapId,
    BRACE_MAP_UID_DATA_KEY,
    BRACE_MAP_LEGACY_ID_DATA_KEY,
    stampBraceNode
  )
}
