/**
 * Mobile canvas EventBus handlers (palette, Tab, Kitty, auto-complete).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import { handleKittyAddNodeWithRecommendationsRequest } from '@/composables/kitty/kittyAddNodeWithRecommendations'
import { resolveKittyChildNodeId } from '@/composables/kitty/kittyDiagramChildren'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'
import { isMindMapDiagramType } from '@/utils/conceptMapDesktopViewport'
import type { useAuthStore } from '@/stores/auth'
import type { useDiagramStore } from '@/stores/diagram'
import type { useInlineRecommendationsStore } from '@/stores/inlineRecommendations'
import type { useLLMResultsStore } from '@/stores/llmResults'
import type { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import type { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'

const OWNER = 'MobileCanvasPage'

export interface UseMobileCanvasEventHandlersOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  authStore: ReturnType<typeof useAuthStore>
  inlineRecStore: ReturnType<typeof useInlineRecommendationsStore>
  llmResultsStore: ReturnType<typeof useLLMResultsStore>
  focusReviewStore: ReturnType<typeof useConceptMapFocusReviewStore>
  rootConceptReviewStore: ReturnType<typeof useConceptMapRootConceptReviewStore>
  isConceptMap: { value: boolean }
  isAIGenerating: { value: boolean }
  startNodePaletteSession: (opts: { keepSessionId?: boolean; mode?: string }) => void
  startRecommendations: (nodeId: string) => Promise<{ success: boolean; error?: string }>
  handleAIGenerate: () => void | Promise<void>
  handleConceptGeneration: () => void
  translate: (key: string, fallback?: string) => string
  notifyWarning: (message: string) => void
}

export function useMobileCanvasEventHandlers(
  options: UseMobileCanvasEventHandlersOptions
): { teardown: () => void } {
  const {
    diagramStore,
    authStore,
    inlineRecStore,
    llmResultsStore,
    focusReviewStore,
    rootConceptReviewStore,
    isConceptMap,
    isAIGenerating,
    startNodePaletteSession,
    startRecommendations,
    handleAIGenerate,
    handleConceptGeneration,
    translate,
    notifyWarning,
  } = options

  eventBus.onWithOwner(
    'nodePalette:opened',
    (data: { hasRestoredSession?: boolean; wasPanelAlreadyOpen?: boolean }) => {
      if (diagramStore.type === 'concept_map') return
      if (!data.hasRestoredSession && diagramStore.data?.nodes?.length) {
        startNodePaletteSession({ keepSessionId: data.wasPanelAlreadyOpen ?? false })
      }
    },
    OWNER
  )

  eventBus.onWithOwner(
    'node_editor:tab_pressed',
    (data: { nodeId?: string; draftText?: string }) => {
      const nodeId = data?.nodeId
      if (!nodeId) return

      if (diagramStore.type === 'concept_map' && nodeId === 'topic') {
        const draft = typeof data.draftText === 'string' ? data.draftText.trim() : ''
        if (draft) {
          eventBus.emit('node:text_updated', { nodeId: 'topic', text: draft })
        }
        void focusReviewStore.runFocusReviewManual()
        return
      }

      if (diagramStore.type === 'concept_map') {
        const rootTid = getTopicRootConceptTargetId(diagramStore.data?.connections)
        if (rootTid && nodeId === rootTid) {
          const draft = typeof data.draftText === 'string' ? data.draftText.trim() : ''
          if (draft) {
            eventBus.emit('node:text_updated', { nodeId: rootTid, text: draft })
          }
          if (!authStore.isAuthenticated) {
            notifyWarning(translate('notification.signInToUse'))
            return
          }
          void rootConceptReviewStore.runRootConceptManual()
          return
        }
      }

      const nodes = diagramStore.data?.nodes ?? []
      const node = nodes.find((n) => n.id === nodeId) as
        | { id?: string; type?: string; data?: { nodeType?: string } }
        | undefined
      if (
        !node ||
        !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
      ) {
        return
      }
      if (!inlineRecStore.isReady) return
      if (diagramStore.type === 'concept_map' && !llmResultsStore.selectedModel) {
        notifyWarning(
          translate('notification.conceptMapTabNeedsAi', '请先在顶栏启用「启动 AI」再使用 Tab 推荐')
        )
        return
      }
      if (!authStore.isAuthenticated) {
        notifyWarning(translate('notification.signInToUse'))
        return
      }
      void startRecommendations(nodeId)
    },
    OWNER
  )

  eventBus.onWithOwner(
    'diagram:auto_complete_requested',
    () => {
      if (!authStore.isAuthenticated) {
        notifyWarning(translate('notification.signInToUse'))
        return
      }
      if (isAIGenerating.value) return
      if (isConceptMap.value) {
        handleConceptGeneration()
        return
      }
      void handleAIGenerate()
    },
    OWNER
  )

  eventBus.onWithOwner(
    'kitty:inline_recommendations_requested',
    (data: { nodeId?: string; nodeIndex?: number }) => {
      const nodes = diagramStore.data?.nodes ?? []
      let nid = resolveKittyChildNodeId(diagramStore.type, nodes, {
        nodeId: data.nodeId,
        nodeIndex: data.nodeIndex,
      })
      if (!nid) nid = diagramStore.selectedNodes[0]
      if (!nid) {
        notifyWarning(translate('canvas.toolbar.selectNodesToDelete', '请先选择一个节点'))
        return
      }
      const node = nodes.find((x) => x.id === nid)
      if (
        !node ||
        !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
      ) {
        notifyWarning(translate('notification.nodeNotEligible', '该节点不支持推荐'))
        return
      }
      if (!inlineRecStore.isReady) return
      if (diagramStore.type === 'concept_map' && !llmResultsStore.selectedModel) {
        notifyWarning(
          translate('notification.conceptMapTabNeedsAi', '请先在顶栏启用「启动 AI」再使用 Tab 推荐')
        )
        return
      }
      if (!authStore.isAuthenticated) {
        notifyWarning(translate('notification.signInToUse'))
        return
      }
      void startRecommendations(nid)
    },
    OWNER
  )

  eventBus.onWithOwner(
    'kitty:add_node_with_recommendations_requested',
    (data: { text?: string }) => {
      void handleKittyAddNodeWithRecommendationsRequest({
        text: data.text,
        diagramStore,
        startRecommendations,
        inlineRecReady: inlineRecStore.isReady,
        isAuthenticated: authStore.isAuthenticated,
        conceptMapAiEnabled: Boolean(llmResultsStore.selectedModel),
        translate,
        notifyWarning,
      })
    },
    OWNER
  )

  eventBus.onWithOwner(
    'mindmap:canvas_mode_changed',
    ({ previousMode, newMode }) => {
      if (isMindMapDiagramType(diagramStore.type)) {
        diagramStore.reconcileMindMapCanvasMode(previousMode, newMode)
      }
    },
    OWNER
  )

  function teardown(): void {
    eventBus.removeAllListenersForOwner(OWNER)
  }

  return { teardown }
}
