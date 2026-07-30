import type { Ref } from 'vue'

import type { DiagramType } from '@/types'
import { markMindMapLoadRecalc } from '@/utils/mindMapLoadDebug'

/**
 * Coalesce burst mind-map layout invalidations (e.g. many ResizeObservers on load)
 * into at most one recalc per animation frame.
 *
 * Optional `syncStorePositions` runs once per frame before the trigger bump so
 * Pinia node X/Y match the display layout (single position SoT).
 */
export function createMindMapRecalcScheduler(
  type: Ref<DiagramType | null>,
  mindMapRecalcTrigger: Ref<number>,
  syncStorePositions?: () => void
): () => void {
  let rafId: number | null = null

  function runRecalc(): void {
    markMindMapLoadRecalc()
    syncStorePositions?.()
    mindMapRecalcTrigger.value++
  }

  return function scheduleMindMapRecalc(): void {
    const diagramType = type.value
    if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return

    if (typeof requestAnimationFrame !== 'function') {
      runRecalc()
      return
    }

    if (rafId !== null) return
    rafId = requestAnimationFrame(() => {
      rafId = null
      runRecalc()
    })
  }
}
