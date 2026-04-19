import type { NodeChange, NodeDragEvent, NodeMouseEvent } from '@vue-flow/core'

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
  emit: {
    (e: 'nodeClick', node: MindGraphNode): void
    (e: 'nodeDoubleClick', node: MindGraphNode): void
    (e: 'nodeDragStop', node: MindGraphNode): void
  }
  scheduleFitAfterStructuralNodeChange: (hasFitTriggeringChange: boolean) => void
  vueFlowHandlers: DiagramCanvasVueFlowHandlerApi
}

export function useDiagramCanvasVueFlowHandlers(
  options: UseDiagramCanvasVueFlowHandlersOptions
): void {
  const { diagramStore, emit, scheduleFitAfterStructuralNodeChange, vueFlowHandlers } = options

  const { onNodesChange, onNodeClick, onNodeDoubleClick, onNodeDragStop } = vueFlowHandlers

  onNodesChange((changes) => {
    let hasFitTriggeringChange = false
    const conceptMapPositionNodeIds = new Set<string>()

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

    scheduleFitAfterStructuralNodeChange(hasFitTriggeringChange)
  })

  onNodeClick(({ node }) => {
    diagramStore.selectNodes(node.id)
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
