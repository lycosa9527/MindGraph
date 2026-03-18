import { computed } from 'vue'

import type { DiagramNode } from '@/types'

import type { DiagramContext } from './types'

export function useCopyPasteSlice(ctx: DiagramContext) {
  const { data, selectedNodes, copiedNodes } = ctx

  const canPaste = computed(() => copiedNodes.value.length > 0)

  function copySelectedNodes(): void {
    if (!data.value?.nodes || selectedNodes.value.length === 0) return
    const nodesToCopy = data.value.nodes.filter((n) => selectedNodes.value.includes(n.id))
    copiedNodes.value = nodesToCopy.map((node) => ({
      ...JSON.parse(JSON.stringify(node)),
      id: `copy-${node.id}-${Date.now()}`,
    }))
  }

  function pasteNodesAt(flowPosition: { x: number; y: number }): void {
    if (copiedNodes.value.length === 0) return
    const offset = 20
    copiedNodes.value.forEach((node, index) => {
      const newNode: DiagramNode = {
        ...JSON.parse(JSON.stringify(node)),
        id: `node-${Date.now()}-${index}`,
        position: {
          x: flowPosition.x + index * offset,
          y: flowPosition.y + index * offset,
        },
      }
      ctx.addNode(newNode)
    })
    ctx.pushHistory('粘贴节点')
  }

  return { canPaste, copySelectedNodes, pasteNodesAt }
}
