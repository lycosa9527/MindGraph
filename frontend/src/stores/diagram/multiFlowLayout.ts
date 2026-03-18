import type { DiagramContext } from './types'

/**
 * Multi-flow map layout width tracking slice.
 * Manages topic-node and per-node widths for visual balance,
 * triggering reactive layout recalculation.
 */
export function useMultiFlowLayoutSlice(ctx: DiagramContext) {
  function setTopicNodeWidth(width: number | null): void {
    ctx.topicNodeWidth.value = width
    if (ctx.type.value === 'multi_flow_map') {
      ctx.multiFlowMapRecalcTrigger.value++
    }
  }

  function setNodeWidth(nodeId: string, width: number | null): void {
    if (width === null) {
      delete ctx.nodeWidths.value[nodeId]
    } else {
      ctx.nodeWidths.value[nodeId] = width
    }
    if (ctx.type.value === 'multi_flow_map') {
      ctx.multiFlowMapRecalcTrigger.value++
    }
  }

  return { setTopicNodeWidth, setNodeWidth }
}
