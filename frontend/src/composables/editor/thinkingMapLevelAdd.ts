/**
 * Outer-level and inner-level adds for tree, brace, and double bubble maps.
 * Enter and the first toolbar button add the outer level.
 * Tab and the second toolbar button add the inner level.
 * Brace maps have a third button that adds one level below the selected node.
 */
import type { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import type { InsertLabel } from '@/diagramBilingual/insertLabel'
import {
  braceMapRootId,
  resolveBraceMapSubpartAttachParentId,
} from '@/stores/diagram/braceMapParentResolve'
import type { Connection, DiagramNode } from '@/types'
import {
  type DoubleBubbleRole,
  readDoubleBubbleIndex,
  readDoubleBubbleRole,
} from '@/utils/doubleBubbleMapIdentity'
import {
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeParentCategoryId,
  treeMapColumnsOf,
} from '@/utils/treeMapIdentity'

type DiagramSession = ReturnType<typeof useDiagramSession>

type LevelAddTranslate = (key: string, named?: Record<string, unknown>) => string

/** Node label in the diagram's file language(s). */
type LevelAddLabel = (key: string, named?: Record<string, unknown>) => InsertLabel

type LevelAddNotify = {
  success: (message: string) => void
  successKey: (key: string) => void
  warningKey: (key: string) => void
}

function selectNode(diagramStore: DiagramSession, nodeId: string | undefined): void {
  if (nodeId) diagramStore.selectNodes(nodeId)
}

function treeCategoryIdForItem(
  nodes: DiagramNode[],
  selectedId: string | undefined
): string | null {
  const selected = selectedId ? nodes.find((node) => node.id === selectedId) : undefined
  if (selected && isTreeMapCategoryNode(selected)) return selected.id
  if (selected && isTreeMapLeafNode(selected)) return readTreeParentCategoryId(selected)
  const columns = treeMapColumnsOf(nodes)
  return columns[columns.length - 1]?.category.id ?? null
}

function bracePartIdForSubpart(
  nodes: DiagramNode[],
  connections: Connection[],
  selectedId: string | undefined
): string | undefined {
  const rootId = braceMapRootId(nodes, connections)
  if (!rootId) return undefined
  if (selectedId && selectedId !== rootId && selectedId !== 'dimension-label') {
    const partId = resolveBraceMapSubpartAttachParentId(selectedId, connections, rootId)
    if (partId && partId !== rootId) return partId
  }
  const parts = connections
    .filter((edge) => edge.source === rootId && edge.target !== 'dimension-label')
    .map((edge) => edge.target)
  return parts[parts.length - 1]
}

/** Selected brace node below the whole, else the last subpart of the last part that has one. */
function braceNodeIdForNextLevel(
  nodes: DiagramNode[],
  connections: Connection[],
  selectedId: string | undefined
): string | undefined {
  const rootId = braceMapRootId(nodes, connections)
  if (!rootId) return undefined
  if (
    selectedId &&
    selectedId !== rootId &&
    selectedId !== 'dimension-label' &&
    nodes.some((node) => node.id === selectedId)
  ) {
    return selectedId
  }
  const childrenOf = (id: string) =>
    connections.filter((edge) => edge.source === id).map((edge) => edge.target)
  const parts = childrenOf(rootId).filter((id) => id !== 'dimension-label')
  for (let index = parts.length - 1; index >= 0; index--) {
    const subparts = childrenOf(parts[index])
    if (subparts.length > 0) return subparts[subparts.length - 1]
  }
  return undefined
}

function createdChildId(
  before: ReadonlySet<string>,
  nodes: DiagramNode[],
  connections: Connection[],
  parentId: string
): string | undefined {
  const created = nodes.filter((node) => !before.has(node.id))
  const attached = created.filter((node) =>
    connections.some((edge) => edge.source === parentId && edge.target === node.id)
  )
  return attached[attached.length - 1]?.id ?? created[created.length - 1]?.id
}

function listLength(value: unknown): number {
  return Array.isArray(value) ? value.length : 0
}

function selectLatestDoubleBubble(diagramStore: DiagramSession, role: DoubleBubbleRole): void {
  const matches = (diagramStore.data?.nodes ?? [])
    .filter((node) => readDoubleBubbleRole(node) === role)
    .sort((left, right) => readDoubleBubbleIndex(left) - readDoubleBubbleIndex(right))
  selectNode(diagramStore, matches[matches.length - 1]?.id)
}

export function createThinkingMapLevelAdds(
  diagramStore: DiagramSession,
  t: LevelAddTranslate,
  label: LevelAddLabel,
  notify: LevelAddNotify
) {
  function addTreeCategoryNode(): boolean {
    if (!diagramStore.addTreeMapCategory(label('canvas.toolbar.newBranch'))) return false
    const columns = treeMapColumnsOf(diagramStore.data?.nodes ?? [])
    selectNode(diagramStore, columns[columns.length - 1]?.category.id)
    notify.successKey('canvas.toolbar.branchAdded')
    return true
  }

  function addTreeItemNode(): boolean {
    const nodes = diagramStore.data?.nodes
    if (!nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return false
    }
    const categoryId = treeCategoryIdForItem(nodes, diagramStore.selectedNodes[0])
    if (!categoryId) {
      notify.warningKey('canvas.toolbar.selectTreeBranchForChild')
      return false
    }
    if (!diagramStore.addTreeMapChild(categoryId, label('canvas.toolbar.newChild'))) {
      notify.warningKey('canvas.toolbar.selectTreeBranchForChild')
      return false
    }
    const column = treeMapColumnsOf(diagramStore.data?.nodes ?? []).find(
      (entry) => entry.category.id === categoryId
    )
    const leaves = column?.leaves ?? []
    selectNode(diagramStore, leaves[leaves.length - 1]?.id)
    notify.successKey('canvas.toolbar.childAdded')
    return true
  }

  function addBracePartNode(): boolean {
    const nodes = diagramStore.data?.nodes
    const connections = diagramStore.data?.connections ?? []
    if (!nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return false
    }
    const rootId = braceMapRootId(nodes, connections)
    if (!rootId) return false
    const before = new Set(nodes.map((node) => node.id))
    if (!diagramStore.addBraceMapPart(rootId, label('canvas.toolbar.newPart'))) return false
    const refreshed = diagramStore.data?.nodes ?? []
    const edges = diagramStore.data?.connections ?? []
    selectNode(diagramStore, createdChildId(before, refreshed, edges, rootId))
    notify.successKey('canvas.toolbar.partAdded')
    return true
  }

  function addBraceSubpartNode(): boolean {
    const nodes = diagramStore.data?.nodes
    const connections = diagramStore.data?.connections ?? []
    if (!nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return false
    }
    const partId = bracePartIdForSubpart(nodes, connections, diagramStore.selectedNodes[0])
    if (!partId) {
      notify.warningKey('canvas.toolbar.selectPartForSubpart')
      return false
    }
    const groupEmpty = !connections.some((edge) => edge.source === partId)
    const before = new Set(nodes.map((node) => node.id))
    const added = groupEmpty
      ? diagramStore.addBraceMapPart(partId, undefined, [
          label('canvas.toolbar.subpartLabel1'),
          label('canvas.toolbar.subpartLabel2'),
        ])
      : diagramStore.addBraceMapPart(partId, label('canvas.toolbar.newSubpart'))
    if (!added) return false
    const refreshed = diagramStore.data?.nodes ?? []
    const edges = diagramStore.data?.connections ?? []
    selectNode(diagramStore, createdChildId(before, refreshed, edges, partId))
    notify.successKey('canvas.toolbar.subpartAdded')
    return true
  }

  /** One level below the target node: two children when it has none, else one more. */
  function addBraceNextLevelNode(): boolean {
    const nodes = diagramStore.data?.nodes
    const connections = diagramStore.data?.connections ?? []
    if (!nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return false
    }
    const parentId = braceNodeIdForNextLevel(nodes, connections, diagramStore.selectedNodes[0])
    if (!parentId) {
      notify.warningKey('canvas.toolbar.selectNodeForNextLevel')
      return false
    }
    const groupEmpty = !connections.some((edge) => edge.source === parentId)
    const before = new Set(nodes.map((node) => node.id))
    const added = diagramStore.addBraceMapChildren(
      parentId,
      groupEmpty
        ? [label('canvas.toolbar.subpartLabel1'), label('canvas.toolbar.subpartLabel2')]
        : [label('canvas.toolbar.newSubpart')]
    )
    if (!added) return false
    const refreshed = diagramStore.data?.nodes ?? []
    const edges = diagramStore.data?.connections ?? []
    selectNode(diagramStore, createdChildId(before, refreshed, edges, parentId))
    notify.successKey('canvas.toolbar.nextLevelAdded')
    return true
  }

  function addDoubleBubbleSimilarityNode(): boolean {
    const spec = diagramStore.getDoubleBubbleSpecFromData()
    if (!spec) return false
    const text = label('canvas.toolbar.similarityWithIndex', {
      n: listLength(spec.similarities) + 1,
    })
    if (!diagramStore.addDoubleBubbleMapNode('similarity', text)) return false
    diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
    selectLatestDoubleBubble(diagramStore, 'similarity')
    notify.successKey('canvas.toolbar.nodeAddedGeneric')
    return true
  }

  function addDoubleBubbleDifferenceNode(): boolean {
    const spec = diagramStore.getDoubleBubbleSpecFromData()
    if (!spec) return false
    const pairIndex =
      Math.max(listLength(spec.leftDifferences), listLength(spec.rightDifferences)) + 1
    const text = label('canvas.toolbar.differenceAWithIndex', { n: pairIndex })
    const pairText = label('canvas.toolbar.differenceBWithIndex', { n: pairIndex })
    if (!diagramStore.addDoubleBubbleMapNode('leftDiff', text, pairText)) return false
    diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
    selectLatestDoubleBubble(diagramStore, 'leftDiff')
    notify.successKey('canvas.toolbar.differencePairAdded')
    return true
  }

  return {
    addTreeCategoryNode,
    addTreeItemNode,
    addBracePartNode,
    addBraceSubpartNode,
    addBraceNextLevelNode,
    addDoubleBubbleSimilarityNode,
    addDoubleBubbleDifferenceNode,
  }
}
