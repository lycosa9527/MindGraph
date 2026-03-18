import { computed } from 'vue'

import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useSelectionSlice(ctx: DiagramContext) {
  const { data, selectedNodes } = ctx

  const hasSelection = computed(() => selectedNodes.value.length > 0)

  const selectedNodeData = computed(() => {
    if (!data.value?.nodes || selectedNodes.value.length === 0) return []
    return data.value.nodes.filter((node) => selectedNodes.value.includes(node.id))
  })

  function selectNodes(nodeIds: string | string[]): boolean {
    const ids = Array.isArray(nodeIds) ? nodeIds : [nodeIds]

    if (ids.some((id) => typeof id !== 'string')) {
      console.error('Invalid node IDs - all IDs must be strings')
      return false
    }

    selectedNodes.value = ids
    emitEvent('diagram:selection_changed', { selectedNodes: ids })
    return true
  }

  function clearSelection(): void {
    selectedNodes.value = []
    emitEvent('diagram:selection_changed', { selectedNodes: [] })
  }

  function addToSelection(nodeId: string): void {
    if (!selectedNodes.value.includes(nodeId)) {
      selectedNodes.value.push(nodeId)
    }
  }

  function removeFromSelection(nodeId: string): void {
    const index = selectedNodes.value.indexOf(nodeId)
    if (index > -1) {
      selectedNodes.value.splice(index, 1)
    }
  }

  return {
    hasSelection,
    selectedNodeData,
    selectNodes,
    clearSelection,
    addToSelection,
    removeFromSelection,
  }
}
