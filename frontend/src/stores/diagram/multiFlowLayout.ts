import type { DiagramContext } from './types'

/**
 * Multi-flow map event-pill width. The layout computed reads topicNodeWidth,
 * so setting it relays the cause and effect columns out around the pill.
 */
export function useMultiFlowLayoutSlice(ctx: DiagramContext) {
  function setTopicNodeWidth(width: number | null): void {
    // A measure taken before the event pill has laid out is 0. Storing that
    // collapses the event to a point and every arrow meets there.
    if (width != null && !(width > 0)) return
    if (ctx.topicNodeWidth.value === width) return
    ctx.topicNodeWidth.value = width
  }

  return { setTopicNodeWidth }
}
