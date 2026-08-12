/**
 * Shared Pinia / module clears for canvas Reset and leave-canvas teardown.
 * Does not touch diagram data, autosave, collab sessions, or emit reset_requested.
 */
import { canvasVirtualKeyboardOpen } from '@/composables/canvasToolbar/useCanvasVirtualKeyboardOpen'
import { resetMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { resetLearningSheetCustomModeUi } from '@/composables/mindMap/useLearningSheetCustomMode'
import {
  useAiContentLevelStore,
  useConceptMapFocusReviewStore,
  useConceptMapRelationshipStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  useMindClassroomStore,
  usePanelsStore,
} from '@/stores'
import { useCanvasNodeIndicatorsStore } from '@/stores/canvasNodeIndicators'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useKittySessionStore } from '@/stores/kittySession'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'

export function clearCanvasEphemeralSession(): void {
  useLLMResultsStore().reset()
  useInlineRecommendationsStore().reset()
  useConceptMapFocusReviewStore().clear()
  useConceptMapRootConceptReviewStore().clear()
  useMindMapSubgraphPreviewStore().clear()
  useDiagramTranslateUiStore().abortTranslate()
  useConceptMapRelationshipStore().clearAll()
  usePanelsStore().reset()
  useKittySessionStore().resetSessionUi()
  useCanvasNodeIndicatorsStore().clearAll()
  resetLearningSheetCustomModeUi()
  resetMindMapSideToolbarState()
  canvasVirtualKeyboardOpen.value = false
  useAiContentLevelStore().resetGeneratedLevelSession()
  const classroom = useMindClassroomStore()
  if (classroom.isLecturing) {
    classroom.clearSession()
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel()
    }
  }
  classroom.closeModal()
}
