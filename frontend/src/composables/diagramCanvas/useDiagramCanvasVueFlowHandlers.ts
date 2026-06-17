import type { GraphNode, NodeChange, NodeDragEvent, NodeMouseEvent, NodeSelectionChange } from '@vue-flow/core'

import { useDiagramStore } from '@/stores'
import type { MindGraphNode } from '@/types'

const FIT_TRIGGERING_CHANGE_TYPES = ['position', 'dimensions', 'remove', 'add'] as const

export interface DiagramCanvasVueFlowHandlerApi {
  onNodesChange: (handler: (changes: NodeChange[]) => void) => void
  onNodeClick: (handler: (event: NodeMouseEvent) => void) => void
  onNodeDoubleClick: (handler: (event: NodeMouseEvent) => void) => void
  onNodeDragStop: (handler: (event: NodeDragEvent) => void) => void
}

export interface UseDiagramCanvasVueFlowHandlersOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  getVueFlowNodes: () => GraphNode[]
  emit: {
    (e: 'nodeClick', node: MindGraphNode): void
    (e: 'nodeDoubleClick', node: MindGraphNode): void
    (e: 'nodeDragStop', node: MindGraphNode): void
  }
  scheduleFitAfterStructuralNodeChange: (hasFitTriggeringChange: boolean) => void
  vueFlowHandlers: DiagramCanvasVueFlowHandlerApi
  onSelectionDragEnd?: () => void
}

export function useDiagramCanvasVueFlowHandlers(
  options: UseDiagramCanvasVueFlowHandlersOptions
): void {
  const {
    diagramStore,
    getVueFlowNodes,
    emit,
    scheduleFitAfterStructuralNodeChange,
    vueFlowHandlers,
    onSelectionDragEnd,
  } = options

  const { onNodesChange, onNodeClick, onNodeDoubleClick, onNodeDragStop } = vueFlowHandlers

  function selectionIdsEqual(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false
    const sortedA = [...a].sort()
    const sortedB = [...b].sort()
    return sortedA.every((id, i) => id === sortedB[i])
  }

  function applySelectChanges(changes: NodeSelectionChange[]): void {
    const next = new Set(diagramStore.selectedNodes)
    for (const change of changes) {
      if (change.selected) next.add(change.id)
      else next.delete(change.id)
    }
    const ids = [...next]
    if (selectionIdsEqual(ids, diagramStore.selectedNodes)) return
    if (ids.length === 0) {
      diagramStore.clearSelection()
      return
    }
    diagramStore.selectNodes(ids)
  }

  function syncSelectionFromVueFlow(): void {
    const ids = getVueFlowNodes()
      .filter((n) => n.selected)
      .map((n) => n.id)
    const current = diagramStore.selectedNodes
    if (selectionIdsEqual(ids, current)) return
    if (ids.length === 0) {
      diagramStore.clearSelection()
      return
    }
    diagramStore.selectNodes(ids)
  }

  onNodesChange((changes) => {
    let hasFitTriggeringChange = false
    const conceptMapPositionNodeIds = new Set<string>()
    const selectChanges = changes.filter(
      (change): change is NodeSelectionChange => change.type === 'select'
    )

    changes.forEach((change) => {
      if (change.type === 'position' && change.position) {
        diagramStore.updateNodePosition(change.id, change.position, false)
        if (diagramStore.type === 'concept_map') {
          conceptMapPositionNodeIds.add(change.id)
        }
      }
      if (
        FIT_TRIGGERING_CHANGE_TYPES.includes(
          change.type as (typeof FIT_TRIGGERING_CHANGE_TYPES)[number]
        )
      ) {
        hasFitTriggeringChange = true
      }
    })

    for (const nodeId of conceptMapPositionNodeIds) {
      diagramStore.updateConnectionArrowheadsForNode(nodeId)
    }

    if (selectChanges.length > 0) {
      applySelectChanges(selectChanges)
      onSelectionDragEnd?.()
    } else if (changes.some((change) => change.type === 'select')) {
      syncSelectionFromVueFlow()
      onSelectionDragEnd?.()
    }

    scheduleFitAfterStructuralNodeChange(hasFitTriggeringChange)
  })

  onNodeClick(({ node }) => {
    emit('nodeClick', node as unknown as MindGraphNode)
  })

  onNodeDoubleClick(({ node }) => {
    emit('nodeDoubleClick', node as unknown as MindGraphNode)
  })

  onNodeDragStop(({ node }) => {
    diagramStore.saveCustomPosition(node.id, node.position.x, node.position.y)
    if (diagramStore.type === 'concept_map') {
      diagramStore.updateConnectionArrowheadsForNode(node.id)
    }
    diagramStore.pushHistory('Move node')
    emit('nodeDragStop', node as unknown as MindGraphNode)
  })
}
