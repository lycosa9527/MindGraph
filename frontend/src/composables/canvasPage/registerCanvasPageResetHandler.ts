import type { Ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { resetMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import type { useMindMapSlidePresentation } from '@/composables/mindMap/useMindMapSlidePresentation'
import type { MindMapPresentationToolId } from '@/types/diagram'

type SlidePresentationApi = ReturnType<typeof useMindMapSlidePresentation>

type DiagramAutoSaveResetApi = {
  cancelTimer: () => void
  setSuppressFromLibrary: () => void
}

type SnapshotHistoryResetApi = {
  clearSnapshots: () => void
}

/**
 * Resets CanvasPage-local refs when the user confirms "Reset to default template".
 * Registered once during CanvasPage setup; torn down with other `CanvasPage` bus owners.
 */
export function registerCanvasPageResetHandler(options: {
  snapshotHistory: SnapshotHistoryResetApi
  diagramAutoSave: DiagramAutoSaveResetApi
  resetPresentationStateOnLeave: () => void
  exitPresentationFullscreen: () => Promise<void>
  presentationRailOpen: Ref<boolean>
  mindMapPresentationTool: Ref<MindMapPresentationToolId>
  slidePresentation: SlidePresentationApi
  canvasZoom: Ref<number | null>
}): void {
  eventBus.onWithOwner(
    'diagram:reset_requested',
    () => {
      options.diagramAutoSave.cancelTimer()
      options.snapshotHistory.clearSnapshots()
      options.resetPresentationStateOnLeave()
      void options.exitPresentationFullscreen()
      options.presentationRailOpen.value = false
      options.mindMapPresentationTool.value = 'hand'
      options.slidePresentation.stopSlideShow()
      options.slidePresentation.reset()
      resetMindMapSideToolbarState()
      options.canvasZoom.value = null
      eventBus.emit('view:zoom_reset_requested', {})
      options.diagramAutoSave.setSuppressFromLibrary()
    },
    'CanvasPage'
  )
}
