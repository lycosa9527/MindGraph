import {
  type InsertLabelInput,
  diagramInsertLabel,
  insertLabelFields,
} from '@/diagramBilingual/insertLabel'
import { BRACE_MAP_UID_DATA_KEY, takeBraceMapStableId } from '@/utils/braceMapIdentity'

import { useConceptMapRelationshipStore } from '../conceptMapRelationship'
import { recalculateBraceMapLayout } from '../specLoader'
import {
  braceMapRootId,
  isBraceMapPartAddTarget,
  resolveBraceMapSubpartAttachParentId,
} from './braceMapParentResolve'
import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { commitDeleteLayout } from './commitDeleteLayout'
import { emitCtxEvent } from './events'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import type { DiagramContext } from './types'

export function useBraceMapOpsSlice(ctx: DiagramContext) {
  const { type, data } = ctx

  function addBraceMapPart(
    parentId: string,
    text?: InsertLabelInput,
    subpartTexts?: [InsertLabelInput, InsertLabelInput]
  ): boolean {
    if (type.value !== 'brace_map' || !data.value?.nodes || !data.value?.connections) return false

    const parentNode = data.value.nodes.find((n) => n.id === parentId)
    if (!parentNode) return false

    const connections = data.value.connections ?? []
    const rootId = braceMapRootId(data.value.nodes, connections)
    const isAddingPart = isBraceMapPartAddTarget(parentId, parentNode, rootId)
    const attachParentId =
      isAddingPart || !rootId
        ? parentId
        : resolveBraceMapSubpartAttachParentId(parentId, connections, rootId)

    const partText =
      text ??
      diagramInsertLabel(
        data.value.languages,
        isAddingPart ? 'diagram.newPart' : 'diagram.newSubpart'
      )
    const claimed = new Set(data.value.nodes.map((n) => n.id).filter(Boolean))
    claimed.add('brace-whole')
    claimed.add('dimension-label')

    const place = (parent: string, label: InsertLabelInput): string => {
      const id = takeBraceMapStableId(claimed)
      ctx.addNode({
        id,
        ...insertLabelFields(label),
        type: 'brace',
        position: { x: 0, y: 0 },
        data: { [BRACE_MAP_UID_DATA_KEY]: id },
      })
      ctx.addConnection(parent, id)
      return id
    }

    if (!isAddingPart && subpartTexts) {
      for (const label of subpartTexts) place(attachParentId, label)
    } else {
      const newId = place(attachParentId, partText)
      if (isAddingPart && subpartTexts) {
        place(newId, subpartTexts[0])
        place(newId, subpartTexts[1])
      }
    }

    commitBraceMapAdd()
    return true
  }

  function commitBraceMapAdd(): void {
    if (!data.value) return
    ctx.pushHistory('Add brace map part')
    emitCtxEvent(ctx, 'diagram:node_added', { node: null })

    const layoutNodes = recalculateBraceMapLayout(
      data.value.nodes,
      data.value.connections ?? [],
      ctx.nodeDimensions.value
    )
    data.value.nodes = layoutNodes
  }

  /** Attach children straight under `parentId`, at any depth below the whole. */
  function addBraceMapChildren(parentId: string, texts: readonly InsertLabelInput[]): boolean {
    if (type.value !== 'brace_map' || !data.value?.nodes || !data.value?.connections) return false
    if (texts.length === 0 || parentId === 'dimension-label') return false
    if (!data.value.nodes.some((n) => n.id === parentId)) return false

    const claimed = new Set(data.value.nodes.map((n) => n.id).filter(Boolean))
    claimed.add('brace-whole')
    claimed.add('dimension-label')
    for (const label of texts) {
      const id = takeBraceMapStableId(claimed)
      ctx.addNode({
        id,
        ...insertLabelFields(label),
        type: 'brace',
        position: { x: 0, y: 0 },
        data: { [BRACE_MAP_UID_DATA_KEY]: id },
      })
      ctx.addConnection(parentId, id)
    }

    commitBraceMapAdd()
    return true
  }

  function removeBraceMapNodes(nodeIds: string[]): number {
    if (isDiagramPresentationReadOnly(ctx)) return 0
    if (type.value !== 'brace_map' || !data.value?.nodes) return 0

    const connections = data.value.connections ?? []
    const rootId = braceMapRootId(data.value.nodes, connections)
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
      if (ctx.emitDiagramEvents && !ctx.isReadonly.value) {
        const relStore = useConceptMapRelationshipStore()
        removedConnIds.forEach((id) => relStore.clearConnection(id))
      }
    }

    commitDeleteLayout(ctx, deletedIds)
    emitCtxEvent(ctx, 'diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedIds.length
  }

  return { addBraceMapPart, addBraceMapChildren, removeBraceMapNodes }
}
