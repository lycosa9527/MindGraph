import { eventBus } from '@/composables/useEventBus'

import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useTreeMapOpsSlice(ctx: DiagramContext) {
  const { type, data, selectedNodes } = ctx

  function buildTreeMapSpecFromNodes(): Record<string, unknown> | null {
    if (!data.value || type.value !== 'tree_map') return null
    const nodes = data.value.nodes
    const rootNode = nodes.find((n) => n.id === 'tree-topic')
    if (!rootNode) return null
    const rootId = rootNode.id ?? 'tree-topic'
    const categoryNodes = nodes
      .filter((n) => /^tree-cat-\d+$/.test(n.id ?? ''))
      .sort(
        (a, b) =>
          parseInt((a.id ?? '0').replace('tree-cat-', ''), 10) -
          parseInt((b.id ?? '0').replace('tree-cat-', ''), 10),
      )
    const categories = categoryNodes.map((cat, catIndex) => {
      const leaves = nodes
        .filter((n) => {
          const m = (n.id ?? '').match(/^tree-leaf-(\d+)-(\d+)$/)
          return m && parseInt(m[1], 10) === catIndex
        })
        .sort(
          (a, b) =>
            parseInt((a.id ?? '0').split('-').pop() ?? '0', 10) -
            parseInt((b.id ?? '0').split('-').pop() ?? '0', 10),
        )
      return {
        id: cat.id,
        text: cat.text,
        children: leaves.map((l) => ({ id: l.id, text: l.text, children: [] })),
      }
    })
    const dimension = (data.value as Record<string, unknown>).dimension as string | undefined
    const altDims = (data.value as Record<string, unknown>).alternative_dimensions as
      | string[]
      | undefined
    return {
      root: {
        id: rootId,
        text: rootNode.text,
        children: categories,
      },
      dimension,
      alternative_dimensions: altDims,
    }
  }

  function removeTreeMapNodes(nodeIds: string[]): number {
    if (type.value !== 'tree_map' || !data.value?.nodes) return 0
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return 0

    const idsToRemove = new Set(nodeIds)
    if (idsToRemove.has('tree-topic') || idsToRemove.has('dimension-label')) return 0

    const categoryIdsToRemove = new Set(nodeIds.filter((id) => /^tree-cat-\d+$/.test(id)))

    const root = spec.root as {
      id?: string
      text: string
      children?: Array<{
        id?: string
        text: string
        children?: Array<{ id?: string; text: string }>
      }>
    }
    const categories = root.children ?? []

    let deletedCount = 0
    const newCategories = categories
      .filter((cat) => {
        if (categoryIdsToRemove.has(cat.id ?? '')) {
          deletedCount += 1 + (cat.children?.length ?? 0)
          return false
        }
        return true
      })
      .map((cat) => ({
        text: cat.text,
        children: (cat.children ?? [])
          .filter((leaf) => {
            if (idsToRemove.has(leaf.id ?? '')) {
              deletedCount++
              return false
            }
            return true
          })
          .map((leaf) => ({ text: leaf.text })),
      }))

    if (deletedCount === 0) return 0

    const newSpec = {
      ...spec,
      root: { ...root, id: undefined, children: newCategories },
    }
    ctx.loadFromSpec(newSpec, 'tree_map')

    const deletedIds = [
      ...nodeIds,
      ...categories
        .filter((c) => categoryIdsToRemove.has(c.id ?? ''))
        .flatMap((c) => (c.children ?? []).map((l) => l.id).filter(Boolean) as string[]),
    ]
    deletedIds.forEach((id) => {
      ctx.clearCustomPosition(id)
      ctx.clearNodeStyle(id)
      ctx.removeFromSelection(id)
    })
    ctx.pushHistory('Delete nodes')
    emitEvent('diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedCount
  }

  function getTreeMapDescendantIds(nodeId: string): Set<string> {
    const result = new Set<string>([nodeId])
    if (/^tree-leaf-\d+-\d+$/.test(nodeId)) return result
    if (!data.value?.connections) return result
    const childrenMap = new Map<string, string[]>()
    data.value.connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })
    function collect(id: string): void {
      for (const childId of childrenMap.get(id) ?? []) {
        if (
          (childId.startsWith('tree-cat-') || childId.startsWith('tree-leaf-')) &&
          childId !== 'tree-topic'
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
    targetType: 'topic' | 'child' | 'sibling',
    targetId?: string,
  ): boolean {
    if (type.value !== 'tree_map') return false
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false

    const root = spec.root as {
      id?: string
      text: string
      children?: Array<{
        id?: string
        text: string
        children?: Array<{ id?: string; text: string }>
      }>
    }
    const categories = root.children ?? []

    const isCategory = (id: string) => /^tree-cat-\d+$/.test(id)
    const isLeaf = (id: string) => /^tree-leaf-\d+-\d+$/.test(id)

    const findCategoryIndex = (id: string) => {
      const m = id.match(/^tree-cat-(\d+)$/)
      return m ? parseInt(m[1], 10) : -1
    }

    let sourceCatIdx = -1
    let sourceLeafIdx = -1
    let sourceItem: { id?: string; text: string; children?: unknown[] } | null = null

    if (isCategory(nodeId)) {
      sourceCatIdx = findCategoryIndex(nodeId)
      if (sourceCatIdx < 0 || sourceCatIdx >= categories.length) return false
      sourceItem = categories[sourceCatIdx]
    } else if (isLeaf(nodeId)) {
      const m = nodeId.match(/^tree-leaf-(\d+)-(\d+)$/)
      if (!m) return false
      sourceCatIdx = parseInt(m[1], 10)
      sourceLeafIdx = parseInt(m[2], 10)
      const cat = categories[sourceCatIdx]
      const leaves = cat?.children ?? []
      if (sourceLeafIdx < 0 || sourceLeafIdx >= leaves.length) return false
      sourceItem = leaves[sourceLeafIdx]
    } else {
      return false
    }
    if (!sourceItem) return false

    if (targetType === 'sibling' && targetId) {
      if (isCategory(nodeId) && isCategory(targetId)) {
        const targetCatIdx = findCategoryIndex(targetId)
        if (targetCatIdx < 0 || targetCatIdx >= categories.length) return false
        const [removed] = categories.splice(sourceCatIdx, 1)
        const adj = sourceCatIdx < targetCatIdx ? targetCatIdx - 1 : targetCatIdx
        const [removedTarget] = categories.splice(adj, 1)
        if (sourceCatIdx < targetCatIdx) {
          categories.splice(sourceCatIdx, 0, removedTarget)
          categories.splice(targetCatIdx, 0, removed)
        } else {
          categories.splice(targetCatIdx, 0, removed)
          categories.splice(sourceCatIdx, 0, removedTarget)
        }
      } else if (isLeaf(nodeId) && isLeaf(targetId)) {
        const tm = targetId.match(/^tree-leaf-(\d+)-(\d+)$/)
        if (!tm) return false
        const targetCatIdx = parseInt(tm[1], 10)
        const targetLeafIdx = parseInt(tm[2], 10)
        const srcCat = categories[sourceCatIdx]
        const tgtCat = categories[targetCatIdx]
        const srcLeaves = srcCat?.children ?? []
        const tgtLeaves = tgtCat?.children ?? []
        const srcLeaf = srcLeaves[sourceLeafIdx]
        const tgtLeaf = tgtLeaves[targetLeafIdx]
        if (!srcLeaf || !tgtLeaf) return false
        if (sourceCatIdx === targetCatIdx) {
          srcLeaves[sourceLeafIdx] = tgtLeaf
          srcLeaves[targetLeafIdx] = srcLeaf
        } else {
          srcLeaves.splice(sourceLeafIdx, 1)
          tgtLeaves.splice(targetLeafIdx, 1)
          srcLeaves.splice(sourceLeafIdx, 0, tgtLeaf)
          tgtLeaves.splice(targetLeafIdx, 0, srcLeaf)
        }
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
    } else if (targetType === 'topic' && targetId === 'tree-topic') {
      if (isLeaf(nodeId)) return false
      const [removed] = categories.splice(sourceCatIdx, 1)
      categories.push(removed)
    } else {
      return false
    }

    const cleanCategories = categories.map((cat) => ({
      text: cat.text,
      children: (cat.children ?? []).map((leaf) => ({ text: leaf.text })),
    }))
    const newSpec = { ...spec, root: { ...root, id: undefined, children: cleanCategories } }
    ctx.loadFromSpec(newSpec, 'tree_map')
    if (data.value?._customPositions) data.value._customPositions = {}
    if (data.value?._node_styles) data.value._node_styles = {}
    selectedNodes.value = []
    ctx.pushHistory('Move branch')
    emitEvent('diagram:operation_completed', { operation: 'move_branch' })
    eventBus.emit('diagram:branch_moved', {})
    return true
  }

  function addTreeMapCategory(text: string): boolean {
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false
    const root = spec.root as {
      text: string
      children?: Array<{ text: string; children?: unknown[] }>
    }
    if (!root.children) {
      root.children = []
    }
    root.children.push({ text, children: [] })
    ctx.loadFromSpec(spec, 'tree_map')
    ctx.pushHistory('Add tree category')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  function addTreeMapChild(categoryId: string, text: string): boolean {
    const spec = buildTreeMapSpecFromNodes()
    if (!spec) return false
    const root = spec.root as {
      children?: Array<{ id?: string; text: string; children?: Array<{ text: string }> }>
    }
    const categories = root.children ?? []
    const category = categories.find((c) => c.id === categoryId)
    if (!category) return false
    if (!category.children) {
      category.children = []
    }
    category.children.push({ text })
    ctx.loadFromSpec(spec, 'tree_map')
    ctx.pushHistory('Add tree child')
    emitEvent('diagram:node_added', { node: null })
    return true
  }

  return {
    buildTreeMapSpecFromNodes,
    removeTreeMapNodes,
    getTreeMapDescendantIds,
    moveTreeMapBranch,
    addTreeMapCategory,
    addTreeMapChild,
  }
}
