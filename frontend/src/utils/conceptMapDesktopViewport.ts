import type { DiagramSession } from '@/stores/diagram'
import type { useUIStore } from '@/stores/ui'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'

type DiagramSessionLike = Pick<DiagramSession, 'type' | 'mindMapCanvasMode'>

export function isMindMapDiagramType(type: string | null | undefined): boolean {
  return type === 'mindmap' || type === 'mind_map'
}

/**
 * Desktop concept maps: viewport is user-controlled only (no auto fit / programmatic pan-zoom).
 * Mobile (`uiStore.isMobile`) keeps assistive fits (e.g. after palette close, initial topic zoom).
 */
export function isDesktopConceptMapManualViewport(
  diagramStore: Pick<DiagramSession, 'type'>,
  uiStore: ReturnType<typeof useUIStore>
): boolean {
  return diagramStore.type === 'concept_map' && !uiStore.isMobile
}

/** Mind map v2: assistive fit only on first canvas enter; user/export fits use userInitiated / forExport. */
export function isMindMapManualViewport(diagramStore: DiagramSessionLike): boolean {
  return (
    isMindMapDiagramType(diagramStore.type) &&
    isSessionMindMapV2VisualDesignActive(diagramStore.mindMapCanvasMode)
  )
}

/** Diagram types that skip programmatic auto-fit unless userInitiated / forExport. */
export function isManualViewportMode(
  diagramStore: DiagramSessionLike,
  uiStore: ReturnType<typeof useUIStore>
): boolean {
  return (
    isMindMapManualViewport(diagramStore) ||
    isDesktopConceptMapManualViewport(diagramStore, uiStore)
  )
}
