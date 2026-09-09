/**
 * Drag the 概要 range top/bottom to include or exclude sibling topics.
 */
import { type ComputedRef, type Ref, computed, toValue } from 'vue'

import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { diagramPresentationReadOnlyRef } from '@/composables/presentation/presentationDiagramEdit'
import { siblingBoxesForSummary } from '@/stores/diagram/mindMapSummaryLayout'
import type { MindMapSummarySpec } from '@/types'
import { coveredPathsFromVerticalRange, sameMindMapSummaryPaths } from '@/utils/mindMapSummary'
import { MINDMAP_SUMMARY_RANGE_PAD } from '@/utils/mindMapSummaryBrace'

const RANGE_MIN_H = 20

export type SummaryRangeDrag = {
  summaryId: string
  edge: 'top' | 'bottom'
  pointerId: number
  startCanvasY: number
  startRangeY: number
  startRangeH: number
  originPaths: string[]
  previewY: number
  previewH: number
  previewPaths: string[]
}

export type SummaryRangeBox = {
  rangeY: number
  rangeH: number
}

function clampRangePreview(
  edge: 'top' | 'bottom',
  startY: number,
  startH: number,
  dy: number,
  slots: readonly { y: number; height: number }[]
): { y: number; h: number } {
  if (slots.length === 0) return { y: startY, h: startH }
  const extentTop = slots[0].y - MINDMAP_SUMMARY_RANGE_PAD
  const last = slots[slots.length - 1]
  const extentBottom = last.y + last.height + MINDMAP_SUMMARY_RANGE_PAD
  let top = startY
  let bottom = startY + startH
  if (edge === 'top') top += dy
  else bottom += dy
  top = Math.max(extentTop, top)
  bottom = Math.min(extentBottom, bottom)
  if (bottom - top < RANGE_MIN_H) {
    if (edge === 'top') top = Math.max(extentTop, bottom - RANGE_MIN_H)
    else bottom = Math.min(extentBottom, top + RANGE_MIN_H)
  }
  return { y: top, h: Math.max(RANGE_MIN_H, bottom - top) }
}

function captureRangePointer(event: PointerEvent): void {
  const target = event.currentTarget
  if (target instanceof Element) {
    target.setPointerCapture(event.pointerId)
  }
}

function releaseRangePointer(event: PointerEvent): void {
  const target = event.currentTarget
  if (target instanceof Element && target.hasPointerCapture(event.pointerId)) {
    target.releasePointerCapture(event.pointerId)
  }
}

export function useMindMapSummaryRangeDrag(options: {
  rangeDrag: Ref<SummaryRangeDrag | null>
  overlayRoot: Ref<HTMLElement | null>
  viewport: ComputedRef<{ x: number; y: number; zoom: number }>
  findRange: (summaryId: string) => SummaryRangeBox | null
  findSummary: (summaryId: string) => MindMapSummarySpec | undefined
}) {
  const diagramStore = useDiagramSession()
  const rangeDrag = options.rangeDrag
  const canEdit = computed(
    () => !diagramPresentationReadOnlyRef.value && !toValue(diagramStore.isReadonly)
  )

  function clientToCanvasY(clientY: number): number {
    const root = options.overlayRoot.value
    const vp = options.viewport.value
    if (!root) return 0
    const pane = root.getBoundingClientRect()
    return (clientY - pane.top - vp.y) / vp.zoom
  }

  function onRangeEdgeDown(summaryId: string, edge: 'top' | 'bottom', event: PointerEvent): void {
    if (!canEdit.value || event.button !== 0) return
    const box = options.findRange(summaryId)
    const summary = options.findSummary(summaryId)
    if (!box || !summary) return
    const canvasY = clientToCanvasY(event.clientY)
    rangeDrag.value = {
      summaryId,
      edge,
      pointerId: event.pointerId,
      startCanvasY: canvasY,
      startRangeY: box.rangeY,
      startRangeH: box.rangeH,
      originPaths: [...summary.coveredPaths],
      previewY: box.rangeY,
      previewH: box.rangeH,
      previewPaths: [...summary.coveredPaths],
    }
    captureRangePointer(event)
  }

  function onRangeEdgeMove(event: PointerEvent): void {
    const drag = rangeDrag.value
    if (!drag || drag.pointerId !== event.pointerId) return
    const data = diagramStore.data
    const summary = options.findSummary(drag.summaryId)
    if (!data?.nodes || !summary) return
    const slots = siblingBoxesForSummary(
      data.nodes,
      data.connections ?? [],
      summary,
      diagramStore.mindMapNodeWidths ?? {},
      diagramStore.mindMapNodeHeights ?? {}
    )
    if (slots.length === 0) return
    const dy = clientToCanvasY(event.clientY) - drag.startCanvasY
    const clamped = clampRangePreview(drag.edge, drag.startRangeY, drag.startRangeH, dy, slots)
    rangeDrag.value = {
      ...drag,
      previewY: clamped.y,
      previewH: clamped.h,
      previewPaths: coveredPathsFromVerticalRange(slots, clamped.y, clamped.y + clamped.h),
    }
  }

  function onRangeEdgeUp(event: PointerEvent): void {
    const drag = rangeDrag.value
    if (!drag || drag.pointerId !== event.pointerId) return
    releaseRangePointer(event)
    const nextPaths = drag.previewPaths
    const origin = drag.originPaths
    rangeDrag.value = null
    if (!sameMindMapSummaryPaths(nextPaths, origin)) {
      diagramStore.updateMindMapSummaryCoveredPaths(drag.summaryId, nextPaths)
    }
  }

  function clearRangeDrag(): void {
    rangeDrag.value = null
  }

  return {
    onRangeEdgeDown,
    onRangeEdgeMove,
    onRangeEdgeUp,
    clearRangeDrag,
  }
}
