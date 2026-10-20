/**
 * Teleported node chrome (floating toolbar, + handles) lives on `body` at
 * z-index 5000+. In-page sheets cannot stack above that, so hide chrome while
 * a covering panel, side tool, or body dialog is open.
 */
import { type ComputedRef, computed } from 'vue'

import { canvasCoveringOverlayOpen } from '@/components/common/swissGlassStack'
import { usePanelsStore } from '@/stores'

import { coveringMindMapSideToolOpen } from './useMindMapSideToolbarState'

export { isCoveringMindMapSideTool } from './useMindMapSideToolbarState'

export function canvasNodeChromeBlockedByOverlay(input: {
  diagramBrainstormOpen: boolean
  aiBrainstormOpen: boolean
  coveringSideTool: boolean
  coveringDialogOpen: boolean
}): boolean {
  return (
    input.diagramBrainstormOpen ||
    input.aiBrainstormOpen ||
    input.coveringSideTool ||
    input.coveringDialogOpen
  )
}

export function useCanvasNodeChromeOverlayGate(): ComputedRef<boolean> {
  const panelsStore = usePanelsStore()
  return computed(() =>
    canvasNodeChromeBlockedByOverlay({
      diagramBrainstormOpen: panelsStore.diagramBrainstormPanel.isOpen,
      aiBrainstormOpen: panelsStore.aiBrainstormPanel.isOpen,
      coveringSideTool: coveringMindMapSideToolOpen(),
      coveringDialogOpen: canvasCoveringOverlayOpen(),
    })
  )
}
