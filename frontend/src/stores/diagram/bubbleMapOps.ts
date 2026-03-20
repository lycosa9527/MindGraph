import { getMindmapBranchColor } from '@/config/mindmapColors'

import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useBubbleMapOpsSlice(ctx: DiagramContext) {
  const { type, data } = ctx

  function removeBubbleMapNodes(nodeIds: string[]): number {
    if (type.value !== 'bubble_map' || !data.value?.nodes) return 0

    const idsToRemove = new Set(nodeIds.filter((id) => id.startsWith('bubble-')))
    if (idsToRemove.size === 0) return 0

    const deletedIds: string[] = []
    data.value.nodes = data.value.nodes.filter((n) => {
      if (idsToRemove.has(n.id)) {
        deletedIds.push(n.id)
        ctx.clearCustomPosition(n.id)
        ctx.clearNodeStyle(n.id)
        ctx.removeFromSelection(n.id)
        return false
      }
      return true
    })

    const bubbleNodes = data.value.nodes.filter(
      (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
    )
    bubbleNodes.forEach((bubbleNode, i) => {
      bubbleNode.id = `bubble-${i}`
    })
    data.value.connections = bubbleNodes.map((_, i) => ({
      id: `edge-topic-bubble-${i}`,
      source: 'topic',
      target: `bubble-${i}`,
      style: { strokeColor: getMindmapBranchColor(i).border },
    }))

    emitEvent('diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedIds.length
  }

  return { removeBubbleMapNodes }
}
