/**
 * useCanvasPageMountedHandlers
 *
 * Registers the three large ``eventBus.onWithOwner`` blocks that belong to
 * CanvasPage's ``onMounted`` lifecycle:
 *   - snapshot:requested  → snapshot capture flow
 *   - node_editor:tab_pressed → inline rec / focus-review / root-review routing
 *   - nodePalette:opened  → node palette session start
 *
 * All listeners are registered under the ``'CanvasPage'`` owner so they are
 * torn down by ``eventBus.removeAllListenersForOwner('CanvasPage')`` in
 * ``onUnmounted``.
 */
import { type ComputedRef, nextTick, onMounted } from 'vue'

import { useLanguage, useNotifications, useSnapshotHistory } from '@/composables'
import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import { eventBus } from '@/composables/core/useEventBus'
import { SAVE } from '@/config'
import {
  useAuthStore,
  useConceptMapRootConceptReviewStore,
  useDiagramStore,
  useInlineRecommendationsStore,
  useLLMResultsStore,
} from '@/stores'
import { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'

export function useCanvasPageMountedHandlers(options: {
  snapshotHistory: ReturnType<typeof useSnapshotHistory>
  startRecommendations: (nodeId: string) => void
  startNodePaletteSession: (opts: { keepSessionId: boolean }) => void
  isDiagramOwner?: ComputedRef<boolean>
}) {
  const { snapshotHistory, startRecommendations, startNodePaletteSession, isDiagramOwner } = options

  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const authStore = useAuthStore()
  const llmResultsStore = useLLMResultsStore()
  const inlineRecStore = useInlineRecommendationsStore()
  const focusReviewStore = useConceptMapFocusReviewStore()
  const rootConceptReviewStore = useConceptMapRootConceptReviewStore()
  const notify = useNotifications()
  const { t } = useLanguage()

  onMounted(() => {
    // ── snapshot:requested ────────────────────────────────────────────────
    eventBus.onWithOwner(
      'snapshot:requested',
      async () => {
        if (diagramStore.collabSessionActive && isDiagramOwner?.value === false) return
        const diagramId = savedDiagramsStore.activeDiagramId
        if (!diagramId) return
        const spec = diagramStore.getSpecForSave()
        if (!spec) return
        const result = await snapshotHistory.takeSnapshot(diagramId, spec)
        if (!result) return
        if (result.ok) {
          notify.success(t('canvas.toolbar.snapshotTaken', { n: result.snapshot.version_number }))
          return
        }
        const { status, message } = result
        if (status === 413) {
          notify.error(t('canvas.toolbar.snapshotTooLarge', { max: SAVE.MAX_SPEC_SIZE_KB }))
          return
        }
        if (status === 429) {
          notify.error(t('canvas.toolbar.snapshotRateLimited'))
          return
        }
        if (status === 404) {
          notify.error(t('canvas.toolbar.snapshotDiagramNotFound'))
          return
        }
        if (status === 409) {
          const hint = message.toLowerCase()
          if (hint.includes('save the diagram') || hint.includes('saved to the database')) {
            notify.error(t('canvas.toolbar.snapshotSaveFirst'))
          } else {
            notify.error(message || t('canvas.toolbar.snapshotConflict'))
          }
          return
        }
        if (message) {
          notify.error(message)
          return
        }
        notify.error(t('canvas.toolbar.snapshotFailed'))
      },
      'CanvasPage'
    )

    // ── node_editor:tab_pressed ──────────────────────────────────────────
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
              notify.warning(t('notification.signInToUse'))
              return
            }
            void rootConceptReviewStore.runRootConceptManual()
            return
          }
        }

        const nodes = diagramStore.data?.nodes ?? []
        const node = nodes.find((n: { id?: string }) => n.id === nodeId) as
          | { id?: string; type?: string }
          | undefined
        if (
          !node ||
          !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
        )
          return
        if (!inlineRecStore.isReady) return
        if (diagramStore.type === 'concept_map') {
          if (!llmResultsStore.selectedModel) {
            notify.warning(
              t(
                'notification.conceptMapTabNeedsAi',
                'Please enable AI in the bar before Tab recommendations.'
              )
            )
            return
          }
          if (!authStore.isAuthenticated) {
            notify.warning(t('notification.signInToUse'))
            return
          }
        }
        if (diagramStore.collabSessionActive && isDiagramOwner?.value === false) return
        void startRecommendations(nodeId)
      },
      'CanvasPage'
    )

    // ── nodePalette:opened ───────────────────────────────────────────────
    eventBus.onWithOwner(
      'nodePalette:opened',
      (data: { hasRestoredSession?: boolean; wasPanelAlreadyOpen?: boolean }) => {
        if (diagramStore.type === 'concept_map') return
        if (!data.hasRestoredSession && diagramStore.data?.nodes?.length) {
          nextTick().then(() =>
            startNodePaletteSession({ keepSessionId: data.wasPanelAlreadyOpen ?? false })
          )
        }
      },
      'CanvasPage'
    )
  })
}

export type CanvasPageMountedHandlersOptions = Parameters<typeof useCanvasPageMountedHandlers>[0]
