/**
 * Bubble-map identity: live ``node.id`` is a UUID (topic stays ``topic``).
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

export const BUBBLE_TOPIC_NODE_ID = 'topic'
export const BUBBLE_MAP_UID_DATA_KEY = 'bubbleMapUid'
export const BUBBLE_MAP_LEGACY_ID_DATA_KEY = 'bubbleMapLegacyId'
export const BUBBLE_MAP_RESERVED_IDS = [BUBBLE_TOPIC_NODE_ID] as const

const BUBBLE_LEFTOVER = /^bubble-(\d+)$/

export function isBubbleMapTopicId(nodeId: string | undefined | null): boolean {
  return nodeId === BUBBLE_TOPIC_NODE_ID
}

export function isLeftoverBubbleMapId(nodeId: string | undefined | null): boolean {
  return Boolean(nodeId && BUBBLE_LEFTOVER.test(nodeId))
}

export function parseLeftoverBubbleIndex(nodeId: string): number {
  const match = BUBBLE_LEFTOVER.exec(nodeId)
  return match ? parseInt(match[1], 10) : -1
}

export function isBubbleMapAttributeNode(node: { id?: string; type?: string }): boolean {
  if (isBubbleMapTopicId(node.id)) return false
  if (node.type === 'bubble' || node.type === 'child') return true
  return isLeftoverBubbleMapId(node.id)
}

export function readBubbleGroupIndex(node: {
  id?: string
  data?: Record<string, unknown>
}): number {
  const group = readStampedNumber(node.data, 'groupIndex')
  if (group >= 0) return group
  return parseLeftoverBubbleIndex(node.id ?? '')
}

export function takeBubbleMapStableId(claimed: Set<string>, preferred?: string | null): string {
  return takeThinkingMapStableId(claimed, isLeftoverBubbleMapId, preferred)
}

export function stampBubbleAttributeData(
  groupIndex: number,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return { ...extra, groupIndex }
}

export function bubbleMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  return thinkingMapAliasesFromKeys(nodes, BUBBLE_MAP_UID_DATA_KEY, BUBBLE_MAP_LEGACY_ID_DATA_KEY)
}

export function resolveBubbleMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = bubbleMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverBubbleMapId(mapped)) return mapped
  const leftover = parseLeftoverBubbleIndex(cleaned)
  if (leftover < 0) return null
  const found = nodes.find(
    (node) => isBubbleMapAttributeNode(node) && readBubbleGroupIndex(node) === leftover
  )
  return found?.id ?? null
}

function leftoverBubbleIndex(node: DiagramNode): number {
  const fromId = parseLeftoverBubbleIndex(node.id ?? '')
  if (fromId >= 0) return fromId
  const legacy = readStampedString(node.data, BUBBLE_MAP_LEGACY_ID_DATA_KEY)
  return legacy ? parseLeftoverBubbleIndex(legacy) : -1
}

function stampBubbleNode(node: DiagramNode): DiagramNode {
  if (isBubbleMapTopicId(node.id) || !isBubbleMapAttributeNode(node)) return node
  const stamped = readBubbleGroupIndex(node)
  const index = stamped >= 0 ? stamped : leftoverBubbleIndex(node)
  const uid = readStampedString(node.data, BUBBLE_MAP_UID_DATA_KEY) ?? node.id
  return {
    ...node,
    data: {
      ...stampBubbleAttributeData(index >= 0 ? index : 0, node.data),
      [BUBBLE_MAP_UID_DATA_KEY]: uid,
    },
  }
}

export function migrateBubbleMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult {
  return migrateLeftoverSlotIds(
    nodes,
    connections,
    nodeStyles,
    BUBBLE_MAP_RESERVED_IDS,
    isLeftoverBubbleMapId,
    BUBBLE_MAP_UID_DATA_KEY,
    BUBBLE_MAP_LEGACY_ID_DATA_KEY,
    stampBubbleNode
  )
}
