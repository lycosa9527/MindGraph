import { watch } from 'vue'

import type { useDiagramStore } from '@/stores/diagram'
import type { DiagramNode } from '@/types'
import { normalizeLabel } from '@/utils/cmapLabels'
import type { LayoutPositionsByLabel } from '@/utils/cmapLayoutExtract'
import {
  type TopLeftSizedRect,
  countOverlappingRects,
  relaxTopLeftPillLayoutsEstimated,
} from '@/utils/cmapLayoutOverlap'

/**
 * One-shot overlap relaxation for cmap-imported concept maps once DOM widths/heights settle.
 */

export function useConceptMapCmapMeasuredLayoutRelax(
  diagramStore: ReturnType<typeof useDiagramStore>
): void {
  watch(
    () => diagramStore.layoutRecalcTrigger,
    () => {
      if (diagramStore.type !== 'concept_map') {
        return
      }

      const payload = diagramStore.data as Record<string, unknown> | undefined
      const nodesCandidate = payload?.nodes as DiagramNode[] | undefined
      if (!payload || !Array.isArray(nodesCandidate) || nodesCandidate.length === 0) {
        return
      }

      if (payload['_import_cmap_measured_relax_pending'] !== true) {
        return
      }

      const layoutRaw = payload._layout_positions_by_label as LayoutPositionsByLabel | undefined
      if (
        typeof layoutRaw !== 'object' ||
        layoutRaw === null ||
        Object.keys(layoutRaw).length === 0
      ) {
        delete payload['_import_cmap_measured_relax_pending']
        return
      }

      const dimsBag = diagramStore.nodeDimensions as Record<
        string,
        { width?: number; height?: number }
      >
      const nodesVisible = nodesCandidate

      const sizesById: Record<string, { width: number; height: number }> = {}
      for (const n of nodesVisible) {
        const d = dimsBag[n.id]
        if (!(d?.width && d.height) || d.width < 14 || d.height < 14) {
          return
        }
        sizesById[n.id] = { width: d.width, height: d.height }
      }

      delete payload['_import_cmap_measured_relax_pending']

      const positions: Record<string, { x: number; y: number }> = {}
      const anchors: Record<string, { x: number; y: number }> = {}

      for (const n of nodesVisible) {
        const base = {
          x: n.position?.x ?? 0,
          y: n.position?.y ?? 0,
        }
        positions[n.id] = { ...base }
        const lbl = normalizeLabel(String(n.text ?? ''))
        const anchorLay = lbl.length > 0 ? layoutRaw[lbl] : undefined
        anchors[n.id] = anchorLay ? { x: anchorLay.x, y: anchorLay.y } : { ...base }
      }

      function toRects(map: Record<string, { x: number; y: number }>): TopLeftSizedRect[] {
        return nodesVisible.map((n) => {
          const pt = map[n.id] ?? { x: 0, y: 0 }
          const s = sizesById[n.id] ?? { width: 140, height: 50 }
          return {
            key: n.id,
            x: pt.x,
            y: pt.y,
            width: s.width,
            height: s.height,
          }
        })
      }

      const gapPx = 5
      const rectsBefore = toRects(positions)
      const overlapsBefore = countOverlappingRects(rectsBefore, gapPx)

      if (overlapsBefore === 0) {
        return
      }

      const relaxed = relaxTopLeftPillLayoutsEstimated(
        positions,
        sizesById,
        anchors,
        48,
        gapPx,
        0.07
      )
      const afterCount = countOverlappingRects(toRects(relaxed), gapPx)

      if (afterCount > overlapsBefore) {
        return
      }

      for (const n of nodesVisible) {
        const next = relaxed[n.id]
        const prevPos = positions[n.id]
        if (!(next && prevPos)) continue
        if (Math.abs(next.x - prevPos.x) > 2 || Math.abs(next.y - prevPos.y) > 2) {
          diagramStore.updateNodePosition(n.id, { x: next.x, y: next.y }, false)
        }
      }
    },
    { flush: 'post' }
  )
}
