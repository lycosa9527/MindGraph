/**
 * When the 概要 placement range box (rect + grips) is shown on the canvas overlay.
 */
import { parseMindMapSummaryNodeId } from '@/utils/mindMapSummary'

export type MindMapSummaryRangeChromeContext = {
  toolbarSummaryId: string | null
  draggingSummaryId: string | null | undefined
  selectedNodeIds: readonly string[]
}

/** Range rect stays up while inserting, selecting the 概要 topic, styling, or dragging the range. */
export function isMindMapSummaryRangeChromeActive(
  summaryId: string,
  ctx: MindMapSummaryRangeChromeContext
): boolean {
  if (ctx.toolbarSummaryId === summaryId) return true
  if (ctx.draggingSummaryId === summaryId) return true
  for (const nodeId of ctx.selectedNodeIds) {
    const parsed = parseMindMapSummaryNodeId(nodeId)
    if (parsed?.summaryId === summaryId && parsed.childPath.length === 0) {
      return true
    }
  }
  return false
}

/** Three-dot style handle ring — toolbar open or range drag, not mere topic selection. */
export function isMindMapSummaryStyleHandleActive(
  summaryId: string,
  ctx: Pick<MindMapSummaryRangeChromeContext, 'toolbarSummaryId' | 'draggingSummaryId'>
): boolean {
  if (ctx.toolbarSummaryId === summaryId) return true
  return ctx.draggingSummaryId === summaryId
}
