import { ref } from 'vue'

import { DEFAULT_CENTER_X } from '@/composables/diagrams/layoutConfig'
import { useDiagramStore } from '@/stores'

export type OutlineDropPosition = 'before' | 'after' | 'child'

export function useMindMapOutlineDrag() {
  const diagramStore = useDiagramStore()
  const draggingNodeId = ref<string | null>(null)
  const dropTarget = ref<{ nodeId: string; position: OutlineDropPosition } | null>(null)

  function canDragNode(nodeId: string): boolean {
    return nodeId !== 'topic' && nodeId.startsWith('branch-')
  }

  function onDragStart(event: DragEvent, nodeId: string): void {
    if (!canDragNode(nodeId)) {
      event.preventDefault()
      return
    }
    draggingNodeId.value = nodeId
    event.dataTransfer?.setData('text/plain', nodeId)
    event.dataTransfer!.effectAllowed = 'move'
  }

  function onDragEnd(): void {
    draggingNodeId.value = null
    dropTarget.value = null
  }

  function resolveDropPosition(event: DragEvent, nodeId: string): OutlineDropPosition {
    if (nodeId === 'topic') return 'child'
    const el = event.currentTarget as HTMLElement | null
    if (!el) return 'after'
    const rect = el.getBoundingClientRect()
    const relY = event.clientY - rect.top
    const h = rect.height || 1
    if (relY < h * 0.28) return 'before'
    if (relY > h * 0.72) return 'child'
    return 'after'
  }

  function onDragOver(event: DragEvent, nodeId: string): void {
    if (!draggingNodeId.value || draggingNodeId.value === nodeId) return
    event.preventDefault()
    event.dataTransfer!.dropEffect = 'move'
    dropTarget.value = { nodeId, position: resolveDropPosition(event, nodeId) }
  }

  function onDragLeave(): void {
    dropTarget.value = null
  }

  function onDrop(event: DragEvent, nodeId: string): void {
    event.preventDefault()
    const draggedId = draggingNodeId.value
    if (!draggedId || draggedId === nodeId) {
      onDragEnd()
      return
    }

    const position = resolveDropPosition(event, nodeId)

    if (nodeId === 'topic' || position === 'child') {
      if (nodeId === 'topic') {
        diagramStore.moveMindMapBranch(
          draggedId,
          'topic',
          undefined,
          undefined,
          DEFAULT_CENTER_X + 1
        )
      } else {
        diagramStore.moveMindMapBranch(draggedId, 'child', nodeId)
      }
    } else if (position === 'before') {
      diagramStore.moveMindMapBranch(draggedId, 'before', nodeId)
    } else {
      diagramStore.moveMindMapBranch(draggedId, 'after', nodeId)
    }

    onDragEnd()
  }

  function isDropBefore(nodeId: string): boolean {
    return dropTarget.value?.nodeId === nodeId && dropTarget.value.position === 'before'
  }

  function isDropAfter(nodeId: string): boolean {
    return dropTarget.value?.nodeId === nodeId && dropTarget.value.position === 'after'
  }

  function isDropChild(nodeId: string): boolean {
    return dropTarget.value?.nodeId === nodeId && dropTarget.value.position === 'child'
  }

  return {
    draggingNodeId,
    canDragNode,
    onDragStart,
    onDragEnd,
    onDragOver,
    onDragLeave,
    onDrop,
    isDropBefore,
    isDropAfter,
    isDropChild,
  }
}
