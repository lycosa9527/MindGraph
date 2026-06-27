import { eventBus } from '@/composables/core/useEventBus'
import {
  useConceptMapFocusReviewStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
  usePanelsStore,
} from '@/stores'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { useDiagramTranslateUiStore } from '@/stores/diagramTranslateUi'
import { useMindMapSubgraphPreviewStore } from '@/stores/mindMapSubgraphPreview'

/**
 * Abort in-flight AI streams and clear ephemeral Pinia state before undo/redo
 * restores a diagram snapshot. Keeps ancillary UI from fighting the restored data.
 */
export function applyCanvasHistoryNavigationSync(): void {
  useLLMResultsStore().cancelAllRequests()
  useInlineRecommendationsStore().reset()
  useConceptMapFocusReviewStore().clear()
  useConceptMapRootConceptReviewStore().clear()
  useMindMapSubgraphPreviewStore().clear()
  useDiagramTranslateUiStore().abortTranslate()
  eventBus.emit('node_palette:streaming_stop_requested', {})
}
