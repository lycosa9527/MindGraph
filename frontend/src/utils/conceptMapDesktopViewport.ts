import type { useDiagramStore } from '@/stores/diagram'
import type { useUIStore } from '@/stores/ui'

export function isMindMapDiagramType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

/**
 * Desktop concept maps: viewport is user-controlled only (no auto fit / programmatic pan-zoom).
 * Mobile (`uiStore.isMobile`) keeps assistive fits (e.g. after palette close, initial topic zoom).
 */
export function isDesktopConceptMapManualViewport(
  diagramStore: ReturnType<typeof useDiagramStore>,
  uiStore: ReturnType<typeof useUIStore>
): boolean {
  return diagramStore.type === 'concept_map' && !uiStore.isMobile
}

/** Mind maps: no auto-fit in v2; legacy mind maps keep assistive fit on init. */
export function isMindMapManualViewport(
  diagramStore: ReturnType<typeof useDiagramStore>,
  uiStore: ReturnType<typeof useUIStore>
): boolean {
  return isMindMapDiagramType(diagramStore.type) && uiStore.mindMapCanvasMode === 'v2'
}

/** Diagram types that skip programmatic auto-fit unless userInitiated / forExport. */
export function isManualViewportMode(
  diagramStore: ReturnType<typeof useDiagramStore>,
  uiStore: ReturnType<typeof useUIStore>
): boolean {
  return (
    isMindMapManualViewport(diagramStore, uiStore) ||
    isDesktopConceptMapManualViewport(diagramStore, uiStore)
  )
}
