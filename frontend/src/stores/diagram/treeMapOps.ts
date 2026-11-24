import type { InsertLabelInput } from '@/diagramBilingual/insertLabel'
import type { Connection, DiagramNode } from '@/types'
import {
  TREE_TOPIC_NODE_ID,
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  treeMapColumnsOf,
} from '@/utils/treeMapIdentity'

import { recalculateTreeMapLayout } from '../specLoader/treeMap'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { emitCtxEvent } from './events'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import {
  appendTreeMapCategory,
  appendTreeMapChild,
  arrangeTreeMapNodes,
  insertTreeMapCategoryAt,
  insertTreeMapChildAt,
  materializeTreeMapGraph,
  removeTreeMapGraphNodes,
} from './treeMapStructure'
import type { DiagramContext } from './types'

function carriedGloss(node: { textSecondary?: string }): { textSecondary?: string } {
  const line = String(node.textSecondary ?? '').trim()
  return line ? { textSecondary: line } : {}
}

export function useTreeMapOpsSlice(ctx: DiagramContext) {
  const { type, data, selectedNodes } = ctx

  function buildTreeMapSpecFromNodes(): Record<string, unknown> | null {
    if (!data.value || type.value !== 'tree_map') return null
    const nodes = data.value.nodes
    const rootNode = nodes.find((n) => n.id === TREE_TOPIC_NODE_ID)
    if (!rootNode) return null
    const rootId = rootNode.id ?? TREE_TOPIC_NODE_ID
    const categories = treeMapColumnsOf(nodes).map((column) => ({
      id: column.category.id,
      text: column.category.text,
      ...carriedGloss(column.category),
      children: column.leaves.map((leaf) => ({
        id: leaf.id,
        text: leaf.text,
        ...carriedGloss(leaf),
        children: [],
      })),
    }))
    const record = data.value as Record<string, unknown>
    const dimension = record.dimension as string | undefined
    const altDims = record.alternative_dimensions as string[] | undefined
    const dimensionNode = nodes.find((node) => node.id === 'dimension-label')
    const dimensionSecondary = String(dimensionNode?.textSecondary ?? '').trim()
    const languages = record.languages
    return {
      root: {
        id: rootId,
        text: rootNode.text,
        ...carriedGloss(rootNode),
        children: categories,
      },
      dimension,
      ...(dimensionSecondary ? { dimensionSecondary } : {}),
      alternative_dimensions: altDims,
      ...(languages && typeof languages === 'object' ? { languages } : {}),
    }
  }

  function commitTreeMapGraph(
    nodes: DiagramNode[],
    connections: Connection[],
    historyLabel: string,
    event: 'add' | 'delete',
    deletedIds: string[] = []
  ): void {
    if (!data.value) return
    data.value.nodes = recalculateTreeMapLayout(nodes, ctx.nodeDimensions.value)
    data.value.connections = connections
    if (event === 'delete') {
      for (const id of deletedIds) {
        delete ctx.nodeDimensions.value[id]
        ctx.clearCustomPosition(id)
        ctx.clearNodeStyle(id)
        ctx.removeFromSelection(id)
      }
      ctx.pushHistory(historyLabel)
      emitCtxEvent(ctx, 'diagram:nodes_deleted', { nodeIds: deletedIds })
      return
    }
    ctx.pushHistory(historyLabel)
    emitCtxEvent(ctx, 'diagram:node_added', { node: null })
  }

  function removeTreeMapNodes(nodeIds: string[]): number {
    if (isDiagramPresentationReadOnly(ctx)) return 0
    if (type.value !== 'tree_map' || !data.value?.nodes) return 0
    const next = removeTreeMapGraphNodes(data.value.nodes, nodeIds)
    if (!next) return 0
    if (collabForeignLockBlocksAnyId(ctx, new Set(next.deletedIds))) {
      emitCollabDeleteBlocked()
      return 0
    }
    commitTreeMapGraph(next.nodes, next.connections, 'Delete nodes', 'delete', next.deletedIds)
    return next.deletedIds.length
  }

  function getTreeMapDescendantIds(nodeId: string): Set<string> {
    const result = new Set<string>([nodeId])
    const node = data.value?.nodes.find((n) => n.id === nodeId)
    if (node && isTreeMapLeafNode(node)) return result
    if (!data.value?.connections) return result
    const childrenMap = new Map<string, string[]>()
    data.value.connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })
    function collect(id: string): void {
      for (const childId of childrenMap.get(id) ?? []) {
        const child = data.value?.nodes.find((n) => n.id === childId)
        if (
          child &&
          (isTreeMapCategoryNode(child) || isTreeMapLeafNode(child)) &&
          childId !== TREE_TOPIC_NODE_ID
        ) {
          result.add(childId)
          collect(childId)
        }
      }
    }
    collect(nodeId)
    return result
  }

  function moveTreeMapBranch(
    nodeId: string,
    targetType: 'topic' | 'child' | 'before' | 'after' | 'sibling',
    targetId?: string
  ): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (type.value !== 'tree_map') return false
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false

    type TreeLeaf = { id?: string; text: string; textSecondary?: string }
    type TreeCategory = {
      id?: string
      text: string
      textSecondary?: string
      children?: TreeLeaf[]
    }
    const root = spec.root as {
      id?: string
      text: string
      children?: TreeCategory[]
    }
    const categories = root.children ?? []

    const nodeById = new Map((data.value?.nodes ?? []).map((n) => [n.id, n]))
    const isCategory = (id: string) => {
      const node = nodeById.get(id)
      return Boolean(node && isTreeMapCategoryNode(node))
    }
    const isLeaf = (id: string) => {
      const node = nodeById.get(id)
      return Boolean(node && isTreeMapLeafNode(node))
    }

    const findCategoryIndex = (id: string) => categories.findIndex((cat) => cat.id === id)

    let sourceCatIdx: number
    let sourceLeafIdx = -1
    let sourceItem: TreeCategory | TreeLeaf | null

    if (isCategory(nodeId)) {
      sourceCatIdx = findCategoryIndex(nodeId)
      if (sourceCatIdx < 0 || sourceCatIdx >= categories.length) return false
      sourceItem = categories[sourceCatIdx]
    } else if (isLeaf(nodeId)) {
      sourceCatIdx = categories.findIndex((cat) =>
        (cat.children ?? []).some((leaf) => leaf.id === nodeId)
      )
      const cat = categories[sourceCatIdx]
      const leaves = cat?.children ?? []
      sourceLeafIdx = leaves.findIndex((leaf) => leaf.id === nodeId)
      if (sourceLeafIdx < 0 || sourceLeafIdx >= leaves.length) return false
      sourceItem = leaves[sourceLeafIdx]
    } else {
      return false
    }
    if (!sourceItem) return false

    const insertPlacement = targetType === 'sibling' ? 'before' : targetType

    if ((insertPlacement === 'before' || insertPlacement === 'after') && targetId) {
      if (isCategory(nodeId) && isCategory(targetId)) {
        const targetCatIdx = findCategoryIndex(targetId)
        if (targetCatIdx < 0 || targetCatIdx >= categories.length) return false
        const [removed] = categories.splice(sourceCatIdx, 1)
        let insertIdx = insertPlacement === 'before' ? targetCatIdx : targetCatIdx + 1
        if (sourceCatIdx < insertIdx) insertIdx -= 1
        categories.splice(insertIdx, 0, removed)
      } else if (isLeaf(nodeId) && isLeaf(targetId)) {
        const targetCatIdx = categories.findIndex((cat) =>
          (cat.children ?? []).some((leaf) => leaf.id === targetId)
        )
        const targetLeafIdx = (categories[targetCatIdx]?.children ?? []).findIndex(
          (leaf) => leaf.id === targetId
        )
        if (targetCatIdx < 0 || targetLeafIdx < 0) return false
        const srcCat = categories[sourceCatIdx]
        const tgtCat = categories[targetCatIdx]
        const srcLeaves = srcCat?.children ?? []
        const tgtLeaves = tgtCat?.children ?? []
        const [removed] = srcLeaves.splice(sourceLeafIdx, 1)
        let insertIdx = insertPlacement === 'before' ? targetLeafIdx : targetLeafIdx + 1
        if (sourceCatIdx === targetCatIdx && sourceLeafIdx < insertIdx) insertIdx -= 1
        tgtLeaves.splice(insertIdx, 0, removed)
      } else if (isLeaf(nodeId) && isCategory(targetId)) {
        const targetCatIdx = findCategoryIndex(targetId)
        if (targetCatIdx < 0) return false
        const srcCat = categories[sourceCatIdx]
        const tgtCat = categories[targetCatIdx]
        const srcLeaves = srcCat?.children ?? []
        const [removed] = srcLeaves.splice(sourceLeafIdx, 1)
        if (!tgtCat.children) tgtCat.children = []
        const insertIdx = insertPlacement === 'before' ? 0 : tgtCat.children.length
        tgtCat.children.splice(insertIdx, 0, removed)
      } else {
        return false
      }
    } else if (targetType === 'child' && targetId && isCategory(targetId)) {
      if (!isLeaf(nodeId)) return false
      const targetCatIdx = findCategoryIndex(targetId)
      if (targetCatIdx < 0 || targetCatIdx >= categories.length) return false
      const srcCat = categories[sourceCatIdx]
      const tgtCat = categories[targetCatIdx]
      const srcLeaves = srcCat?.children ?? []
      const [removed] = srcLeaves.splice(sourceLeafIdx, 1)
      if (!tgtCat.children) tgtCat.children = []
      tgtCat.children.push(removed)
    } else if (targetType === 'topic' && targetId === TREE_TOPIC_NODE_ID) {
      if (isLeaf(nodeId)) return false
      const [removed] = categories.splice(sourceCatIdx, 1)
      categories.push(removed)
    } else {
      return false
    }

    const cleanCategories = categories.map((cat) => ({
      id: cat.id,
      text: cat.text,
      ...carriedGloss(cat),
      children: (cat.children ?? []).map((leaf) => ({
        id: leaf.id,
        text: leaf.text,
        ...carriedGloss(leaf),
      })),
    }))
    if (!data.value?.nodes) return false
    const graph = materializeTreeMapGraph(arrangeTreeMapNodes(data.value.nodes, cleanCategories))
    data.value.nodes = recalculateTreeMapLayout(graph.nodes, ctx.nodeDimensions.value)
    data.value.connections = graph.connections
    if (data.value._customPositions) data.value._customPositions = {}
    selectedNodes.value = []
    ctx.selectedConnectionId.value = null
    ctx.pushHistory('Move branch')
    emitCtxEvent(ctx, 'diagram:operation_completed', { operation: 'move_branch' })
    ctx.viewBus.emit('diagram:branch_moved', {})
    return true
  }

  function addTreeMapCategory(label: InsertLabelInput): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (type.value !== 'tree_map' || !data.value?.nodes) return false
    const next = appendTreeMapCategory(data.value.nodes, label)
    if (!next) return false
    commitTreeMapGraph(next.nodes, next.connections, 'Add tree category', 'add')
    return true
  }

  function insertTreeMapCategory(label: InsertLabelInput, atIndex: number): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (type.value !== 'tree_map' || !data.value?.nodes) return false
    const next = insertTreeMapCategoryAt(data.value.nodes, label, atIndex)
    if (!next) return false
    commitTreeMapGraph(next.nodes, next.connections, 'Add tree category', 'add')
    return true
  }

  function addTreeMapChild(categoryId: string, label: InsertLabelInput): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (type.value !== 'tree_map' || !data.value?.nodes) return false
    const next = appendTreeMapChild(data.value.nodes, categoryId, label)
    if (!next) return false
    commitTreeMapGraph(next.nodes, next.connections, 'Add tree child', 'add')
    return true
  }

  function insertTreeMapChild(
    categoryId: string,
    label: InsertLabelInput,
    atIndex: number
  ): boolean {
    if (isDiagramPresentationReadOnly(ctx)) return false
    if (type.value !== 'tree_map' || !data.value?.nodes) return false
    const next = insertTreeMapChildAt(data.value.nodes, categoryId, label, atIndex)
    if (!next) return false
    commitTreeMapGraph(next.nodes, next.connections, 'Add tree child', 'add')
    return true
  }

  return {
    buildTreeMapSpecFromNodes,
    removeTreeMapNodes,
    getTreeMapDescendantIds,
    moveTreeMapBranch,
    addTreeMapCategory,
    insertTreeMapCategory,
    addTreeMapChild,
    insertTreeMapChild,
  }
}
