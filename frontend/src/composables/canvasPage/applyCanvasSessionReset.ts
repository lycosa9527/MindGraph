import { eventBus } from '@/composables/core/useEventBus'
import { resetLearningSheetCustomModeUi } from '@/composables/mindMap/useLearningSheetCustomMode'
import {
  useConceptMapFocusReviewStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
} from '@/stores'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

/**
 * Abort in-flight AI streams and clear ephemeral Pinia state before reloading
 * the default template. CanvasPage listens for `diagram:reset_requested` to
 * reset page-local refs (presentation rail, snapshots, autosave suppress).
 */
export function applyCanvasSessionReset(): void {
  useLLMResultsStore().reset()
  useInlineRecommendationsStore().reset()
  useConceptMapFocusReviewStore().clear()
  useConceptMapRootConceptReviewStore().clear()
  useMindMapSubgraphPreviewStore().clear()
  useDiagramTranslateUiStore().abortTranslate()
  usePanelsStore().reset()
  resetLearningSheetCustomModeUi()

  const diagramStore = useDiagramStore()
  diagramStore.clearSelection()
  diagramStore.clearHistory()
  diagramStore.clearCopiedNodes()
  diagramStore.clearKittyDiagramReviewAnnotations()
  diagramStore.resetSessionEditCount()

  useSavedDiagramsStore().clearActiveDiagram()

  eventBus.emit('diagram:reset_requested', {})
}
