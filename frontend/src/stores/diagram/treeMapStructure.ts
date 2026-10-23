/**
 * Tree-map add/delete on the live node list.
 * Ids stay put. Category and leaf indexes are rewritten dense, and the
 * vertical connector chain is rebuilt to match the spec loader.
 */
import type { Connection, DiagramNode } from '@/types'
import { thinkingMapStampedBranchColor } from '@/utils/thinkingMapChrome'
import {
  TREE_MAP_UID_DATA_KEY,
  TREE_TOPIC_NODE_ID,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeCategoryIndex,
  readTreeLeafIndex,
  stampTreeCategoryData,
  stampTreeLeafData,
  takeTreeMapStableId,
  treeMapColumnsOf,
} from '@/utils/treeMapIdentity'

export interface TreeMapGraphEdit {
  nodes: DiagramNode[]
  connections: Connection[]
  deletedIds: string[]
}

function claimedIds(nodes: readonly DiagramNode[]): Set<string> {
  const claimed = new Set<string>([TREE_TOPIC_NODE_ID, 'dimension-label'])
  for (const node of nodes) {
    if (node.id) claimed.add(node.id)
  }
  return claimed
}

function connector(
  source: string,
  target: string,
  edgeType: 'step' | 'tree',
  categoryIndex: number
): Connection {
  return {
    id: `edge-${source}-${target}`,
    source,
    target,
    edgeType,
    sourcePosition: 'bottom',
    targetPosition: 'top',
    style: { strokeColor: thinkingMapStampedBranchColor(categoryIndex).border },
  }
}

/** Dense indexes and a fresh topic → category → leaf chain. Node ids are unchanged. */
export function materializeTreeMapGraph(nodes: readonly DiagramNode[]): TreeMapGraphEdit {
  const topic = nodes.find((node) => node.id === TREE_TOPIC_NODE_ID)
  const extras = nodes.filter(
    (node) =>
      node.id !== TREE_TOPIC_NODE_ID && !isTreeMapCategoryNode(node) && !isTreeMapLeafNode(node)
  )
  const nextNodes: DiagramNode[] = []
  const connections: Connection[] = []
  if (topic) nextNodes.push(topic)

  treeMapColumnsOf(nodes).forEach((column, catIndex) => {
    const category = column.category
    if (!category.id) return
    nextNodes.push({
      ...category,
      data: stampTreeCategoryData(catIndex, {
        ...category.data,
        [TREE_MAP_UID_DATA_KEY]: category.id,
      }),
    })
    connections.push(connector(TREE_TOPIC_NODE_ID, category.id, 'step', catIndex))
    let previousId = category.id
    column.leaves.forEach((leaf, leafIndex) => {
      if (!leaf.id) return
      nextNodes.push({
        ...leaf,
        data: stampTreeLeafData(catIndex, leafIndex, category.id, {
          ...leaf.data,
          [TREE_MAP_UID_DATA_KEY]: leaf.id,
        }),
      })
      connections.push(connector(previousId, leaf.id, 'tree', catIndex))
      previousId = leaf.id
    })
  })

  nextNodes.push(...extras)
  return { nodes: nextNodes, connections, deletedIds: [] }
}

export function appendTreeMapCategory(
  nodes: readonly DiagramNode[],
  text: string
): TreeMapGraphEdit | null {
  if (!nodes.some((node) => node.id === TREE_TOPIC_NODE_ID)) return null
  const claimed = claimedIds(nodes)
  const id = takeTreeMapStableId(claimed)
  const sortLast =
    nodes.reduce((max, node) => {
      if (!isTreeMapCategoryNode(node)) return max
      return Math.max(max, readTreeCategoryIndex(node))
    }, -1) + 1
  const draft: DiagramNode[] = [
    ...nodes,
    {
      id,
      text,
      type: 'branch',
      position: { x: 0, y: 0 },
      data: stampTreeCategoryData(sortLast, { [TREE_MAP_UID_DATA_KEY]: id }),
    },
  ]
  return materializeTreeMapGraph(draft)
}

export function appendTreeMapChild(
  nodes: readonly DiagramNode[],
  categoryId: string,
  text: string
): TreeMapGraphEdit | null {
  const category = nodes.find((node) => node.id === categoryId && isTreeMapCategoryNode(node))
  if (!category?.id) return null
  const claimed = claimedIds(nodes)
  const id = takeTreeMapStableId(claimed)
  const catIndex = readTreeCategoryIndex(category)
  const leaves =
    treeMapColumnsOf(nodes).find((column) => column.category.id === category.id)?.leaves ?? []
  const leafIndex = leaves.reduce((max, leaf) => Math.max(max, readTreeLeafIndex(leaf)), -1) + 1
  const draft: DiagramNode[] = [
    ...nodes,
    {
      id,
      text,
      type: 'branch',
      position: { x: 0, y: 0 },
      data: stampTreeLeafData(catIndex, leafIndex, category.id, {
        [TREE_MAP_UID_DATA_KEY]: id,
      }),
    },
  ]
  return materializeTreeMapGraph(draft)
}

export function removeTreeMapGraphNodes(
  nodes: readonly DiagramNode[],
  nodeIds: readonly string[]
): TreeMapGraphEdit | null {
  if (nodeIds.length === 0) return null
  const requested = new Set(nodeIds)
  if (requested.has(TREE_TOPIC_NODE_ID) || requested.has('dimension-label')) return null

  const removed = new Set<string>()
  for (const column of treeMapColumnsOf(nodes)) {
    const catId = column.category.id
    if (!catId) continue
    if (requested.has(catId)) {
      removed.add(catId)
      for (const leaf of column.leaves) {
        if (leaf.id) removed.add(leaf.id)
      }
      continue
    }
    for (const leaf of column.leaves) {
      if (leaf.id && requested.has(leaf.id)) removed.add(leaf.id)
    }
  }
  if (removed.size === 0) return null

  const kept = nodes.filter((node) => !node.id || !removed.has(node.id))
  const materialized = materializeTreeMapGraph(kept)
  return { ...materialized, deletedIds: [...removed] }
}

/** Place live nodes in spec order and restamp indexes so a move survives regrouping. */
export function arrangeTreeMapNodes(
  nodes: readonly DiagramNode[],
  categories: readonly { id?: string; children?: readonly { id?: string }[] }[]
): DiagramNode[] {
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const placed = new Set<string>()
  const ordered: DiagramNode[] = []
  const topic = byId.get(TREE_TOPIC_NODE_ID)
  if (topic?.id) {
    ordered.push(topic)
    placed.add(topic.id)
  }
  categories.forEach((category, catIndex) => {
    const catNode = category.id ? byId.get(category.id) : undefined
    if (!catNode?.id) return
    placed.add(catNode.id)
    ordered.push({
      ...catNode,
      data: stampTreeCategoryData(catIndex, {
        ...catNode.data,
        [TREE_MAP_UID_DATA_KEY]: catNode.id,
      }),
    })
    ;(category.children ?? []).forEach((leaf, leafIndex) => {
      const leafNode = leaf.id ? byId.get(leaf.id) : undefined
      if (!leafNode?.id) return
      placed.add(leafNode.id)
      ordered.push({
        ...leafNode,
        data: stampTreeLeafData(catIndex, leafIndex, catNode.id, {
          ...leafNode.data,
          [TREE_MAP_UID_DATA_KEY]: leafNode.id,
        }),
      })
    })
  })
  for (const node of nodes) {
    if (node.id && !placed.has(node.id)) ordered.push(node)
  }
  return ordered
}
