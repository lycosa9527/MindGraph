import type { useDiagramStore } from '@/stores/diagram'
import type { useUIStore } from '@/stores/ui'

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
