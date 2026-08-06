/**
 * In-place `?type=` blank-load while CanvasPage / MobileCanvasPage stay mounted.
 * Initial entry is still handled by onMounted route loaders; this watch covers
 * query changes without remount (and dedupes against switch/reset helpers).
 */
import { watch } from 'vue'
import type { LocationQuery, RouteLocationNormalizedLoaded } from 'vue-router'

import {
  isNewCanvasTypeQuery,
  loadBlankCanvasForType,
  resolveDiagramTypeFromQuery,
} from '@/composables/canvasPage/newCanvasBootstrap'
import type { DiagramType } from '@/types'

export type NewCanvasTypeQueryBootstrapOptions = {
  route: RouteLocationNormalizedLoaded
  setDiagramType: (diagramType: DiagramType) => boolean
  clearActiveDiagram: () => void
  loadDefaultTemplate: (diagramType: DiagramType) => boolean
  setSelectedChartType: (chineseName: string) => void
  /** Current Pinia diagram data presence — empty sessions must not dedupe. */
  hasDiagramData: () => boolean
  /** Optional post-blank hook (desktop kitty seed strip, etc.). */
  afterBlankLoad?: (diagramType: DiagramType, query: LocationQuery) => void
}

export function useNewCanvasTypeQueryBootstrap(
  options: NewCanvasTypeQueryBootstrapOptions
): void {
  watch(
    () => resolveDiagramTypeFromQuery(options.route.query),
    (type, prevType) => {
      if (!type || type === prevType) return
      if (!isNewCanvasTypeQuery(options.route.query)) return

      const loaded = loadBlankCanvasForType({
        diagramType: type,
        setDiagramType: options.setDiagramType,
        clearActiveDiagram: options.clearActiveDiagram,
        loadDefaultTemplate: options.loadDefaultTemplate,
        setSelectedChartType: options.setSelectedChartType,
        hasDiagramData: options.hasDiagramData(),
      })
      if (loaded) {
        options.afterBlankLoad?.(type, options.route.query)
      }
    }
  )
}
