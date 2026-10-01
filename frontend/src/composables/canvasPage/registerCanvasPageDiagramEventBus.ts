import type { Ref } from 'vue'

import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import {
  type ThinkingMapSlashCommand,
  readThinkingMapSlashRole,
  resolveThinkingMapNodeSlash,
} from '@/composables/canvasPage/thinkingMapNodeSlash'
import { eventBus } from '@/composables/core/useEventBus'
import { useNodeActions } from '@/composables/editor/useNodeActions'
import { restoreLearningSheetUiFromDiagram } from '@/composables/mindMap/useLearningSheetCustomMode'
import { useDiagramStore, usePanelsStore } from '@/stores'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import { isDiagramPresentationReadOnly } from '@/stores/diagram/presentationReadOnlyGuard'
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
  const { handleDeleteNode, handleAddNode, handleAddChild, handleAddSibling, handleAddBranch } =
    useNodeActions({
      registerEventBusListeners: false,
    })
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
    () => {
      diagramStore.seedHistoryBaselineIfEmpty()
      panelsStore.clearNodePaletteState({ clearSessions: false })
      panelsStore.clearAiBrainstormState({ clearSessions: false })
      restoreLearningSheetUiFromDiagram()
    },
    'CanvasPage'
  )

  eventBus.onWithOwner(
    'diagram:learning_sheet_changed',
    () => {
      diagramStore.sessionEditCount += 1
    },
    'CanvasPage'
  )
  eventBus.onWithOwner(
    'diagram:type_changed',
    () => {
      panelsStore.clearNodePaletteState()
      panelsStore.clearAiBrainstormState()
    },
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
  function runThinkingMapSlash(command: ThinkingMapSlashCommand, nodeIds: string[]): void {
    if (command === 'add_tree_category') {
      diagramStore.clearSelection()
      void handleAddNode()
      return
    }
    if (!diagramStore.selectNodes(nodeIds)) return
    if (command === 'delete') {
      void handleDeleteNode()
      return
    }
    if (command === 'add_child') {
      void handleAddChild()
      return
    }
    if (command === 'add_branch') {
      void handleAddBranch()
      return
    }
    void handleAddNode()
  }

  eventBus.onWithOwner(
    'diagram:node_slash_requested',
    ({ action, nodeIds }) => {
      if (nodeIds.length === 0 || isDiagramPresentationReadOnly(diagramStore)) return
      const nodeId = nodeIds[0]
      if (!nodeId) return
      if (isThinkingMapDiagramType(diagramStore.type)) {
        const role = readThinkingMapSlashRole(
          diagramStore.type,
          nodeId,
          diagramStore.data?.nodes ?? [],
          diagramStore.data?.connections ?? []
        )
        const command = resolveThinkingMapNodeSlash(diagramStore.type, action, role)
        if (!command) return
        const ids = action === 'delete' ? nodeIds : [nodeId]
        runThinkingMapSlash(command, ids)
        return
      }
      const mindMap = diagramStore.type === 'mindmap' || diagramStore.type === 'mind_map'
      if (action === 'sibling' && !mindMap) return
      const ids = action === 'delete' ? nodeIds : [nodeId]
      if (!diagramStore.selectNodes(ids)) return
      if (action === 'delete') {
        void handleDeleteNode()
        return
      }
      const node = diagramStore.data?.nodes.find((item) => item.id === nodeId)
      const topic = nodeId === 'topic' || node?.type === 'topic' || node?.type === 'center'
      if (action === 'sibling') {
        if (topic) void handleAddBranch()
        else void handleAddSibling()
        return
      }
      if (mindMap && topic) void handleAddBranch()
      else void handleAddChild()
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
