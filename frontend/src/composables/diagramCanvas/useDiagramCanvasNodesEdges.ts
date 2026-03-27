import { type MaybeRefOrGetter, computed, toValue } from 'vue'

import { useBranchMoveDrag } from '@/composables/editor/useBranchMoveDrag'
import { useDiagramStore } from '@/stores'

export interface UseDiagramCanvasNodesEdgesOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  branchMove: ReturnType<typeof useBranchMoveDrag>
  collabLockedNodeIds: MaybeRefOrGetter<string[]>
}

export function useDiagramCanvasNodesEdges(options: UseDiagramCanvasNodesEdgesOptions) {
  const { diagramStore, branchMove, collabLockedNodeIds } = options

  const storeNodes = computed(() => diagramStore.vueFlowNodes)
  const storeEdges = computed(() => diagramStore.vueFlowEdges)

  const nodes = computed(() => {
    const hidden = branchMove.state.value.hiddenIds
    let list = storeNodes.value
    if (hidden.size > 0) {
      list = list.filter((n) => !hidden.has(n.id))
    }
    const locked = toValue(collabLockedNodeIds)
    if (locked.length === 0) {
      return list
    }
    const lockedSet = new Set(locked)
    return list.map((n) => (lockedSet.has(n.id) ? { ...n, draggable: false } : n))
  })

  const nodesLength = computed(() => nodes.value.length)

  const edges = computed(() => {
    if (diagramStore.type === 'brace_map') {
      return []
    }
    const hidden = branchMove.state.value.hiddenIds
    if (hidden.size === 0) return storeEdges.value
    return storeEdges.value.filter((e) => !hidden.has(e.source) && !hidden.has(e.target))
  })

  return { nodes, edges, nodesLength }
}
