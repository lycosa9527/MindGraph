/**
 * Double-bubble identity: live ``node.id`` is a UUID (topics stay fixed).
 * Role + ``groupIndex`` are the current column address only.
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

export const DOUBLE_BUBBLE_LEFT_TOPIC_ID = 'left-topic'
export const DOUBLE_BUBBLE_RIGHT_TOPIC_ID = 'right-topic'
export const DOUBLE_BUBBLE_UID_DATA_KEY = 'doubleBubbleMapUid'
export const DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY = 'doubleBubbleMapLegacyId'
export const DOUBLE_BUBBLE_ROLE_DATA_KEY = 'doubleBubbleRole'
export const DOUBLE_BUBBLE_RESERVED_IDS = [
  DOUBLE_BUBBLE_LEFT_TOPIC_ID,
  DOUBLE_BUBBLE_RIGHT_TOPIC_ID,
] as const

export type DoubleBubbleRole = 'similarity' | 'leftDiff' | 'rightDiff'

const SIM_LEFTOVER = /^similarity-(\d+)$/
const LEFT_DIFF_LEFTOVER = /^left-diff-(\d+)$/
const RIGHT_DIFF_LEFTOVER = /^right-diff-(\d+)$/

export function isDoubleBubbleTopicId(nodeId: string | undefined | null): boolean {
  return nodeId === DOUBLE_BUBBLE_LEFT_TOPIC_ID || nodeId === DOUBLE_BUBBLE_RIGHT_TOPIC_ID
}

export function isLeftoverDoubleBubbleId(nodeId: string | undefined | null): boolean {
  if (!nodeId) return false
  return (
    SIM_LEFTOVER.test(nodeId) || LEFT_DIFF_LEFTOVER.test(nodeId) || RIGHT_DIFF_LEFTOVER.test(nodeId)
  )
}

export function parseLeftoverDoubleBubbleRef(
  nodeId: string
): { role: DoubleBubbleRole; index: number } | null {
  const sim = SIM_LEFTOVER.exec(nodeId)
  if (sim) return { role: 'similarity', index: parseInt(sim[1], 10) }
  const left = LEFT_DIFF_LEFTOVER.exec(nodeId)
  if (left) return { role: 'leftDiff', index: parseInt(left[1], 10) }
  const right = RIGHT_DIFF_LEFTOVER.exec(nodeId)
  if (right) return { role: 'rightDiff', index: parseInt(right[1], 10) }
  return null
}

export function readDoubleBubbleRole(node: {
  id?: string
  data?: Record<string, unknown>
}): DoubleBubbleRole | null {
  const stamped = node.data?.[DOUBLE_BUBBLE_ROLE_DATA_KEY]
  if (stamped === 'similarity' || stamped === 'leftDiff' || stamped === 'rightDiff') {
    return stamped
  }
  return parseLeftoverDoubleBubbleRef(node.id ?? '')?.role ?? null
}

export function readDoubleBubbleIndex(node: {
  id?: string
  data?: Record<string, unknown>
}): number {
  const group = readStampedNumber(node.data, 'groupIndex')
  if (group >= 0) return group
  return parseLeftoverDoubleBubbleRef(node.id ?? '')?.index ?? -1
}

export function isDoubleBubbleRoleNode(
  node: { id?: string; type?: string; data?: Record<string, unknown> },
  role: DoubleBubbleRole
): boolean {
  return readDoubleBubbleRole(node) === role
}

export function takeDoubleBubbleMapStableId(
  claimed: Set<string>,
  preferred?: string | null
): string {
  return takeThinkingMapStableId(claimed, isLeftoverDoubleBubbleId, preferred)
}

export function stampDoubleBubbleData(
  role: DoubleBubbleRole,
  groupIndex: number,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    groupIndex,
    [DOUBLE_BUBBLE_ROLE_DATA_KEY]: role,
  }
}

export function doubleBubbleMapIdentityAliases(
  nodes: readonly DiagramNode[]
): Record<string, string> {
  return thinkingMapAliasesFromKeys(
    nodes,
    DOUBLE_BUBBLE_UID_DATA_KEY,
    DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY
  )
}

export function resolveDoubleBubbleMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = doubleBubbleMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverDoubleBubbleId(mapped)) return mapped
  const leftover = parseLeftoverDoubleBubbleRef(cleaned)
  if (!leftover) return null
  const found = nodes.find(
    (node) =>
      readDoubleBubbleRole(node) === leftover.role && readDoubleBubbleIndex(node) === leftover.index
  )
  return found?.id ?? null
}

function leftoverDoubleBubbleRef(node: DiagramNode): {
  role: DoubleBubbleRole
  index: number
} | null {
  const fromId = parseLeftoverDoubleBubbleRef(node.id ?? '')
  if (fromId) return fromId
  const legacy = readStampedString(node.data, DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY)
  return legacy ? parseLeftoverDoubleBubbleRef(legacy) : null
}

function stampDoubleBubbleNode(node: DiagramNode): DiagramNode {
  if (isDoubleBubbleTopicId(node.id)) return node
  const leftover = leftoverDoubleBubbleRef(node)
  const role = readDoubleBubbleRole(node) ?? leftover?.role
  if (!role) return node
  const stampedIndex = readDoubleBubbleIndex(node)
  const index = stampedIndex >= 0 ? stampedIndex : (leftover?.index ?? -1)
  const uid = readStampedString(node.data, DOUBLE_BUBBLE_UID_DATA_KEY) ?? node.id
  return {
    ...node,
    data: {
      ...stampDoubleBubbleData(role, index >= 0 ? index : 0, node.data),
      [DOUBLE_BUBBLE_UID_DATA_KEY]: uid,
    },
  }
}

export function migrateDoubleBubbleMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult {
  return migrateLeftoverSlotIds(
    nodes,
    connections,
    nodeStyles,
    DOUBLE_BUBBLE_RESERVED_IDS,
    isLeftoverDoubleBubbleId,
    DOUBLE_BUBBLE_UID_DATA_KEY,
    DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY,
    stampDoubleBubbleNode
  )
}
