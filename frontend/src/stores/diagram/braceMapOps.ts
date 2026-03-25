import { useConceptMapRelationshipStore } from '../conceptMapRelationship'
import { recalculateBraceMapLayout } from '../specLoader'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useBraceMapOpsSlice(ctx: DiagramContext) {
  const { type, data } = ctx

  function addBraceMapPart(
    parentId: string,
    text?: string,
    subpartTexts?: [string, string]
  ): boolean {
    if (type.value !== 'brace_map' || !data.value?.nodes || !data.value?.connections) return false

    const parentNode = data.value.nodes.find((n) => n.id === parentId)
    if (!parentNode) return false

    const isAddingPart = parentId === 'topic' || parentNode.type === 'topic'
    const partText = text ?? (isAddingPart ? 'New Part' : 'New Subpart')
    const baseId = Date.now()
    const newId = `brace-part-${baseId}`

    ctx.addNode({
      id: newId,
      text: partText,
      type: 'brace',
      position: { x: 0, y: 0 },
    })
    ctx.addConnection(parentId, newId)

    if (isAddingPart) {
      const [sub1Text, sub2Text] = subpartTexts ?? ['New Subpart 1', 'New Subpart 2']
      const sub1Id = `brace-part-${baseId}-1`
      const sub2Id = `brace-part-${baseId}-2`
      ctx.addNode({
        id: sub1Id,
        text: sub1Text,
        type: 'brace',
        position: { x: 0, y: 0 },
      })
      ctx.addNode({
        id: sub2Id,
        text: sub2Text,
        type: 'brace',
        position: { x: 0, y: 0 },
      })
      ctx.addConnection(newId, sub1Id)
      ctx.addConnection(newId, sub2Id)
    }

    ctx.pushHistory('Add brace map part')
    emitEvent('diagram:node_added', { node: null })

    const layoutNodes = recalculateBraceMapLayout(
      data.value.nodes,
      data.value.connections ?? [],
      ctx.nodeDimensions.value
    )
    data.value.nodes = layoutNodes

    return true
  }

  function removeBraceMapNodes(nodeIds: string[]): number {
    if (type.value !== 'brace_map' || !data.value?.nodes) return 0

    const targetIds = new Set(data.value.connections?.map((c) => c.target) ?? [])
    const rootId =
      data.value.nodes.find((n) => n.type === 'topic')?.id ??
      data.value.nodes.find((n) => !targetIds.has(n.id))?.id
    if (!rootId) return 0

    const childrenMap = new Map<string, string[]>()
    data.value.connections?.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })

    function collectDescendants(id: string): Set<string> {
      const set = new Set<string>([id])
      for (const childId of childrenMap.get(id) ?? []) {
        for (const desc of collectDescendants(childId)) set.add(desc)
      }
      return set
    }

    const toRemove = new Set<string>()
    for (const id of nodeIds) {
      if (id === rootId || id === 'dimension-label') continue
      for (const desc of collectDescendants(id)) toRemove.add(desc)
    }
    if (toRemove.size === 0) return 0

    if (collabForeignLockBlocksAnyId(ctx, toRemove)) {
      emitCollabDeleteBlocked()
      return 0
    }

    const deletedIds: string[] = []
    data.value.nodes = data.value.nodes.filter((n) => {
      if (toRemove.has(n.id)) {
        deletedIds.push(n.id)
        ctx.clearCustomPosition(n.id)
        ctx.clearNodeStyle(n.id)
        ctx.removeFromSelection(n.id)
        return false
      }
      return true
    })
    if (data.value.connections) {
      const removedConnIds = data.value.connections
        .filter((c) => toRemove.has(c.source) || toRemove.has(c.target))
        .map((c) => c.id)
        .filter((id): id is string => !!id)
      data.value.connections = data.value.connections.filter(
        (c) => !toRemove.has(c.source) && !toRemove.has(c.target)
      )
      const relStore = useConceptMapRelationshipStore()
      removedConnIds.forEach((id) => relStore.clearConnection(id))
    }

    emitEvent('diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedIds.length
  }

  return { addBraceMapPart, removeBraceMapNodes }
}
