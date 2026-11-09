/**
 * Keep Vue Flow node positions on the store layout.
 * Vue Flow pauses its `nodes` prop watcher for one tick whenever its own node
 * store changes (for example when it records node sizes on mount) and does not
 * replay a prop change that lands in that window. A relayout from measured
 * sizes lands there on first paint, so the canvas would keep the pre-measure
 * positions. After each change, re-apply the list if any position was dropped.
 */
import { type Ref, nextTick, watch } from 'vue'

import { type Node, useVueFlow } from '@vue-flow/core'

export function useDiagramCanvasNodeSync(vueFlowId: string, nodes: Ref<Node[]>): void {
  const { findNode, setNodes } = useVueFlow(vueFlowId)

  function positionsDropped(list: Node[]): boolean {
    for (const node of list) {
      const painted = findNode(node.id)
      if (!painted) return true
      if (painted.dragging) return false
      if (painted.position.x !== node.position.x || painted.position.y !== node.position.y) {
        return true
      }
    }
    return false
  }

  watch(nodes, (list) => {
    void nextTick(() => {
      if (nodes.value !== list) return
      if (positionsDropped(list)) setNodes(list)
    })
  })
}
