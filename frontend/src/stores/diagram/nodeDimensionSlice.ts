import type { DiagramContext } from './types'

/**
 * Generic node dimension tracking slice.
 * Stores actual DOM-measured width/height for any diagram node,
 * triggering reactive layout recalculation via layoutRecalcTrigger.
 *
 * Two modes:
 *  - Batch mode: after loadFromSpec arms an expected node count,
 *    the trigger fires only when every node has reported its dimensions.
 *  - Live mode: any individual dimension change fires the trigger immediately.
 */
export function useNodeDimensionSlice(ctx: DiagramContext) {
  let pendingNodeCount = 0

  function setExpectedNodeCount(count: number): void {
    pendingNodeCount = count
  }

  function setNodeDimensions(nodeId: string, width: number | null, height: number | null): void {
    const wasBatch = pendingNodeCount > 0

    if (width === null && height === null) {
      if (!(nodeId in ctx.nodeDimensions.value)) return
      delete ctx.nodeDimensions.value[nodeId]
      if (!wasBatch) ctx.layoutRecalcTrigger.value++
      return
    }

    if (wasBatch) pendingNodeCount--

    const existing = ctx.nodeDimensions.value[nodeId]
    const newW = width ?? existing?.width ?? 0
    const newH = height ?? existing?.height ?? 0

    const unchanged =
      existing && Math.abs(existing.width - newW) < 1 && Math.abs(existing.height - newH) < 1

    if (!unchanged) {
      ctx.nodeDimensions.value[nodeId] = { width: newW, height: newH }
    }

    if (wasBatch) {
      if (pendingNodeCount <= 0) {
        pendingNodeCount = 0
        ctx.layoutRecalcTrigger.value++
      }
    } else if (!unchanged) {
      ctx.layoutRecalcTrigger.value++
    }
  }

  function clearNodeDimensions(): void {
    pendingNodeCount = 0
    ctx.nodeDimensions.value = {}
  }

  function getNodeDimension(nodeId: string): { width: number; height: number } | undefined {
    return ctx.nodeDimensions.value[nodeId]
  }

  return { setNodeDimensions, clearNodeDimensions, getNodeDimension, setExpectedNodeCount }
}
