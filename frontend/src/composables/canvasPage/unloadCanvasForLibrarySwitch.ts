/**
 * Drop the previous diagram from the canvas before a library fetch so the old
 * toolbar / nodes never paint across the await. Callers must flush dirty
 * autosave first when a save API is available.
 */
import { canvasVirtualKeyboardOpen } from '@/composables/canvasToolbar/useCanvasVirtualKeyboardOpen'
import { resetMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { applyDiagramTypeForCanvasChrome } from '@/composables/canvasPage/diagramTypeMaps'
import { resetLearningSheetCustomModeUi } from '@/composables/mindMap/useLearningSheetCustomMode'
import {
  useConceptMapFocusReviewStore,
  useConceptMapRelationshipStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
} from '@/stores'
import { useCanvasNodeIndicatorsStore } from '@/stores/canvasNodeIndicators'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useKittySessionStore } from '@/stores/kittySession'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import type { DiagramType } from '@/types'

/**
 * Close live UI tied to the previous diagram without wiping other diagrams'
 * keyed palette / brainstorm session maps (those are restored on reopen).
 */
function clearEphemeralUiForLibrarySwitch(): void {
  useLLMResultsStore().reset()
  useInlineRecommendationsStore().reset()
  useConceptMapFocusReviewStore().clear()
  useConceptMapRootConceptReviewStore().clear()
  useMindMapSubgraphPreviewStore().clear()
  useDiagramTranslateUiStore().abortTranslate()
  useConceptMapRelationshipStore().clearAll()

  const panelsStore = usePanelsStore()
  panelsStore.closeAllPanels()
  panelsStore.clearNodePaletteState({ clearSessions: false })
  panelsStore.clearAiBrainstormState({ clearSessions: false })

  useKittySessionStore().resetSessionUi()
  useCanvasNodeIndicatorsStore().clearAll()
  resetLearningSheetCustomModeUi()
  resetMindMapSideToolbarState()
  canvasVirtualKeyboardOpen.value = false
}

export function unloadCanvasForLibrarySwitch(
  nextDiagramType: string | null | undefined
): void {
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()

  // reset() clears collabSessionActive, but workshopCode (CanvasPage) may still
  // be live — restore the flag so autosave stays gated and remote patches apply.
  const wasCollabSessionActive = diagramStore.collabSessionActive

  diagramStore.reset()
  if (wasCollabSessionActive) {
    diagramStore.setCollabSessionActive(true)
  }

  savedDiagramsStore.clearActiveDiagram()
  applyDiagramTypeForCanvasChrome(
    (diagramType: DiagramType) => diagramStore.setDiagramType(diagramType),
    nextDiagramType
  )
  clearEphemeralUiForLibrarySwitch()
}
