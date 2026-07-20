import type { Ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import type { FileCenterActivePackageContext } from '@/composables/fileCenter/useFileCenterActivePackage'
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
 *
 * Shared Pinia / module clears run in ``applyCanvasSessionReset`` →
 * ``clearCanvasEphemeralSession`` before this handler fires.
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
  fileCenterActivePackage: FileCenterActivePackageContext
}): void {
  eventBus.onWithOwner(
    'diagram:reset_requested',
    (payload) => {
      options.diagramAutoSave.cancelTimer()
      options.snapshotHistory.clearSnapshots()
      options.resetPresentationStateOnLeave()
      void options.exitPresentationFullscreen()
      options.presentationRailOpen.value = false
      options.mindMapPresentationTool.value = 'hand'
      options.slidePresentation.stopSlideShow()
      options.slidePresentation.reset()
      options.canvasZoom.value = null
      // Delete Document Summary package + COS extract (not leave-canvas local clear).
      options.fileCenterActivePackage.discardSession({
        diagramId: payload.diagramId ?? null,
      })
      eventBus.emit('view:zoom_reset_requested', {})
      options.diagramAutoSave.setSuppressFromLibrary()
    },
    'CanvasPage'
  )
}
