import type { Ref } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import {
  useConceptMapFocusReviewStore,
  useConceptMapRootConceptReviewStore,
  useDiagramStore,
  usePanelsStore,
} from '@/stores'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

/**
 * Zoom sync, node palette clears, concept-map picker dismiss, teacher usage edit counters.
 * Call once during CanvasPage setup; listeners use owner `CanvasPage` and are removed on unmount.
 */
export function registerCanvasPageDiagramEventBus(options: {
  canvasZoom: Ref<number | null>
}): void {
  const { canvasZoom } = options
  const diagramStore = useDiagramStore()
  const panelsStore = usePanelsStore()
  const focusReviewStore = useConceptMapFocusReviewStore()
  const rootConceptReviewStore = useConceptMapRootConceptReviewStore()

  eventBus.onWithOwner(
    'view:zoom_changed',
    (data) => {
      const zoom = (data as { zoom?: number }).zoom
      if (zoom != null) {
        canvasZoom.value = zoom
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:loaded',
    () => panelsStore.clearNodePaletteState({ clearSessions: false }),
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'diagram:type_changed',
    () => panelsStore.clearNodePaletteState(),
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'canvas:pane_clicked',
    () => {
      if (diagramStore.type !== 'concept_map') return
      focusReviewStore.clear()
      rootConceptReviewStore.clear()
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'state:selection_changed',
    ({ selectedNodes }: { selectedNodes: string[] }) => {
      if (diagramStore.type !== 'concept_map') return
      const nodes = selectedNodes ?? []
      const rootId = getTopicRootConceptTargetId(diagramStore.data?.connections)

      const focusActive = focusReviewStore.validating || focusReviewStore.reviewWaveComplete
      if (focusActive && !nodes.includes('topic')) {
        focusReviewStore.clear()
      }

      const rootActive =
        rootConceptReviewStore.streamPhase !== 'idle' ||
        rootConceptReviewStore.reviewWaveComplete ||
        rootConceptReviewStore.loadingMoreSuggestions
      if (rootActive && (!rootId || !nodes.includes(rootId))) {
        rootConceptReviewStore.clear()
      }
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:node_added',
    () => {
      diagramStore.sessionEditCount += 1
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'diagram:node_updated',
    () => {
      diagramStore.sessionEditCount += 1
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'diagram:nodes_deleted',
    (data: { nodeIds?: string[] }) => {
      diagramStore.sessionEditCount += data?.nodeIds?.length ?? 1
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'diagram:position_changed',
    () => {
      diagramStore.sessionEditCount += 1
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'diagram:style_changed',
    () => {
      diagramStore.sessionEditCount += 1
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'diagram:operation_completed',
    (payload: { operation?: string }) => {
      if (payload?.operation === 'move_branch') diagramStore.sessionEditCount += 1
    },
    'CanvasPage'
  )
}
