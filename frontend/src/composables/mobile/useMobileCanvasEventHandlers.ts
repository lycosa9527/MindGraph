/**
 * Mobile canvas EventBus handlers (palette, Tab, Kitty, auto-complete).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { handleKittyAutoCompleteBranchRequest } from '@/composables/kitty/handleKittyAutoCompleteBranchRequest'
import { handleKittyAddNodeWithRecommendationsRequest } from '@/composables/kitty/kittyAddNodeWithRecommendations'
import type { useAuthStore } from '@/stores/auth'
import type { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import type { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'
import type { useDiagramStore } from '@/stores/diagram'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

const OWNER = 'MobileCanvasPage'

export interface UseMobileCanvasEventHandlersOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  authStore: ReturnType<typeof useAuthStore>
  focusReviewStore: ReturnType<typeof useConceptMapFocusReviewStore>
  rootConceptReviewStore: ReturnType<typeof useConceptMapRootConceptReviewStore>
  isConceptMap: { value: boolean }
  isAIGenerating: { value: boolean }
  startNodePaletteSession: (opts: { keepSessionId?: boolean; mode?: string }) => void
  handleAIGenerate: (options?: {
    generationInstructions?: string
    topicOverride?: string
    isLearningSheet?: boolean
  }) => void | Promise<void>
  handleConceptGeneration: () => void
  translate: (key: string, fallback?: string) => string
  notifyWarning: (message: string) => void
}

export function useMobileCanvasEventHandlers(options: UseMobileCanvasEventHandlersOptions): {
  teardown: () => void
} {
  const {
    diagramStore,
    authStore,
    focusReviewStore,
    rootConceptReviewStore,
    isConceptMap,
    isAIGenerating,
    startNodePaletteSession,
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
        }
      }
    },
    OWNER
  )

  eventBus.onWithOwner(
    'diagram:auto_complete_requested',
    (data?: {
      source?: string
      topic?: string
      diagramType?: string
      isLearningSheet?: boolean
    }) => {
      if (!authStore.isAuthenticated) {
        notifyWarning(translate('notification.signInToUse'))
        return
      }
      if (isAIGenerating.value) return
      if (isConceptMap.value) {
        handleConceptGeneration()
        return
      }
      const topicOverride =
        typeof data?.topic === 'string' && data.topic.trim() !== '' ? data.topic.trim() : undefined
      void Promise.resolve(
        handleAIGenerate({
          topicOverride,
          isLearningSheet: data?.isLearningSheet === true,
        })
      ).then(() => {
        eventBus.emit('kitty:auto_complete_observe', {
          status: 'finished',
          action: 'auto_complete',
        })
      })
    },
    OWNER
  )

  eventBus.onWithOwner(
    'diagram:auto_complete_branch_requested',
    (data: { nodeId?: string; nodeLabel?: string }) => {
      if (!authStore.isAuthenticated) {
        notifyWarning(translate('notification.signInToUse'))
        return
      }
      void handleKittyAutoCompleteBranchRequest(data)
    },
    OWNER
  )

  eventBus.onWithOwner(
    'kitty:add_node_with_recommendations_requested',
    (data: { text?: string }) => {
      void handleKittyAddNodeWithRecommendationsRequest({
        text: data.text,
        diagramStore,
        translate,
        notifyWarning,
      })
    },
    OWNER
  )

  eventBus.onWithOwner(
    'mindmap:canvas_mode_changed',
    ({ previousMode, newMode }) => {
      // Always keep session-owned mode in sync; bucket reconcile runs only for mind maps.
      diagramStore.reconcileMindMapCanvasMode(previousMode, newMode)
    },
    OWNER
  )

  function teardown(): void {
    eventBus.removeAllListenersForOwner(OWNER)
  }

  return { teardown }
}
