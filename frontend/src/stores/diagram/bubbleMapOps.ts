import { getMindmapBranchColor } from '@/config/mindmapColors'
import {
  BUBBLE_MAP_UID_DATA_KEY,
  BUBBLE_TOPIC_NODE_ID,
  isBubbleMapAttributeNode,
  stampBubbleAttributeData,
} from '@/utils/bubbleMapIdentity'

import { collabForeignLockBlocksAnyId, emitCollabDeleteBlocked } from './collabHelpers'
import { isDiagramPresentationReadOnly } from './presentationReadOnlyGuard'
import { emitCtxEvent } from './events'
import type { DiagramContext } from './types'

export function useBubbleMapOpsSlice(ctx: DiagramContext) {
  const { type, data } = ctx

  function removeBubbleMapNodes(nodeIds: string[]): number {
    if (isDiagramPresentationReadOnly(ctx)) return 0
    if (type.value !== 'bubble_map' || !data.value?.nodes) return 0

    const idsToRemove = new Set(
      nodeIds.filter((id) => {
        const node = data.value?.nodes.find((n) => n.id === id)
        return Boolean(node && isBubbleMapAttributeNode(node))
      })
    )
    if (idsToRemove.size === 0) return 0

    if (collabForeignLockBlocksAnyId(ctx, idsToRemove)) {
      emitCollabDeleteBlocked()
      return 0
    }

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

    const bubbleNodes = data.value.nodes.filter((n) => isBubbleMapAttributeNode(n))
    bubbleNodes.forEach((bubbleNode, i) => {
      bubbleNode.data = stampBubbleAttributeData(i, {
        ...bubbleNode.data,
        [BUBBLE_MAP_UID_DATA_KEY]: bubbleNode.id,
      })
    })
    data.value.connections = bubbleNodes.map((bubbleNode, i) => ({
      id: `edge-${BUBBLE_TOPIC_NODE_ID}-${bubbleNode.id}`,
      source: BUBBLE_TOPIC_NODE_ID,
      target: bubbleNode.id,
      style: { strokeColor: getMindmapBranchColor(i).border },
    }))

    emitCtxEvent(ctx, 'diagram:nodes_deleted', { nodeIds: deletedIds })
    return deletedIds.length
  }

  return { removeBubbleMapNodes }
}
