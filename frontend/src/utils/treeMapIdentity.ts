/**
 * Tree-map identity: live ``node.id`` is a UUID (topic / label stay fixed).
 * Category / leaf index and parent id are the current address only.
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

export const TREE_TOPIC_NODE_ID = 'tree-topic'
export const TREE_DIMENSION_LABEL_ID = 'dimension-label'
export const TREE_MAP_UID_DATA_KEY = 'treeMapUid'
export const TREE_MAP_LEGACY_ID_DATA_KEY = 'treeMapLegacyId'
export const TREE_CATEGORY_INDEX_DATA_KEY = 'categoryIndex'
export const TREE_LEAF_INDEX_DATA_KEY = 'leafIndex'
export const TREE_PARENT_CATEGORY_ID_DATA_KEY = 'parentCategoryId'
export const TREE_MAP_RESERVED_IDS = [TREE_TOPIC_NODE_ID, TREE_DIMENSION_LABEL_ID] as const

const CAT_LEFTOVER = /^tree-cat-(\d+)$/
const LEAF_LEFTOVER = /^tree-leaf-(\d+)-(\d+)$/

export function isTreeMapReservedId(nodeId: string | undefined | null): boolean {
  return nodeId === TREE_TOPIC_NODE_ID || nodeId === TREE_DIMENSION_LABEL_ID
}

export function isLeftoverTreeMapId(nodeId: string | undefined | null): boolean {
  if (!nodeId) return false
  return CAT_LEFTOVER.test(nodeId) || LEAF_LEFTOVER.test(nodeId)
}

export function parseLeftoverTreeCategoryIndex(nodeId: string): number {
  const match = CAT_LEFTOVER.exec(nodeId)
  return match ? parseInt(match[1], 10) : -1
}

export function parseLeftoverTreeLeafRef(
  nodeId: string
): { categoryIndex: number; leafIndex: number } | null {
  const match = LEAF_LEFTOVER.exec(nodeId)
  if (!match) return null
  return { categoryIndex: parseInt(match[1], 10), leafIndex: parseInt(match[2], 10) }
}

export function isTreeMapCategoryNode(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): boolean {
  if (node.data?.nodeType === 'branch') return true
  return parseLeftoverTreeCategoryIndex(node.id ?? '') >= 0
}

export function isTreeMapLeafNode(node: {
  id?: string
  type?: string
  data?: Record<string, unknown>
}): boolean {
  if (node.data?.nodeType === 'leaf') return true
  return parseLeftoverTreeLeafRef(node.id ?? '') != null
}

export function readTreeCategoryIndex(node: {
  id?: string
  data?: Record<string, unknown>
}): number {
  const stamped = readStampedNumber(node.data, TREE_CATEGORY_INDEX_DATA_KEY)
  if (stamped >= 0) return stamped
  const group = readStampedNumber(node.data, 'groupIndex')
  if (group >= 0) return group
  const leftoverCat = parseLeftoverTreeCategoryIndex(node.id ?? '')
  if (leftoverCat >= 0) return leftoverCat
  return parseLeftoverTreeLeafRef(node.id ?? '')?.categoryIndex ?? -1
}

export function readTreeLeafIndex(node: { id?: string; data?: Record<string, unknown> }): number {
  const stamped = readStampedNumber(node.data, TREE_LEAF_INDEX_DATA_KEY)
  if (stamped >= 0) return stamped
  return parseLeftoverTreeLeafRef(node.id ?? '')?.leafIndex ?? -1
}

export function readTreeParentCategoryId(node: { data?: Record<string, unknown> }): string | null {
  return readStampedString(node.data, TREE_PARENT_CATEGORY_ID_DATA_KEY)
}

export function takeTreeMapStableId(claimed: Set<string>, preferred?: string | null): string {
  return takeThinkingMapStableId(claimed, isLeftoverTreeMapId, preferred)
}

export function stampTreeCategoryData(
  categoryIndex: number,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    nodeType: 'branch',
    groupIndex: categoryIndex,
    [TREE_CATEGORY_INDEX_DATA_KEY]: categoryIndex,
  }
}

export function stampTreeLeafData(
  categoryIndex: number,
  leafIndex: number,
  parentCategoryId: string,
  extra?: Record<string, unknown>
): Record<string, unknown> {
  return {
    ...extra,
    nodeType: 'leaf',
    groupIndex: categoryIndex,
    [TREE_CATEGORY_INDEX_DATA_KEY]: categoryIndex,
    [TREE_LEAF_INDEX_DATA_KEY]: leafIndex,
    [TREE_PARENT_CATEGORY_ID_DATA_KEY]: parentCategoryId,
  }
}

export function treeMapIdentityAliases(nodes: readonly DiagramNode[]): Record<string, string> {
  return thinkingMapAliasesFromKeys(nodes, TREE_MAP_UID_DATA_KEY, TREE_MAP_LEGACY_ID_DATA_KEY)
}

export function resolveTreeMapAliasId(
  hint: string | null | undefined,
  nodes: readonly DiagramNode[]
): string | null {
  if (!hint || !hint.trim()) return null
  const cleaned = hint.trim()
  const mapped = treeMapIdentityAliases(nodes)[cleaned]
  if (mapped && !isLeftoverTreeMapId(mapped)) return mapped
  const leftoverCat = parseLeftoverTreeCategoryIndex(cleaned)
  if (leftoverCat >= 0) {
    const cat = nodes.find(
      (node) => isTreeMapCategoryNode(node) && readTreeCategoryIndex(node) === leftoverCat
    )
    return cat?.id ?? null
  }
  const leftoverLeaf = parseLeftoverTreeLeafRef(cleaned)
  if (!leftoverLeaf) return null
  const leaf = nodes.find(
    (node) =>
      isTreeMapLeafNode(node) &&
      readTreeCategoryIndex(node) === leftoverLeaf.categoryIndex &&
      readTreeLeafIndex(node) === leftoverLeaf.leafIndex
  )
  return leaf?.id ?? null
}

function parentFromConnections(nodeId: string, connections: Connection[]): string | null {
  const incoming = connections.find((connection) => connection.target === nodeId)
  return incoming && incoming.source !== TREE_TOPIC_NODE_ID ? incoming.source : null
}

function leftoverTreeHint(node: DiagramNode): string {
  return readStampedString(node.data, TREE_MAP_LEGACY_ID_DATA_KEY) ?? node.id ?? ''
}

function stampTreeNode(node: DiagramNode, connections: Connection[]): DiagramNode {
  if (isTreeMapReservedId(node.id)) return node
  const uid = readStampedString(node.data, TREE_MAP_UID_DATA_KEY) ?? node.id
  const leftoverHint = leftoverTreeHint(node)
  const leftoverCat = parseLeftoverTreeCategoryIndex(leftoverHint)
  const leftoverLeaf = parseLeftoverTreeLeafRef(leftoverHint)
  if (isTreeMapCategoryNode(node) || leftoverCat >= 0) {
    const index = readTreeCategoryIndex(node)
    const catIndex = index >= 0 ? index : leftoverCat
    return {
      ...node,
      data: {
        ...stampTreeCategoryData(catIndex >= 0 ? catIndex : 0, node.data),
        [TREE_MAP_UID_DATA_KEY]: uid,
      },
    }
  }
  if (isTreeMapLeafNode(node) || leftoverLeaf) {
    const categoryIndex = readTreeCategoryIndex(node)
    const leafIndex = readTreeLeafIndex(node)
    const parent =
      readTreeParentCategoryId(node) ?? parentFromConnections(node.id, connections) ?? ''
    return {
      ...node,
      data: {
        ...stampTreeLeafData(
          categoryIndex >= 0 ? categoryIndex : (leftoverLeaf?.categoryIndex ?? 0),
          leafIndex >= 0 ? leafIndex : (leftoverLeaf?.leafIndex ?? 0),
          parent,
          node.data
        ),
        [TREE_MAP_UID_DATA_KEY]: uid,
      },
    }
  }
  return node
}

export function migrateTreeMapIdentityIds(
  nodes: DiagramNode[],
  connections: Connection[],
  nodeStyles?: Record<string, NodeStyle>
): ThinkingMapMigrateResult {
  const migrated = migrateLeftoverSlotIds(
    nodes,
    connections,
    nodeStyles,
    TREE_MAP_RESERVED_IDS,
    isLeftoverTreeMapId,
    TREE_MAP_UID_DATA_KEY,
    TREE_MAP_LEGACY_ID_DATA_KEY,
    (node) => node
  )
  const categoryByLeftover = new Map<number, string>()
  for (const node of migrated.nodes) {
    if (!isTreeMapCategoryNode(node)) continue
    const index = readTreeCategoryIndex(node)
    if (index >= 0) categoryByLeftover.set(index, node.id)
  }
  const stamped = migrated.nodes.map((node) => {
    if (!isTreeMapLeafNode(node)) return stampTreeNode(node, migrated.connections)
    const parent = readTreeParentCategoryId(node)
    const leftoverParent = parent && isLeftoverTreeMapId(parent) ? migrated.idMap[parent] : parent
    const categoryIndex = readTreeCategoryIndex(node)
    const fromIndex = categoryByLeftover.get(categoryIndex) ?? leftoverParent ?? ''
    return stampTreeNode(
      {
        ...node,
        data: {
          ...node.data,
          [TREE_PARENT_CATEGORY_ID_DATA_KEY]: fromIndex || parent || '',
        },
      },
      migrated.connections
    )
  })
  return { ...migrated, nodes: stamped }
}
