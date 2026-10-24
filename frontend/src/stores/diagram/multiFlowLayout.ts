import type { DiagramContext } from './types'

/**
 * Multi-flow map layout width tracking slice.
 * Manages topic-node and per-node widths for visual balance,
 * triggering reactive layout recalculation.
 */
export function useMultiFlowLayoutSlice(ctx: DiagramContext) {
  function setTopicNodeWidth(width: number | null): void {
    // A measure taken before the event pill has laid out is 0. Storing that
    // collapses the event to a point and every arrow meets there.
    if (width != null && !(width > 0)) return
    if (ctx.topicNodeWidth.value === width) return
    ctx.topicNodeWidth.value = width
    if (ctx.type.value === 'multi_flow_map') {
      ctx.multiFlowMapRecalcTrigger.value++
    }
  }

  function setNodeWidth(nodeId: string, width: number | null): void {
    const widths = ctx.nodeWidths.value
    if (width === null) {
      if (!(nodeId in widths)) return
      delete widths[nodeId]
    } else if (widths[nodeId] === width) {
      return
    } else {
      widths[nodeId] = width
    }
    if (ctx.type.value === 'multi_flow_map') {
      ctx.multiFlowMapRecalcTrigger.value++
    }
  }

  return { setTopicNodeWidth, setNodeWidth }
}
