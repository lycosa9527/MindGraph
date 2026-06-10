/**
 * Mobile canvas inline recommendation bottom bar (pagination, dismiss, Tab mode).
 */
import { type ComputedRef, computed, ref, watch } from 'vue'

import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import { getTopicRootConceptTargetId } from '@/utils/conceptMapTopicRootEdge'
import type { useDiagramStore } from '@/stores/diagram'
import type { useInlineRecommendationsStore } from '@/stores/inlineRecommendations'
import type { useAuthStore } from '@/stores/auth'
import type { useLLMResultsStore } from '@/stores/llmResults'
import type { useConceptMapFocusReviewStore } from '@/stores/conceptMapFocusReview'
import type { useConceptMapRootConceptReviewStore } from '@/stores/conceptMapRootConceptReview'

const MOBILE_REC_PER_PAGE_NON_CONCEPT = 3
const MOBILE_REC_PER_PAGE_CONCEPT_MAP = 4

export interface UseMobileCanvasInlineRecBarOptions {
  diagramStore: ReturnType<typeof useDiagramStore>
  inlineRecStore: ReturnType<typeof useInlineRecommendationsStore>
  authStore: ReturnType<typeof useAuthStore>
  llmResultsStore: ReturnType<typeof useLLMResultsStore>
  focusReviewStore: ReturnType<typeof useConceptMapFocusReviewStore>
  rootConceptReviewStore: ReturnType<typeof useConceptMapRootConceptReviewStore>
  isConceptMap: ComputedRef<boolean>
  startRecommendations: (nodeId: string) => Promise<void>
  selectOptionByGlobalIndex: (nodeId: string, globalIndex: number) => void
  fetchNextBatch: (nodeId: string) => Promise<void>
  translate: (key: string, fallback?: string) => string
  notifyWarning: (message: string) => void
}

export function useMobileCanvasInlineRecBar(options: UseMobileCanvasInlineRecBarOptions) {
  const {
    diagramStore,
    inlineRecStore,
    authStore,
    llmResultsStore,
    focusReviewStore,
    rootConceptReviewStore,
    isConceptMap,
    startRecommendations,
    selectOptionByGlobalIndex,
    fetchNextBatch,
    translate,
    notifyWarning,
  } = options

  const mobileRecPage = ref(0)

  const mobileRecPerPage = computed(() =>
    isConceptMap.value ? MOBILE_REC_PER_PAGE_CONCEPT_MAP : MOBILE_REC_PER_PAGE_NON_CONCEPT
  )

  const inlineRecActive = computed(() => !!inlineRecStore.activeNodeId)

  const inlineRecGenerating = computed(() => {
    const nid = inlineRecStore.activeNodeId
    return !!nid && inlineRecStore.generatingNodeIds.has(nid)
  })

  const showMobileConceptRecBottom = computed(
    () => isConceptMap.value && (inlineRecActive.value || inlineRecGenerating.value)
  )

  const mobileRecOptions = computed(() => {
    const nid = inlineRecStore.activeNodeId
    if (!nid) return []
    const all = inlineRecStore.allOptions[nid] ?? []
    const per = mobileRecPerPage.value
    const start = mobileRecPage.value * per
    return all.slice(start, start + per)
  })

  const mobileRecTotalPages = computed(() => {
    const nid = inlineRecStore.activeNodeId
    if (!nid) return 0
    const total = (inlineRecStore.allOptions[nid] ?? []).length
    const per = mobileRecPerPage.value
    return total <= 0 ? 0 : Math.ceil(total / per)
  })

  const mobileCanPrev = computed(() => mobileRecPage.value > 0)

  const mobileRecFetching = computed(() => {
    const nid = inlineRecStore.activeNodeId
    return !!nid && inlineRecStore.fetchingNextBatchNodeIds.has(nid)
  })

  watch(
    () => inlineRecStore.activeNodeId,
    () => {
      mobileRecPage.value = 0
    }
  )

  watch(isConceptMap, () => {
    mobileRecPage.value = 0
  })

  function handleRecSelect(localIdx: number): void {
    const nid = inlineRecStore.activeNodeId
    if (!nid) return
    const per = mobileRecPerPage.value
    const globalIdx = mobileRecPage.value * per + localIdx
    selectOptionByGlobalIndex(nid, globalIdx)
  }

  async function handleRecNext(): Promise<void> {
    const nid = inlineRecStore.activeNodeId
    if (!nid) return
    const per = mobileRecPerPage.value
    const hasMoreLocal = mobileRecPage.value < mobileRecTotalPages.value - 1
    if (hasMoreLocal) {
      mobileRecPage.value++
      return
    }
    await fetchNextBatch(nid)
    const newTotal = (inlineRecStore.allOptions[nid] ?? []).length
    const newTotalPages = Math.ceil(newTotal / per)
    if (newTotalPages > mobileRecPage.value + 1) {
      mobileRecPage.value++
    }
  }

  function handleRecPrev(): void {
    if (mobileRecPage.value > 0) mobileRecPage.value--
  }

  function handleRecDismiss(): void {
    inlineRecStore.invalidateAll()
  }

  function handleTabMode(): void {
    if (!authStore.isAuthenticated) {
      notifyWarning(translate('notification.signInToUse'))
      return
    }
    if (!inlineRecStore.isReady) return

    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId) {
      notifyWarning(translate('canvas.toolbar.selectNodesToDelete', '请先选择一个节点'))
      return
    }

    if (isConceptMap.value && selectedId === 'topic') {
      void focusReviewStore.runFocusReviewManual()
      return
    }
    if (isConceptMap.value) {
      const rootTid = getTopicRootConceptTargetId(diagramStore.data?.connections)
      if (rootTid && selectedId === rootTid) {
        void rootConceptReviewStore.runRootConceptManual()
        return
      }
    }
    if (isConceptMap.value && !llmResultsStore.selectedModel) {
      notifyWarning(
        translate('notification.conceptMapTabNeedsAi', '请先在顶栏启用「启动 AI」再使用 Tab 推荐')
      )
      return
    }

    const nodes = diagramStore.data?.nodes ?? []
    const node = nodes.find((n) => n.id === selectedId)
    if (
      !node ||
      !isNodeEligibleForInlineRec(diagramStore.type, node, diagramStore.data?.connections)
    ) {
      notifyWarning(translate('notification.nodeNotEligible', '该节点不支持推荐'))
      return
    }
    void startRecommendations(selectedId)
  }

  return {
    mobileRecPage,
    mobileRecPerPage,
    inlineRecActive,
    inlineRecGenerating,
    showMobileConceptRecBottom,
    mobileRecOptions,
    mobileRecTotalPages,
    mobileCanPrev,
    mobileRecFetching,
    handleRecSelect,
    handleRecNext,
    handleRecPrev,
    handleRecDismiss,
    handleTabMode,
  }
}
