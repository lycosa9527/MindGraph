import { DEFAULT_CENTER_X, DEFAULT_NODE_WIDTH } from '@/composables/diagrams/layoutConfig'
import { eventBus } from '@/composables/core/useEventBus'

import { useConceptMapRelationshipStore } from '../conceptMapRelationship'
import { getMindMapCurveExtents } from './events'
import type { DiagramContext } from './types'

/** Reconcile layout caches and selection after undo/redo swaps diagram data. */
export function reconcileAfterHistoryRestore(ctx: DiagramContext): void {
  const {
    data,
    type,
    selectedNodes,
    selectedConnectionId,
    copiedNodes,
    nodeDimensions,
    layoutRecalcTrigger,
    mindMapNodeWidths,
    mindMapNodeHeights,
    mindMapTopicActualWidth,
    mindMapTopicBranchGaps,
    mindMapRecalcTrigger,
    mindMapCurveExtentBaseline,
  } = ctx

  if (!data.value) {
    return
  }

  const nodeIds = new Set(data.value.nodes.map((node) => node.id))
  selectedNodes.value = selectedNodes.value.filter((id) => nodeIds.has(id))

  const activeConnectionId = selectedConnectionId.value
  if (
    activeConnectionId &&
    !data.value.connections?.some((connection) => connection.id === activeConnectionId)
  ) {
    selectedConnectionId.value = null
  }

  copiedNodes.value = []

  nodeDimensions.value = {}
  for (const node of data.value.nodes) {
    const estimatedWidth = node.data?.estimatedWidth as number | undefined
    const estimatedHeight = node.data?.estimatedHeight as number | undefined
    if (estimatedWidth && estimatedHeight && node.id) {
      nodeDimensions.value[node.id] = { width: estimatedWidth, height: estimatedHeight }
    }
  }

  const diagramType = type.value
  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    // Seed from estimates so Y restack does not wait on a ResizeObserver storm.
    const widths: Record<string, number> = {}
    const heights: Record<string, number> = {}
    let topicWidth: number | null = null
    for (const node of data.value.nodes) {
      const estimatedWidth = node.data?.estimatedWidth as number | undefined
      const estimatedHeight = node.data?.estimatedHeight as number | undefined
      if (estimatedWidth !== undefined) widths[node.id] = estimatedWidth
      if (estimatedHeight !== undefined) heights[node.id] = estimatedHeight
      if (
        node.id === 'topic' &&
        (node.type === 'topic' || node.type === 'center') &&
        estimatedWidth !== undefined
      ) {
        topicWidth = estimatedWidth
      }
    }
    mindMapNodeWidths.value = widths
    mindMapNodeHeights.value = heights
    mindMapTopicActualWidth.value = topicWidth
    mindMapTopicBranchGaps.value = null
    mindMapRecalcTrigger.value += 1

    const topicNode = data.value.nodes.find(
      (node) => node.id === 'topic' && (node.type === 'topic' || node.type === 'center')
    )
    if (topicNode) {
      const resolvedTopicWidth =
        topicWidth ??
        (topicNode.data?.estimatedWidth as number | undefined) ??
        DEFAULT_NODE_WIDTH
      const centerX =
        topicNode.position != null
          ? topicNode.position.x + resolvedTopicWidth / 2
          : DEFAULT_CENTER_X
      mindMapCurveExtentBaseline.value = getMindMapCurveExtents(data.value.nodes, centerX)
    } else {
      mindMapCurveExtentBaseline.value = null
    }
  } else {
    mindMapCurveExtentBaseline.value = null
  }

  layoutRecalcTrigger.value += 1
  useConceptMapRelationshipStore().clearAll()

  eventBus.emit('diagram:history_restored', { diagramType: diagramType ?? undefined })
}
