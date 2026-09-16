/**
 * Multi-flow identity: live ``node.id`` is a UUID (event stays ``event``).
 * Cause / effect role + ``groupIndex`` are the current column address only.
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

export const MULTI_FLOW_EVENT_NODE_ID = 'event'
export const MULTI_FLOW_UID_DATA_KEY = 'multiFlowMapUid'
export const MULTI_FLOW_LEGACY_ID_DATA_KEY = 'multiFlowMapLegacyId'
export const MULTI_FLOW_ROLE_DATA_KEY = 'multiFlowRole'
export const MULTI_FLOW_RESERVED_IDS = [MULTI_FLOW_EVENT_NODE_ID] as const

export type MultiFlowRole = 'cause' | 'effect'

const CAUSE_LEFTOVER = /^cause-(\d+)$/
const EFFECT_LEFTOVER = /^effect-(\d+)$/

export function isMultiFlowEventId(nodeId: string | undefined | null): boolean {
  return nodeId === MULTI_FLOW_EVENT_NODE_ID
}

export function isLeftoverMultiFlowMapId(nodeId: string | undefined | null): boolean {
  if (!nodeId) return false
  return CAUSE_LEFTOVER.test(nodeId) || EFFECT_LEFTOVER.test(nodeId)
}

export function parseLeftoverMultiFlowRef(
  nodeId: string
): { role: MultiFlowRole; index: number } | null {
  const cause = CAUSE_LEFTOVER.exec(nodeId)
  if (cause) return { role: 'cause', index: parseInt(cause[1], 10) }
  const effect = EFFECT_LEFTOVER.exec(nodeId)
  if (effect) return { role: 'effect', index: parseInt(effect[1], 10) }
  return null
}

export function readMultiFlowRole(node: {
  id?: string
  data?: Record<string, unknown>
}): MultiFlowRole | null {
  const stamped = node.data?.[MULTI_FLOW_ROLE_DATA_KEY]
  if (stamped === 'cause' || stamped === 'effect') return stamped
  return parseLeftoverMultiFlowRef(node.id ?? '')?.role ?? null
}

export function readMultiFlowIndex(node: { id?: string; data?: Record<string, unknown> }): number {
  const group = readStampedNumber(node.data, 'groupIndex')
  if (group >= 0) return group
  return parseLeftoverMultiFlowRef(node.id ?? '')?.index ?? -1
}

export function isMultiFlowCauseNode(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): boolean {
  return readMultiFlowRole(node) === 'cause'
}

export function isMultiFlowEffectNode(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): boolean {
  return readMultiFlowRole(node) === 'effect'
}

export function takeMultiFlowMapStableId(claimed: Set<string>, preferred?: string | null): string {
  return takeThinkingMapStableId(claimed, isLeftoverMultiFlowMapId, preferred)
}

export function stampMultiFlowData(
  role: MultiFlowRole,
  groupIndex: number,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    groupIndex,
    [MULTI_FLOW_ROLE_DATA_KEY]: role,
  }
}

export function multiFlowMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  return thinkingMapAliasesFromKeys(nodes, MULTI_FLOW_UID_DATA_KEY, MULTI_FLOW_LEGACY_ID_DATA_KEY)
}

export function resolveMultiFlowMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = multiFlowMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverMultiFlowMapId(mapped)) return mapped
  const leftover = parseLeftoverMultiFlowRef(cleaned)
  if (!leftover) return null
  const found = nodes.find(
    (node) =>
      readMultiFlowRole(node) === leftover.role && readMultiFlowIndex(node) === leftover.index
  )
  return found?.id ?? null
}

function leftoverMultiFlowRef(node: DiagramNode): { role: MultiFlowRole; index: number } | null {
  const fromId = parseLeftoverMultiFlowRef(node.id ?? '')
  if (fromId) return fromId
  const legacy = readStampedString(node.data, MULTI_FLOW_LEGACY_ID_DATA_KEY)
  return legacy ? parseLeftoverMultiFlowRef(legacy) : null
}

function stampMultiFlowNode(node: DiagramNode): DiagramNode {
  if (isMultiFlowEventId(node.id)) return node
  const leftover = leftoverMultiFlowRef(node)
  const role = readMultiFlowRole(node) ?? leftover?.role
  if (!role) return node
  const stampedIndex = readMultiFlowIndex(node)
  const index = stampedIndex >= 0 ? stampedIndex : (leftover?.index ?? -1)
  const uid = readStampedString(node.data, MULTI_FLOW_UID_DATA_KEY) ?? node.id
  return {
    ...node,
    data: {
      ...stampMultiFlowData(role, index >= 0 ? index : 0, node.data),
      [MULTI_FLOW_UID_DATA_KEY]: uid,
    },
  }
}

export function migrateMultiFlowMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult {
  return migrateLeftoverSlotIds(
    nodes,
    connections,
    nodeStyles,
    MULTI_FLOW_RESERVED_IDS,
    isLeftoverMultiFlowMapId,
    MULTI_FLOW_UID_DATA_KEY,
    MULTI_FLOW_LEGACY_ID_DATA_KEY,
    stampMultiFlowNode
  )
}
