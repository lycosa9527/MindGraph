import type { Ref } from 'vue'

import type { DiagramType } from '@/types'

/**
 * Coalesce burst mind-map layout invalidations (e.g. many ResizeObservers on load)
 * into at most one recalc per animation frame.
 */
export function createMindMapRecalcScheduler(
  type: Ref<DiagramType | null>,
  mindMapRecalcTrigger: Ref<number>
): () => void {
  let rafId: number | null = null

  return function scheduleMindMapRecalc(): void {
    const diagramType = type.value
    if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return

    if (typeof requestAnimationFrame !== 'function') {
      mindMapRecalcTrigger.value++
      return
    }

    if (rafId !== null) return
    rafId = requestAnimationFrame(() => {
      rafId = null
      mindMapRecalcTrigger.value++
    })
  }
}
