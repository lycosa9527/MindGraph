import type { DiagramContext } from './types'

/**
 * Generic node dimension tracking slice.
 * Stores actual DOM-measured width/height for any diagram node,
 * triggering reactive layout recalculation via layoutRecalcTrigger.
 *
 * Two modes:
 *  - Batch mode: after loadFromSpec arms an expected node count,
 *    the trigger fires once when every node has reported (or the stream goes quiet).
 *    Duplicate ResizeObserver callbacks for the same id do not end the batch early.
 *  - Live mode: any individual dimension change fires the trigger immediately.
 */

/** After the last new node id, flush without waiting for nodes that never mount. */
const MEASURE_BATCH_QUIET_MS = 64
/** Fallback when nothing reports. */
const MEASURE_BATCH_ARM_SAFETY_MS = 1500
/** Fallback after progress has started but the full set never arrives. */
const MEASURE_BATCH_PROGRESS_SAFETY_MS = 750

export function useNodeDimensionSlice(ctx: DiagramContext) {
  let pendingExpected = 0
  let reportedIds: Set<string> | null = null
  let quietTimer: ReturnType<typeof setTimeout> | null = null
  let safetyTimer: ReturnType<typeof setTimeout> | null = null
  let settleGeneration = 0

  function clearBatchTimers(): void {
    if (quietTimer != null) {
      clearTimeout(quietTimer)
      quietTimer = null
    }
    if (safetyTimer != null) {
      clearTimeout(safetyTimer)
      safetyTimer = null
    }
  }

  function armSafety(ms: number): void {
    if (safetyTimer != null) {
      clearTimeout(safetyTimer)
    }
    safetyTimer = setTimeout(() => {
      safetyTimer = null
      flushMeasureBatch()
    }, ms)
  }

  function endMeasureHold(): void {
    const generation = settleGeneration
    const release = (): void => {
      if (settleGeneration !== generation) return
      ctx.layoutMeasureSettling.value = false
    }
    if (typeof requestAnimationFrame !== 'function') {
      release()
      return
    }
    // Keep transform transitions off until the flushed positions have painted.
    requestAnimationFrame(() => {
      requestAnimationFrame(release)
    })
  }

  function flushMeasureBatch(): void {
    clearBatchTimers()
    if (reportedIds == null || pendingExpected <= 0) {
      pendingExpected = 0
      reportedIds = null
      endMeasureHold()
      return
    }
    pendingExpected = 0
    reportedIds = null
    ctx.layoutRecalcTrigger.value++
    endMeasureHold()
  }

  function setExpectedNodeCount(count: number): void {
    clearBatchTimers()
    settleGeneration++
    pendingExpected = Math.max(0, count)
    if (pendingExpected <= 0) {
      reportedIds = null
      ctx.layoutMeasureSettling.value = false
      return
    }
    reportedIds = new Set()
    ctx.layoutMeasureSettling.value = true
    armSafety(MEASURE_BATCH_ARM_SAFETY_MS)
  }

  function setNodeDimensions(nodeId: string, width: number | null, height: number | null): void {
    const batch = reportedIds != null && pendingExpected > 0

    if (width === null && height === null) {
      if (!(nodeId in ctx.nodeDimensions.value)) return
      delete ctx.nodeDimensions.value[nodeId]
      if (!batch) ctx.layoutRecalcTrigger.value++
      return
    }

    const existing = ctx.nodeDimensions.value[nodeId]
    const newW = width ?? existing?.width ?? 0
    const newH = height ?? existing?.height ?? 0

    const unchanged =
      existing && Math.abs(existing.width - newW) < 1 && Math.abs(existing.height - newH) < 1

    if (!unchanged) {
      ctx.nodeDimensions.value[nodeId] = { width: newW, height: newH }
    }

    if (batch && reportedIds) {
      const wasNew = !reportedIds.has(nodeId)
      reportedIds.add(nodeId)
      if (reportedIds.size >= pendingExpected) {
        flushMeasureBatch()
        return
      }
      if (wasNew) {
        armSafety(MEASURE_BATCH_PROGRESS_SAFETY_MS)
        if (quietTimer != null) {
          clearTimeout(quietTimer)
        }
        quietTimer = setTimeout(() => {
          quietTimer = null
          flushMeasureBatch()
        }, MEASURE_BATCH_QUIET_MS)
      }
      return
    }

    if (!unchanged) {
      ctx.layoutRecalcTrigger.value++
    }
  }

  function clearNodeDimensions(): void {
    clearBatchTimers()
    settleGeneration++
    pendingExpected = 0
    reportedIds = null
    ctx.layoutMeasureSettling.value = false
    ctx.nodeDimensions.value = {}
  }

  function getNodeDimension(nodeId: string): { width: number; height: number } | undefined {
    return ctx.nodeDimensions.value[nodeId]
  }

  return { setNodeDimensions, clearNodeDimensions, getNodeDimension, setExpectedNodeCount }
}
